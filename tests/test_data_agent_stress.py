import time
import unittest
import threading
from typing import List
from app.database import SessionLocal, init_db
from app.agents.data_agent import DataAgent

class TestDataAgentStress(unittest.TestCase):
    """Stress tests concurrency handling of the DataAgent."""

    def setUp(self):
        init_db()

    def test_concurrent_requests(self):
        """Dispatches 100 concurrent requests across distinct threads to verify deadlock immunity."""
        queries = [
            {"query": "recharge in Salem", "loc": "SALEM", "type": "district"},
            {"query": "extraction in Coimbatore", "loc": "COIMBATORE", "type": "district"},
            {"query": "stage of extraction in Erode", "loc": "ERODE", "type": "district"}
        ]
        
        results = []
        errors = []
        threads: List[threading.Thread] = []
        
        def run_agent(idx):
            q_template = queries[idx % len(queries)]
            state_input = {
                "session_id": f"stress_{idx}",
                "query": q_template["query"],
                "original_query": q_template["query"],
                "resolved_location": q_template["loc"],
                "resolved_location_type": q_template["type"],
                "resolved_year": "2024-2025",
                "intent": "data",
                "response_type": "text",
                "routing_history": []
            }
            
            try:
                start = time.time()
                res = DataAgent.process(state_input)
                dur = (time.time() - start) * 1000.0
                results.append((dur, res))
            except Exception as e:
                errors.append(e)

        # Dispatch 100 threads
        start_time = time.time()
        for i in range(100):
            t = threading.Thread(target=run_agent, args=(i,))
            threads.append(t)
            t.start()
            
        # Join all threads
        for t in threads:
            t.join()
            
        total_time = (time.time() - start_time) * 1000.0
        
        # Verify no deadlocks/exceptions occurred
        self.assertEqual(len(errors), 0, f"Encountered {len(errors)} thread execution errors: {errors}")
        self.assertEqual(len(results), 100)
        
        latencies = [r[0] for r in results]
        sorted_lats = sorted(latencies)
        p95_lat = sorted_lats[int(len(sorted_lats) * 0.95)]
        
        print(f"\n--- CONCURRENT STRESS RESULTS ---")
        print(f"Concurrent Threads: 100")
        print(f"Total Wall Time: {total_time:.2f} ms")
        print(f"P95 Individual Latency: {p95_lat:.2f} ms")
        print(f"---------------------------------")
        
        self.assertLess(p95_lat, 1000.0, "Stress P95 latency is greater than the target 1.0 second.")

if __name__ == "__main__":
    unittest.main()
