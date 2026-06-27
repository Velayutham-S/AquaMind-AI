# Retrieval Explainability Report
Date: 2026-06-27 UTC

## 1. Feature Description
The `RetrievalExplainer` maps search candidate metrics (similarity scores, BM25 keyword matching scores, and Cross-Encoder reranker score) directly to selection reasons and entity alignments. This provides deep tracing for context selection, logging:
- `similarity_score`
- `bm25_score`
- `cross_encoder_score`
- `matched_entities`
- `document`
- `reason_selected`
- `priority_category`
- `rank`

Explanations are stored under `state.retrieval_explanations` and are output to console and markdown execution report logs for debugging and telemetry.

---

## 2. Test Verification Status
- **Test Suite**: [test_retrieval_explainer.py](file:///d:/AquamindAI/tests/test_retrieval_explainer.py)
- **Status**: ✅ **PASSED**

### Test Cases Summary
1. `test_explanations_reporting`: Verified rank sorting, dense similarity log extraction, BM25 lexical score checks, Cross-Encoder rerank details, keyword entity matching, and rule-based selection reasons.
