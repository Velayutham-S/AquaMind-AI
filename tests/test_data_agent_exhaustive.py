import unittest
from app.database import SessionLocal, init_db
from app.agents.data_agent import DataAgent

# Exhaustive suite of 100 groundwater inquiries
DATA_AGENT_100_QUERIES = [
    # Point queries for Salem, Coimbatore, Ariyalur, Tiruppur, Erode, Karur, Namakkal, etc. (1-30)
    {"q": "Recharge in Salem", "loc": "SALEM", "type": "district", "year": "2024-2025"},
    {"q": "Extraction in Coimbatore", "loc": "COIMBATORE", "type": "district", "year": "2024-2025"},
    {"q": "Stage of extraction in Erode", "loc": "ERODE", "type": "district", "year": "2024-2025"},
    {"q": "Categorization of Ariyalur", "loc": "ARIYALUR", "type": "district", "year": "2024-2025"},
    {"q": "GEC recharge in Tiruppur", "loc": "TIRUPPUR", "type": "district", "year": "2024-2025"},
    {"q": "Groundwater extraction in Madurai", "loc": "MADURAI", "type": "district", "year": "2024-2025"},
    {"q": "Stage in Trichy", "loc": "TIRUCHIRAPPALLI", "type": "district", "year": "2024-2025"},
    {"q": "Annual extractable limit in Thanjavur", "loc": "THANJAVUR", "type": "district", "year": "2024-2025"},
    {"q": "Categorization in Erode", "loc": "ERODE", "type": "district", "year": "2024-2025"},
    {"q": "Recharge in Karur", "loc": "KARUR", "type": "district", "year": "2024-2025"},
    {"q": "Stage in Namakkal", "loc": "NAMAKKAL", "type": "district", "year": "2024-2025"},
    {"q": "Resource summary of Dindigul", "loc": "DINDIGUL", "type": "district", "year": "2024-2025"},
    {"q": "Rainfall recharge in Vellore", "loc": "VELLORE", "type": "district", "year": "2024-2025"},
    {"q": "Stage in Tirunelveli", "loc": "TIRUNELVELI", "type": "district", "year": "2024-2025"},
    {"q": "Recharge in Dharmapuri", "loc": "DHARMAPURI", "type": "district", "year": "2024-2025"},
    # Generate 15 more point variations for other districts / years
    *[{"q": f"Recharge in Salem for year {yr}", "loc": "SALEM", "type": "district", "year": yr} for yr in ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]],
    *[{"q": f"Stage in Coimbatore for year {yr}", "loc": "COIMBATORE", "type": "district", "year": yr} for yr in ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]],
    *[{"q": f"Extraction in Erode for year {yr}", "loc": "ERODE", "type": "district", "year": yr} for yr in ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]],
    
    # Trend queries across consecutive time limits (31-50)
    *[{"q": f"Recharge trend in {dist}", "loc": dist, "type": "district", "year": None} for dist in ["SALEM", "COIMBATORE", "ERODE", "ARIYALUR", "TIRUPPUR", "MADURAI", "TIRUNELVELI", "VELLORE", "KARUR", "NAMAKKAL"]],
    *[{"q": f"Extraction trend in {dist}", "loc": dist, "type": "district", "year": None} for dist in ["SALEM", "COIMBATORE", "ERODE", "ARIYALUR", "TIRUPPUR", "MADURAI", "TIRUNELVELI", "VELLORE", "KARUR", "NAMAKKAL"]],
    
    # Ranking queries: top / bottom over-exploited, low recharge (51-70)
    *[{"q": f"Top {k} over-exploited districts", "loc": "SALEM", "type": "district", "year": "2024-2025"} for k in range(5, 15)],
    *[{"q": f"Lowest recharge districts top {k}", "loc": "COIMBATORE", "type": "district", "year": "2024-2025"} for k in range(5, 15)],
    
    # Comparison queries: Salem vs Coimbatore, etc. (71-90)
    *[{"q": f"Comparison between {d1} and {d2}", "loc": d1, "type": "district", "year": "2024-2025"} for d1, d2 in [
        ("SALEM", "COIMBATORE"), ("ERODE", "TIRUPPUR"), ("ARIYALUR", "CUDDALORE"), ("MADURAI", "TIRUNELVELI"),
        ("VELLORE", "RANIPET"), ("KARUR", "NAMAKKAL"), ("THANJAVUR", "TIRUVARUR"), ("SIVAGANGA", "RAMANATHAPURAM"),
        ("TENKASI", "TIRUNELVELI"), ("RANIPET", "TIRUPATHUR")
    ]],
    *[{"q": f"Resource comparison {d1} vs {d2} for 2023", "loc": d1, "type": "district", "year": "2022-2023"} for d1, d2 in [
        ("SALEM", "COIMBATORE"), ("ERODE", "TIRUPPUR"), ("ARIYALUR", "CUDDALORE"), ("MADURAI", "TIRUNELVELI"),
        ("VELLORE", "RANIPET"), ("KARUR", "NAMAKKAL"), ("THANJAVUR", "TIRUVARUR"), ("SIVAGANGA", "RAMANATHAPURAM"),
        ("TENKASI", "TIRUNELVELI"), ("RANIPET", "TIRUPATHUR")
    ]],
    
    # Geographic layers / villages / aquifers / station parameters (91-100)
    {"q": "Well station levels in Salem", "loc": "SALEM", "type": "district", "year": None},
    {"q": "Aquifer status in Coimbatore", "loc": "COIMBATORE", "type": "district", "year": None},
    {"q": "Recharge levels in Salem Watershed", "loc": "SALEM", "type": "district", "year": None},
    {"q": "Water level monitoring in Erode Well", "loc": "ERODE", "type": "district", "year": None},
    {"q": "Rainfall in Coimbatore station", "loc": "COIMBATORE", "type": "district", "year": None},
    {"q": "Salem station groundwater levels", "loc": "SALEM", "type": "district", "year": None},
    {"q": "Erode aquifer recharge capacity", "loc": "ERODE", "type": "district", "year": None},
    {"q": "Coimbatore river basin station values", "loc": "COIMBATORE", "type": "district", "year": None},
    {"q": "Salem district village level changes", "loc": "SALEM", "type": "district", "year": None},
    {"q": "Tiruppur groundwater observation wells", "loc": "TIRUPPUR", "type": "district", "year": None}
]

class TestDataAgentExhaustive(unittest.TestCase):
    """Exhaustive test suite verifying the DataAgent against 100 groundwater queries."""

    def setUp(self):
        init_db()

    def test_exhaustive_queries_execution(self):
        """Dispatches 100 structured groundwater queries verifying correctness of data structures and zero SQL syntax failures."""
        for idx, q_dict in enumerate(DATA_AGENT_100_QUERIES):
            state_input = {
                "session_id": f"exhaustive_test_{idx}",
                "query": q_dict["q"],
                "original_query": q_dict["q"],
                "resolved_location": q_dict["loc"],
                "resolved_location_type": q_dict["type"],
                "resolved_year": q_dict["year"],
                "intent": "data",
                "response_type": "text",
                "routing_history": []
            }
            
            res = DataAgent.process(state_input)
            
            self.assertIn("context_data", res, f"Query {idx} failed: context_data missing")
            self.assertIn("confidence_score", res, f"Query {idx} failed: confidence_score missing")
            self.assertIn("citations", res, f"Query {idx} failed: citations missing")
            self.assertIn("response", res, f"Query {idx} failed: response missing")
            self.assertIsInstance(res["context_data"], list)
            self.assertIsInstance(res["citations"], list)
            self.assertIsInstance(res["response"], str)
            self.assertGreaterEqual(res["confidence_score"], 0.0)
            self.assertLessEqual(res["confidence_score"], 1.0)

if __name__ == "__main__":
    unittest.main()
