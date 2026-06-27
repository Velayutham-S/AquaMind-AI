import unittest
from unittest.mock import patch, MagicMock
from app.supervisor.planner import Planner
from app.agents.llm import LLMService

# A suite of 100 diverse planning queries representing all groundwater categories
BENCHMARK_100_QUERIES = [
    # General AI conversation (1-10)
    "Hello, how can you help me today?", "Who are you?", "What is AquaMind AI?", "Can you explain hydrology?",
    "Tell me a joke about water.", "What is the formula of water?", "Why is groundwater important?",
    "How does rain recharge aquifers?", "Tell me about Tamil Nadu climate.", "Help me analyze well data.",
    # Groundwater GEC queries (11-30)
    "What is the recharge in Salem?", "Show extraction in Coimbatore.", "Stage of extraction in Erode.",
    "Categorization of Ariyalur district.", "Give me resource numbers for Tiruppur in 2024.",
    "Recharge of groundwater in Cuddalore.", "Total extraction in Dharmapuri.", "Stage in Dindigul for 2023.",
    "Category of Madurai.", "Annual extractable resource in Tirunelveli.", "Rainfall recharge in Vellore.",
    "Groundwater stage in Salem for 2024-25.", "Recharge in Coimbatore in 2024-25.",
    "Extraction in Erode in 2024-25.", "Recharge in Ariyalur in 2024-25.", "Extraction in Tiruppur in 2024-25.",
    "Stage in Cuddalore in 2024-25.", "Categorization of Dharmapuri in 2024-25.",
    "Stage in Dindigul in 2024-25.", "Extraction in Madurai in 2024-25.",
    # Knowledge / RAG queries (31-50)
    "What is GEC 2015 methodology?", "How are check dams constructed?", "What are CGWA regulations?",
    "Explain rainwater harvesting methods.", "What is the difference between confined and unconfined aquifers?",
    "Tell me about Tamil Nadu Groundwater Act 2003.", "What is dynamic groundwater assessment?",
    "CGWA guidelines for critical areas.", "How do check dams recharge aquifers?", "Explain watershed management.",
    "What is the status of saline water intrusion in Chennai?", "How is groundwater quality assessed?",
    "What are GEC classification categories?", "What is safe category definition?", "Define over-exploited blocks.",
    "What is the role of rainfall in recharging aquifers?", "How does urbanisation affect recharge?",
    "Explain aquifer mapping programs.", "What is river basin management?", "What are check dam specifications?",
    # Prediction / Time series queries (51-65)
    "Forecast recharge in Salem by 2030.", "Project extraction stage in Coimbatore to 2030.",
    "What will Erode water level be in 2030?", "Future trend of extraction in Ariyalur.",
    "Project Tiruppur resource availability by 2030.", "Forecast groundwater draft for Cuddalore.",
    "Will Dharmapuri groundwater category change by 2030?", "Dindigul water level projection for 2030.",
    "Predict Madurai recharge levels.", "Future extraction trends in Tirunelveli.",
    "Forecast Vellore groundwater stage.", "Salem 2030 water level forecast.", "Coimbatore stage projection 2030.",
    "Erode recharge projection 2030.", "Tiruppur stage projection 2030.",
    # Simulation / Policy queries (66-80)
    "What if extraction in Salem increases by 20%?", "Simulate 15% drop in Coimbatore rainfall.",
    "How does Erode respond if recharge drops by 10%?", "What if Ariyalur recharge increases by 30%?",
    "Simulate domestic extraction increase in Tiruppur.", "What if industrial extraction in Cuddalore doubles?",
    "Simulate climate change impact in Dharmapuri.", "Erode 20% extraction hike scenario.",
    "What if check dams are built in Salem?", "Simulate rainfall drop in Coimbatore.",
    "How does Salem respond if agriculture extraction drops by 15%?", "Simulate Erode draft hike.",
    "Rainfall drop impact in Ariyalur.", "What if extraction in Dharmapuri increases by 30%?",
    "Simulate Salem groundwater recharge increase.",
    # GIS / Maps / Visual queries (81-90)
    "Show a map of Salem groundwater stations.", "Generate a chart comparing Coimbatore vs Salem.",
    "Plot extraction stage trend for Erode.", "Map of critical blocks in Tiruppur.",
    "Show recharge trends chart for Ariyalur.", "Plot water levels for Erode village.",
    "Map of aquifers in Coimbatore.", "Show a chart of extraction categories in Dharmapuri.",
    "Plot GEC resources for Salem.", "Show check dam sites map in Salem.",
    # Tamil / Tanglish / Mixed Script queries (91-100)
    "சேலம் நிலத்தடி நீர் நிலை என்ன?", "கோவை நிலத்தடி நீர் எடுப்பு நிலை என்ன?",
    "Erode மாவட்ட groundwater status enna?", "Salem check dams pathi sollu.",
    "Rainfall drop aana கோவை-ல enna aagum?", "மழை குறைந்தால் Salem water level enna aagum?",
    "CGWA rules pathi sollu.", "2030-ல் கோவை நிலத்தடி நீர் எப்படி இருக்கும்?",
    "சேலம் recharge trend chart காடு.", "Tirunelveli water status detailed report venum."
]

class TestPlanningLLM(unittest.TestCase):
    """Exhaustive planning test suite verifying 100 queries against LLM schemas and recovery logic."""

    def test_schema_validations_all_100_queries(self):
        """Verifies that the planner extracts standard schemas (intent, entities, agents, tools) for 100 queries."""
        # Setup generic mock planner return mapping to verify keys and parsing pipelines
        def mock_llm_json_call(prompt, system_prompt=None):
            # Inspect prompt to deduce intent dynamically
            p_lower = prompt.lower()
            intent = "knowledge"
            agents = ["KnowledgeAgent"]
            tools = []
            
            if "recharge" in p_lower or "extraction" in p_lower or "stage" in p_lower or "status" in p_lower:
                intent = "structured data"
                agents = ["DataAgent"]
            if "forecast" in p_lower or "predict" in p_lower or "2030" in p_lower or "project" in p_lower:
                intent = "prediction"
                agents = ["DataAgent", "PredictionAgent"]
            if "what if" in p_lower or "simulate" in p_lower or "increases by" in p_lower or "drop" in p_lower:
                intent = "simulation"
                agents = ["DataAgent", "SimulationAgent"]
            if "map" in p_lower or "plot" in p_lower or "chart" in p_lower:
                tools = ["ChartGenerator"]
                
            return {
                "intent": intent,
                "reasoning": [f"Mocked analysis of: {prompt[:30]}"],
                "language": "Tamil" if ("சேலம்" in prompt or "கோவை" in prompt) else "English",
                "entities": {"location": "SALEM", "year": "2024-2025"},
                "agents": agents,
                "tools": tools,
                "response_type": "chart" if tools else "text",
                "confidence": 0.95
            }

        with patch("app.agents.llm.LLMService.call_json", side_effect=mock_llm_json_call):
            with patch("app.supervisor.planner_cache.PlannerCache.get_cached_plan", return_value=None):
                for idx, query in enumerate(BENCHMARK_100_QUERIES):
                    classification = "prediction" if "2030" in query else ("simulation" if "what if" in query.lower() or "simulate" in query.lower() else "data")
                    plan = Planner.plan(query, classification, {"location": "SALEM"})
                    
                    self.assertIn("intent", plan, f"Query {idx} failed: intent missing")
                    self.assertIn("reasoning", plan, f"Query {idx} failed: reasoning missing")
                    self.assertIn("agents", plan, f"Query {idx} failed: agents missing")
                    self.assertIn("tools", plan, f"Query {idx} failed: tools missing")
                    self.assertIsInstance(plan["reasoning"], list)
                    self.assertIsInstance(plan["agents"], list)
                    self.assertIsInstance(plan["tools"], list)

    def test_fallback_model_retry_logic(self):
        """Verifies that if the primary LLM rate limits, the planner falls back to the secondary model."""
        call_count = 0
        
        def mock_post(url, headers=None, json=None, timeout=None):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if json and json.get("model") == "llama-3.3-70b-versatile":
                mock_resp.status_code = 500
                mock_resp.text = "Internal Server Error"
            else:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": '{"intent": "knowledge", "reasoning": ["Fallback model success"], "language": "English", "entities": {}, "agents": ["GeneralAgent"], "tools": [], "response_type": "text", "confidence": 0.80}'
                        }
                    }]
                }
            return mock_resp

        with patch("httpx.post", side_effect=mock_post):
            with patch("app.supervisor.planner_cache.PlannerCache.get_cached_plan", return_value=None):
                plan = Planner.plan("Explain check dams", "knowledge", {})
                self.assertEqual(call_count, 2) # Should call primary first, then fallback secondary
                self.assertIn("Fallback model success", plan["reasoning"])
                self.assertEqual(plan["agents"], ["GeneralAgent"])

if __name__ == "__main__":
    unittest.main()
