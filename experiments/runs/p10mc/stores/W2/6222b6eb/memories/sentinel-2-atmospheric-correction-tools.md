---
created: 2026-09-02T23:44:56.150415137Z
updated: 2026-09-02T23:44:56.150415137Z
weight: 1.0
last_accessed: 2026-09-02T23:45:21.460294732Z
access_count: 1
pinned: false
links: []
abstract: Sentinel-2 atmospheric correction tools - Sen2Cor (ESA, Level-1A input, commercial), SIAC_GEE (Google Earth Engine, 6S model, open-source), MAJA (CNES, physical model, a priori data)
---

## Comparison of Sen2Cor, SIAC_GEE, and MAJA

### Sen2Cor
- **Developer:** European Space Agency (ESA)
- **Algorithm:** L2A_Process algorithm combining physical models, look-up tables, and machine learning
- **Input format:** Level-1A images
- **Output format:** Level-2A product
- **Platform:** Standalone software installed locally
- **Batch processing:** One image at a time
- **Licensing:** Commercial (requires license)
- **Output control:** Limited flexibility in output format selection

### SIAC_GEE (Sentinel-2 Image Atmospheric Correction in Google Earth Engine)
- **Developer:** MarcYin
- **Algorithm:** 6S radiative transfer model (Second Simulation of a Satellite Signal in the Solar Spectrum)
- **Input format:** Level-1C images
- **Output format:** User-configurable (can select specific bands)
- **Platform:** JavaScript code running on Google Earth Engine cloud platform
- **Batch processing:** Yes, can process multiple images
- **Licensing:** Open-source, free
- **Output control:** High flexibility in output format and band selection

### MAJA (Method for Atmospheric Correction and Orthorectification)
- **Developer:** French Space Agency (CNES)
- **Algorithm:** Physical atmospheric model combined with a priori information
- **Approach:** Uses multiple observations and prior knowledge for atmospheric correction
- **Software:** MAJA software package

## Key Differences
- **Approach:** 6S uses radiative transfer model; MAJA uses physical model with a priori data; Sen2Cor uses hybrid approach with ML
- **Results:** All three produce similar overall atmospheric correction but outputs may vary in specifics
- **Selection:** Depends on specific study needs and available resources