# LEDSIGNPART3 — Delta COS-102 LED Sign Reverse Engineering

Replacement controller for a Delta COS-102 LAAAA LED sign (5 boards, 200×32 RGB,
SUM2030GAS2 drivers) using an ESP32-S3.

- `docs/DEVELOPING.md` — **how the controller works, and how to write your own
  effects and text animations**
- `docs/PROTOCOL.md` — **the decoded protocol** (frame structure, latch codes,
  config payloads, timing). Supersedes the older control reference.
- `docs/HARDWARE.md` — level shifting (74AHCT125), wiring, GPIO map, what to
  measure before power-up.
- `analysis/` — capture decoding tools (pure Python, no deps):
  `decode_capture.py <csv>` for a structural report, `deep_analysis.py
  timeline|payload|init|vsync|edges <csv>` for deep dives. `reports/` holds
  generated reports.
- `firmware/` — PlatformIO (ESP-IDF) project: protocol replay + interactive
  discovery console + test patterns. See `firmware/README.md` for the bring-up
  and discovery workflow.

Capture files live in `~/Captures/` (gusmanb LogicAnalyzer CSV exports).
