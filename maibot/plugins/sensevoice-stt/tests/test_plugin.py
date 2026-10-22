"""测试 plugin — mock maibot_sdk 和客户端，验证 Hook/Command/HomeCard。"""

import asyncio
import base64
import os
import sys
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

_VALID_B64 = base64.b64encode(b"test_audio_data").decode()  # 有效的 base64 测试数据

# ---- mock maibot_sdk（必须在 import plugin 之前） ----

_mock_types = MagicMock()
_mock_types.ErrorPolicy = MagicMock()
_mock_types.ErrorPolicy.SKIP = "SKIP"
_mock_types.HookMode = MagicMock()
_mock_types.HookMode.BLOCKING = "BLOCKING"
_mock_types.HookOrder = MagicMock()
_mock_types.HookOrder.EARLY = "EARLY"

_mock_sdk = MagicMock()
_mock_sdk.HookHandler = lambda *a, **kw: lambda fn: fn
_mock_sdk.Command = lambda **kw: lambda fn: fn
_mock_sdk.HomeCard = lambda **kw: lambda fn: fn

class _MockPluginBase:
    def __init__(self):
        self.ctx = MagicMock()
        self.ctx.logger = MagicMock()
        self.ctx.paths = MagicMock()
        self.ctx.paths.runtime_dir = "/tmp/fake_runtime"
        self.config = MagicMock()

_mock_sdk.MaiBotPlugin = _MockPluginBase

sys.modules["maibot_sdk"] = _mock_sdk
sys.modules["maibot_sdk.types"] = _mock_types

# ---- mock aiohttp（plugin.py 的 stt_client 依赖）----
_mock_aiohttp = MagicMock()
_mock_aiohttp.ClientTimeout = lambda total: total
_mock_aiohttp.ClientConnectorError = type("ClientConnectorError", (Exception,), {})
_mock_aiohttp.FormData = MagicMock


def _install_plugin_mocks():
    sys.modules["maibot_sdk"] = _mock_sdk
    sys.modules["maibot_sdk.types"] = _mock_types
    sys.modules["aiohttp"] = _mock_aiohttp


_install_plugin_mocks()

# ---- 被测模块（用 package 加载以支持 plugin.py 的相对导入）----

import importlib
import importlib.util
import types
import unittest

_plugin_dir = os.path.join(os.path.dirname(__file__), "..")
_plugin_dir = os.path.realpath(_plugin_dir)

# 创建合成 package 承载插件模块
_pkg = types.ModuleType("_stt_pkg")
_pkg.__path__ = [_plugin_dir]
_pkg.__file__ = os.path.join(_plugin_dir, "__init__.py")
sys.modules["_stt_pkg"] = _pkg

_spec = importlib.util.spec_from_file_location(
    "_stt_pkg.plugin",
    os.path.join(_plugin_dir, "plugin.py"),
    submodule_search_locations=[_plugin_dir],
)
pmod = importlib.util.module_from_spec(_spec)
pmod.__package__ = "_stt_pkg"
sys.modules["_stt_pkg.plugin"] = pmod
_spec.loader.exec_module(pmod)


def _reload_plugin_module():
    _install_plugin_mocks()
    importlib.reload(pmod)


def _fake_transcribe_result(success=True, text="hello", error_type=None, attempt=1):
    from _stt_pkg.core.stt_client import TranscriptionResult
    if success:
        return TranscriptionResult.ok(text, attempt)
    return TranscriptionResult.fail(error_type or "timeout", attempt)


class TestRebuildPlainText(unittest.TestCase):
    def setUp(self):
        _reload_plugin_module()

    def test_all_types(self):
        segs = [
            {"type": "text", "data": "你好"},
            {"type": "voice"},
            {"type": "image"},
            {"type": "reply"},
        ]
        result = pmod.rebuild_plain_text(segs)
        self.assertEqual(result, "你好[voice][image][reply]")

    def test_mixed_text_voice(self):
        segs = [
            {"type": "text", "data": "前面"},
            {"type": "voice"},
            {"type": "text", "data": "后面"},
        ]
        result = pmod.rebuild_plain_text(segs)
        self.assertEqual(result, "前面[voice]后面")

    def test_only_text(self):
        segs = [{"type": "text", "data": "纯文本"}]
        result = pmod.rebuild_plain_text(segs)
        self.assertEqual(result, "纯文本")

    def test_empty_segments(self):
        result = pmod.rebuild_plain_text([])
        self.assertEqual(result, "[unsupported]")

    def test_non_dict_items_skipped(self):
        segs = [{"type": "text", "data": "a"}, "not_a_dict"]
        result = pmod.rebuild_plain_text(segs)
        self.assertEqual(result, "a")


class TestCreatePlugin(unittest.TestCase):
    def test_returns_plugin_instance(self):
        p = pmod.create_plugin()
        self.assertIsInstance(p, pmod.SenseVoiceSttPlugin)


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        _reload_plugin_module()
        self.p = pmod.SenseVoiceSttPlugin()
        self.p.config.plugin.enabled = True
        self.p.config.stt.endpoint_url = "http://sensevoice:50000/v1/audio/transcriptions"
        self.p.config.stt.timeout_seconds = 30
        self.p.config.stt.language = "auto"

    def test_on_load_inits_client(self):
        asyncio.run(self.p.on_load())
        self.assertIsNotNone(self.p._client)

    def test_on_load_disabled(self):
        self.p.config.plugin.enabled = False
        asyncio.run(self.p.on_load())
        self.assertIsNone(self.p._client)

    def test_on_unload_clears_client(self):
        asyncio.run(self.p.on_load())
        asyncio.run(self.p.on_unload())
        self.assertIsNone(self.p._client)

    def test_on_config_update_self_scope(self):
        self.p._client = None
        asyncio.run(self.p.on_config_update("self", {}, "0.3.0"))
        self.assertIsNotNone(self.p._client)

    def test_on_config_update_ignored_scope(self):
        self.p._client = None
        asyncio.run(self.p.on_config_update("bot", {}, "0.3.0"))
        self.assertIsNone(self.p._client)


class TestTranscribeHook(unittest.TestCase):
    def setUp(self):
        _reload_plugin_module()
        self.p = pmod.SenseVoiceSttPlugin()
        self.p.config.plugin.enabled = True
        self.p.config.stt.endpoint_url = "http://sensevoice:50000/v1/audio/transcriptions"
        self.p.config.stt.timeout_seconds = 30
        self.p.config.stt.language = "auto"
        asyncio.run(self.p.on_load())

    def test_no_voice_segments(self):
        msg = {
            "raw_message": [{"type": "text", "data": "hello"}],
            "processed_plain_text": "hello",
        }
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))
        self.assertIsNone(result)
        self.assertEqual(self.p._stats["total_requests"], 0)

    def test_no_message_returns_none(self):
        result = asyncio.run(self.p.transcribe_voice_segments(message=None))
        self.assertIsNone(result)

    def test_no_client_returns_none(self):
        self.p._client = None
        msg = {"raw_message": [{"type": "voice", "binary_data_base64": "AA=="}]}
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))
        self.assertIsNone(result)

    def test_raw_not_list_returns_none(self):
        msg = {"raw_message": "not_a_list"}
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))
        self.assertIsNone(result)

    def test_skip_voice_without_base64(self):
        msg = {
            "raw_message": [{"type": "voice", "binary_data_base64": ""}],
            "processed_plain_text": "[voice]",
        }
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))
        self.assertIsNone(result)

    def test_transcribe_voice_to_text(self):
        self.p._client.transcribe = AsyncMock(
            return_value=_fake_transcribe_result(success=True, text="你好")
        )
        msg = {
            "raw_message": [
                {"type": "voice", "binary_data_base64": _VALID_B64},
            ],
            "processed_plain_text": "[voice]",
            "display_message": "[voice]",
        }
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))

        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "continue")
        modified_msg = result["modified_kwargs"]["message"]
        self.assertEqual(modified_msg["raw_message"][0]["type"], "text")
        self.assertEqual(modified_msg["raw_message"][0]["data"], "你好")
        self.assertEqual(modified_msg["processed_plain_text"], "你好")
        self.assertEqual(self.p._stats["total_requests"], 1)
        self.assertEqual(self.p._stats["total_success"], 1)
        self.assertEqual(self.p._stats["total_failure"], 0)
        self.assertEqual(self.p._stats["consecutive_failures"], 0)

    def test_transcribe_failure_preserves_voice(self):
        self.p._client.transcribe = AsyncMock(
            return_value=_fake_transcribe_result(success=False, error_type="timeout")
        )
        msg = {
            "raw_message": [{"type": "voice", "binary_data_base64": _VALID_B64}],
            "processed_plain_text": "[voice]",
        }
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))

        self.assertIsNone(result)
        self.assertEqual(msg["raw_message"][0]["type"], "voice")
        self.assertEqual(self.p._stats["total_requests"], 1)
        self.assertEqual(self.p._stats["total_success"], 0)
        self.assertEqual(self.p._stats["total_failure"], 1)
        self.assertEqual(self.p._stats["consecutive_failures"], 1)

    def test_consecutive_failure_warning(self):
        self.p._client.transcribe = AsyncMock(
            return_value=_fake_transcribe_result(success=False)
        )
        msg = {
            "raw_message": [{"type": "voice", "binary_data_base64": _VALID_B64}],
            "processed_plain_text": "[voice]",
        }
        for i in range(3):
            asyncio.run(self.p.transcribe_voice_segments(message=msg))

        self.p.ctx.logger.warning.assert_called()
        warning_args = [c[0][0] for c in self.p.ctx.logger.warning.call_args_list]
        self.assertTrue(any("连续失败" in str(a) for a in warning_args))

    def test_multiple_segments_mixed(self):
        self.p._client.transcribe = AsyncMock(side_effect=[
            _fake_transcribe_result(success=True, text="第一段"),
            _fake_transcribe_result(success=False),
            _fake_transcribe_result(success=True, text="第三段"),
        ])
        msg = {
            "raw_message": [
                {"type": "voice", "binary_data_base64": _VALID_B64},
                {"type": "text", "data": "中间"},
                {"type": "voice", "binary_data_base64": _VALID_B64},
                {"type": "voice", "binary_data_base64": _VALID_B64},
            ],
            "processed_plain_text": "[voice]中间[voice][voice]",
        }
        result = asyncio.run(self.p.transcribe_voice_segments(message=msg))

        self.assertIsNotNone(result)
        raw = result["modified_kwargs"]["message"]["raw_message"]
        self.assertEqual(raw[0]["type"], "text")
        self.assertEqual(raw[0]["data"], "第一段")
        self.assertEqual(raw[1]["type"], "text")
        self.assertEqual(raw[2]["type"], "voice")  # 失败保留
        self.assertEqual(raw[3]["type"], "text")
        self.assertEqual(raw[3]["data"], "第三段")
        self.assertEqual(self.p._stats["total_success"], 2)
        self.assertEqual(self.p._stats["total_failure"], 1)


class TestHomeCard(unittest.TestCase):
    def test_returns_blocks(self):
        _reload_plugin_module()
        from _stt_pkg.core.stt_client import HealthCheckResult

        p = pmod.SenseVoiceSttPlugin()
        p.config.plugin.enabled = True
        p.config.stt.endpoint_url = "http://localhost:50000"
        asyncio.run(p.on_load())
        p._client.check_health = AsyncMock(return_value=HealthCheckResult.ready())

        card = asyncio.run(p.stt_home_card())
        self.assertIn("blocks", card)
        self.assertIsInstance(card["blocks"], list)
        self.assertTrue(len(card["blocks"]) > 0)
        entries = card["blocks"][0]["entries"]
        self.assertEqual(entries["插件状态"], "启用")
        self.assertEqual(entries["后端健康"], "ready")
        self.assertEqual(entries["Endpoint"], "http://localhost:50000")

    def test_home_card_disabled(self):
        _reload_plugin_module()
        p = pmod.SenseVoiceSttPlugin()
        p.config.plugin.enabled = False
        p.config.stt.endpoint_url = "http://localhost:50000"
        p._client = None

        card = asyncio.run(p.stt_home_card())
        entries = card["blocks"][0]["entries"]
        self.assertEqual(entries["插件状态"], "已禁用")
        self.assertEqual(entries["后端健康"], "未启用")

    def test_home_card_sidecar_unreachable(self):
        _reload_plugin_module()
        from _stt_pkg.core.stt_client import HealthCheckResult

        p = pmod.SenseVoiceSttPlugin()
        p.config.plugin.enabled = True
        p.config.stt.endpoint_url = "http://localhost:50000/v1/audio/transcriptions"
        asyncio.run(p.on_load())
        p._client.check_health = AsyncMock(
            return_value=HealthCheckResult.fail("connection")
        )

        card = asyncio.run(p.stt_home_card())
        entries = card["blocks"][0]["entries"]
        self.assertEqual(entries["后端健康"], "unreachable/connection")


class TestStatsTracking(unittest.TestCase):
    def setUp(self):
        _reload_plugin_module()
        self.p = pmod.SenseVoiceSttPlugin()

    def test_reset_on_load(self):
        self.p._stats = {"total_requests": 999}
        with patch("_stt_pkg.plugin.SenseVoiceClient"):
            asyncio.run(self.p.on_load())
        self.assertEqual(self.p._stats["total_requests"], 0)

    def test_success_resets_consecutive_failures(self):
        self.p._stats["consecutive_failures"] = 5
        from _stt_pkg.core.stt_client import TranscriptionResult
        self.p._record_transcription(TranscriptionResult.ok("test"))
        self.assertEqual(self.p._stats["consecutive_failures"], 0)
        self.assertEqual(self.p._stats["total_success"], 1)


if __name__ == "__main__":
    unittest.main()
