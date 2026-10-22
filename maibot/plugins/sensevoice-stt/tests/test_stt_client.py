"""测试 stt_client — mock aiohttp，验证 TranscriptionResult 和重试逻辑。"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---- 确保 aiohttp 在 sys.modules 中被 mock ----
_mock_aiohttp = MagicMock()
_mock_aiohttp.ClientTimeout = lambda total: total
_mock_aiohttp.ClientConnectorError = type("ClientConnectorError", (Exception,), {})
_mock_aiohttp.FormData = MagicMock
sys.modules["aiohttp"] = _mock_aiohttp

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import importlib
import core.stt_client as stt_module


class TestTranscriptionResult(unittest.TestCase):
    def setUp(self):
        importlib.reload(stt_module)

    def test_ok(self):
        r = stt_module.TranscriptionResult.ok(" hello ")
        self.assertTrue(r.success)
        self.assertEqual(r.text, "hello")
        self.assertIsNone(r.error_type)
        self.assertEqual(r.attempt, 1)

    def test_fail(self):
        r = stt_module.TranscriptionResult.fail("timeout", attempt=2)
        self.assertFalse(r.success)
        self.assertEqual(r.text, "")
        self.assertEqual(r.error_type, "timeout")
        self.assertEqual(r.attempt, 2)


class TestSenseVoiceClient(unittest.TestCase):
    def setUp(self):
        importlib.reload(stt_module)
        self.tmpdir = tempfile.mkdtemp()
        self.audio_path = os.path.join(self.tmpdir, "test.wav")
        with open(self.audio_path, "wb") as f:
            f.write(b"\x00\xFF" * 100)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _client(self, **kw):
        return stt_module.SenseVoiceClient(
            endpoint_url=kw.pop("url", "http://localhost:50000/v1/audio/transcriptions"),
            timeout=kw.pop("timeout", 5),
            language=kw.pop("language", "auto"),
            **kw,
        )

    def _make_mock_session(self, post_return=None, get_return=None):
        """构造一个支持 async with 的 mock ClientSession。"""
        sess = MagicMock()
        sess.__aenter__ = AsyncMock(return_value=sess)
        sess.__aexit__ = AsyncMock(return_value=False)
        sess.post = MagicMock(return_value=post_return)
        sess.get = MagicMock(return_value=get_return)
        return sess

    def _make_resp_ctx(self, status, json_data=None):
        """构造 async with session.post(...) as resp: 的 mock。"""
        ctx = MagicMock()
        resp = MagicMock()
        resp.status = status
        resp.json = AsyncMock(return_value=json_data or {})
        ctx.__aenter__ = AsyncMock(return_value=resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    def test_successful_transcription(self):
        client = self._client()
        ctx = self._make_resp_ctx(200, {"text": "你好世界"})
        sess = self._make_mock_session(ctx)

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.transcribe(self.audio_path))

        self.assertTrue(result.success)
        self.assertEqual(result.text, "你好世界")
        self.assertEqual(result.attempt, 1)

    def test_build_health_url_from_transcription_endpoint(self):
        self.assertEqual(
            stt_module.build_health_url(
                "http://localhost:50000/v1/audio/transcriptions"
            ),
            "http://localhost:50000/health",
        )

    def test_build_health_url_from_nested_endpoint(self):
        self.assertEqual(
            stt_module.build_health_url(
                "http://localhost:50000/api/v1/audio/transcriptions"
            ),
            "http://localhost:50000/api/health",
        )

    def test_check_health_ready(self):
        client = self._client()
        ctx = self._make_resp_ctx(200, {"status": "ready"})
        sess = self._make_mock_session(get_return=ctx)

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.check_health())

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "ready")
        self.assertIsNone(result.error_type)

    def test_check_health_loading(self):
        client = self._client()
        ctx = self._make_resp_ctx(200, {"status": "loading"})
        sess = self._make_mock_session(get_return=ctx)

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.check_health())

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "loading")
        self.assertEqual(result.error_type, "not_ready")

    def test_check_health_connection_error(self):
        client = self._client()
        sess = self._make_mock_session()
        sess.get = MagicMock(
            side_effect=stt_module.aiohttp.ClientConnectorError(
                "mock", OSError("refused")
            )
        )

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.check_health())

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "unreachable")
        self.assertEqual(result.error_type, "connection")

    def test_http_500_no_retry(self):
        client = self._client()
        ctx = self._make_resp_ctx(500, {})
        sess = self._make_mock_session(ctx)

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.transcribe(self.audio_path))

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "http_error")
        self.assertEqual(result.attempt, 1)

    @patch("core.stt_client.asyncio.sleep", new_callable=AsyncMock)
    def test_retry_on_timeout(self, mock_sleep):
        client = self._client()
        sess = MagicMock()
        sess.__aenter__ = AsyncMock(return_value=sess)
        sess.__aexit__ = AsyncMock(return_value=False)
        sess.post = MagicMock(side_effect=asyncio.TimeoutError())

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.transcribe(self.audio_path))

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "timeout")
        self.assertEqual(result.attempt, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("core.stt_client.asyncio.sleep", new_callable=AsyncMock)
    def test_retry_success_after_timeout(self, mock_sleep):
        client = self._client()
        ctx = self._make_resp_ctx(200, {"text": "重试成功"})

        sess_fail = MagicMock()
        sess_fail.__aenter__ = AsyncMock(return_value=sess_fail)
        sess_fail.__aexit__ = AsyncMock(return_value=False)
        sess_fail.post = MagicMock(side_effect=asyncio.TimeoutError())

        sess_ok = self._make_mock_session(ctx)

        with patch(
            "core.stt_client.aiohttp.ClientSession",
            side_effect=[sess_fail, sess_ok],
        ):
            result = asyncio.run(client.transcribe(self.audio_path))

        self.assertTrue(result.success)
        self.assertEqual(result.text, "重试成功")
        self.assertEqual(result.attempt, 2)

    @patch("core.stt_client.asyncio.sleep", new_callable=AsyncMock)
    def test_connection_error(self, mock_sleep):
        client = self._client()
        sess = MagicMock()
        sess.__aenter__ = AsyncMock(return_value=sess)
        sess.__aexit__ = AsyncMock(return_value=False)
        sess.post = MagicMock(
            side_effect=stt_module.aiohttp.ClientConnectorError(
                "mock", OSError("refused")
            )
        )

        with patch("core.stt_client.aiohttp.ClientSession", return_value=sess):
            result = asyncio.run(client.transcribe(self.audio_path))

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "connection")
        self.assertEqual(result.attempt, 2)


if __name__ == "__main__":
    unittest.main()
