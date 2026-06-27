import time
import os
from typing import Dict, Any, Optional
from app.logging_config import logger

try:
    import psutil
except ImportError:
    psutil = None

class KnowledgeMetrics:
    @staticmethod
    def start_tracking() -> dict:
        """Starts tracking baseline latencies and memory allocations."""
        mem_start = 0.0
        if psutil:
            try:
                mem_start = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            except Exception:
                pass
                
        import torch
        gpu_start = 0.0
        if torch.cuda.is_available():
            gpu_start = torch.cuda.memory_allocated() / (1024 * 1024)
            
        return {
            "start_time": time.time(),
            "mem_start": mem_start,
            "gpu_start": gpu_start
        }

    @staticmethod
    def stop_tracking(
        tracker: dict,
        retrieval_dur_ms: float = 0.0,
        rerank_dur_ms: float = 0.0,
        compress_dur_ms: float = 0.0,
        gen_dur_ms: float = 0.0,
        chunks_searched: int = 0,
        chunks_retrieved: int = 0,
        chunks_reranked: int = 0,
        chunks_compressed: int = 0,
        context_len: int = 0,
        output_len: int = 0
    ) -> Dict[str, Any]:
        """Stops tracking and compiles all telemetry metrics including CPU/GPU deltas."""
        total_dur = (time.time() - tracker["start_time"]) * 1000.0
        
        mem_end = 0.0
        if psutil:
            try:
                mem_end = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            except Exception:
                pass
                
        import torch
        gpu_end = 0.0
        if torch.cuda.is_available():
            gpu_end = torch.cuda.memory_allocated() / (1024 * 1024)
            
        cpu_delta = max(0.0, mem_end - tracker["mem_start"])
        gpu_delta = max(0.0, gpu_end - tracker["gpu_start"])
        
        context_tokens = context_len // 4
        output_tokens = output_len // 4
        
        metrics = {
            "retrieval_latency_ms": float(retrieval_dur_ms),
            "rerank_latency_ms": float(rerank_dur_ms),
            "compression_latency_ms": float(compress_dur_ms),
            "generation_latency_ms": float(gen_dur_ms),
            "total_latency_ms": float(total_dur),
            "chunks_searched": int(chunks_searched),
            "chunks_retrieved": int(chunks_retrieved),
            "chunks_reranked": int(chunks_reranked),
            "chunks_compressed": int(chunks_compressed),
            "context_tokens": int(context_tokens),
            "output_tokens": int(output_tokens),
            "memory_usage_mb": float(mem_end),
            "memory_delta_mb": float(cpu_delta),
            "gpu_usage_mb": float(gpu_end),
            "gpu_delta_mb": float(gpu_delta)
        }
        
        logger.info(f"KnowledgeMetrics compiled: Total Latency={total_dur:.2f}ms | Memory Delta={cpu_delta:.2f}MB")
        return metrics
