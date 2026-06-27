import time
import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.logging_config import logger

try:
    import psutil
except ImportError:
    psutil = None

class DataMetrics:
    """Tracks and records execution latency, scanned rows, index usage, and system resources delta."""

    @classmethod
    def start_tracking(cls) -> Dict[str, Any]:
        """Captures initial baseline state before execution."""
        mem = 0.0
        if psutil:
            try:
                process = psutil.Process(os.getpid())
                mem = process.memory_info().rss / (1024 * 1024) # MB
            except Exception:
                pass
        return {
            "start_time": time.time(),
            "start_memory": mem
        }

    @classmethod
    def stop_tracking(
        cls, 
        db: Session, 
        sql_str: str, 
        params: Dict[str, Any], 
        start_state: Dict[str, Any], 
        rows_returned: int
    ) -> Dict[str, Any]:
        """Calculates final telemetry parameters, running EXPLAIN QUERY PLAN to audit indexes."""
        end_time = time.time()
        latency_ms = (end_time - start_state["start_time"]) * 1000.0
        
        # Calculate memory delta
        mem_end = 0.0
        if psutil:
            try:
                process = psutil.Process(os.getpid())
                mem_end = process.memory_info().rss / (1024 * 1024)
            except Exception:
                pass
        mem_delta = max(0.0, mem_end - start_state["start_memory"])
        
        # Explain Query Plan execution
        indexes_used = []
        rows_scanned = rows_returned # baseline fallback
        table_scan_detected = False
        
        if sql_str and db:
            try:
                explain_sql = text(f"EXPLAIN QUERY PLAN {sql_str}")
                res = db.execute(explain_sql, params).fetchall()
                for row in res:
                    # columns of explain: selectid, order, from, detail
                    detail = str(row[3])
                    if "USING INDEX" in detail:
                        # Extract index name
                        parts = detail.split("USING INDEX")
                        if len(parts) > 1:
                            index_name = parts[1].strip().split()[0]
                            indexes_used.append(index_name)
                    if "SCAN TABLE" in detail:
                        table_scan_detected = True
                        
                # Estimate rows scanned based on plan:
                if table_scan_detected:
                    # Query table size if scan detected to get real scanned rows
                    # (This is just an estimation, we can default to rows_returned * 10 for table scan)
                    rows_scanned = max(rows_returned * 10, 100)
                else:
                    # Logarithmic or indexed lookup: small scans
                    rows_scanned = max(rows_returned, 1)
            except Exception as explain_err:
                logger.warning(f"EXPLAIN QUERY PLAN audit failed: {explain_err}")
                
        metrics = {
            "sql_build_time_ms": 0.0, # Will be set by client
            "query_execution_time_ms": latency_ms,
            "rows_returned": rows_returned,
            "rows_scanned": rows_scanned,
            "indexes_used": list(set(indexes_used)),
            "memory_mb": float(mem_delta),
            "total_latency_ms": latency_ms
        }
        logger.info(f"Query Telemetry logged: {metrics}")
        return metrics
