# Backlog (agent keeps this ordered; status: open | done | blocked: reason)

| # | P | Item | Acceptance test | Status |
|---|---|------|-----------------|--------|
| 1 | P1 | PFC private data: delete the "PFC Credit Policy Compendium & Lending Verticals" table and every compendium mention; remove "PFC" from hub/hero/section titles ("Power Sector & PFC Hub", "PFC Intelligence Hub") and the "PFC & REC Radar · 45+ Policies" tile. Keep PFC-NRD / "Open PFC News Radar" and PFC.NS stock data. | Harness PFC wording checks PASS | done 2026-11-04 |
| 2 | P1 | Fix mobile horizontal scroll on #research, #dhamma, #options, #backtest (600–740 px overflow). | Harness mobile overflow PASS for these | done 2026-11-04 |
| 3 | P1 | Fix mobile horizontal scroll on #hub and #radar (43–67 px). | Harness mobile overflow PASS | done 2026-11-04 |
| 4 | P2 | Show an "Data as of <date>" stamp on every data-driven section, read from the embedded snapshot metadata (no invented dates). | Stamp visible in all data sections | open |
| 5 | P2 | Load time: decompress each embedded data blob only when its section is first opened. | Desktop load time falls; no JS errors | open |
| 6 | P2 | Accessibility: every icon-only button has aria-label; visible keyboard focus; text contrast ≥ 4.5:1. | Spot-check 3 sections with Playwright | open |
| 7 | P3 | One consistent design system across sections (spacing, card, table, button styles via existing CSS tokens). | Visual review of 13 screenshots | open |
| 8 | P1 | Fake "live" prices: `tickLiveStream()` moves Nifty/stock prices by `Math.random()` every 2 s and labels them "LIVE NSE/BSE", "Real-time quotes", "Live Stream: ON"; `updateLiveClock()` prints hard-coded "03 Nov 2026" with today's clock as "(LIVE)". Breaks rule 3 (invented numbers) and contradicts the gate's "delayed, static snapshot" disclaimer. Remove the random tick; show the snapshot date; say "Live" only when a real fetch succeeded. | Offline: Nifty 50 pill value identical in two reads 10 s apart; no "(LIVE)"/"Real-time" text when no fetch succeeded; harness no worse | open |
| 9 | P1 | Mobile chrome eats the screen: at 390×844 the sticky header (nav + status rows) is ~350 px and the fixed footer ~80 px, so ~50% of the viewport never shows content. Collapse nav into one scroll row / menu and shrink footer on ≤700 px. | At 390 px, fixed/sticky header + footer height ≤ 25% of viewport; each section hero visible without scrolling | done 2026-11-04 |
| 10 | P3 | Hub copy speaks to the owner, not the visitor: "integration of your four domains" on the public hub. Reword to third person (e.g. "the four CA Money Mantra sites"). | No "your four domains" in visible text; hub screenshot reviewed | open |
