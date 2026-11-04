# Backlog (agent keeps this ordered; status: open | done | blocked: reason)

| # | P | Item | Acceptance test | Status |
|---|---|------|-----------------|--------|
| 1 | P1 | Remove PFC internal/branding references from visible text ("PFC Credit Policy Compendium", "Power Sector & PFC Hub", "PFC Intelligence Hub", "Open PFC News Radar", "PFC & REC Radar" label). Rename to neutral power-sector wording. Keep PFC.NS as a stock. | Harness wording checks PASS | open |
| 2 | P1 | Fix mobile horizontal scroll on #research, #dhamma, #options, #backtest (600–740 px overflow). | Harness mobile overflow PASS for these | open |
| 3 | P1 | Fix mobile horizontal scroll on #hub and #radar (43–67 px). | Harness mobile overflow PASS | open |
| 4 | P2 | Show an "Data as of <date>" stamp on every data-driven section, read from the embedded snapshot metadata (no invented dates). | Stamp visible in all data sections | open |
| 5 | P2 | Load time: decompress each embedded data blob only when its section is first opened. | Desktop load time falls; no JS errors | open |
| 6 | P2 | Accessibility: every icon-only button has aria-label; visible keyboard focus; text contrast ≥ 4.5:1. | Spot-check 3 sections with Playwright | open |
| 7 | P3 | One consistent design system across sections (spacing, card, table, button styles via existing CSS tokens). | Visual review of 13 screenshots | open |
