import unittest
from app.agents.table_formatter import TableFormatter

class TestTableFormatter(unittest.TestCase):
    """Tests compiling records to structured Markdown tables."""

    def test_markdown_formatting(self):
        """Verifies correct table formatting parsing columns and values."""
        records = [
            {"district": "SALEM", "total_recharge": 124.50},
            {"district": "COIMBATORE", "total_recharge": 98.20}
        ]
        mapping = {
            "district": "District",
            "total_recharge": "Recharge (ham)"
        }
        table = TableFormatter.format_markdown_table(records, mapping)
        self.assertIn("| District | Recharge (ham) |", table)
        self.assertIn("| SALEM | 124.50 |", table)
        self.assertIn("| COIMBATORE | 98.20 |", table)

if __name__ == "__main__":
    unittest.main()
