import json
import os
from typing import List, Dict, Any, Optional
from app.config import Config
from app.logging_config import logger
from app.embeddings.vector_store import VectorStoreManager
from app.embeddings.bm25 import BM25Manager

class RetrievalOrchestrator:
    @staticmethod
    def retrieve_hybrid(queries: List[str], filter_dict: Optional[dict] = None, k: int = 15) -> Dict[str, List[Dict[str, Any]]]:
        """Performs hybrid dense and sparse retrieval across multiple queries and deduplicates them."""
        vstore = VectorStoreManager()
        
        try:
            bm25_searcher = BM25Manager.get_instance()
        except Exception as e:
            logger.error(f"Failed to load BM25 Manager: {e}")
            bm25_searcher = None
            
        dense_results = []
        sparse_results = []
        
        # Deduplication structures
        seen_dense = set()
        seen_sparse = set()
        
        for q in queries:
            # Dense similarity search
            dense_candidates = vstore.similarity_search(q, k=k, filter_dict=filter_dict)
            for c in dense_candidates:
                key = (c["text"], c["metadata"].get("document_id"), c["metadata"].get("page_number"))
                if key not in seen_dense:
                    seen_dense.add(key)
                    dense_results.append(c)
            # Sparse keyword search
            if bm25_searcher:
                sparse_candidates = bm25_searcher.search(q, k=k, filter_dict=filter_dict)
                for c in sparse_candidates:
                    key = (c["text"], c["metadata"].get("document_id"), c["metadata"].get("page_number"))
                    if key not in seen_sparse:
                        seen_sparse.add(key)
                        sparse_results.append(c)
                        
        return {
            "dense": dense_results,
            "sparse": sparse_results
        }

    @staticmethod
    def lookup_knowledge_graph(location_name: Optional[str]) -> List[Dict[str, Any]]:
        """Searches data/knowledge_graph.json to extract regional administrative and hydrological cross-links."""
        if not location_name:
            return []
            
        graph_path = Config.BASE_DIR / "data" / "knowledge_graph.json"
        if not graph_path.exists():
            logger.warning("Knowledge Graph json file not found.")
            return []
            
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                graph = json.load(f)
            
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])
            
            # Find target node
            target_node = None
            loc_upper = location_name.upper()
            for n in nodes:
                if n["name"].upper() == loc_upper:
                    target_node = n
                    break
                    
            if not target_node:
                return []
                
            target_id = target_node["id"]
            related_links = []
            
            # Find incoming and outgoing edges
            for e in edges:
                if e["source"] == target_id:
                    target_details = next((n for n in nodes if n["id"] == e["target"]), None)
                    if target_details:
                        related_links.append({
                            "relationship": e["type"],
                            "node_name": target_details["name"],
                            "node_type": target_details["type"],
                            "direction": "outgoing"
                        })
                elif e["target"] == target_id:
                    source_details = next((n for n in nodes if n["id"] == e["source"]), None)
                    if source_details:
                        related_links.append({
                            "relationship": e["type"],
                            "node_name": source_details["name"],
                            "node_type": source_details["type"],
                            "direction": "incoming"
                        })
                        
            logger.info(f"Knowledge Graph lookup for '{location_name}' found {len(related_links)} links.")
            
            # Wrap links as candidate lists
            candidates = []
            for link in related_links:
                text_desc = f"Knowledge Graph Link: Location '{location_name}' has relationship '{link['relationship']}' with '{link['node_name']}' ({link['node_type']})."
                candidates.append({
                    "text": text_desc,
                    "metadata": {
                        "source": "Knowledge Graph",
                        "category": "Hydrological Graph Link",
                        "document_id": "graph_lookup",
                        "page_number": 0,
                        "district": location_name,
                        "node_name": link["node_name"],
                        "node_type": link["node_type"]
                    },
                    "score": 0.85
                })
            return candidates
        except Exception as e:
            logger.error(f"Knowledge Graph lookup error: {e}")
            return []
