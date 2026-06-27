import time
from datetime import datetime
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from app.agents.state import AgentState
from app.logging_config import logger
from app.agents.llm import LLMService
from app.embeddings.reranker import RerankerManager

# Import Phase 4 helper modules
from app.agents.query_rewriter import QueryRewriter
from app.agents.multi_query_generator import MultiQueryGenerator
from app.agents.retrieval_orchestrator import RetrievalOrchestrator
from app.agents.context_ranker import ContextRanker
from app.agents.context_compressor import ContextCompressor
from app.agents.knowledge_grounding import KnowledgeGrounding
from app.agents.knowledge_citations import KnowledgeCitations
from app.agents.knowledge_confidence import KnowledgeConfidence
from app.agents.knowledge_metrics import KnowledgeMetrics
from app.agents.knowledge_report import KnowledgeAgentReport

# Import Phase 4.1 helper modules
from app.agents.metadata_filter import MetadataFilter
from app.agents.retrieval_explainer import RetrievalExplainer
from app.agents.answer_evaluator import AnswerEvaluator
from app.agents.self_reflection import SelfReflection

class KnowledgeAgent:
    METADATA = {
        "description": "Authoritative Production Knowledge Agent for RAG-based hydrologic reports, FAQs, and regulations.",
        "capabilities": ["rag", "policy", "guidelines", "faq"],
        "supported_inputs": ["state"],
        "supported_outputs": ["state_diff"]
    }

    @staticmethod
    def call_synthesize_llm(query: str, compressed_chunks: List[dict], lang: str) -> str:
        """Helper to invoke LLM for response synthesis based on grounded context sources."""
        context_block = ""
        for idx, c in enumerate(compressed_chunks):
            meta = c.get("metadata", {})
            doc_title = meta.get("title") or meta.get("document_name") or "Unknown"
            context_block += f"Source [{idx+1}] (Doc: {doc_title}, Page {meta.get('page_number')}):\n{c['text']}\n\n"
            
        system_prompt = (
            "You are the Lead Groundwater Hydrologist and Expert AI Synthesizer for AquaMind AI.\n"
            "Your task is to draft a comprehensive, authoritative, and data-driven response to the user's query.\n"
            "Adhere strictly to these parameters:\n"
            "1. Grounding: Rely only on the provided context sources. Do not make up facts or extrapolate beyond the sources.\n"
            "2. Citations: Interlace superscript bracket numbers (e.g. [1], [2]) matching the source indices when referencing facts.\n"
            "3. Formatting: Use clean markdown headers, bullet points, and tables. Avoid plain text blocks.\n"
            "4. Language: If the user query contains Tamil script or was flagged as language='ta' or language='mixed', answer in clear standard Tamil script. Otherwise, answer in English.\n"
            "5. Tone: Professional, informative, and expert-level."
        )
        
        user_content = (
            f"Query: {query}\n\n"
            f"Context Sources:\n{context_block}"
        )
        
        return LLMService.call(prompt=user_content, system_prompt=system_prompt)

    @staticmethod
    def process(state: AgentState, config: RunnableConfig = None) -> dict:
        """Process node representing the full Phase 4 Production Knowledge pipeline with Phase 4.1 enhancements."""
        metrics_tracker = KnowledgeMetrics.start_tracking()
        
        session_id = state.get("session_id", "default")
        query = state["query"]
        original_query = state.get("original_query", query)
        resolved_location = state.get("resolved_location")
        lang = state.get("language", "en")
        
        logger.info(f"KnowledgeAgent starting process for session: {session_id} | Query: '{query}'")
        
        progress_events = []
        timeline = []
        
        def emit_progress(stage: str, message: str, progress_pct: int):
            event = {
                "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "stage": stage,
                "message": message,
                "progress": progress_pct
            }
            progress_events.append(event)
            logger.info(f"[PROGRESS {progress_pct}%] {stage}: {message}")

        # 1. Query Rewrite
        emit_progress("Query Rewrite", "Optimizing user question...", 10)
        start = time.time()
        rewritten_query = QueryRewriter.rewrite(query)
        rewrite_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Query Rewrite",
            "duration_ms": int(rewrite_dur)
        })
        
        # 2. Multi Query Generation
        emit_progress("Multi Query Generation", "Expanding search queries...", 20)
        start = time.time()
        alt_queries = MultiQueryGenerator.generate(rewritten_query)
        gen_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Multi Query Generation",
            "duration_ms": int(gen_dur)
        })

        # 3. Metadata Filtering Inference
        emit_progress("Metadata Filtering", "Extracting metadata filters...", 30)
        start = time.time()
        inferred_filters = MetadataFilter.infer_filters(rewritten_query, state)
        filter_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Metadata Filtering",
            "duration_ms": int(filter_dur)
        })
        
        # 4. Hybrid Retrieval
        emit_progress("Hybrid Retrieval", "Searching Dense & Sparse indexes...", 45)
        start = time.time()
        
        hybrid_res = RetrievalOrchestrator.retrieve_hybrid(alt_queries, filter_dict=inferred_filters, k=15)
        dense_results = hybrid_res["dense"]
        sparse_results = hybrid_res["sparse"]
        
        graph_results = RetrievalOrchestrator.lookup_knowledge_graph(resolved_location)
        ret_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Hybrid Retrieval",
            "duration_ms": int(ret_dur)
        })
        
        # 5. Context Ranker (RRF & category prioritization)
        merged_candidates = ContextRanker.rank_and_merge(
            dense_results, sparse_results, graph_results
        )
        
        # Apply Metadata Filter on retrieved candidates before reranking
        filtered_candidates = MetadataFilter.filter_chunks(merged_candidates, inferred_filters)
        
        # 6. Cross Encoder Rerank
        emit_progress("Reranking", "Reranking candidate paragraphs...", 60)
        start = time.time()
        reranked_chunks = RerankerManager.rerank(rewritten_query, filtered_candidates, top_k=8)
        rerank_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Reranking",
            "duration_ms": int(rerank_dur)
        })
        
        # 7. Context Compressor
        emit_progress("Compression", "Compressing context snippets...", 70)
        start = time.time()
        compressed_chunks = ContextCompressor.compress(reranked_chunks, max_chars=4000)
        compress_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Compression",
            "duration_ms": int(compress_dur)
        })

        # 8. Retrieval Explainability
        retrieval_exps = RetrievalExplainer.explain(compressed_chunks, rewritten_query)
        
        # 9. LLM Generation
        emit_progress("Generation", "Generating answer...", 80)
        start = time.time()
        answer = KnowledgeAgent.call_synthesize_llm(rewritten_query, compressed_chunks, lang)
        gen_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Answer Generation",
            "duration_ms": int(gen_dur)
        })
        
        # 10. Grounding Verification
        grounding_data = KnowledgeGrounding.verify(answer, compressed_chunks)
        grounding_score = grounding_data.get("grounding_score", 1.0)
        
        # 11. Answer Evaluator
        emit_progress("Evaluation", "Auditing answer quality...", 90)
        eval_data = AnswerEvaluator.evaluate(query, answer, compressed_chunks, grounding_data)
        eval_score = eval_data.get("evaluation_score", 1.0)

        # 12. Self-Reflection and Retry Pipeline (conditional retry)
        reflection_attempted = False
        reflection_reason = ""
        retry_generation = False
        reflection_dur = 0.0

        if grounding_score < 0.90 or eval_score < 0.90:
            emit_progress("Self Reflection", "Triggering retry cycle...", 95)
            reflection_attempted = True
            reflection_reason = f"Grounding: {grounding_score:.2f}, Evaluation: {eval_score:.2f} below 0.90 threshold."
            
            start_ref = time.time()
            ref_query = SelfReflection.generate_reflection_query(
                rewritten_query,
                eval_data.get("missing_topics", []),
                eval_data.get("missing_entities", [])
            )
            
            ref_hybrid = RetrievalOrchestrator.retrieve_hybrid([ref_query], filter_dict=inferred_filters, k=10)
            ref_dense = ref_hybrid["dense"]
            ref_sparse = ref_hybrid["sparse"]
            ref_graph = RetrievalOrchestrator.lookup_knowledge_graph(resolved_location)
            
            ref_merged = ContextRanker.rank_and_merge(ref_dense, ref_sparse, ref_graph)
            ref_filtered = MetadataFilter.filter_chunks(ref_merged, inferred_filters)
            
            expanded_candidates = SelfReflection.merge_contexts(filtered_candidates, ref_filtered)
            
            ref_reranked = RerankerManager.rerank(ref_query, expanded_candidates, top_k=8)
            ref_compressed = ContextCompressor.compress(ref_reranked, max_chars=4000)
            
            improved_answer = KnowledgeAgent.call_synthesize_llm(rewritten_query, ref_compressed, lang)
            reflection_dur = (time.time() - start_ref) * 1000.0
            timeline.append({
                "time": datetime.utcnow().strftime("%H:%M:%S"),
                "stage": "Self Reflection Retry",
                "duration_ms": int(reflection_dur)
            })
            
            ref_grounding = KnowledgeGrounding.verify(improved_answer, ref_compressed)
            ref_eval = AnswerEvaluator.evaluate(query, improved_answer, ref_compressed, ref_grounding)
            
            retry_generation = True
            
            if ref_grounding.get("grounding_score", 1.0) < 0.90 or ref_eval.get("evaluation_score", 1.0) < 0.90:
                improved_answer = (
                    "⚠️ **CONFIDENCE WARNING**: This response could not be fully grounded or evaluated with high confidence. "
                    "Please cross-reference with primary documents.\n\n" + improved_answer
                )
                
            answer = improved_answer
            compressed_chunks = ref_compressed
            grounding_data = ref_grounding
            grounding_score = ref_grounding.get("grounding_score", 1.0)
            eval_data = ref_eval
            eval_score = ref_eval.get("evaluation_score", 1.0)
            retrieval_exps = RetrievalExplainer.explain(compressed_chunks, ref_query)

        # 13. Citation Builder
        emit_progress("Citation Building", "Compiling document citations...", 97)
        citations = KnowledgeCitations.compile_citations(answer, compressed_chunks)
        
        # 14. Confidence scaling
        confidence_data = KnowledgeConfidence.calculate(
            filtered_candidates, reranked_chunks, grounding_score
        )
        
        context_len = sum(len(c["text"]) for c in compressed_chunks)
        
        metrics = KnowledgeMetrics.stop_tracking(
            tracker=metrics_tracker,
            retrieval_dur_ms=ret_dur,
            rerank_dur_ms=rerank_dur,
            compress_dur_ms=compress_dur,
            gen_dur_ms=gen_dur,
            chunks_searched=len(filtered_candidates),
            chunks_retrieved=len(dense_results) + len(sparse_results),
            chunks_reranked=len(reranked_chunks),
            chunks_compressed=len(compressed_chunks),
            context_len=context_len,
            output_len=len(answer)
        )
        
        metrics["filtering_latency_ms"] = float(filter_dur)
        metrics["evaluation_latency_ms"] = float(timeline[-1]["duration_ms"]) if not retry_generation else float(timeline[-2]["duration_ms"])
        metrics["reflection_latency_ms"] = float(reflection_dur)
        metrics["retry_rate"] = 1.0 if retry_generation else 0.0
        metrics["reflection_success_rate"] = 1.0 if (retry_generation and grounding_score >= 0.90 and eval_score >= 0.90) else 0.0
        
        report_data = {
            "original_query": original_query,
            "rewritten_query": rewritten_query,
            "alt_queries": alt_queries,
            "timeline": timeline,
            "reranked_chunks": reranked_chunks,
            "assertions": grounding_data.get("assertions", []),
            "grounding_score": grounding_score,
            "citations": citations,
            "confidence": confidence_data,
            "metrics": metrics,
            "metadata_filters": inferred_filters,
            "retrieval_explanations": retrieval_exps,
            "evaluation_result": eval_data,
            "reflection_attempted": reflection_attempted,
            "reflection_reason": reflection_reason,
            "retry_generation": retry_generation,
            "evaluation_score": eval_score,
            "citation_quality": eval_data.get("citation_quality", "HIGH"),
            "grounding_quality": eval_data.get("grounding_quality", "HIGH")
        }
        
        KnowledgeAgentReport.generate(session_id, report_data)
        
        emit_progress("Completed", "Pipeline execution complete.", 100)
        
        history = list(state.get("routing_history", []))
        history.append("knowledge")
        
        routing_plan = ["recommendation", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break
                
        return {
            "context_knowledge": [
                {
                    "text": c["text"],
                    "document_name": c["metadata"].get("title") or c["metadata"].get("document_name") or "Unknown",
                    "page_number": c["metadata"].get("page_number", "N/A"),
                    "source": c["metadata"].get("source", "CGWB"),
                    "category": c["metadata"].get("category"),
                    "score": c.get("retrieval_score", 0.0)
                }
                for c in compressed_chunks
            ],
            "citations": citations,
            "response": answer,
            "confidence_score": confidence_data["confidence_score"],
            "confidence_reason": f"RAG search grounding complete. Score: {grounding_score:.2f} ({confidence_data['confidence_level']})",
            "evaluation": {
                "grounding_score": grounding_score,
                "hallucination_detected": grounding_data.get("hallucination_detected", False),
                "summary": f"Audit status: {confidence_data['confidence_level']}. Grounding verified."
            },
            "routing_history": history,
            "current_node": next_node,
            
            # Phase 4.1 State mappings
            "metadata_filters": inferred_filters,
            "retrieval_explanations": retrieval_exps,
            "evaluation_result": eval_data,
            "reflection_attempted": reflection_attempted,
            "reflection_reason": reflection_reason,
            "retry_generation": retry_generation,
            "evaluation_score": eval_score,
            "citation_quality": eval_data.get("citation_quality", "HIGH"),
            "grounding_quality": eval_data.get("grounding_quality", "HIGH")
        }
