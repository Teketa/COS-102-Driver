#!/usr/bin/env python3
"""Brute-force the (slot, word) -> (x, y) mapping against cap22's absolute
slots, using the known content (red 4px border, clock box = don't care).

Structural model (derived from PCB trace + IN/OUT cascade measurement):
- word w: board = w//10 (w40-49 = board1); pair q=(w%10)//2 = PCB chip-row;
  side t=(w%10)%2 -> chip within pair (PCB col 0 vs 3 per traced zigzag).
- slot s -> (phase p, channel c).
- stripe q serves 6 LED rows; phase = (column-group G 0..3, row-half H 0..1);
  channel c -> (col-in-group j5 0..4, row-in-half r3 0..2), 1 of 16 unused.
- chip side -> column interleave (even/odd pair columns) or halves.
x = board*40 + <side/G/j5 arrangement>, y = stripe*6 + <H/r3 arrangement>.
"""
import sys, itertools
sys.path.insert(0, '.')
from fit_mapping import extract, CAPS

W, H = 200, 30

# --- expected content (red channel) ---
# 2 = must be ON, 0 = must be OFF, 1 = don't care (clock box + fuzz margin)
def build_expected():
    img = [[0]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if y < 4 or y >= H-4 or x < 4 or x >= W-4:
                img[y][x] = 2
    # clock box don't-care (digits 12px high, unknown font/width; be generous)
    for y in range(8, 22):
        for x in range(50, 150):
            img[y][x] = 1
    return img

EXPECTED = build_expected()

# traced chip PCB-column per (pair q, side t): 0 or 3
PCB_COL = [(0,3),(3,0),(0,3),(3,0),(0,3)]

def make_mapper(P):
    (s_mode, p_rev, c_rev, pg_mode, g_rev, h_rev,
     c_mode, j_rev, r_rev, side_mode, side_swap,
     stripe_rev, board_rev, unused_c) = P

    def loc(s, w):
        # slot -> phase, channel
        if s_mode == 0: p, c = s // 16, s % 16
        else:           p, c = s % 8, s // 8
        if p_rev: p = 7 - p
        if c_rev: c = 15 - c
        # phase -> column-group G, row-half H
        if pg_mode == 0: G, Hh = p // 2, p % 2
        else:            G, Hh = p % 4, p // 4
        if g_rev: G = 3 - G
        if h_rev: Hh = 1 - Hh
        # channel -> j5 (col in group), r3 (row in half); one channel unused
        cc = c
        if cc == unused_c: return None
        if cc > unused_c: cc -= 1
        if c_mode == 0: j5, r3 = cc // 3, cc % 3
        else:           j5, r3 = cc % 5, cc // 5
        if j_rev: j5 = 4 - j5
        if r_rev: r3 = 2 - r3
        # word -> board, stripe, side
        b = w // 10
        board = (4 - b) if board_rev else b
        q = (w % 10) // 2
        t = (w % 10) % 2
        stripe = (4 - q) if stripe_rev else q
        pcb = PCB_COL[q][t]
        side = (pcb == 3) ^ side_swap  # 0/1
        # x within board
        J = G * 5 + j5           # 0..19 column-pair / half index
        if side_mode == 0:       # chips interleave even/odd columns
            x_in = 2 * J + (1 if side else 0)
        else:                    # chips are left/right halves
            x_in = (20 if side else 0) + J
        y = stripe * 6 + Hh * 3 + r3
        x = board * 40 + x_in
        return x, y
    return loc

def score(loc, slots_abs, limit):
    """slots_abs: list of (slot_index, on_set). Return mismatches (early out)."""
    bad = 0
    for s, on in slots_abs:
        for w in range(50):
            r = loc(s, w)
            lit = w in on
            if r is None:
                if lit: bad += 1
            else:
                x, y = r
                e = EXPECTED[y][x]
                if e == 2 and not lit: bad += 1
                elif e == 0 and lit: bad += 1
            if bad > limit: return bad
    return bad

def main():
    wins = extract(22, "04:31:50")
    pi = next(i for i, w in enumerate(wins) if w["kind"] == "preamble")
    slots_abs = []
    for i, w in enumerate(wins):
        if w["kind"] != "slot": continue
        if i > pi: idx = i - pi - 1
        else: idx = 128 - (pi - i)  # window pi-1 = slot 127, pi-2 = 126, ...
        slots_abs.append((idx % 128, w["on"]))
    print(f"fitting against {len(slots_abs)} absolute slots "
          f"({sorted(s for s,_ in slots_abs)})")

    axes = [range(2)] * 13
    best = []
    total = 0
    for comb in itertools.product(*axes):
        for unused_c in (0, 15):
            P = comb + (unused_c,)
            total += 1
            loc = make_mapper(P)
            bad = score(loc, slots_abs, limit=3)
            if bad <= 3:
                best.append((bad, P))
    best.sort()
    print(f"tried {total} candidates; hits with <=3 mismatches: {len(best)}")
    for bad, P in best[:20]:
        print(f"  mismatches={bad}  params={P}")

if __name__ == "__main__":
    main()
