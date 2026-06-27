import unittest
from app.agents.query_builder import QueryBuilder

class TestQueryBuilder(unittest.TestCase):
    """Tests dynamic parameterized SQL generation to prevent injection and format criteria."""

    def test_simple_select(self):
        """Verifies simple SELECT statements compile correctly."""
        sql, params = QueryBuilder.build("district_assessments", ["district", "total_recharge"])
        self.assertEqual(sql, "SELECT district, total_recharge FROM district_assessments")
        self.assertEqual(params, {})

    def test_where_clause(self):
        """Verifies WHERE clauses compile and bind parameters correctly."""
        sql, params = QueryBuilder.build(
            table_name="district_assessments",
            select_fields=["district", "year"],
            filters={"district": "SALEM", "year": "2024-2025"}
        )
        self.assertIn("district = :p_0", sql)
        self.assertIn("year = :p_1", sql)
        self.assertEqual(params["p_0"], "SALEM")
        self.assertEqual(params["p_1"], "2024-2025")

    def test_in_operator(self):
        """Verifies list inputs map to SQL IN clauses."""
        sql, params = QueryBuilder.build(
            table_name="district_assessments",
            select_fields=["district"],
            filters={"district": ["SALEM", "COIMBATORE"]}
        )
        self.assertIn("district IN (:p_0, :p_1)", sql)
        self.assertEqual(params["p_0"], "SALEM")
        self.assertEqual(params["p_1"], "COIMBATORE")

    def test_comparison_operators(self):
        """Verifies comparison operators compile correctly."""
        sql, params = QueryBuilder.build(
            table_name="monitoring_data",
            select_fields=["value"],
            filters={"value": (">=", 10.5)}
        )
        self.assertIn("value >= :p_0", sql)
        self.assertEqual(params["p_0"], 10.5)

if __name__ == "__main__":
    unittest.main()
