# 2.34.1

Consolidates the installed LG display implementation with the published integration. Preserves existing configuration entries, views and entity identifiers. Includes native bridge reuse, capture recovery and on-demand camera selection, improved web transport timing and platform diagnostics. Retains published startup, source-switching, HDMI fallback and offline lifecycle regressions. Display app 1.22.5 uses Display Studio 1.5.0.

Validation: 878 Python tests pass on Home Assistant 2025.3.4 and 2026.9.4, and in an isolated 2026.10.4 container. 322 Chromium/WebKit tests pass. Eight saved layout documents containing 104 views pass the new Studio validator. All 19 saved settings hashes and all installed component source hashes remain unchanged. Physical device actions were not repeated for this repository consolidation.
