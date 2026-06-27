import os
import json
from datetime import datetime
from pathlib import Path
from app.config import Config
from app.logging_config import logger

class KnowledgeAgentReport:
    @classmethod
    def generate(cls, session_id: str, data: dict) -> str:
        """Generates a detailed Markdown report representing the Knowledge Agent's internal retrieval, rerank, grounding, and confidence logs."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        reports_dir = Config.BASE_DIR / "reports" / "executions"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        alt_queries = "\n".join([f"- `{q}`" for q in data.get("alt_queries", [])])
        
        timeline = data.get("timeline", [])
        timeline_str = "\n↓\n".join([f"{t.get('time')} | {t.get('stage')} | {t.get('duration_ms')} ms" for t in timeline])
        
        assertions = data.get("assertions", [])
        assertion_rows = []
        for idx, a in enumerate(assertions):
            status_emoji = "✅" if a.get("status") == "supported" else ("⚠️" if a.get("status") == "neutral" else "❌")
            assertion_rows.append(f"| {idx+1} | {a.get('fact')} | {status_emoji} {a.get('status').upper()} | {a.get('source_index')} |")
        assertions_table = (
            "| ID | Asserted Statement | Grounding Status | Source Reference |\n"
            "|---|---|---|---|\n" + "\n".join(assertion_rows)
        ) if assertion_rows else "No grounding assertions compiled."
        
        citations = data.get("citations", [])
        citation_rows = []
        for c in citations:
            citation_rows.append(
                f"| [{c.get('citation_id')}] | {c.get('document_name')} | Page {c.get('page_number')} | "
                f"{c.get('section')} | {c.get('collection')} | v{c.get('version')} |"
            )
        citations_table = (
            "| Citation | Document Title | Page | Section / Category | Collection | Version |\n"
            "|---|---|---|---|---|---|\n" + "\n".join(citation_rows)
        ) if citation_rows else "No citations compiled."

        candidates = data.get("reranked_chunks", [])
        candidate_rows = []
        for idx, c in enumerate(candidates[:5]):
            meta = c.get("metadata", {})
            candidate_rows.append(
                f"| {idx+1} | {meta.get('title') or meta.get('document_name') or 'Unknown'} | Page {meta.get('page_number') or 'N/A'} | "
                f"{c.get('rrf_score', 0.0):.4f} | {c.get('rerank_score', 0.0):.4f} | {c.get('retrieval_score', 0.0):.4f} |"
            )
        candidates_table = (
            "| Rank | Document | Page | RRF Score | Rerank Score | Final Combined Score |\n"
            "|---|---|---|---|---|---|\n" + "\n".join(candidate_rows)
        ) if candidate_rows else "No candidates matched."
        
        confidence = data.get("confidence", {})
        overall_conf = confidence.get("confidence_score", 0.0)
        conf_level = confidence.get("confidence_level", "LOW")
        breakdown = confidence.get("confidence_breakdown") or {}
        breakdown_str = "\n".join([f"- **{comp.title()}**: {score:.2f}" for comp, score in breakdown.items()])
        
        metrics = data.get("metrics", {})
        metrics_table = f"""
| Metric Parameter | Value |
|---|---|
| Chunks Searched | {metrics.get('chunks_searched', 0)} |
| Chunks Retrieved | {metrics.get('chunks_retrieved', 0)} |
| Chunks Reranked | {metrics.get('chunks_reranked', 0)} |
| Chunks Compressed | {metrics.get('chunks_compressed', 0)} |
| Context Tokens | {metrics.get('context_tokens', 0)} |
| Output Tokens | {metrics.get('output_tokens', 0)} |
| Memory Delta | {metrics.get('memory_delta_mb', 0.0):.2f} MB |
| GPU Delta | {metrics.get('gpu_delta_mb', 0.0):.2f} MB |
"""
        
        # Phase 4.1 additions: Metadata Filters, Retrieval explanations, Evaluation details, Reflection
        filters = data.get("metadata_filters") or {}
        filters_str = "\n".join([f"- **{k}**: `{v}`" for k, v in filters.items()]) if filters else "*No filters applied.*"

        exps = data.get("retrieval_explanations") or []
        exp_rows = []
        for e in exps:
            entities_str = ", ".join(e.get("matched_entities", [])) or "None"
            exp_rows.append(
                f"| {e.get('rank')} | {e.get('document')} | {e.get('similarity_score', 0.0):.3f} | "
                f"{e.get('bm25_score', 0.0):.2f} | {e.get('cross_encoder_score', 0.0):.2f} | "
                f"{entities_str} | {e.get('reason_selected')} |"
            )
        explanations_table = (
            "| Rank | Document | Sim Score | BM25 Score | CE Score | Matched Entities | Selection Reason |\n"
            "|---|---|---|---|---|---|---|\n" + "\n".join(exp_rows)
        ) if exp_rows else "*No explanations compiled.*"

        eval_score = data.get("evaluation_score", 1.0)
        eval_result = data.get("evaluation_result") or {}
        missing_topics = ", ".join(eval_result.get("missing_topics", [])) or "None"
        missing_entities = ", ".join(eval_result.get("missing_entities", [])) or "None"
        contradictions = ", ".join(eval_result.get("contradictions", [])) or "None"
        
        eval_summary = f"""
- **Answer Evaluator Score**: `{eval_score:.2f}` (Quality rating: {data.get('grounding_quality', 'HIGH')})
- **Answer Completeness**: `{eval_result.get('answer_complete', True)}`
- **Citation Quality**: `{eval_result.get('citation_quality', 'HIGH')}`
- **Grounding Quality**: `{eval_result.get('grounding_quality', 'HIGH')}`
- **Identified Missing Topics**: `{missing_topics}`
- **Identified Missing Entities**: `{missing_entities}`
- **Identified Contradictions**: `{contradictions}`
"""

        reflection_attempted = data.get("reflection_attempted", False)
        reflection_reason = data.get("reflection_reason", "N/A")
        retry_generation = data.get("retry_generation", False)
        
        reflection_summary = f"""
- **Self-Reflection Attempted**: `{reflection_attempted}`
- **Reflection Trigger Reason**: `{reflection_reason}`
- **Expanded Retry Generation Executed**: `{retry_generation}`
"""

        mermaid_graph = """```mermaid
graph TD
    User([User Query]) --> Rewrite[Query Rewriter]
    Rewrite --> Multi[Multi-Query Generator]
    Multi --> Filter[Metadata Filter]
    Filter --> Retrieve[Retrieval Orchestrator]
    Retrieve --> Dense[Dense: FAISS Index]
    Retrieve --> Sparse[Sparse: BM25 Index]
    Retrieve --> Graph[Knowledge Graph Lookup]
    Dense --> Ranker[Context Ranker: RRF fusion]
    Sparse --> Ranker
    Graph --> Ranker
    Ranker --> Reranker[Cross-Encoder Reranker]
    Reranker --> Explainer[Retrieval Explainer]
    Explainer --> Compressor[Context Compressor]
    Compressor --> Ground[Grounding Auditor]
    Ground --> Evaluator[Answer Evaluator]
    Evaluator --> Generate[LLM Synthesizer]
    Generate --> Check{Quality Score >= 0.90?}
    Check -- Yes --> Citations[Citation Builder]
    Check -- No (First Try) --> Reflect[Self-Reflection Retry]
    Reflect --> Retrieve
    Check -- No (Second Try) --> Warning[Confidence Warning]
    Warning --> Citations
    Citations --> End([Final Answer])
```"""

        report_md = f"""# Knowledge Agent RAG Execution Report - {timestamp}
Session ID: `{session_id}`

## 1. Query Processing
- **Original Query**: `{data.get('original_query')}`
- **Rewritten Query**: `{data.get('rewritten_query')}`
- **Multi-Query Expansions**:
{alt_queries}

## 2. Inferred Metadata Filters
{filters_str}

## 3. Execution Timeline
```
{timeline_str}
```

## 4. Retrieval Chunk Selection Explanations
{explanations_table}

## 5. Grounding Fact Verification Audit
- **Grounding Validation Score**: `{data.get('grounding_score', 0.0):.2f}`
{assertions_table}

## 6. Answer Evaluator Quality Audit
{eval_summary}

## 7. Self-Reflection & Retry Metrics
{reflection_summary}

## 8. Citations Table
{citations_table}

## 9. Confidence Breakdown
- **Overall Confidence**: `{overall_conf:.2f}` (**{conf_level}**)
- **Component Factor Scores**:
{breakdown_str}

## 10. Metrics Telemetry
{metrics_table}

## 11. RAG Pipeline Execution Graph
{mermaid_graph}
"""
        
        file_path = reports_dir / f"knowledge_{session_id}.md"
        latest_path = reports_dir / "latest_knowledge.md"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(report_md)
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(report_md)
            logger.info(f"KnowledgeAgent report written to {file_path} and {latest_path}.")
        except Exception as e:
            logger.error(f"Failed to write KnowledgeAgent report: {e}")
            
        return report_md
