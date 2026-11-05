# Delta COS-102 LED Sign — Decoded Control Protocol

Decoded from logic-analyzer captures (gusmanb V6.0 / Pico 2, 100 MS/s) of the
original controller driving board 1's IDC IN connector. This supersedes the
earlier `COS-102_control_reference.md` where they differ.

Status markers: ✅ measured/confirmed · ⚠️ inferred, high confidence · ❓ open.

## 1. Electrical interface (IDC IN, board 1)

| IDC pin | Signal | Notes |
|---|---|---|
| 1 | **Data RED (copy)** | ✅ Bit-exact copy of pin 4. Drive with the same signal. |
| 2 | **Data BLUE** | ✅ measured (Capture34, blue content) — chain → U602 |
| 3 | **Data GREEN** | ✅ measured (Capture35) — chain → U601 |
| 4 | **Data RED** | ✅ measured (Capture33, red content) — chain → U600 |
| 6 | Addr C (MSB) | ✅ |
| 7 | Addr B | ✅ |
| 8 | Addr A (LSB) | ✅ |
| 9 | LAT (LE) | ✅ |
| 10 | CLK (DCLK) | ✅ |
| 11 | GCLK | ✅ |
| 12, 14, 16 | GND | ✅ measured |
| 5, 13, 15 | ❓ unknown — check with meter before assuming |

✅ Logic level **5 V** (measured on U630 pin 20, control board disconnected).

## 2. Driver architecture (SUM2030GAS2)

✅ The captures prove this is an **SRAM-based S-PWM driver, MBI5153/ICN2053 class**:
data loading (CLK/LAT/data) and display scanning (GCLK/address) run completely
**asynchronously** — latch timing drifts freely through the scan timing, and data
written while GCLK is stopped (boot) is displayed later.

Each driver: 16 outputs, internal SRAM holding 16-bit grayscale per output per
scan row, internal PWM counter clocked by GCLK. 50 drivers per color line
chained across the 5 boards (10/board), 16 bits each → **800-bit shift chain per
color**.

## 3. Latch codes (LE pulse width in CLK rising edges)

| Code | Function | Evidence |
|---|---|---|
| 1 (or 0) | Data latch — writes one 800-bit shift into SRAM | ✅ steady state; boot captures show LAT pulsed in CLK-idle (0 edges) also works |
| 3 | **Vsync / frame swap** | ✅ opens every frame preamble, every 16.73 ms |
| 14 | Pre-active (precedes each config write) | ✅ |
| 10 | Write config register A — payload `0x03EA` broadcast on R, G, B | ✅ every frame |
| 8 | Write config register B — payload per color: R=`0xD893` G=`0x3493` B=`0xF393` (⚠️ current gain / white balance) | ✅ every frame |
| 4 | Write config register (boot only) — payload `0x03EA` broadcast | ✅ Capture5, earliest boot stage |

Config writes: shift 800 bits (the 16-bit register value repeated ×50 so every
driver in the chain gets it), then assert LE for the code's number of CLK edges.
The final 16 bits before the latch land in each driver's shift register.

❓ Register bit-field meanings unknown (no full datasheet). Not needed for
operation — replay the captured values.

## 4. Frame structure (data side) — 59.77 Hz

Measured frame period **16.7298 ms**. Latch slot = **126.19 µs**. Data shifts at
**12.5 MHz** (original controller's choice; drivers rated ≤30 MHz).

```
per frame:
  128 × data latch:            800 bits per color @12.5MHz (64.1 µs)
                               + LAT (1 CLK edge wide), every 126.19 µs slot
  ~3.5 slots CLK-quiet (442 µs)
  VSYNC: isolated ~4-clock CLK burst, LE high across 3 edges
  +0.4 µs: code 14 (LE across 14 edges, CLK running)
  800 bits = 0x03EA ×50  → code 10 latch
  +0.4 µs: code 14
  800 bits = gains ×50   → code 8 latch
  1 slot gap → first data latch of next frame
```

✅ **Pointer semantics — SOLVED on hardware (2026-07-26):**
- **Vsync resets the SRAM write pointer.** Config-write commands **advance**
  it. The OEM sends 127 data latches because its per-frame config rewrite
  consumes pointer step(s).
- **Config registers are sticky** — per-frame rewrite is unnecessary. The
  replacement controller writes config once at boot and then runs
  **vsync-only frames with all 128 data latches**: fully stable.
- **GCLK must be stopped around vsync** (chaotic row alignment otherwise),
  and the stop must be **aligned to the scan-cycle boundary** (after phase 7);
  pausing mid-cycle randomizes the frame's row alignment.
- ✅ **The address lines must rest at 0 during the vsync/preamble.** Captures
  17/18/19 all show the OEM stepping the address 7 → 0 *before* the vsync and
  holding 0 for the whole preamble. Resting on phase 7 (the natural end of a
  scan cycle) leaves the panel in a different scan state at frame swap and
  displaces rows — visible as pixels jittering vertically with colour fringing.

✅ The **entire preamble happens while GCLK is stopped** (~174 µs quiet window).
The display side pauses for it; first GCLK burst after the boundary is 1044
pulses instead of 1041, then back to normal.

✅ Data launched on CLK rising edge (~15 ns after); drivers sample on the rising
edge. SPI mode-0 style shifting (data stable before rising edge) is correct.

## 5. Display scan (GCLK + address) — free-running

```
repeat forever (per scan row, 86.24 µs):
  1041 GCLK pulses @ 12.5 MHz (83.28 µs)
  ~3.0 µs GCLK quiet:  ~1.3 µs after burst end → address advances (0..7 cyclic)
                       ~1.75 µs later → next burst
```

✅ 1041 pulses/burst, constant across all captures. Scan cycle = 8 × 86.24 µs =
690 µs (~1450 Hz). Not synchronized to the data side or the frame rate — the
drivers' internal PWM counters track GCLK; the external address lines select the
row FETs via the HC138.

⚠️ 1041 ≈ 1024 + 17 suggests a 1024-count grayscale section per row per scan
plus overhead clocks; S-PWM accumulates full depth over multiple scan cycles.
Not needed to operate — replay 1041.

## 6. Data content model

✅ Each 800-bit shift = **fifty 16-bit grayscale words**, one per driver, MSB
shifted first. The word vocabulary in captures is tiny (0x0000, 0x0002, 0xFDDF,
…) with dense values repeating at scattered chain positions — conclusive for
per-channel grayscale words, not per-pixel bitmaps.

⚠️ Frame fill model: 128 SRAM positions per driver (16 channels × 8 scan rows),
one position per data latch, 128 latches per frame = full rewrite. The write
pointer presumably resets at vsync. Which latch index maps to which (row,
channel) is undetermined — resolved easily with the ESP32 discovery tests.

✅ **Geometry: 40 × 30 populated LEDs per board** (recounted). The electronics
address 40×32 (160 outputs/color × 8 scan phases = 1280 slots vs 1200 LEDs):
a de-populated 40×32 design, 2 logical rows without LEDs. Whole sign =
**200 × 30 visible**, framebuffer 200 × 32 logical. Candidate explanation for
the constant filler words (e.g. runs of 0x0002) seen in content captures.

## 6a. Pixel mapping — SOLVED

✅ Fitted offline from Captures 20–22 (known content: 4px red border + centered
HH:MM:SS clock) and verified: borders render as exact solid rows/4px columns,
and the shared hour digits render pixel-identically across captures while
minute/second regions differ. Cascade slice per board proven by the IN/OUT
captures (exact 160-clock delay).

```
slot s (0..127):  channel c = s/8,  phase p = s%8
word w (0..49):   chain board b = w/10   (b=4 -> board 1 = leftmost, at the
                  controller end; b=0 -> board 5, rightmost)
                  local l = w%10, chip-row q = l/2 (0 = OUT-side PCB row),
                  chip-in-pair t = l%2 -> PCB column via traced zigzag
                  [(0,3),(3,0),(0,3),(3,0),(0,3)]

x = (4-b)*40 + (4-q)*8 + xf     xf = p (even channels), 7-p (odd channels)
y = half*15 + rf[c]             PCB-col-3 chip = rows 0..14 ("top" half),
                                PCB-col-0 chip = rows 15..29
```

- Each chip drives an 8-column × **16-row** block: chip-row q = 8-column group
  (reversed), phase = column within group (serpentine by channel parity),
  channel = row. The two chips of a pair are **16 rows apart** (col-3 chip =
  rows 0–15, col-0 chip = rows 16–31); **rows 30/31 are the unpopulated ones**
  (= the 30-vs-32 de-population, 2 rows × 40 cols × 5 boards ✓).
- Row table **measured on hardware (full channel walk)**: even channels →
  row `8 + c/2`, odd channels → row `(c-1)/2`, i.e.
  rf = {8,0,9,1,10,2,11,3,12,4,13,5,14,6,15,7}; bottom row = top + 16.
  Channels 12/14 have no bottom partner (rows 30/31). Orientation confirmed:
  no mirror, no flip (border test).
- Scan is effectively a **column mux**: each phase enables every-8th column
  via the HC138/FETs; driver channels are rows.

❓ Grayscale bit order within the word (MSB-first assumed; content captures
only exercise full-on/off) — confirm with a gradient once running.

## 7. Open questions

1. ❓ Complete the rf[] channel-row table (a few channels unobserved) + global
   mirror_x/flip_y + unused-channel index. → `map rf` / `map set` on hardware,
   or captures covering slots 48–119 of the clock screen.
2. ❓ Word bit order (MSB vs LSB first as grayscale value). → Gradient test.
3. ❓ Is stopping GCLK during vsync/config *required*? → Try with it running.
4. ❓ Is the per-frame config rewrite required, or is boot-time enough? →
   `preamble off` + `auto`.
5. ✅ ~~127 vs 128 latches~~ solved: pointer free-runs, one preamble command
   counts, 127 data latches keep alignment (§4).

Resolved: VCC = 5 V ✅; IDC GND = 12/14/16 ✅; 30 rows = de-populated 40×32,
one unused channel per chip per phase ✅; pin 1 = RED copy ✅; colors
B/G/R on pins 2/3/4 ✅; cascade = 160 clk/board ✅; pixel mapping ✅ (§6a).

## 8. Measured constants (replay reference)

| Parameter | Value |
|---|---|
| CLK / GCLK frequency | 12.5 MHz (80 ns) |
| Bits per shift per color | 800 (50 × 16-bit words) |
| Data latch slot | 126.19 µs |
| Data latches per frame | 127 (+1 pointer step consumed by a preamble command; pointer free-runs mod 128, no vsync reset) |
| Frame period / rate | 16.7298 ms / 59.77 Hz |
| GCLK pulses per burst | 1041 (1044 once after preamble) |
| Scan row period | 86.24 µs; addr +1 in 3.0 µs GCLK gap |
| Scan | 8 phases, binary 0→7 |
| Preamble | vsync(3) → 14 → [0x03EA×50]+latch 10 → 14 → [R 0xD893 / G 0x3493 / B 0xF393 ×50]+latch 8 |
| Boot-only extra | code 4 write, payload 0x03EA×50, GCLK+scan stopped |
| Tail before vsync | ~3.5 slots CLK-quiet (442 µs) |
