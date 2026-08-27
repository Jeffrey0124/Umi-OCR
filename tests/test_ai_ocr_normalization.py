import importlib.util
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "UmiOCR-data"
PLUGIN_PATH = DATA_ROOT / "plugins" / "AIOCR" / "ai_ocr.py"
sys.path[:0] = [
    str(DATA_ROOT),
    str(DATA_ROOT / "site-packages"),
    str(DATA_ROOT / "py_src" / "imports"),
]

spec = importlib.util.spec_from_file_location("ai_ocr_under_test", PLUGIN_PATH)
ai_ocr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_ocr)


class AiOcrNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.api = ai_ocr.Api({"a_provider": "openai"})

    def sanitize(self, text, output_format="text_only"):
        self.api._current_output_format = output_format
        return self.api._sanitize_ocr_result(
            {
                "code": 100,
                "data": [{"text": text, "box": [], "score": 1.0}],
            }
        )

    def test_emoji_only_result_becomes_no_text(self):
        for text in ("🎁", "⭐", "1️⃣", "🎁⭐"):
            with self.subTest(text=text):
                self.assertEqual(self.sanitize(text), {"code": 101, "data": ""})

    def test_emoji_is_removed_without_discarding_real_text(self):
        result = self.sanitize("豪华礼包🎁")

        self.assertEqual(result["code"], 100)
        self.assertEqual(result["data"][0]["text"], "豪华礼包")

    def test_markdown_keeps_structure_while_removing_emoji(self):
        result = self.sanitize("# 礼包 🎁", output_format="markdown")

        self.assertEqual(result["code"], 100)
        self.assertEqual(result["data"][0]["text"], "# 礼包 ")

    def test_no_text_token_becomes_no_text(self):
        for text in (
            "<<<UMI_OCR_NO_TEXT_7F3A>>>",
            "```<<<UMI_OCR_NO_TEXT_7F3A>>>```",
            "<<<UMI_OCR_NO_TEXT_7F3A>>>。",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.sanitize(text), {"code": 101, "data": ""})

    def test_prompt_defines_the_no_text_token_and_forbids_emoji(self):
        self.api.global_config["a_prompt_text_only"] = "识别文字"
        prompt = self.api._build_prompt(
            {"output_format": "text_only", "language": "auto"}
        )

        self.assertIn("<<<UMI_OCR_NO_TEXT_7F3A>>>", prompt)
        self.assertIn("不得", prompt)
        self.assertIn("Emoji", prompt)

    def test_all_configured_default_prompts_define_the_stable_output_rules(self):
        source = (PLUGIN_PATH.parent / "ai_ocr_config.py").read_text(encoding="utf-8")

        for key in (
            "a_prompt_text_only",
            "a_prompt_with_coordinates",
            "a_prompt_markdown",
        ):
            with self.subTest(key=key):
                match = re.search(
                    rf'"{key}"\s*:\s*\{{(?P<body>.*?)\n\s*\}},', source, re.S
                )
                self.assertIsNotNone(match)
                self.assertIn("<<<UMI_OCR_NO_TEXT_7F3A>>>", match["body"])
                self.assertIn("Emoji", match["body"])
                self.assertIn("装饰", match["body"])


if __name__ == "__main__":
    unittest.main()
