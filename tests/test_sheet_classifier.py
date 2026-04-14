import unittest

from src.function_app.services.sheet_classifier import classify_sheet


class TestSheetClassifier(unittest.TestCase):
    def test_classifies_instructional_sheet_as_excluded(self) -> None:
        result = classify_sheet("REQUIREMENTS", ["Col1", "Col2"], [])
        self.assertTrue(result["likely_exclude"])
        self.assertEqual(result["business_meaning"], "instructional")

    def test_classifies_tabular_data_sheet_as_data(self) -> None:
        rows = [
            {"Origin": "Dallas", "Destination": "Austin", "Rate": 1000},
            {"Origin": "Houston", "Destination": "Dallas", "Rate": 900},
            {"Origin": "Waco", "Destination": "Austin", "Rate": 700},
        ]
        result = classify_sheet("SINGLE FTL LIVE LOAD TRAILERS", ["Origin", "Destination", "Rate", "Miles"], rows)
        self.assertFalse(result["likely_exclude"])
        self.assertEqual(result["business_meaning"], "data")


if __name__ == "__main__":
    unittest.main()
