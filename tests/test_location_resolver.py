import unittest
from app.database import SessionLocal, init_db
from app.agents.location_resolver import LocationResolver

class TestLocationResolver(unittest.TestCase):
    """Tests geographic and master-table name resolution logic."""

    def setUp(self):
        init_db()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_alias_resolution(self):
        """Verifies that common aliases are correctly mapped to their canonical forms."""
        res_kovai = LocationResolver.resolve_location(self.db, "kovai")
        self.assertEqual(res_kovai["resolved"], "COIMBATORE")
        self.assertEqual(res_kovai["type"], "district")

        res_trichy = LocationResolver.resolve_location(self.db, "trichy")
        self.assertEqual(res_trichy["resolved"], "TIRUCHIRAPPALLI")
        self.assertEqual(res_trichy["type"], "district")

    def test_tamil_translation(self):
        """Verifies that Tamil script names are correctly translated."""
        res = LocationResolver.resolve_location(self.db, "சேலம்")
        self.assertEqual(res["resolved"], "SALEM")
        self.assertEqual(res["type"], "district")

    def test_fuzzy_matching(self):
        """Verifies fuzzy matching for minor misspellings."""
        # Salem misspelling
        res = LocationResolver.resolve_location(self.db, "Salim", threshold=0.6)
        self.assertEqual(res["resolved"], "SALEM")
        
        # Coimbatore misspelling
        res2 = LocationResolver.resolve_location(self.db, "Coimbator", threshold=0.7)
        self.assertEqual(res2["resolved"], "COIMBATORE")

if __name__ == "__main__":
    unittest.main()
