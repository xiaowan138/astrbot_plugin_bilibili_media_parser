import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


class ConfigSchemaTests(unittest.TestCase):
    def test_every_config_key_used_by_main_has_a_schema_entry(self):
        source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        used = set(
            re.findall(
                r'(?:_config_int|self\.config\.get)\(\s*"([a-z_]+)"', source
            )
        )
        schema = json.loads(
            (PROJECT_ROOT / "_conf_schema.json").read_text(encoding="utf-8")
        )
        missing = sorted(used - set(schema))
        self.assertEqual(
            missing,
            [],
            f"main.py 使用了但 _conf_schema.json 未声明的配置项：{missing}",
        )

    def test_schema_defaults_match_main_py_defaults(self):
        source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        schema = json.loads(
            (PROJECT_ROOT / "_conf_schema.json").read_text(encoding="utf-8")
        )
        for key, entry in schema.items():
            match = re.search(
                rf'_config_int\(\s*"{re.escape(key)}",\s*(-?\d+)', source
            )
            if match:
                self.assertEqual(
                    entry.get("default"),
                    int(match.group(1)),
                    f"{key} 的 schema 默认值与 main.py 不一致",
                )
            bool_match = re.search(
                rf'self\.config\.get\(\s*"{re.escape(key)}",\s*(True|False)\)', source
            )
            if bool_match:
                self.assertEqual(
                    entry.get("default"),
                    bool_match.group(1) == "True",
                    f"{key} 的 schema 默认值与 main.py 不一致",
                )

    def test_schema_new_feature_keys_exist(self):
        schema = json.loads(
            (PROJECT_ROOT / "_conf_schema.json").read_text(encoding="utf-8")
        )
        required = {
            "max_links_per_message": 3,
            "enable_live_monitor": False,
            "live_monitor_keyword": "开播提醒",
            "live_monitor_interval_seconds": 60,
            "live_query_keyword": "直播查询",
            "enable_audio_download": False,
            "audio_download_keyword": "音频下载",
        }
        for key, default in required.items():
            self.assertIn(key, schema, f"缺少新功能配置项 {key}")
            self.assertEqual(schema[key].get("default"), default)


if __name__ == "__main__":
    unittest.main()
