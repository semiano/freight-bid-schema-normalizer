import unittest

from src.function_app.services.normalization_service import (
    normalize_bool,
    normalize_country,
    normalize_record,
    normalize_value,
)


class TestNormalizationService(unittest.TestCase):
    def test_normalize_country_maps_known_variants(self) -> None:
        self.assertEqual(normalize_country("US"), "USA")
        self.assertEqual(normalize_country(" canada "), "CAN")
        self.assertEqual(normalize_country("mx"), "MEX")

    def test_normalize_bool_maps_common_string_values(self) -> None:
        self.assertEqual(normalize_bool("Y"), True)
        self.assertEqual(normalize_bool("no"), False)
        self.assertEqual(normalize_bool(""), "")

    def test_normalize_value_trims_strings(self) -> None:
        self.assertEqual(normalize_value("Origin City", "  Dallas "), "Dallas")

    def test_normalize_record_applies_bool_columns(self) -> None:
        record = {
            "Origin Country": "us",
            "Hazmat": "1",
            "Origin City": "  Austin  ",
        }
        normalized = normalize_record(record, bool_columns={"Hazmat"})

        self.assertEqual(normalized["Origin Country"], "USA")
        self.assertEqual(normalized["Hazmat"], True)
        self.assertEqual(normalized["Origin City"], "Austin")


if __name__ == "__main__":
    unittest.main()
