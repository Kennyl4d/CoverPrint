import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from translations import TRANSLATIONS


class TranslationTests(unittest.TestCase):
    def test_all_application_strings_are_translated(self):
        keys = set()
        for filename in ("app/coverprint.py", "windows/coverprint_windows.py"):
            tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
                    if isinstance(node.args[0], ast.Constant):
                        keys.add(node.args[0].value)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ("ABOUT_DESCRIPTION", "ABOUT_LICENSE"):
                            keys.add(ast.literal_eval(node.value))
        self.assertEqual(len(TRANSLATIONS) + 1, 14)
        for language, messages in TRANSLATIONS.items():
            with self.subTest(language=language):
                self.assertFalse(keys - messages.keys())
                self.assertTrue(all(messages[key].strip() for key in keys))
                self.assertIn("GPL-3.0-only", messages[next(key for key in keys if key.startswith("CoverPrint is licensed"))])


if __name__ == "__main__":
    unittest.main()
