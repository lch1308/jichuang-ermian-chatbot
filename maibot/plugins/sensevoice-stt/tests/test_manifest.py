"""测试 manifest — 验证插件市场安装所需的元信息和依赖声明。"""

import json
from pathlib import Path
import unittest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class TestManifest(unittest.TestCase):
    def setUp(self):
        with open(_PLUGIN_ROOT / "_manifest.json", encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_version_and_type(self):
        self.assertEqual(self.manifest["version"], "0.3.0")
        self.assertEqual(self.manifest["plugin_type"], "media")

    def test_declares_only_plugin_runtime_dependency(self):
        deps = self.manifest["dependencies"]
        self.assertEqual(
            deps,
            [
                {
                    "type": "python_package",
                    "name": "aiohttp",
                    "version_spec": ">=3.9.0",
                }
            ],
        )

    def test_sidecar_dependencies_not_installed_into_maibot(self):
        dep_names = {dep.get("name") for dep in self.manifest["dependencies"]}
        self.assertFalse({"torch", "torchaudio", "funasr", "modelscope"} & dep_names)


if __name__ == "__main__":
    unittest.main()
