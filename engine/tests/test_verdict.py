"""结论规则：和桌面端 desktop/shared/verdict.ts 用同一套标准用例（tests-shared/verdict-cases.json），逐字一致"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from avengine.models import Finding  # noqa: E402
from avengine.verdict import verdict  # noqa: E402

CASES = os.path.join(os.path.dirname(__file__), "..", "..", "tests-shared", "verdict-cases.json")


class VerdictGoldenTest(unittest.TestCase):
    def test_golden_cases(self):
        with open(CASES, encoding="utf-8") as f:
            cases = json.load(f)["cases"]
        self.assertGreaterEqual(len(cases), 10)
        for c in cases:
            with self.subTest(c["name"]):
                fs = [Finding(detector=x["detector"], category=x["category"], severity=x["severity"], title="t",
                              start=x["start"], end=x["end"], signal=x["signal"]) for x in c["findings"]]
                v = verdict(fs, c["category"], c["ai_models_ran"])
                self.assertEqual({"level": v.level, "text": v.text}, c["expect"])


if __name__ == "__main__":
    unittest.main()
