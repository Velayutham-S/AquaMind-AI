# Geographical Mapping Engine & Master Data Quality Report
Total unique villages/stations cataloged: 2328
---
## Data Quality & Missing Fields Analysis
- **Village Names (English) completeness:** 100.0%
- **Village Names (Tamil) completeness:** 0.0% (all set to NULL as Tamil translations are missing in source data)
- **Taluk mapping completeness:** 100.0% (derived from monitoring blocks/tehsils)
- **Firka mapping completeness:** 100.0% (mapped to closest block administrative unit)
- **Missing Latitude/Longitude coordinates:** 11 stations (0.5%)
- **Missing Pincodes:** 2328 (100.0% - not present in source telemetry datasets)
- **Missing LGD Codes:** 2328 (100.0% - not present in source telemetry datasets)

## Resolution Hierarchy Verification Summary
- Mapped Administrative units: District -> Taluk -> Firka -> Village
- Mapped Hydrological units: River Basin -> Watershed -> Aquifer