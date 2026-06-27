import os
import time
import json
import random
from datetime import datetime
from app.config import Config
from app.database import SessionLocal, init_db
from app.agents.graph import agent_graph
from app.logging_config import logger

# Seeding baseline templates for benchmark expansion to 1000 questions
QUESTION_TEMPLATES = [
    # English GEC Data Questions
    {"template": "What is the groundwater status in {district}?", "intent": "data", "lang": "en"},
    {"template": "Can you give me GEC resource numbers for {district} in {year}?", "intent": "data", "lang": "en"},
    {"template": "Show the extraction stage trend in {district}.", "intent": "data", "lang": "en"},
    
    # Tamil GEC Data Questions
    {"template": "{district} மாவட்ட நிலத்தடி நீர் நிலை என்ன?", "intent": "data", "lang": "ta"},
    {"template": "{district} நிலத்தடி நீர் எடுப்பு நிலை என்ன?", "intent": "data", "lang": "ta"},
    
    # Prediction Questions
    {"template": "Project groundwater availability for {district} in 2030.", "intent": "prediction", "lang": "en"},
    {"template": "Will the extraction stage in {district} become critical by 2030?", "intent": "prediction", "lang": "en"},
    {"template": "2030-ல் {district} நிலத்தடி நீர் மட்டம் எப்படி இருக்கும்?", "intent": "prediction", "lang": "ta"},

    # Simulation Questions
    {"template": "What happens in {district} if extraction increases by 20%?", "intent": "simulation", "lang": "en"},
    {"template": "How will {district} respond if rainfall drops by 15%?", "intent": "simulation", "lang": "en"},
    {"template": "மழை 15% குறைந்தால் {district} நிலத்தடி நீர் என்னவாகும்?", "intent": "simulation", "lang": "ta"},
    
    # Policy / Regulation Questions
    {"template": "What are the CGWA regulations for over-exploited areas like {district}?", "intent": "knowledge", "lang": "en"},
    {"template": "Tell me about Tamil Nadu Groundwater Act water rules.", "intent": "knowledge", "lang": "en"},
    {"template": "நிலத்தடி நீர் ஒழுங்குமுறை விதிகள் என்ன?", "intent": "knowledge", "lang": "ta"},
    
    # General Science / FAQ Questions
    {"template": "What is the GEC 2015 methodology?", "intent": "knowledge", "lang": "en"},
    {"template": "How do check dams help in groundwater recharge?", "intent": "knowledge", "lang": "en"},
    {"template": "மழைநீர் சேகரிப்பு என்றால் என்ன?", "intent": "knowledge", "lang": "ta"}
]

DISTRICTS = [
    "Salem", "Coimbatore", "Ariyalur", "Tiruppur", "Cuddalore", "Dharmapuri", 
    "Dindigul", "Madurai", "Tirunelveli", "Vellore", "Erode", "Trichy", "Kovai", "Nellai"
]

YEARS = ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]

class HydrologyBenchmark:
    @staticmethod
    def generate_benchmark_suite(size: int = 1000) -> list:
        """Expands baseline templates dynamically to construct 1000 benchmark questions and exports them."""
        suite = []
        random.seed(42) # Set seed for deterministic generation
        
        for i in range(size):
            tmpl = random.choice(QUESTION_TEMPLATES)
            dist = random.choice(DISTRICTS)
            year = random.choice(YEARS)
            
            query = tmpl["template"].format(district=dist, year=year)
            
            # Map expectation attributes
            expected_sources = []
            expected_coll = "General Science"
            difficulty = "Easy"
            
            if tmpl["intent"] == "data":
                expected_sources = [f"{year}.xlsx (GEC Firka Assessment)", "District Assessment Excel Sheets"]
                expected_coll = "Resource Assessment"
                difficulty = "Easy" if "status" in query or "மாவட்ட" in query else "Medium"
            elif tmpl["intent"] == "prediction":
                expected_sources = ["Predictive Trend Analytics Engine", "Year Book PDFs"]
                expected_coll = "Resource Assessment"
                difficulty = "Medium"
            elif tmpl["intent"] == "simulation":
                expected_sources = ["Simulation Model Guidelines", "Artificial Recharge documents"]
                expected_coll = "Modelling & Simulation"
                difficulty = "Hard"
            elif tmpl["intent"] == "knowledge":
                if "CGWA" in query or "Act" in query or "ஒழுங்குமுறை" in query:
                    expected_sources = ["Tamil Nadu Groundwater Act 2003", "CGWA Regulations 2020"]
                    expected_coll = "Regulations & Policy"
                    difficulty = "Medium"
                else:
                    expected_sources = ["GEC 2015 Guidelines PDF", "check_dams_recharge_data"]
                    expected_coll = "General Science"
                    difficulty = "Easy"
                    
            suite.append({
                "id": i + 1,
                "question": query,
                "query": query,
                "expected_intent": tmpl["intent"],
                "expected_sources": expected_sources,
                "expected_collection": expected_coll,
                "difficulty": difficulty,
                "language": tmpl["lang"]
            })
            
        # Write compilation to data/benchmark_answers.json
        answers_path = Config.BASE_DIR / "data" / "benchmark_answers.json"
        with open(answers_path, "w", encoding="utf-8") as f:
            json.dump(suite, f, indent=2)
            
        logger.info(f"Successfully compiled {len(suite)} benchmark QA mappings to: {answers_path}")
        return suite

    @staticmethod
    def run_evaluations(sample_size: int = 10):
        """Runs evaluation tests on a sample of the generated benchmark suite."""
        logger.info(f"HydrologyBenchmark running evaluation suite. Sample size: {sample_size}")
        init_db()
        
        suite = HydrologyBenchmark.generate_benchmark_suite(1000)
        logger.info(f"Successfully generated full benchmark suite of {len(suite)} questions.")
        
        # Select sample for live execution to manage time and costs
        sample = random.sample(suite, sample_size)
        
        results = []
        routing_correct = 0
        total_latency = 0.0
        
        for q in sample:
            start_time = time.time()
            session_id = f"eval_{q['id']}"
            
            logger.info(f"Running Eval {q['id']}/{sample_size}: '{q['query']}'")
            
            state_input = {
                "session_id": session_id,
                "query": q["query"],
                "original_query": q["query"],
                "language": q["language"],
                "intent": "knowledge",
                "resolved_location": None,
                "resolved_location_type": None,
                "resolved_year": None,
                "context_data": None,
                "context_knowledge": None,
                "context_prediction": None,
                "context_simulation": None,
                "context_recommendations": None,
                "context_analytics": None,
                "chart_paths": [],
                "map_html": None,
                "pdf_report_path": None,
                "routing_history": [],
                "current_node": "supervisor",
                "response": "",
                "confidence_score": 0.0,
                "confidence_reason": "",
                "citations": [],
                "evaluation": None
            }
            
            try:
                out = agent_graph.invoke(state_input)
                latency = time.time() - start_time
                total_latency += latency
                
                # Check routing correctness
                actual_nodes = out.get("routing_history", [])
                expected = q["expected_intent"]
                
                # Determine if correct routing node was visited
                is_correct = False
                if expected == "general" and "general" in actual_nodes:
                    is_correct = True
                elif expected == "data" and "data" in actual_nodes:
                    is_correct = True
                elif expected == "prediction" and "prediction" in actual_nodes:
                    is_correct = True
                elif expected == "simulation" and "simulation" in actual_nodes:
                    is_correct = True
                elif expected == "knowledge" and "knowledge" in actual_nodes:
                    is_correct = True
                    
                if is_correct:
                    routing_correct += 1

                audit = out.get("evaluation", {})
                
                results.append({
                    "id": q["id"],
                    "query": q["query"],
                    "expected_intent": expected,
                    "actual_routing": actual_nodes,
                    "routing_correct": is_correct,
                    "latency_sec": latency,
                    "confidence_score": out.get("confidence_score", 0.0),
                    "auditor_grounding": audit.get("grounding_score", "N/A"),
                    "auditor_hallucination": audit.get("hallucination_detected", "N/A"),
                })
            except Exception as e:
                logger.error(f"Eval run failed for query {q['id']}: {e}")
                results.append({
                    "id": q["id"],
                    "query": q["query"],
                    "error": str(e)
                })

        # Calculate metrics
        valid_runs = [r for r in results if "error" not in r]
        avg_latency = total_latency / len(valid_runs) if valid_runs else 0
        routing_accuracy = routing_correct / len(valid_runs) if valid_runs else 0
        avg_confidence = sum([r["confidence_score"] for r in valid_runs]) / len(valid_runs) if valid_runs else 0

        # Save Markdown report
        report_dir = Config.BASE_DIR / "reports" / "evaluation_runs"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "latest_run.md"
        
        report_content = [
            f"# AquaMind AI Platform Evaluation Run",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Benchmark Expanded: 1,000 questions",
            f"Evaluated Test Sample Size: {sample_size}",
            f"---",
            f"## Performance & Routing Summary",
            f"- **Supervisor Routing Accuracy:** {routing_accuracy*100:.1f}%",
            f"- **Average End-to-End Latency:** {avg_latency:.2f} seconds",
            f"- **Average Response Confidence Score:** {avg_confidence:.2f}",
            f"\n## Audited Transaction Logs\n",
            "| ID | Query | Expected Intent | Actual Routing | Confidence | Latency | Grounding Score | Hallucination Detected |",
            "|---|---|---|---|---|---|---|---|",
        ]
        
        for r in results:
            if "error" in r:
                report_content.append(f"| {r['id']} | {r['query']} | N/A | ERROR | N/A | N/A | N/A | N/A |")
            else:
                nodes_str = " -> ".join(r["actual_routing"])
                report_content.append(
                    f"| {r['id']} | {r['query']} | {r['expected_intent']} | {nodes_str} | "
                    f"{r['confidence_score']:.2f} | {r['latency_sec']:.2f}s | {r['auditor_grounding']} | {r['auditor_hallucination']} |"
                )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))

        logger.info(f"Evaluation report generated successfully at: {report_path}")
        print("\n=== BENCHMARK SUMMARY ===")
        print(f"Routing Accuracy: {routing_accuracy*100:.1f}%")
        print(f"Average Latency: {avg_latency:.2f}s")
        print(f"Average Confidence: {avg_confidence:.2f}")
        print(f"Detailed report saved to: {report_path}")

if __name__ == "__main__":
    # Run test evaluation benchmark
    HydrologyBenchmark.run_evaluations(sample_size=5)
