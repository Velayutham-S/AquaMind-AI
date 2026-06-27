import os
import time
from datetime import datetime
from pathlib import Path
from app.config import Config
from app.logging_config import logger

class ExecutionReportGenerator:
    """Compiles and saves detailed supervisor execution telemetry reports to disk."""

    @classmethod
    def generate(cls, session_data: dict, evaluation: dict) -> str:
        """Generates a markdown report for the current execution and saves it."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Calculate total latency
        timeline = session_data.get("execution_timeline") or []
        total_latency_ms = sum(t.get("duration_ms", 0) for t in timeline)
        
        # Build timeline text
        timeline_rows = []
        for t in timeline:
            timeline_rows.append(f"{t.get('time')} | {t.get('stage')} | {t.get('duration_ms')} ms")
        timeline_str = "\n↓\n".join(timeline_rows)
        
        # Build reasoning text
        reasoning = session_data.get("reasoning") or []
        reasoning_str = "\n".join([f"- {r}" for r in reasoning]) if reasoning else "- No reasoning logged."
        
        # Build progress events text
        progress_events = session_data.get("progress_events") or []
        events_rows = []
        for e in progress_events:
            events_rows.append(f"| {e.get('time')} | {e.get('progress')}% | {e.get('stage')} | {e.get('message')} |")
        events_table = (
            "| Time | Progress | Stage | Message |\n"
            "|---|---|---|---|\n" + "\n".join(events_rows)
        )
        
        # Build confidence breakdown text
        overall_conf = session_data.get("overall_confidence", 0.0)
        conf_level = session_data.get("confidence_level", "LOW")
        breakdown = session_data.get("confidence_breakdown") or {}
        breakdown_str = "\n".join([f"- **{comp}**: {score:.2f}" for comp, score in breakdown.items()])
        
        # Build Mermaid graph
        agents = session_data.get("execution_plan", {}).get("agents", [])
        tools = session_data.get("execution_plan", {}).get("tools", [])
        
        # Format list
        agents_str = ", ".join(agents) if agents else "None"
        tools_str = ", ".join(tools) if tools else "None"
        
        mermaid_graph = (
            "```mermaid\n"
            "graph TD\n"
            "    User([User Query]) --> Pre[Preprocessing]\n"
            "    Pre --> Plan[Planner]\n"
            "    Plan --> Route[Router]\n"
        )
        for a in agents:
            mermaid_graph += f"    Route --> {a}[{a}]\n"
            mermaid_graph += f"    {a} --> Collate[Evidence Aggregator]\n"
        if not agents:
            mermaid_graph += "    Route --> Collate[Evidence Aggregator]\n"
        mermaid_graph += (
            "    Collate --> Synth[Response Synthesizer]\n"
            "    Synth --> Eval[Output Validator]\n"
            "    Eval --> End([Final Response])\n"
            "```"
        )
        
        # Evaluation Summary
        eval_score = evaluation.get("grounding_score", 0.0) if evaluation else 0.0
        hallucination = evaluation.get("hallucination_detected", False) if evaluation else False
        eval_summary = evaluation.get("summary", "No evaluation summary available.") if evaluation else "No evaluation summary available."
        
        report_md = f"""# Supervisor Execution Report - {timestamp}

## 1. Execution Timeline
```
{timeline_str}
```

## 2. Planner Reasoning
{reasoning_str}

## 3. Streaming Progress Events
{events_table}

## 4. Selected Agents & Tools
- **Selected Agents**: `{agents_str}`
- **Selected Tools**: `{tools_str}`

## 5. Confidence Breakdown
- **Overall Confidence**: `{overall_conf:.2f}` (**{conf_level}**)
- **Component Scores**:
{breakdown_str}

## 6. Latency Breakdown
- **Total Latency**: `{total_latency_ms} ms` (`{total_latency_ms/1000.0:.3f} s`)

## 7. Execution Graph
{mermaid_graph}

## 8. Post-Execution Evaluation
- **Grounding Score**: `{eval_score:.2f}`
- **Hallucination Detected**: `{hallucination}`
- **Auditor Summary**: {eval_summary}

## 9. Final Production Status
- **Status**: {"✅ READY" if overall_conf >= 0.70 and not hallucination else "❌ NOT READY"}
"""
        
        # Write to reports/executions/
        executions_dir = Config.BASE_DIR / "reports" / "executions"
        executions_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = executions_dir / f"{timestamp}.md"
        latest_path = executions_dir / "latest.md"
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report_md)
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(report_md)
            logger.info(f"Execution report written to {filepath} and {latest_path}")
        except Exception as e:
            logger.error(f"Failed to write execution report: {e}")
            
        return report_md
