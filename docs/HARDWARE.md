# ESP32-S3 → COS-102 Interface Hardware

## Level shifting: your SN74AHCT125N is the right part

The panel logic is (presumed) 5 V HC-family. The **AHCT** input threshold is TTL
(V_IH = 2.0 V), so 3.3 V ESP32 outputs drive it directly, and it re-drives at
5 V CMOS levels. Propagation ~6 ns — far faster than the 80 ns bit period.
Verdict: **use the AHCT125s you have.** Three chips give 12 buffers; you need 10.

Considered alternatives (only worth it if you rebuild the adapter later):
- 74AHCT245 / 74AHCT541: same electrical role, 8 channels in one package —
  tidier, one chip + one spare gate. No performance difference at 12.5 MHz.
- TXS0108 / TXB0104 auto-direction shifters: **avoid** — weak one-shot drivers,
  ring badly into ribbon cables.

## Gate allocation (3 × AHCT125)

Group the timing-critical set in one package to minimize skew:

| Chip | Gate | Signal | → IDC IN pin |
|---|---|---|---|
| U1 | 1 | CLK | 10 |
| U1 | 2 | Data BLUE | 2 |
| U1 | 3 | Data GREEN | 3 |
| U1 | 4 | Data RED | 4 **and 1** (pin 1 is a verified copy of the red line — bridge both pins to this output) |
| U2 | 1 | LAT | 9 |
| U2 | 2 | GCLK | 11 |
| U2 | 3 | Addr A | 8 |
| U2 | 4 | Addr B | 7 |
| U3 | 1 | Addr C | 6 |
| U3 | 2–4 | spare (tie inputs to GND) | — |

- All 1OE/2OE… enable pins → GND (always enabled).
- VCC from the **panel's 5 V** near the IDC connector, 100 nF ceramic per chip.
- 33–51 Ω series resistor on each buffer output into the ribbon (damps ringing;
  optional but cheap insurance).
- Common ground: ESP32 GND ↔ panel GND, short and thick; use the ribbon's
  ground pins too (verify which IDC pins are GND with a meter — likely 5,
  12–16).

## REQUIRED: bulk capacitor on the ESP32 supply

⚠️ **Fit a 470–1000 µF electrolytic across the ESP32's 5 V input, as close to
the board as practical**, with a 100 nF ceramic beside it.

Diagnosed on the bench: every WiFi transmission draws a burst of ~300 mA for a
few hundred microseconds. Without bulk capacitance that sags the shared 5 V
rail, and because the LED drivers' output current follows their supply, **the
whole panel visibly dims on each transmit** — a brightness pulse synchronised
to network traffic (2 s state pushes were plainly visible). The signature is
diagnostic: a *uniform* dip across the entire panel means supply sag, whereas a
timing fault flickers only the row group being scanned.

Two further mitigations, in order of effectiveness:

1. **Power the ESP32 from its own supply** (separate USB adapter), sharing only
   ground with the panel. This removes the coupling entirely and is the most
   robust option.
2. **Cap the WiFi transmit power** — the firmware defaults to 13 dBm instead of
   the full 20 dBm, roughly halving the peak draw. Adjustable at runtime with
   `wifi txpower <dBm>` (try 8 or 5 if any pulsing remains).

Keep the panel's own multi-amp 5 V supply well decoupled too; a sagging rail
under bright content dims the whole sign for the same reason.

## Measured bus speed ceiling

✅ **This panel runs stably up to ~19.5 MHz on both GCLK and the data clock**
(measured by sweeping them from the web UI; 20 MHz and above corrupts the
image). Both clocks hitting the same wall points at the shared path rather
than the driver ICs:

- the SUM2030GAS2 drivers are rated **30 MHz**,
- but every signal passes through the panel's own **SN74HC244** buffers (HC,
  not AHC — noticeably slower edges at 5 V) and a length of ribbon cable with
  substantial capacitance and no termination.

So the ceiling is board-level signal integrity. **18 MHz is the recommended
setting** — a safe margin below the limit, ~44 % faster than the OEM's
12.5 MHz, and it nearly halves the per-frame data-send time (which is what
buys frame-budget headroom). Use the *Fast preset* button in the web UI's
Advanced tab, or `oc fast` on the console, then *Keep after reboot* to persist.

If you ever want more: shorter/shielded ribbon, series termination resistors
at the driver end (33–51 Ω), or replacing the panel's HC244s with AHC/AHCT
parts would likely push the limit toward the drivers' 30 MHz rating.

## Before first power-up

1. ✅ VCC on U630 pin 20 measured: **5 V** — AHCT125 supply confirmed.
2. ✅ IDC GND pins: **12, 14, 16** (measured). Connect ESP32 GND to these.
   Pins 5, 13, 15 still unidentified — meter them before assuming anything.
3. Panel 5 V supply current capability — full-white draws many amps; bench test
   with a current-limited supply first.

## ESP32-S3 GPIO map (defaults in firmware `main/pins.h`)

| Signal | GPIO |
|---|---|
| CLK | 4 |
| Data R | 5 |
| Data G | 6 |
| Data B | 7 |
| LAT | 15 |
| GCLK | 16 |
| Addr A | 17 |
| Addr B | 18 |
| Addr C | 8 |

Chosen to avoid strapping pins (0, 3, 45, 46), USB-JTAG (19/20), and flash/PSRAM
pins (26–37). Change freely in `pins.h` if your board differs.
