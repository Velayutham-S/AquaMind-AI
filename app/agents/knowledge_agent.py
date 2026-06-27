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

class KnowledgeAgent:
    METADATA = {
        "description": "Authoritative Production Knowledge Agent for RAG-based hydrologic reports, FAQs, and regulations.",
        "capabilities": ["rag", "policy", "guidelines", "faq"],
        "supported_inputs": ["state"],
        "supported_outputs": ["state_diff"]
    }

    @staticmethod
    def process(state: AgentState, config: RunnableConfig = None) -> dict:
        """Process node representing the full Phase 4 Production Knowledge pipeline."""
        metrics_tracker = KnowledgeMetrics.start_tracking()
        
        session_id = state.get("session_id", "default")
        query = state["query"]
        original_query = state.get("original_query", query)
        resolved_location = state.get("resolved_location")
        lang = state.get("language", "en")
        
        logger.info(f"KnowledgeAgent starting process for session: {session_id} | Query: '{query}'")
        
        # Setup progress events list
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
        
        # 3. Hybrid Retrieval
        emit_progress("Hybrid Retrieval", "Searching Dense & Sparse indexes...", 35)
        start = time.time()
        filter_dict = {"district": resolved_location} if resolved_location else None
        
        hybrid_res = RetrievalOrchestrator.retrieve_hybrid(alt_queries, filter_dict=filter_dict, k=15)
        dense_results = hybrid_res["dense"]
        sparse_results = hybrid_res["sparse"]
        
        # Knowledge Graph Lookups
        graph_results = RetrievalOrchestrator.lookup_knowledge_graph(resolved_location)
        ret_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Hybrid Retrieval",
            "duration_ms": int(ret_dur)
        })
        
        # 4. Context Ranker (RRF & category prioritization)
        merged_candidates = ContextRanker.rank_and_merge(
            dense_results, sparse_results, graph_results
        )
        
        # 5. Cross Encoder Rerank
        emit_progress("Reranking", "Reranking candidate paragraphs...", 50)
        start = time.time()
        reranked_chunks = RerankerManager.rerank(rewritten_query, merged_candidates, top_k=8)
        rerank_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Reranking",
            "duration_ms": int(rerank_dur)
        })
        
        # 6. Context Compressor
        emit_progress("Compression", "Compressing context snippets...", 65)
        start = time.time()
        compressed_chunks = ContextCompressor.compress(reranked_chunks, max_chars=4000)
        compress_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Compression",
            "duration_ms": int(compress_dur)
        })
        
        # 7. LLM Synthesis (grounded answer generation)
        emit_progress("Generation", "Generating final answer...", 85)
        start = time.time()
        
        # Format compressed context block
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
            f"Query: {rewritten_query}\n\n"
            f"Context Sources:\n{context_block}"
        )
        
        # Call LLM
        answer = LLMService.call(prompt=user_content, system_prompt=system_prompt)
        gen_dur = (time.time() - start) * 1000.0
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Answer Generation",
            "duration_ms": int(gen_dur)
        })
        
        # 8. Grounding Verification
        emit_progress("Grounding", "Verifying response assertions...", 75)
        grounding_data = KnowledgeGrounding.verify(answer, compressed_chunks)
        grounding_score = grounding_data.get("grounding_score", 1.0)
        
        # 9. Citation Builder
        emit_progress("Citation Building", "Compiling document citations...", 95)
        citations = KnowledgeCitations.compile_citations(answer, compressed_chunks)
        
        # 10. Confidence scaling
        confidence_data = KnowledgeConfidence.calculate(
            merged_candidates, reranked_chunks, grounding_score
        )
        
        # Estimate context length
        context_len = sum(len(c["text"]) for c in compressed_chunks)
        
        # 11. Compile Telemetry metrics
        metrics = KnowledgeMetrics.stop_tracking(
            tracker=metrics_tracker,
            retrieval_dur_ms=ret_dur,
            rerank_dur_ms=rerank_dur,
            compress_dur_ms=compress_dur,
            gen_dur_ms=gen_dur,
            chunks_searched=len(merged_candidates),
            chunks_retrieved=len(dense_results) + len(sparse_results),
            chunks_reranked=len(reranked_chunks),
            chunks_compressed=len(compressed_chunks),
            context_len=context_len,
            output_len=len(answer)
        )
        
        # 12. Compile execution report
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
            "metrics": metrics
        }
        
        KnowledgeAgentReport.generate(session_id, report_data)
        
        emit_progress("Completed", "Pipeline execution complete.", 100)
        
        # 13. Determine next node routing path
        history = list(state.get("routing_history", []))
        history.append("knowledge")
        
        routing_plan = ["recommendation", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break
                
        # 14. Return updated StateGraph update dictionary
        # Keep keys matching state: response, citations, confidence_score, grounding_score
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
            "current_node": next_node
        }
