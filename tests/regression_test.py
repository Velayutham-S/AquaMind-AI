import json
import argparse
import sys
from pathlib import Path
from app.config import Config
from app.logging_config import logger
from tests.benchmark_retrieval import run_retrieval_benchmarks

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_regression_check(save_baseline: bool = False, threshold: float = 0.02):
    baseline_path = Config.BASE_DIR / "reports" / "coverage" / "baseline_retrieval_benchmarks.json"
    current_path = Config.BASE_DIR / "reports" / "coverage" / "retrieval_benchmarks.json"
    
    # 1. Trigger fresh benchmark if current run report is missing
    if not current_path.exists():
        logger.info("Fresh retrieval benchmark not found. Running benchmark retrieval...")
        run_retrieval_benchmarks(sample_size=30)
        
    current_data = load_json(current_path)
    
    if save_baseline:
        logger.info(f"Saving current benchmark scores as baseline to: {baseline_path}")
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2)
        print(f"SUCCESS: Saved new baseline snapshot to: {baseline_path}")
        return
        
    # 2. Check if baseline exists
    if not baseline_path.exists():
        logger.warning(f"Baseline file missing. Saving current run as initial baseline.")
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2)
        print(f"SUCCESS: Initial baseline saved at: {baseline_path}")
        return
        
    baseline_data = load_json(baseline_path)
    
    # 3. Compare overall metrics
    base_ov = baseline_data.get("overall", {})
    curr_ov = current_data.get("overall", {})
    
    metrics_to_check = ["precision_at_5", "precision_at_10", "recall_at_5", "recall_at_10", "mrr", "ndcg"]
    
    regressions = []
    print("=== RETRIEVAL REGRESSION REPORT ===")
    print(f"Comparing Current Run against Baseline (Regression Threshold: {threshold*100.0}%)")
    print("-" * 80)
    print(f"{'Metric':<25} | {'Baseline':<12} | {'Current':<12} | {'Diff':<10} | {'Status':<10}")
    print("-" * 80)
    
    for metric in metrics_to_check:
        base_val = base_ov.get(metric, 0.0)
        curr_val = curr_ov.get(metric, 0.0)
        diff = curr_val - base_val
        
        status = "PASSED"
        if diff < -threshold:
            status = "REGRESSED"
            regressions.append((metric, base_val, curr_val, diff))
            
        print(f"{metric:<25} | {base_val:<12.4f} | {curr_val:<12.4f} | {diff:<+10.4f} | {status:<10}")
        
    print("-" * 80)
    
    if regressions:
        logger.error(f"FAILURE: Retrieval quality regression detected in {len(regressions)} metrics!")
        for metric, base, curr, diff in regressions:
            logger.error(f"Metric '{metric}' regressed from {base:.4f} to {curr:.4f} (diff: {diff:+.4f})")
        sys.exit(1)
    else:
        print("SUCCESS: All retrieval regression assertions passed successfully.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regression Assertion Suite")
    parser.add_argument("--save-baseline", action="store_true", help="Save the current benchmark as the target baseline")
    parser.add_argument("--threshold", type=float, default=0.02, help="Maximum allowed score drop before flagging failure")
    args = parser.parse_args()
    
    run_regression_check(save_baseline=args.save_baseline, threshold=args.threshold)
