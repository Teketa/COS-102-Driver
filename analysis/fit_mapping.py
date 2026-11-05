#!/usr/bin/env python3
"""Fit the slot/word -> pixel mapping from the clock captures (20-22).

Content: red border 4px wide around 200x30, clock HH:MM:SS centered, 12px
digits, colons as 2x2 squares. Red line = LA channel 'B' (IDC pin 4).
LAT/GCLK probes were dead; slots are recovered from CLK activity windows
(801 edges = one slot; the merged ~1636-edge window = frame preamble).
"""
import sys
from collections import Counter
sys.path.insert(0, '.')
from capture_lib import parse_capture, rising_edges, CLK, R, G, B

CAPS = [
    (20, "04:28:41"),
    (21, "04:30:17"),
    (22, "04:31:50"),
]

def words16(bits):
    return [int("".join(map(str, bits[i:i+16])), 2) for i in range(0, len(bits)-15, 16)]

def extract(cap, tstr):
    """Return list of windows: dict(kind, red words, on-set)."""
    path = f"/home/lauge/Captures/Capture{cap}-Freq100000000-redborderclock{tstr}.csv"
    ch = parse_capture(path)
    ce = rising_edges(ch[CLK])
    red = [ch[B][i] for i in ce]
    wins = []
    start = 0
    for i in range(1, len(ce)):
        if ce[i] - ce[i-1] > 100:
            wins.append((start, i-1, ce[i]-ce[i-1]))
            start = i
    wins.append((start, len(ce)-1, 0))
    out = []
    for a, b, gap in wins:
        n = b - a + 1
        if n == 801:
            w = words16(red[a+1:b+1])
            on = frozenset(i for i, v in enumerate(w) if bin(v).count("1") >= 8)
            kind = "slot"
        elif n > 1200:
            w, on, kind = [], frozenset(), "preamble"
        else:
            w, on, kind = [], frozenset(), "partial"
        out.append({"kind": kind, "on": on, "words": w, "gap_after_us": gap/100.0})
    return out

def classify(on):
    if not on: return "0"
    if on <= {47, 48, 49}: return "L"       # only chain-end (board1/left?) drivers
    if on <= {0, 1, 2}: return "R"          # only chain-start (board5/right?) drivers
    if len(on) >= 45: return "F"            # full row
    return "D"                              # dense/mixed

def main():
    data = {}
    for cap, tstr in CAPS:
        wins = extract(cap, tstr)
        data[cap] = wins
        cls = "".join(classify(w["on"]) if w["kind"] == "slot" else
                      ("|" if w["kind"] == "preamble" else "~") for w in wins)
        print(f"cap{cap}: {cls}")
        # absolute anchor: slot after preamble = slot 0
        if "|" in cls:
            k = cls.index("|")
            print(f"   preamble at window {k}; windows {k+1}.. are slots 0..")
    # Dump ON-sets for the dense slots of cap22 with absolute indices
    wins = data[22]
    pi = next(i for i, w in enumerate(wins) if w["kind"] == "preamble")
    print("\ncap22 absolute slots:")
    for i, w in enumerate(wins):
        if w["kind"] != "slot": continue
        s = i - pi - 1 if i > pi else None   # absolute for post-preamble
        pre = (128 - (pi - 1 - i) - 1) if i < pi and wins[i]["kind"] == "slot" else None
        idx = s if s is not None else pre
        tag = f"s{idx:3d}" if idx is not None else "  ? "
        print(f"  {tag}: {sorted(w['on'])}")

if __name__ == "__main__":
    main()
