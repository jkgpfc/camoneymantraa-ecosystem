# Changelog

## 2026-11-04 · baseline (set up by Claude)
- Harness baseline: PASS 66 · WARN 0 · FAIL 8 (2 wording, 6 mobile overflow). All 13 sections render, no JS errors.
- Rule change (Jitender): only PFC-NRD may be public; all other PFC data strictly private. Harness now FAILs on 7 PFC mentions + 4 internal-policy mentions.
