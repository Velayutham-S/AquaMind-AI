# Self-Reflection and Retry Pipeline Report
Date: 2026-06-27 UTC

## 1. Feature Description
The `SelfReflection` workflow acts as a fallback state machine that triggers one additional RAG retrieval/generation cycle when answer quality fails target thresholds:
- Grounding Validation Score: < 0.90
- Answer Evaluation Score: < 0.90

### Workflow
1. Identify missing topics/entities (from evaluation results).
2. Generate a reflection query targeting those gaps.
3. Retrieve additional chunks (dense + sparse + graph) applying inferred metadata filters.
4. Merge and de-duplicate new chunks with the previous candidates.
5. Rerank, compress context, and generate an improved answer.
6. Re-run Grounding and Evaluation checks.
7. If the second attempt still fails threshold targets, return the answer with an inline `CONFIDENCE WARNING`.

This prevents infinite loops and guarantees robust answer quality in high-risk scenarios.

---

## 2. Test Verification Status
- **Test Suite**: [test_self_reflection.py](file:///d:/AquamindAI/tests/test_self_reflection.py)
- **Status**: ✅ **PASSED**

### Test Cases Summary
1. `test_generate_reflection_query`: Verified query construction with missing terms.
2. `test_generate_reflection_query_empty`: Verified clean pass-through if no topics/entities are missing.
3. `test_merge_contexts_deduplication`: Verified de-duplication when merging multiple RAG sources.
4. `test_retry_flow_integration`: Verified end-to-end retry cycle execution in the `KnowledgeAgent` when quality falls below 0.90, checking correct state propagation.
