import time
import json
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
from typing import Dict, Any
from app.config import Config
from app.logging_config import logger

class SupervisorMetrics:
    """Collects and logs operational metrics (SQL latency, planning time, memory hit rates, CPU/GPU usage)."""

    @classmethod
    def record_metrics(cls, session_id: str, metrics_data: Dict[str, Any]) -> None:
        """Appends metrics details to system telemetry file."""
        telemetry_file = Config.BASE_DIR / "reports" / "metrics_telemetry.json"
        
        # Load system diagnostics
        try:
            if PSUTIL_AVAILABLE:
                cpu_usage = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                system_stats = {
                    "cpu_percent": cpu_usage,
                    "memory_used_mb": mem.used // (1024 * 1024),
                    "memory_percent": mem.percent
                }
            else:
                system_stats = {}
        except Exception:
            system_stats = {}

        payload = {
            "session_id": session_id,
            "timestamp": time.time(),
            "metrics": metrics_data,
            "system_stats": system_stats
        }

        logger.info(f"[METRICS] Session: {session_id} | Latency: {metrics_data.get('total_latency', 0.0):.2f}s | Planner Cache: {metrics_data.get('cache_hit', False)}")

        try:
            records = []
            if telemetry_file.exists():
                with open(telemetry_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
                    if not isinstance(records, list):
                        records = []
            
            records.append(payload)
            # Limit records to last 1000 items
            records = records[-1000:]
            
            with open(telemetry_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to record telemetry metrics: {e}")
