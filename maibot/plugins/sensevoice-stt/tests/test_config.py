"""测试 config — 验证配置模块结构（mock maibot_sdk）。"""

import os
import sys
import types
import unittest

# 必须在导入 config 之前 mock maibot_sdk
_mock_sdk = types.ModuleType("maibot_sdk")
_mock_sdk.PluginConfigBase = type("PluginConfigBase", (), {})
_mock_sdk.Field = lambda *a, **kw: {"args": a, "kwargs": kw}
sys.modules["maibot_sdk"] = _mock_sdk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import importlib
import core.config as config_module


class TestConfigModule(unittest.TestCase):
    def setUp(self):
        sys.modules["maibot_sdk"] = _mock_sdk
        importlib.reload(config_module)

    def test_module_imports(self):
        self.assertTrue(hasattr(config_module, "PluginSection"))
        self.assertTrue(hasattr(config_module, "SttConfig"))
        self.assertTrue(hasattr(config_module, "SenseVoiceSttPluginConfig"))

    def test_classes_exist(self):
        self.assertIsNotNone(config_module.PluginSection)
        self.assertIsNotNone(config_module.SttConfig)
        self.assertIsNotNone(config_module.SenseVoiceSttPluginConfig)

    def test_webui_section_metadata(self):
        self.assertEqual(config_module.PluginSection.__ui_label__, "插件设置")
        self.assertEqual(config_module.PluginSection.__ui_icon__, "settings")
        self.assertEqual(config_module.SttConfig.__ui_label__, "SenseVoice 后端")
        self.assertEqual(config_module.SttConfig.__ui_icon__, "record_voice_over")

    def test_endpoint_url_placeholder(self):
        extra = config_module.SttConfig.endpoint_url["kwargs"]["json_schema_extra"]
        self.assertEqual(
            extra["placeholder"],
            "http://127.0.0.1:50000/v1/audio/transcriptions",
        )


if __name__ == "__main__":
    unittest.main()
