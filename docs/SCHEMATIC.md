# Level-Shifter Hat: Schematic Specification

The hat takes nine 3.3 V signals, shifts them to 5 V and drives the COS-102
ribbon. It also takes 5 V from the display PSU, filters it, and supplies both
the buffers and the ESP32. The IO names match `firmware/src/pins.h`; changing
one means changing that file.

Where this differs from `HARDWARE.md`, this file is the newer one. IDC pin 1
gets its own buffer gate instead of being bridged to pin 4, and the ESP32 now
runs from the filtered display PSU.

## 1. Overview

```
 Display PSU ─► J1 ─► fuse, TVS ─► beads ─► 47 µH + 1000 µF ─┬─► FB3 ─► buffers
                                                             └─► D2 + 470 µF ─► +5V_ESP (IO)

 IO (3.3 V, 9 signals) ─► U8/U9/U10 SN74AHCT125 ─► 33 Ω ─► P1 ─ ribbon ─► panel "IN"
```

The panel inputs are 5 V HC logic. Bus speed is 18 MHz at the recommended
setting (12.5 MHz was the OEM rate), and the panel fails at about 20 MHz.

## 2. Component list

### Signal path

| Ref | Part | Qty | Function |
|---|---|---|---|
| U8, U9, U10 | SN74AHCT125DR | 3 | Level shifters |
| P1 | HDR-IDC-2.54-2X8P | 1 | Panel ribbon header |
| R1 to R10 | 33 Ω | 10 | Series resistors on buffer outputs (33 to 51 Ω range) |
| C1, C2, C3 | 100 nF | 3 | One at pin 14 of each AHCT125 |
| C4 | 10 µF | 1 | Buffer rail |

### Power input and filter

| Ref | Part | Qty | Function |
|---|---|---|---|
| J1 | 2-pin screw terminal, 5.08 mm | 1 | 5 V and GND from the display PSU |
| F1 | 2 A time-lag fuse | 1 | Protects the hat and its wiring from the PSU's full current |
| D1 | SMBJ5.0A, unidirectional | 1 | Clamps spikes. Also blows F1 if J1 is wired backwards |
| C5 | 100 nF | 1 | High-frequency bypass at the input |
| FB1 | Ferrite bead, ≥ 3 A, ≥ 100 Ω at 100 MHz, DCR ≤ 30 mΩ | 1 | High-frequency filter, 5 V leg |
| FB2 | Same as FB1 | 1 | High-frequency filter, GND leg |
| L1 | 47 µH shielded power inductor, Isat ≥ 1.5 A, DCR ≤ 0.1 Ω | 1 | Main low-frequency filter |
| C6 | 1000 µF, ≥ 10 V, standard aluminium electrolytic | 1 | Main filter capacitor |
| C7 | 100 nF | 1 | Beside C6 |
| FB3 | Ferrite bead, ≥ 500 mA, ≥ 100 Ω at 100 MHz | 1 | Isolates the buffers from the ESP32 branch |
| D2 | Schottky, ≥ 2 A, Vf ≤ 0.4 V at 0.5 A (for example SS34) | 1 | Stops USB power reaching the panel |
| C8 | 470 µF, ≥ 10 V, aluminium electrolytic | 1 | ESP32 WiFi burst reservoir |
| C9 | 100 nF | 1 | Beside C8 |

Use ordinary aluminium electrolytics for C6 and C8, not polymer. Their ESR damps
the filter; a very low ESR raises the resonance peak.

## 3. Signal connections

Each signal runs from its IO through a buffer and a 33 Ω resistor to P1.

| Signal | IO | Buffer | In (A) | Out (Y) | Resistor | P1 pin |
|---|---|---|---|---|---|---|
| CLK | IO4 | U8 gate 1 | 2 | 3 | R1 | 10 |
| Data BLUE | IO7 | U8 gate 2 | 5 | 6 | R2 | 2 |
| Data GREEN | IO6 | U8 gate 3 | 9 | 8 | R3 | 3 |
| Data RED | IO5 | U8 gate 4 | 12 | 11 | R4 | 4 |
| LAT | IO15 | U9 gate 1 | 2 | 3 | R5 | 9 |
| GCLK | IO16 | U9 gate 2 | 5 | 6 | R6 | 11 |
| Addr A | IO17 | U9 gate 3 | 9 | 8 | R7 | 8 |
| Addr B | IO18 | U9 gate 4 | 12 | 11 | R8 | 7 |
| Addr C | IO8 | U10 gate 1 | 2 | 3 | R9 | 6 |
| Data RED copy | IO5 | U10 gate 2 | 5 | 6 | R10 | 1 |

IO5 feeds two buffer inputs, so there are nine IOs for ten outputs.

CLK and the three data lines share U8 on purpose, so they see the same delay.

## 4. Power connections

| From | Through | To |
|---|---|---|
| J1 pin 1 | F1 | +5V_P |
| J1 pin 2 | | GND_IN |
| +5V_P | D1 (cathode on +5V_P) | GND_IN |
| +5V_P | C5 | GND_IN |
| +5V_P | FB1 | +5V_L |
| GND_IN | FB2 | GND |
| +5V_L | L1 | +5V_F |
| +5V_F | C6, C7 | GND |
| +5V_F | FB3 | +5V_BUF |
| +5V_BUF | C4, C1, C2, C3 | GND |
| +5V_F | D2 (anode on +5V_F) | +5V_ESP |
| +5V_ESP | C8, C9 | GND |

IOs to the ESP32 board, besides the signals:

| Net | Goes to |
|---|---|
| +5V_ESP | The board's 5V pin, never its 3V3 pin |
| GND | The board's GND pin |

## 5. Other connections

Buffers:

- U8, U9, U10 pin 14 (VCC) → +5V_BUF. Pin 7 (GND) → GND.
- Enable pins in use → GND: pins 1, 4, 10, 13 on U8 and U9, and pins 1 and 4 on U10.
- U10 gates 3 and 4 are spare: pins 9, 10, 12, 13 → GND. Pins 8 and 11 stay open.

P1:

- Pins 12, 14, 16 → GND (measured).
- Pins 5, 13, 15 → no connection until metered.

## 6. Why the filter is built this way

**Ground.** The hat's reference is the ribbon's ground, because that is what the
panel's inputs compare against. J1's ground is a second path to the same PSU, so
the two form a loop. FB2 keeps high-frequency LED return current out of the hat,
and all of GND stays one plane. A common-mode choke was rejected: any current
that returns only through the ground leg would saturate it.

**Wire J1 to where board 1 receives its power, not at the PSU terminals.** The
panel's power cables drop voltage under load. If J1 is tapped at the PSU, that
drop drives part of the LED current through J1, the hat and the ribbon's ground
wires.

**Filter frequency.** The strongest noise should be at the scan rate, 1.45 kHz
at OEM timing, and its harmonics. The panel noise itself has not been measured.
47 µH with 1000 µF was chosen over 22 µH because 22 µH barely reduces 1.45 kHz.

Calculated filter response (47 µH with 0.1 Ω DCR, 1000 µF with 0.05 Ω ESR, not
yet tested on hardware):

| Frequency | Effect |
|---|---|
| 640 Hz | +3.7 dB, the resonance peak |
| 1.45 kHz | −9 dB |
| 11.6 kHz | −36 dB |
| 100 kHz | −55 dB |
| 1 MHz | −75 dB (the beads add more here) |

**WiFi bursts.** A 300 mA step sags the filtered rail by about 75 mV. For a
200 µs burst, the PSU sees a peak of about 280 mA. C8 helps further on the ESP32
branch, and that was not included in these figures.

**D2.** Without it, plugging in USB with the PSU off could try to power the whole
display from the USB port, if the ESP32 board's 5V pin connects to USB power. It
costs about 0.4 V, so the ESP32 board sees about 4.5 V. The buffers bypass D2 and
stay near 5 V, which they need: the AHCT125 minimum supply is 4.5 V.

**Power-up.** Connect J1 with the PSU off. Connecting to a live PSU gives about
12 A inrush and 5.5 V overshoot, which is within ratings but unnecessary.

## 7. Open question

What are IDC pins 5, 13 and 15 on the panel? Meter them against GND and +5V
before tying them to anything.

## 8. Layout notes

- Put J1 and the filter in one corner, with the buffers and P1 at the far side.
- Run +5V_P and GND_IN as short, wide copper. GND_IN must only reach J1, D1, C5
  and FB2, and the main ground plane starts after FB2.
- Keep L1 away from the signal traces.
- Place U8 to U10 and the 33 Ω resistors close to P1, resistors at the Y pins.
- Put each 100 nF right at its buffer's pin 14.
- Place C8 and C9 next to the pin that goes to the ESP32's 5V.
- C6 and C8 are tall radial parts. Check they clear the ESP32 board and its
  antenna, and keep them and L1 away from the antenna.
- Keep the ribbon no longer than the one tested; the 20 MHz ceiling comes from
  the panel's HC244s and ribbon capacitance.
- The P1 footprint has odd pins on one row and even on the other, which matches
  the panel (GND on 12, 14, 16 is one row). Confirm pin 1 against the ribbon's
  triangle mark before the first power-up.
- Use a solid ground plane under the buffers and connect all three P1 GND pins.
