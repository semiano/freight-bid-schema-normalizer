import unittest

from src.function_app.services.template_loader import load_canonical_schema
from src.function_app.services.validation_service import validate_canonical_records


class TestValidationService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_canonical_schema(
            "src/function_app/templates/canonical_schema.freight_bid_v1.json"
        )
        cls.columns = [column.name for column in cls.schema.columns]

    def _base_record(self) -> dict[str, object]:
        record = {column: "" for column in self.columns}
        record["Customer Lane ID"] = "LANE-001"
        record["Customer Miles"] = 120.5
        return record

    def test_validate_canonical_records_passes_for_valid_record(self) -> None:
        records = [self._base_record()]

        result = validate_canonical_records(records, self.schema)

        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "Passed")
        self.assertEqual(result["issue_counts"]["error"], 0)
        self.assertEqual(result["metrics"]["row_count"], 1)

    def test_validate_canonical_records_fails_for_missing_required(self) -> None:
        record = self._base_record()
        record["Customer Lane ID"] = ""

        result = validate_canonical_records([record], self.schema)

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "Failed")
        self.assertGreaterEqual(result["issue_counts"]["error"], 1)
        self.assertTrue(any(issue["code"] == "required_missing" for issue in result["issues"]))

    def test_validate_canonical_records_fails_for_extra_column(self) -> None:
        record = self._base_record()
        record["Unexpected Field"] = "not allowed"

        result = validate_canonical_records([record], self.schema)

        self.assertFalse(result["passed"])
        self.assertTrue(any(issue["code"] == "extra_columns" for issue in result["issues"]))

    def test_validate_canonical_records_fails_for_type_mismatch(self) -> None:
        record = self._base_record()
        record["Customer Miles"] = "not-a-number"

        result = validate_canonical_records([record], self.schema)

        self.assertFalse(result["passed"])
        self.assertTrue(any(issue["code"] == "type_mismatch" for issue in result["issues"]))

    def test_validate_canonical_records_fails_for_invalid_enum_value(self) -> None:
        record = self._base_record()
        record["FSC Type"] = "UnknownType"

        result = validate_canonical_records([record], self.schema)

        self.assertFalse(result["passed"])
        self.assertTrue(any(issue["code"] == "enum_invalid" for issue in result["issues"]))

    def test_validate_canonical_records_warns_for_cross_field_consistency(self) -> None:
        record = self._base_record()
        record["Origin City"] = "Dallas"
        record["Origin Country"] = ""

        result = validate_canonical_records([record], self.schema)

        self.assertTrue(any(issue["code"] == "cross_field_missing_pair" for issue in result["issues"]))

    def test_validate_canonical_records_warns_for_null_rate_threshold(self) -> None:
        record_one = self._base_record()
        record_two = self._base_record()
        record_one["FO Code"] = ""
        record_two["FO Code"] = ""

        result = validate_canonical_records(
            [record_one, record_two],
            self.schema,
            null_rate_thresholds={"FO Code": 0.5},
        )

        self.assertTrue(any(issue["code"] == "null_rate_exceeded" for issue in result["issues"]))

    def test_validate_canonical_records_can_emit_lineage_summary(self) -> None:
        record = self._base_record()
        record["_source_row_id"] = "input-8:sheet1:row-2"

        result = validate_canonical_records(
            [record],
            self.schema,
            include_lineage=True,
            source_row_id_field="_source_row_id",
        )

        self.assertIn("lineage", result)
        self.assertEqual(result["lineage"]["rows_with_source_id"], 1)
        self.assertEqual(result["lineage"]["coverage"], 1.0)

    def test_validate_canonical_records_lineage_coverage_handles_missing_ids(self) -> None:
        record_one = self._base_record()
        record_two = self._base_record()
        record_one["_source_row_id"] = "s1:r2"
        record_two["_source_row_id"] = ""

        result = validate_canonical_records(
            [record_one, record_two],
            self.schema,
            include_lineage=True,
            source_row_id_field="_source_row_id",
        )

        self.assertIn("lineage", result)
        self.assertEqual(result["lineage"]["rows_with_source_id"], 1)
        self.assertEqual(result["lineage"]["row_count"], 2)
        self.assertEqual(result["lineage"]["coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
