import unittest
from app.agents.data_citations import DataCitations

class TestDataCitations(unittest.TestCase):
    """Tests the structured citation compilation logic."""

    def test_compile_citations(self):
        """Verifies citations include table, primary keys, records count, and source details."""
        records = [
            {"id": 1, "year": "2024-2025", "total_recharge": 12.0},
            {"id": 2, "year": "2024-2025", "total_recharge": 15.0}
        ]
        res = DataCitations.compile_citations("district_assessments", records, "2024-2025")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["database_table"], "district_assessments")
        self.assertEqual(res[0]["record_count"], 2)
        self.assertEqual(res[0]["primary_keys"], [1, 2])
        self.assertEqual(res[0]["source_file"], "Dynamic Ground Water Resources Tamil Nadu 2025.xlsx")

if __name__ == "__main__":
    unittest.main()
