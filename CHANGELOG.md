# Changelog

## 2026-11-04 · baseline (set up by Claude)
- Harness baseline: PASS 66 · WARN 0 · FAIL 8 (2 wording, 6 mobile overflow). All 13 sections render, no JS errors.
- Rule change (Jitender): only PFC-NRD may be public; all other PFC data strictly private. Harness now FAILs on 7 PFC mentions + 4 internal-policy mentions.

## 2026-11-04 · daily run
- Done: #1 PFC private data/branding removed (compendium table, hub titles, policies tile; PFC-NRD kept). #2 + #3 mobile horizontal scroll fixed on hub, research, radar, backtest, options, dhamma (grid tracks minmax(0,1fr), table scroll boxes, select/tag wrap).
- Blocked: none.
- Harness: PASS 65 · FAIL 8 → PASS 73 · FAIL 0.
- Audit added: #8 (P1 random-walk "live" prices), #9 (P1 mobile header/footer cover ~50% of screen), #10 (P3 hub owner-voice copy).

## 2026-11-04 · installable app (Jitender request)
- Done: installable app for Android, iPhone/iPad, Windows and Mac (web manifest, offline service worker, icons, "Install app" button, iOS/macOS Safari steps, section shortcuts). #9 done: on ≤700 px the top bar, quick-jump and timeframe rows are one swipeable row each; footer no longer fixed; header 352 → 60 px; safe-area insets; 16 px inputs (no iOS zoom).
- Checks: Chromium installability errors none; offline reload works from cache; harness PASS 73 · FAIL 0 → PASS 73 · FAIL 0.
- Deploy note: Netlify must publish manifest.webmanifest, sw.js and icons/ next to index.html.

## 2026-11-04 · honest prices (#8)
- Done: #8 removed the random 2-second price walk; prices are now the snapshot or a quote a public source actually returned. Top bar shows "Snapshot <date>" or "Quotes HH:MM IST · <source> · may be delayed"; dot is green only after a real quote. "Live Stream"/"Real-time" labels replaced with "Auto-refresh" and "Not real-time". Sync Now reports success or "No source reachable". Phone: long hero titles wrap.
- Blocked: #11 snapshot Nifty close differs from TradingView by ~189 pts (needs new snapshot); #12 live data source (needs decision).
- Harness: PASS 73 · FAIL 0 → PASS 73 · FAIL 0. Offline: Nifty pill unchanged over 10 s. Mocked source: pill and clock update.
