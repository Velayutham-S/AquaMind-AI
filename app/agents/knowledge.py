from app.agents.state import AgentState
from app.embeddings.vector_store import VectorStoreManager
from app.embeddings.reranker import RerankerManager
from app.logging_config import logger

class KnowledgeAgent:
    # Source priority weights (added to reranker score for final context ranking)
    SOURCE_PRIORITIES = {
        "Resource Assessment": 0.20,
        "Regulations & Policy": 0.15,
        "Guidelines & Policy": 0.15,
        "Artificial Recharge": 0.10,
        "Modelling & Simulation": 0.10,
        "Aquifer Management": 0.05,
        "Year Book": 0.05,
        "FAQ": 0.0,
        "General Science": -0.10
    }

    @staticmethod
    def process(state: AgentState) -> dict:
        """Knowledge node that performs hybrid RAG search, Cross-Encoder reranking, and source-prioritization."""
        query = state["query"]
        loc = state.get("resolved_location")
        
        logger.info(f"KnowledgeAgent executing RAG search for: '{query}'. Location context: {loc}")
        
        # 1. Hybrid Search (FAISS Dense + BM25 Sparse)
        vstore = VectorStoreManager()
        
        try:
            from app.embeddings.bm25 import BM25Manager
            bm25_searcher = BM25Manager.get_instance()
        except Exception as e:
            logger.error(f"Failed to load BM25 Manager: {e}")
            bm25_searcher = None

        filter_dict = {"district": loc} if loc else None
        
        # Dense retrieval
        dense_candidates = vstore.similarity_search(query, k=15, filter_dict=filter_dict)
        if not dense_candidates and filter_dict:
            dense_candidates = vstore.similarity_search(query, k=15)
            
        # Sparse retrieval
        sparse_candidates = []
        if bm25_searcher:
            sparse_candidates = bm25_searcher.search(query, k=15, filter_dict=filter_dict)
            if not sparse_candidates and filter_dict:
                sparse_candidates = bm25_searcher.search(query, k=15)
                
        # Reciprocal Rank Fusion (RRF)
        def rrf_fuse(dense_res, sparse_res, k=60):
            rrf_scores = {}
            def get_key(r):
                # Unique key for RRF deduplication
                meta = r.get("metadata", {})
                return (r.get("text", ""), meta.get("document_id", ""), meta.get("page_number", ""))
            
            for rank, r in enumerate(dense_res):
                key = get_key(r)
                rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            for rank, r in enumerate(sparse_res):
                key = get_key(r)
                rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
                
            seen_keys = set()
            fused = []
            for r in dense_res + sparse_res:
                key = get_key(r)
                if key not in seen_keys:
                    seen_keys.add(key)
                    r_copy = dict(r)
                    r_copy["rrf_score"] = rrf_scores[key]
                    fused.append(r_copy)
            fused.sort(key=lambda x: x["rrf_score"], reverse=True)
            return fused

        candidates = rrf_fuse(dense_candidates, sparse_candidates)

        # 2. Cross-Encoder Reranking
        # This sorts by semantic relevance to query
        reranked = RerankerManager.rerank(query, candidates, top_k=8)

        # 3. Source Ranking Adjustment
        for chunk in reranked:
            category = chunk["metadata"].get("category", "General Science")
            priority_bonus = KnowledgeAgent.SOURCE_PRIORITIES.get(category, 0.0)
            
            # Combine scores: rerank_score (typically ranges from -10 to +10, or normalized logits)
            # and priority bonus. Let's adjust scale accordingly
            orig_score = chunk.get("rerank_score", chunk.get("score", 0.0))
            chunk["final_score"] = orig_score + (priority_bonus * 5.0) # Scale priority to match logit influence
            chunk["priority_bonus"] = priority_bonus

        # Re-sort based on adjusted final score
        final_ranked = sorted(reranked, key=lambda x: x["final_score"], reverse=True)
        top_chunks = final_ranked[:5]

        # Extract context blocks and citation objects
        context_knowledge = []
        citations = []
        
        for idx, chunk in enumerate(top_chunks):
            meta = chunk["metadata"]
            doc_name = meta.get("document_name", "Unknown Document")
            page_num = meta.get("page_number", "N/A")
            source = meta.get("source", "CGWB")
            
            context_knowledge.append({
                "text": chunk["text"],
                "document_name": doc_name,
                "page_number": page_num,
                "source": source,
                "category": meta.get("category"),
                "score": chunk.get("final_score")
            })
            
            citations.append({
                "citation_id": idx + 1,
                "document_name": doc_name,
                "page_number": page_num,
                "source": source,
                "text_snippet": chunk["text"][:200] + "..."
            })

        logger.info(f"RAG search complete. Retrieved {len(top_chunks)} chunks for context.")

        history = list(state.get("routing_history", []))
        history.append("knowledge")

        # Determine next node in routing list
        routing_plan = ["recommendation", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break

        return {
            "context_knowledge": context_knowledge,
            "citations": citations,
            "routing_history": history,
            "current_node": next_node
        }
