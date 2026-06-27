import time
import threading
import os
import unittest
from typing import List, Dict, Any
from unittest.mock import patch
from app.database import SessionLocal, init_db
from app.agents.graph import agent_graph

try:
    import psutil
except ImportError:
    psutil = None

class StressTestRunner:
    """Orchestrates concurrent stress tests under varying virtual user loads and measures telemetry metrics."""

    @staticmethod
    def simulate_users(user_count: int) -> Dict[str, Any]:
        """Dispatches concurrent graph executions across distinct threads and records timings."""
        results = []
        errors = []
        threads: List[threading.Thread] = []
        
        # Mocks to prevent hitting Groq rate limits under high concurrency
        mock_plan = {
            "intent": "data",
            "reasoning": ["User requested recharge rates."],
            "language": "English",
            "entities": {"location": "SALEM", "year": "2024-2025"},
            "agents": ["DataAgent"],
            "tools": [],
            "response_type": "text",
            "confidence": 0.98
        }
        
        def run_user(idx):
            state_input = {
                "session_id": f"stress_session_{user_count}_{idx}",
                "query": "What is the GEC recharge in Salem?",
                "original_query": "What is the GEC recharge in Salem?",
                "language": "en",
                "intent": "data",
                "resolved_location": "SALEM",
                "resolved_location_type": "district",
                "resolved_year": "2024-2025",
                "routing_history": [],
                "current_node": "supervisor",
                "response": "",
                "confidence_score": 0.0,
                "confidence_reason": "",
                "citations": [],
                "evaluation": None
            }
            
            try:
                start = time.time()
                # Run the compiled LangGraph workflow
                agent_graph.invoke(state_input)
                dur = (time.time() - start) * 1000.0 # ms
                results.append(dur)
            except Exception as e:
                errors.append(e)

        # Baseline system metrics
        cpu_start = psutil.cpu_percent(interval=None) if psutil else 0.0
        mem_start = 0.0
        if psutil:
            try:
                mem_start = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            except Exception:
                pass

        start_wall = time.time()
        
        # Run with mocks active
        mock_eval = {
            "routing_accuracy": 1.0,
            "retrieval_precision": 1.0,
            "grounding_score": 0.99,
            "citation_accuracy": 1.0,
            "hallucination_detected": False,
            "language_accuracy": 1.0,
            "summary": "Mocked validation output summary."
        }
        
        def mock_call_json(prompt, system_prompt=None):
            if system_prompt and "Auditor" in system_prompt:
                return mock_eval
            return mock_plan

        def mock_call(prompt, system_prompt=None, json_mode=False):
            import json
            if json_mode:
                return json.dumps(mock_call_json(prompt, system_prompt))
            return "Mocked response text"

        with patch("app.agents.llm.LLMService.call_json", side_effect=mock_call_json):
            with patch("app.agents.llm.LLMService.call", side_effect=mock_call):
                with patch("app.supervisor.planner.Planner.plan", return_value=mock_plan):
                    
                    for i in range(user_count):
                        t = threading.Thread(target=run_user, args=(i,))
                        threads.append(t)
                        t.start()
                        
                    for t in threads:
                        t.join()
                        
        wall_time = (time.time() - start_wall) * 1000.0 # ms
        
        # Calculate stats
        avg_lat = sum(results) / len(results) if results else 0.0
        sorted_results = sorted(results)
        p95_lat = sorted_results[int(len(sorted_results) * 0.95)] if results else 0.0
        
        cpu_end = psutil.cpu_percent(interval=None) if psutil else 0.0
        mem_end = 0.0
        if psutil:
            try:
                mem_end = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            except Exception:
                pass
                
        return {
            "users": user_count,
            "wall_time_ms": wall_time,
            "average_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "errors": len(errors),
            "cpu_delta": max(0.0, cpu_end - cpu_start),
            "memory_delta_mb": max(0.0, mem_end - mem_start)
        }

class TestStressSuite(unittest.TestCase):
    """Stress suite execution validator verifying thread-safety and latency metrics."""

    def setUp(self):
        init_db()

    def test_run_stress_scenarios(self):
        """Dispatches sequential concurrency stress tests for 10, 25, 50, and 100 users."""
        scenarios = [10, 25, 50, 100]
        results = []
        
        for u in scenarios:
            res = StressTestRunner.simulate_users(u)
            results.append(res)
            print(f"Stress Test: Users={res['users']} | WallTime={res['wall_time_ms']:.2f}ms | AvgLat={res['average_latency_ms']:.2f}ms | P95Lat={res['p95_latency_ms']:.2f}ms | Errors={res['errors']}")
            
            # Assert zero errors and deadlocks
            self.assertEqual(res["errors"], 0, f"Stress test failed with errors under load: {res['errors']}")
            self.assertLess(res["average_latency_ms"], 1000.0, "Average latency under load is too high.")
            
        # Format a final stress report dictionary/output if running standalone
        self.assertEqual(len(results), 4)

if __name__ == "__main__":
    unittest.main()
