import unittest
from unittest.mock import patch
from app.agents.metadata_filter import MetadataFilter

class TestMetadataFilter(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {
                "text": "Salem groundwater recharge GEC guideline details.",
                "metadata": {
                    "district": "Salem",
                    "year": "2023-2024",
                    "source": "GEC",
                    "category": "Guideline",
                    "title": "GEC Ground Water Recharge"
                }
            },
            {
                "text": "Tamil Nadu Groundwater Regulation Act 2003 policy details.",
                "metadata": {
                    "district": None,
                    "year": "2003",
                    "source": "State",
                    "category": "Policy",
                    "title": "Tamil Nadu Groundwater Act 2003"
                }
            },
            {
                "text": "CGWB year book data for Trichy.",
                "metadata": {
                    "district": "Trichy",
                    "year": "2024",
                    "source": "CGWB",
                    "category": "Year Book",
                    "title": "CGWB Hydrological Survey 2024"
                }
            }
        ]

    def test_district_filtering(self):
        """Verifies filtering by district name."""
        filters = {"district": "Salem"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["district"], "Salem")

    def test_year_filtering(self):
        """Verifies filtering by year range or specific year."""
        filters = {"assessment_year": "2023-2024"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["year"], "2023-2024")

    def test_collection_filtering(self):
        """Verifies filtering by collection source (e.g. CGWB)."""
        filters = {"collection": "CGWB"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["source"], "CGWB")

    def test_policy_filtering(self):
        """Verifies filtering by policy document matching."""
        filters = {"policy": "Act 2003"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["category"], "Policy")

    def test_guideline_filtering(self):
        """Verifies filtering by guideline document matching."""
        filters = {"guideline": "Recharge"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["category"], "Guideline")

    def test_multiple_filters(self):
        """Verifies applying multiple filter conditions simultaneously."""
        filters = {"district": "Salem", "collection": "GEC", "report_type": "Guideline"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["metadata"]["district"], "Salem")

    def test_missing_filters(self):
        """Verifies that empty filters return all chunks without filtering."""
        res = MetadataFilter.filter_chunks(self.chunks, {})
        self.assertEqual(len(res), 3)

    def test_invalid_filters(self):
        """Verifies that non-matching filters reject chunks correctly."""
        filters = {"district": "Coimbatore"}
        res = MetadataFilter.filter_chunks(self.chunks, filters)
        self.assertEqual(len(res), 0)

    def test_infer_filters(self):
        """Verifies that MetadataFilter infers filter variables from user query."""
        mock_inferred = {
            "district": "SALEM",
            "assessment_year": "2024",
            "collection": "CGWB",
            "report_type": "Guideline"
        }
        state = {
            "resolved_location": "SALEM",
            "resolved_location_type": "district",
            "resolved_year": "2023-2024"
        }
        with patch("app.agents.llm.LLMService.call_json", return_value=mock_inferred):
            filters = MetadataFilter.infer_filters("What does the 2024 CGWB guideline say about Salem?", state)
            self.assertEqual(filters["district"], "SALEM")
            self.assertEqual(filters["collection"], "CGWB")
            self.assertEqual(filters["assessment_year"], "2023-2024") # state year overrides if present

if __name__ == "__main__":
    unittest.main()
