import unittest
import concurrent.futures
import time
from app.agents.graph import agent_graph
from app.logging_config import logger

class TestSupervisorStress(unittest.TestCase):
    """Stress tests the Supervisor Agent StateGraph under multi-user concurrency pressure."""

    def test_concurrent_sessions(self):
        concurrency = 5  # Number of concurrent users
        
        print(f"\n=== RUNNING SUPERVISOR CONCURRENCY STRESS TEST ({concurrency} concurrent requests) ===")
        
        def run_single_request(user_idx):
            state_input = {
                "session_id": f"stress_session_{user_idx}",
                "query": "hello",
                "original_query": "hello",
                "language": "en",
                "intent": "general",
                "resolved_location": None,
                "resolved_location_type": None,
                "resolved_year": None,
                "routing_history": [],
                "current_node": "supervisor",
                "response": "",
                "confidence_score": 0.0,
                "citations": [],
                "evaluation": None
            }
            start = time.time()
            try:
                out = agent_graph.invoke(state_input)
                latency = time.time() - start
                return {
                    "user_idx": user_idx,
                    "success": True,
                    "latency": latency,
                    "response_length": len(out.get("response", ""))
                }
            except Exception as e:
                logger.error(f"Stress request failed for user {user_idx}: {e}")
                return {
                    "user_idx": user_idx,
                    "success": False,
                    "error": str(e)
                }

        start_all = time.time()
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_single_request, i) for i in range(concurrency)]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        total_duration = time.time() - start_all
        
        # Calculate stats
        successes = sum(1 for r in results if r["success"])
        latencies = [r["latency"] for r in results if r["success"]]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        print("=== CONCURRENCY STRESS RESULTS ===")
        print(f"Total Duration : {total_duration:.2f} seconds")
        print(f"Active Users   : {concurrency}")
        print(f"Successful Runs: {successes} / {concurrency}")
        print(f"Average Latency: {avg_latency:.2f} seconds per query")
        print("==================================\n")

        self.assertEqual(successes, concurrency, f"Only {successes} out of {concurrency} concurrent requests completed successfully.")

if __name__ == "__main__":
    unittest.main()
