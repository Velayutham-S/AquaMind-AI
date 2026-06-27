import time
import json
import numpy as np
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal, init_db
from app.logging_config import logger
from app.agents.knowledge import KnowledgeAgent
from tests.expand_benchmark import expand_benchmark_dataset

def calculate_dcg(relevance_scores):
    dcg = 0.0
    for idx, rel in enumerate(relevance_scores):
        dcg += rel / np.log2(idx + 2)
    return dcg

def calculate_ndcg(relevance_scores):
    dcg = calculate_dcg(relevance_scores)
    idcg = calculate_dcg(sorted(relevance_scores, reverse=True))
    if idcg == 0:
        return 0.0
    return dcg / idcg

def run_retrieval_benchmarks(sample_size: int = 100):
    logger.info("Executing Hybrid RAG Cascading Retrieval Quality Benchmark...")
    init_db()
    
    benchmark_path = Config.BASE_DIR / "data" / "benchmark_answers.json"
    if not benchmark_path.exists():
        logger.info("Benchmark answers dataset not found. Generating...")
        expand_benchmark_dataset(target_size=5000)
        
    with open(benchmark_path, "r", encoding="utf-8") as f:
        all_questions = json.load(f)
        
    # Sample questions representing all groups to keep run times reasonable
    random_state = np.random.RandomState(42)
    sample_indices = random_state.choice(len(all_questions), min(len(all_questions), sample_size), replace=False)
    questions = [all_questions[idx] for idx in sample_indices]
    
    logger.info(f"Running retrieval benchmarks on {len(questions)} sampled questions...")
    
    latencies = []
    
    # Global vectors for cascading levels
    mrr_doc_scores = []
    ndcg_doc_scores = []
    p5_doc_scores = []
    p10_doc_scores = []
    r5_doc_scores = []
    r10_doc_scores = []
    
    mrr_coll_scores = []
    ndcg_coll_scores = []
    
    mrr_page_scores = []
    ndcg_page_scores = []
    
    # Group results mapping
    collection_stats = {}
    language_stats = {}
    
    for idx, q in enumerate(questions):
        query = q["query"]
        expected_sources = q.get("expected_sources", [])
        expected_collection = q.get("expected_collection", "Unknown")
        expected_pages = q.get("expected_pages", [])
        lang = q.get("language", "en")
        
        # Initialize stats groups if needed
        if expected_collection not in collection_stats:
            collection_stats[expected_collection] = {"p5": [], "r10": [], "mrr": [], "ndcg": []}
        if lang not in language_stats:
            language_stats[lang] = {"p5": [], "r10": [], "mrr": [], "ndcg": []}
            
        # Build agent input state
        state_input = {
            "query": query,
            "resolved_location": q.get("expected_value", {}).get("district"),
            "resolved_location_type": "district",
            "routing_history": [],
            "current_node": "knowledge"
        }
        
        start_time = time.time()
        # Invoke the hybrid KnowledgeAgent
        output = KnowledgeAgent.process(state_input)
        latency = (time.time() - start_time) * 1000.0 # ms
        latencies.append(latency)
        
        retrieved_chunks = output.get("context_knowledge", [])
        
        # Relevance vectors
        rel_doc = []
        rel_coll = []
        rel_page = []
        
        for chunk in retrieved_chunks:
            doc_name = chunk.get("document_name", "").lower()
            category = chunk.get("category", "").lower()
            page_num = chunk.get("page_number")
            
            # 1. Document Level match
            doc_match = False
            for src in expected_sources:
                if src.lower() in doc_name or doc_name in src.lower():
                    doc_match = True
                    break
            rel_doc.append(1.0 if doc_match else 0.0)
            
            # 2. Collection Level match
            coll_match = expected_collection.lower() in category or category in expected_collection.lower()
            rel_coll.append(1.0 if coll_match else 0.0)
            
            # 3. Page Level match (falls within expected pages or +-1 margin)
            page_match = False
            if page_num:
                try:
                    p_val = int(page_num)
                    for ep in expected_pages:
                        if abs(p_val - int(ep)) <= 1:
                            page_match = True
                            break
                except ValueError:
                    pass
            rel_page.append(1.0 if page_match else 0.0)
            
        # Pad vectors to length 10
        while len(rel_doc) < 10:
            rel_doc.append(0.0)
        while len(rel_coll) < 10:
            rel_coll.append(0.0)
        while len(rel_page) < 10:
            rel_page.append(0.0)
            
        # Compute scores at document level
        p5_doc = sum(rel_doc[:5]) / 5.0
        p10_doc = sum(rel_doc[:10]) / 10.0
        p5_doc_scores.append(p5_doc)
        p10_doc_scores.append(p10_doc)
        
        total_true = len(expected_sources) if expected_sources else 1
        r5_doc = sum(rel_doc[:5]) / total_true
        r10_doc = sum(rel_doc[:10]) / total_true
        r5_doc_scores.append(r5_doc)
        r10_doc_scores.append(r10_doc)
        
        mrr_doc = 0.0
        for r_idx, val in enumerate(rel_doc):
            if val > 0:
                mrr_doc = 1.0 / (r_idx + 1)
                break
        mrr_doc_scores.append(mrr_doc)
        ndcg_doc = calculate_ndcg(rel_doc)
        ndcg_doc_scores.append(ndcg_doc)
        
        # Compute MRR & nDCG at collection level
        mrr_coll = 0.0
        for r_idx, val in enumerate(rel_coll):
            if val > 0:
                mrr_coll = 1.0 / (r_idx + 1)
                break
        mrr_coll_scores.append(mrr_coll)
        ndcg_coll = calculate_ndcg(rel_coll)
        ndcg_coll_scores.append(ndcg_coll)
        
        # Compute MRR & nDCG at page level
        mrr_page = 0.0
        for r_idx, val in enumerate(rel_page):
            if val > 0:
                mrr_page = 1.0 / (r_idx + 1)
                break
        mrr_page_scores.append(mrr_page)
        ndcg_page = calculate_ndcg(rel_page)
        ndcg_page_scores.append(ndcg_page)
        
        # Track subgroup metrics
        collection_stats[expected_collection]["p5"].append(p5_doc)
        collection_stats[expected_collection]["r10"].append(r10_doc)
        collection_stats[expected_collection]["mrr"].append(mrr_doc)
        collection_stats[expected_collection]["ndcg"].append(ndcg_doc)
        
        language_stats[lang]["p5"].append(p5_doc)
        language_stats[lang]["r10"].append(r10_doc)
        language_stats[lang]["mrr"].append(mrr_doc)
        language_stats[lang]["ndcg"].append(ndcg_doc)

    # Average metrics
    avg_latency = float(np.mean(latencies))
    
    # Formulate output structure
    eval_results = {
        "overall": {
            "precision_at_5": round(float(np.mean(p5_doc_scores)), 4),
            "precision_at_10": round(float(np.mean(p10_doc_scores)), 4),
            "recall_at_5": round(float(np.mean(r5_doc_scores)), 4),
            "recall_at_10": round(float(np.mean(r10_doc_scores)), 4),
            "mrr": round(float(np.mean(mrr_doc_scores)), 4),
            "ndcg": round(float(np.mean(ndcg_doc_scores)), 4),
            "latency_ms": round(avg_latency, 2),
            # Cascading levels averages
            "collection_level_mrr": round(float(np.mean(mrr_coll_scores)), 4),
            "collection_level_ndcg": round(float(np.mean(ndcg_coll_scores)), 4),
            "page_level_mrr": round(float(np.mean(mrr_page_scores)), 4),
            "page_level_ndcg": round(float(np.mean(ndcg_page_scores)), 4)
        },
        "collections": {},
        "languages": {}
    }
    
    # Aggregate collections scores
    for coll, stats in collection_stats.items():
        eval_results["collections"][coll] = {
            "precision_at_5": round(float(np.mean(stats["p5"])), 4),
            "recall_at_10": round(float(np.mean(stats["r10"])), 4),
            "mrr": round(float(np.mean(stats["mrr"])), 4),
            "ndcg": round(float(np.mean(stats["ndcg"])), 4)
        }
        
    # Aggregate language subgroups
    for l, stats in language_stats.items():
        eval_results["languages"][l] = {
            "precision_at_5": round(float(np.mean(stats["p5"])), 4),
            "recall_at_10": round(float(np.mean(stats["r10"])), 4),
            "mrr": round(float(np.mean(stats["mrr"])), 4),
            "ndcg": round(float(np.mean(stats["ndcg"])), 4)
        }
        
    # Save test results
    out_path = Config.BASE_DIR / "reports" / "coverage" / "retrieval_benchmarks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2)
        
    logger.info(f"Retrieval Benchmark Run complete. Overall nDCG: {eval_results['overall']['ndcg']}. Report saved to: {out_path}")
    return eval_results

if __name__ == "__main__":
    run_retrieval_benchmarks(sample_size=50)
