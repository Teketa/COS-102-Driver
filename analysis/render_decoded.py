#!/usr/bin/env python3
"""Render decoded content rows from the clock captures using the SOLVED
mapping — the verification that produced digit slices matching the
photographed times (04:28:41 / 04:30:17 / 04:31:50).

Mapping (see docs/PROTOCOL.md §6a):
  slot s: channel c = s//8, phase p = s%8 (serpentine: odd c reverses p)
  word w: chain board b = w//10 (b4 = board 1 = leftmost), q = (w%10)//2,
          t = (w%10)%2; PCB col from traced zigzag.
  x = (4-b)*40 + (4-q)*8 + xf ;  y = (15 if PCB col0 else 0) + rf[c]
Capture slot-offsets solved: cap20 win1 = slot 16, cap21 win0 = slot 6,
cap22 anchored by its in-window preamble.
"""
import sys
sys.path.insert(0, '.')
from fit_mapping import extract

PCB = {0: (0, 3), 1: (3, 0), 2: (0, 3), 3: (3, 0), 4: (0, 3)}

def abs_slots(cap, tstr, first_abs):
    wins = extract(cap, tstr)
    if cap == 22:
        pi = next(i for i, w in enumerate(wins) if w["kind"] == "preamble")
        out = {}
        for i, w in enumerate(wins):
            if w["kind"] != "slot": continue
            idx = (i - pi - 1) if i > pi else (128 - (pi - i)) - 128
            out[idx % 128] = w["on"]
        return out
    return {first_abs + i: w["on"] for i, w in enumerate(wins) if w["kind"] == "slot"}

def render_channel(slots, c):
    rows = {0: [" "] * 200, 3: [" "] * 200}
    for p in range(8):
        s = 8 * c + p
        if s not in slots: continue
        on = slots[s]
        xf = (7 - p) if (c & 1) else p
        for w in range(50):
            b, l = w // 10, w % 10
            q, t = l // 2, l % 2
            x = (4 - b) * 40 + (4 - q) * 8 + xf
            rows[PCB[q][t]][x] = "#" if w in on else "."
    return rows

def main():
    for cap, tstr, off in [(20, "04:28:41", 15), (21, "04:30:17", 6), (22, "04:31:50", 0)]:
        slots = abs_slots(cap, tstr, off)
        print(f"=== cap{cap} ({tstr}) — decoded channel rows")
        for c in range(16):
            r = render_channel(slots, c)
            for pcb in (0, 3):
                line = "".join(r[pcb])
                if line.strip(" "):
                    print(f"  c{c:2d} pcb{pcb}: {line}")
        print()

if __name__ == "__main__":
    main()
