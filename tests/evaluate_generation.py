import os
import json
import time
import random
from pathlib import Path
from app.config import Config
from app.database import SessionLocal, init_db
from app.agents.graph import agent_graph
from app.logging_config import logger

def run_hallucination_evaluation(sample_size: int = 5):
    logger.info("Executing Generation Quality & Hallucination Benchmark...")
    init_db()
    
    benchmark_path = Config.BASE_DIR / "data" / "benchmark_answers.json"
    if not benchmark_path.exists():
        logger.warning("Benchmark QA data missing. Please expand benchmarks first.")
        return None
        
    with open(benchmark_path, "r", encoding="utf-8") as f:
        all_questions = json.load(f)
        
    # Sample a small size to manage API limits
    random.seed(42)
    sample = random.sample(all_questions, min(len(all_questions), sample_size))
    
    results = []
    grounded_count = 0
    partially_grounded_count = 0
    unsupported_count = 0
    hallucinated_count = 0
    
    for idx, q in enumerate(sample):
        query = q["query"]
        logger.info(f"Evaluating generation for query {idx+1}/{sample_size}: '{query}'")
        
        # Construct pipeline input
        state_input = {
            "session_id": f"hallucination_eval_{q['id']}",
            "query": query,
            "original_query": query,
            "language": q.get("language", "en"),
            "intent": q.get("expected_intent", "knowledge"),
            "resolved_location": q.get("expected_value", {}).get("district"),
            "resolved_location_type": "district",
            "resolved_year": q.get("expected_value", {}).get("year"),
            "routing_history": [],
            "current_node": "supervisor",
            "response": "",
            "confidence_score": 0.0,
            "citations": [],
            "evaluation": None
        }
        
        try:
            start_time = time.time()
            out = agent_graph.invoke(state_input)
            latency = time.time() - start_time
            
            # The agent graph automatically runs the EvaluationAgent node at the end.
            # Let's read the audit evaluations from the output state.
            audit = out.get("evaluation") or {}
            
            # Extract scores
            grounding_score = audit.get("grounding_score", 1.0)
            hallucination_detected = audit.get("hallucination_detected", False)
            citation_accuracy = audit.get("citation_accuracy", 1.0)
            
            # Force conversion
            try:
                g_score = float(grounding_score)
            except (ValueError, TypeError):
                g_score = 1.0
                
            # Classify based on RAG grounding constraints
            if hallucination_detected or g_score < 0.4:
                category = "Hallucinated"
                hallucinated_count += 1
            elif g_score >= 0.85:
                category = "Grounded"
                grounded_count += 1
            elif g_score >= 0.60:
                category = "Partially Grounded"
                partially_grounded_count += 1
            else:
                category = "Unsupported"
                unsupported_count += 1
                
            results.append({
                "id": q["id"],
                "query": query,
                "response": out.get("response", ""),
                "grounding_score": g_score,
                "hallucination_detected": bool(hallucination_detected),
                "citation_accuracy": citation_accuracy,
                "category": category,
                "latency_sec": round(latency, 2)
            })
            
            logger.info(f"Query {q['id']} classification: {category} (grounding score: {g_score})")
            
        except Exception as e:
            logger.error(f"Error evaluating query {q['id']}: {e}", exc_info=True)
            results.append({
                "id": q["id"],
                "query": query,
                "error": str(e),
                "category": "Error"
            })
            
    total_valid = len([r for r in results if r.get("category") != "Error"])
    hallucination_rate = (hallucinated_count / total_valid * 100.0) if total_valid > 0 else 0.0
    
    eval_summary = {
        "summary": {
            "total_evaluated": len(results),
            "total_valid": total_valid,
            "grounded_count": grounded_count,
            "partially_grounded_count": partially_grounded_count,
            "unsupported_count": unsupported_count,
            "hallucinated_count": hallucinated_count,
            "hallucination_rate_percentage": round(hallucination_rate, 2),
            "average_grounding_score": round(sum(r.get("grounding_score", 0.0) for r in results if "grounding_score" in r) / total_valid, 2) if total_valid > 0 else 1.0
        },
        "runs": results
    }
    
    out_path = Config.BASE_DIR / "reports" / "coverage" / "hallucination_benchmarks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)
        
    logger.info(f"Hallucination Evaluation Run complete. Hallucination rate: {hallucination_rate}%. Report saved to: {out_path}")
    return eval_summary

if __name__ == "__main__":
    run_hallucination_evaluation(sample_size=3)
