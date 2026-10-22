"""测试 audio_utils — 纯标准库，无外部依赖。"""

import base64
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.audio_utils import cleanup_temp_file, decode_base64_to_wav


class TestDecodeBase64ToWav(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_round_trip(self):
        raw = b"\x00\xFF\x00\xFF" * 100
        b64 = base64.b64encode(raw).decode()
        path = decode_base64_to_wav(b64, self.tmpdir)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".wav"))
        self.assertTrue(path.startswith(self.tmpdir))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), raw)
        os.unlink(path)

    def test_creates_runtime_dir(self):
        nested = os.path.join(self.tmpdir, "nested", "dir")
        raw = b"hello"
        b64 = base64.b64encode(raw).decode()
        path = decode_base64_to_wav(b64, nested)
        self.assertTrue(os.path.exists(path))
        cleanup_temp_file(path)

    def test_empty_data(self):
        b64 = base64.b64encode(b"").decode()
        path = decode_base64_to_wav(b64, self.tmpdir)
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"")
        cleanup_temp_file(path)

    def test_prefix_suffix(self):
        raw = b"data"
        b64 = base64.b64encode(raw).decode()
        path = decode_base64_to_wav(b64, self.tmpdir)
        self.assertIn("maibot_stt_", path)
        self.assertTrue(path.endswith(".wav"))
        cleanup_temp_file(path)


class TestCleanupTempFile(unittest.TestCase):
    def test_deletes_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test")
            path = f.name
        self.assertTrue(os.path.exists(path))
        cleanup_temp_file(path)
        self.assertFalse(os.path.exists(path))

    def test_no_error_on_missing_file(self):
        cleanup_temp_file("/tmp/nonexistent_audio_utils_test_file.wav")

    def test_no_error_on_directory(self):
        with tempfile.TemporaryDirectory() as d:
            cleanup_temp_file(d)  # Should not raise


if __name__ == "__main__":
    unittest.main()
