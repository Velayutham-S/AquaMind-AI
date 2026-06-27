import time
import unittest
from app.database import SessionLocal, init_db
from app.agents.data_agent import DataAgent

class BenchmarkDataAgent(unittest.TestCase):
    """Benchmarks the DataAgent execution speed over 100 queries."""

    def setUp(self):
        init_db()

    def test_benchmark_performance(self):
        """Measures average and P95 execution latency over 100 data requests."""
        queries = [
            {"query": "recharge in Salem", "loc": "SALEM", "type": "district", "year": "2024-2025"},
            {"query": "extraction in Coimbatore", "loc": "COIMBATORE", "type": "district", "year": "2024-2025"},
            {"query": "stage of extraction in Erode", "loc": "ERODE", "type": "district", "year": "2024-2025"},
            {"query": "average groundwater level in Salem", "loc": "SALEM", "type": "district", "year": None}
        ]
        
        latencies = []
        
        # Run 100 iterations (cycling through the queries list)
        for i in range(100):
            q_template = queries[i % len(queries)]
            state_input = {
                "session_id": f"benchmark_{i}",
                "query": q_template["query"],
                "original_query": q_template["query"],
                "resolved_location": q_template["loc"],
                "resolved_location_type": q_template["type"],
                "resolved_year": q_template["year"],
                "intent": "data",
                "response_type": "text",
                "routing_history": []
            }
            
            start = time.time()
            res = DataAgent.process(state_input)
            duration = (time.time() - start) * 1000.0 # ms
            latencies.append(duration)
            
        avg_lat = sum(latencies) / len(latencies)
        sorted_lat = sorted(latencies)
        p95_lat = sorted_lat[int(len(sorted_lat) * 0.95)]
        
        print(f"\n--- DATA AGENT BENCHMARK RESULTS ---")
        print(f"Total Iterations: {len(latencies)}")
        print(f"Average Latency: {avg_lat:.2f} ms")
        print(f"P95 Latency: {p95_lat:.2f} ms")
        print(f"------------------------------------")
        
        self.assertLess(avg_lat, 500.0, "Average latency is greater than the target 500 ms.")
        self.assertLess(p95_lat, 1000.0, "P95 latency is greater than the target 1.0 second.")

if __name__ == "__main__":
    unittest.main()
