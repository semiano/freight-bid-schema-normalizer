import unittest
from pathlib import Path

from src.function_app.services.workbook_profiler import profile_workbook


class TestWorkbookProfiler(unittest.TestCase):
    def test_profiles_input8_and_identifies_known_sheets(self) -> None:
        workbook_path = Path("examples/inputs/Input 8.xlsx")
        profile = profile_workbook(str(workbook_path))

        self.assertEqual(profile.workbook_name, "Input 8.xlsx")
        self.assertGreaterEqual(len(profile.sheets), 5)

        sheet_names = {sheet.name.strip() for sheet in profile.sheets}
        self.assertIn("SINGLE FTL LIVE LOAD TRAILERS", sheet_names)
        self.assertIn("REQUIREMENTS", sheet_names)
        self.assertIn("FSC", sheet_names)
        self.assertIn("LOCATIONS", sheet_names)

    def test_non_data_sheets_flagged_for_exclusion(self) -> None:
        workbook_path = Path("examples/inputs/Input 8.xlsx")
        profile = profile_workbook(str(workbook_path))

        sheets_by_name = {sheet.name.strip(): sheet for sheet in profile.sheets}

        requirements = sheets_by_name["REQUIREMENTS"]
        fsc = sheets_by_name["FSC"]
        locations = sheets_by_name["LOCATIONS"]

        self.assertIn(requirements.likely_business_meaning, {"instructional", "reference", "likely_exclude"})
        self.assertIn(fsc.likely_business_meaning, {"instructional", "reference", "likely_exclude"})
        self.assertIn(locations.likely_business_meaning, {"instructional", "reference", "likely_exclude"})

        all_hints = requirements.classifier_hints + fsc.classifier_hints + locations.classifier_hints
        self.assertTrue(any("name_matches" in hint for hint in all_hints))


if __name__ == "__main__":
    unittest.main()
