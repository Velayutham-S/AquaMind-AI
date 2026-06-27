# AquaMind AI Platform Evaluation Run
Date: 2026-06-25 21:06:11
Total Benchmark Expanded: 1,000 questions
Evaluated Test Sample Size: 5
---
## Performance & Routing Summary
- **Supervisor Routing Accuracy:** 60.0%
- **Average End-to-End Latency:** 46.58 seconds
- **Average Response Confidence Score:** 0.55

## Audited Transaction Logs

| ID | Query | Expected Intent | Actual Routing | Confidence | Latency | Grounding Score | Hallucination Detected |
|---|---|---|---|---|---|---|---|
| 708 | Will the extraction stage in Kovai become critical by 2030? | prediction | supervisor -> data -> recommendation -> gis -> report -> synthesize | 0.50 | 44.61s | 0.1 | True |
| 513 | 2030-ல் Dindigul நிலத்தடி நீர் மட்டம் எப்படி இருக்கும்? | prediction | supervisor -> data -> recommendation -> gis -> report -> synthesize | 0.50 | 40.04s | 0.0 | True |
| 155 | நிலத்தடி நீர் ஒழுங்குமுறை விதிகள் என்ன? | knowledge | supervisor -> knowledge -> recommendation -> gis -> synthesize | 0.50 | 54.99s | 0.0 | True |
| 354 | Tell me about Tamil Nadu Groundwater Act water rules. | knowledge | supervisor -> knowledge -> recommendation -> gis -> synthesize | 0.50 | 44.94s | 0.0 | True |
| 26 | Show the extraction stage trend in Vellore. | data | supervisor -> data -> recommendation -> gis -> report -> synthesize | 0.75 | 48.36s | 1.0 | False |