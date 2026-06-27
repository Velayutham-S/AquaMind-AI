import unittest
from app.agents.data_validator import DataValidator

class TestDataValidator(unittest.TestCase):
    """Tests the structured parameter validation checks."""

    def test_validation_passes(self):
        """Verifies valid parameters resolve successfully."""
        is_valid, msg = DataValidator.validate_query_entities(
            location="SALEM",
            location_type="district",
            year="2024-2025",
            parameter="total_recharge"
        )
        self.assertTrue(is_valid)
        self.assertEqual(msg, "")

    def test_missing_location(self):
        """Verifies validation catch for missing locations."""
        is_valid, msg = DataValidator.validate_query_entities(
            location="",
            location_type="district"
        )
        self.assertFalse(is_valid)
        self.assertIn("missing", msg)

    def test_invalid_location_type(self):
        """Verifies validation fails on unsupported geographical types."""
        is_valid, msg = DataValidator.validate_query_entities(
            location="SALEM",
            location_type="unsupported_type"
        )
        self.assertFalse(is_valid)
        self.assertIn("invalid", msg.lower())

    def test_invalid_parameter(self):
        """Verifies validation catch and suggestions for unsupported parameters."""
        is_valid, msg = DataValidator.validate_query_entities(
            location="SALEM",
            location_type="district",
            parameter="invalid_param_name"
        )
        self.assertFalse(is_valid)
        self.assertIn("not supported", msg)

if __name__ == "__main__":
    unittest.main()
