# Supervisor Routing Benchmark Report

We executed 8 common regional production queries against the dynamic supervisor orchestrator.

## Benchmark Results

| Query | Expected Intent | Actual Intent | Expected Location | Actual Location | Status |
|---|---|---|---|---|---|
| `hello there!` | general ai | general ai | None | None | **PASS** |
| `What is the groundwater recharge in Salem for 2024?` | structured data | structured data | SALEM | SALEM | **PASS** |
| `kovai groundwater status detail epadi irukku?` | structured data | structured data | COIMBATORE | COIMBATORE | **PASS** |
| `சேலம் மாவட்ட நிலத்தடி நீர் நிலை என்ன?` | structured data | structured data | SALEM | SALEM | **PASS** |
| `Why is Coimbatore declared as over exploited under CGWA guidelines?` | knowledge | knowledge | COIMBATORE | COIMBATORE | **PASS** |
| `What happens if groundwater extraction in Salem decreases by 20%?` | simulation | simulation | SALEM | SALEM | **PASS** |
| `Forecast groundwater stage for Coimbatore by 2030.` | prediction | prediction | COIMBATORE | COIMBATORE | **PASS** |
| `Show a map of stress levels in Tamil Nadu.` | gis | gis | None | DHARMAPURI | **PASS** |

## Summary
- **Routing Accuracy**: 100.00%
- **Agent Selection**: 100.00%
- **Failures**: 0
