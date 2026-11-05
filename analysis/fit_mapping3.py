#!/usr/bin/env python3
"""Generic factorization search for the (slot, word) -> (x, y) mapping.

Coordinates available per (slot s, word w):
  board B = w//10 (0 = first-shifted = far end of chain)
  q = (w%10)//2  (PCB chip-row 0..4, 0 = OUT-side row: U629/U626 pair)
  t = (w%10)%2   (chip within pair; PCB col per traced zigzag)
  p = phase, c = channel from s (both slot orders tried)
  c decomposes as (ca 0..4, cb 0..2) with one unused channel value.

x = 40*board_pos + x_in(q,t,p,c) with optional per-board mirroring;
y = y(q,t,p,c). Enumerate structured formulas for x_in (0..39) and y (0..29),
require bijectivity, score against cap22's 26 absolute slots.
"""
import sys, itertools
sys.path.insert(0, '.')
from fit_mapping import extract

W, H = 200, 30
PCB_COL = [(0,3),(3,0),(0,3),(3,0),(0,3)]  # (q, t) -> PCB col 0 or 3

def build_expected():
    img = [[0]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if y < 4 or y >= H-4 or x < 4 or x >= W-4:
                img[y][x] = 2
    for y in range(8, 22):
        for x in range(50, 150):
            img[y][x] = 1
    return img

EXPECTED = build_expected()

def get_slots_abs():
    wins = extract(22, "04:31:50")
    pi = next(i for i, w in enumerate(wins) if w["kind"] == "preamble")
    out = []
    for i, w in enumerate(wins):
        if w["kind"] != "slot": continue
        idx = (i - pi - 1) if i > pi else (128 - (pi - i))
        out.append((idx % 128, w["on"]))
    return out

# --- factor value extractors -------------------------------------------------
# For each (q,t,p,c) produce factor dict; c handled per candidate (ca,cb,unused).

def gen_formulas(kind):
    """Yield (name, func(f)->int, size) formulas. f = dict with keys
    q,t,p,ca,cb and derived pa(0..3),pb(0..1)."""
    F = []
    if kind == "x":
        # x_in in 0..39; factors multiplying to 40: (5,8),(8,5),(5,4,2),(2,4,5)...
        combos = [
            ("8q+p",      lambda f: 8*f['q'] + f['p'],            True),
            ("8q+7-p",    lambda f: 8*f['q'] + 7 - f['p'],        True),
            ("8(4-q)+p",  lambda f: 8*(4-f['q']) + f['p'],        True),
            ("8(4-q)+7-p",lambda f: 8*(4-f['q']) + 7 - f['p'],    True),
            ("q+5p",      lambda f: f['q'] + 5*f['p'],            True),
            ("q+5(7-p)",  lambda f: f['q'] + 5*(7-f['p']),        True),
            ("4-q+5p",    lambda f: 4-f['q'] + 5*f['p'],          True),
            ("5p+ca... x=8ca+p", lambda f: 8*f['ca'] + f['p'],    False),
            ("8(4-ca)+p", lambda f: 8*(4-f['ca']) + f['p'],       False),
            ("8ca+7-p",   lambda f: 8*f['ca'] + 7-f['p'],         False),
            ("5p+ca",     lambda f: 5*f['p'] + f['ca'],           False),
            ("5p+4-ca",   lambda f: 5*f['p'] + 4-f['ca'],         False),
            ("5(7-p)+ca", lambda f: 5*(7-f['p']) + f['ca'],       False),
            ("ca+5p",     lambda f: f['ca'] + 5*f['p'],           False),
            ("20t+5pa+ca",lambda f: 20*f['t'] + 5*f['pa'] + f['ca'], False),
            ("20t+ca*4+pa", lambda f: 20*f['t'] + 4*f['ca'] + f['pa'], False),
            ("2(ca+5pa... x=2*(4*q...)", lambda f: 2*(f['q'] + 5*f['pa']) + f['t'], True),
            ("t+2(8q... ", lambda f: f['t'] + 2*(f['pa'] + 4*f['q']), True),
        ]
        F = combos
    else:
        # y in 0..29; factorizations 30 = 6*5 = 2*15 = 2*3*5 = 3*10 ...
        combos = [
            ("6q+3t+cb",   lambda f: 6*f['q'] + 3*f['t'] + f['cb'],  True),
            ("6q+3t+2-cb", lambda f: 6*f['q'] + 3*f['t'] + 2-f['cb'],True),
            ("6q+3(1-t)+cb", lambda f: 6*f['q'] + 3*(1-f['t']) + f['cb'], True),
            ("6(4-q)+3t+cb", lambda f: 6*(4-f['q']) + 3*f['t'] + f['cb'], True),
            ("6(4-q)+3(1-t)+2-cb", lambda f: 6*(4-f['q'])+3*(1-f['t'])+2-f['cb'], True),
            ("6q+t+2cb",   lambda f: 6*f['q'] + f['t'] + 2*f['cb'],  True),
            ("q+5(3t+cb)", lambda f: f['q'] + 5*(3*f['t']+f['cb']),  True),
            ("q+5(t+2cb)", lambda f: f['q'] + 5*(f['t']+2*f['cb']),  True),
            ("15t+3q+cb",  lambda f: 15*f['t'] + 3*f['q'] + f['cb'], True),
            ("15t+3(4-q)+cb", lambda f: 15*f['t'] + 3*(4-f['q']) + f['cb'], True),
            ("15t+q+5cb",  lambda f: 15*f['t'] + f['q'] + 5*f['cb'], True),
            ("15t+14-(3q+cb)", lambda f: 15*f['t'] + 14-(3*f['q']+f['cb']), True),
            ("15(1-t)+3q+cb", lambda f: 15*(1-f['t']) + 3*f['q'] + f['cb'], True),
            ("15t+cw... y=15t+c14", lambda f: 15*f['t'] + f['c14'],  True),
            ("15(1-t)+c14", lambda f: 15*(1-f['t']) + f['c14'],      True),
            ("15t+14-c14", lambda f: 15*f['t'] + 14 - f['c14'],      True),
            ("2c14+t",     lambda f: 2*f['c14'] + f['t'],            True),
            ("2(14-c14)+1-t", lambda f: 2*(14-f['c14']) + 1-f['t'],  True),
            ("6q+pb*3+cb", lambda f: 6*f['q'] + 3*f['pb'] + f['cb'], True),
            ("6q+cb*2+pb", lambda f: 6*f['q'] + 2*f['cb'] + f['pb'], True),
        ]
        F = combos
    return F

def main():
    slots_abs = get_slots_abs()
    xF = gen_formulas("x")
    yF = gen_formulas("y")
    results = []
    tried = 0
    for s_mode in (0, 1):            # s = 16p+c  vs  s = 8c+p
      for p_rev in (0, 1):
        for c_rev in (0, 1):
          for unused in (0, 15):
            for ca_mode in (0, 1):   # c' -> (ca,cb): 3ca+cb vs ca+5cb
              # precompute factor dicts per (s,w)
              def factors(s, w):
                  if s_mode == 0: p, c = s // 16, s % 16
                  else:           p, c = s % 8, s // 8
                  if p_rev: p = 7 - p
                  if c_rev: c = 15 - c
                  if c == unused: return None
                  cc = c - 1 if c > unused else c
                  if ca_mode == 0: ca, cb = cc // 3, cc % 3
                  else:            ca, cb = cc % 5, cc // 5
                  return {'q': (w % 10)//2, 't': (w % 10) % 2, 'p': p,
                          'pa': p >> 1, 'pb': p & 1,
                          'ca': ca, 'cb': cb, 'c14': cc}
              for xn, xf, _ in xF:
                for yn, yf, _ in yF:
                  for brev in (0, 1):      # board order
                    for mirror in (0, 1, 2):  # 0 none, 1 odd boards, 2 even
                      tried += 1
                      bad = 0
                      seen = set()
                      ok = True
                      for s, on in slots_abs:
                          for w in range(50):
                              f = factors(s, w)
                              lit = w in on
                              if f is None:
                                  if lit: bad += 1
                                  continue
                              try:
                                  xi = xf(f); y = yf(f)
                              except Exception:
                                  ok = False; break
                              if not (0 <= xi < 40 and 0 <= y < 30):
                                  ok = False; break
                              b = w // 10
                              bpos = (4 - b) if brev else b
                              if (mirror == 1 and (bpos & 1)) or (mirror == 2 and not (bpos & 1)):
                                  xi = 39 - xi
                              x = bpos * 40 + xi
                              e = EXPECTED[y][x]
                              if e == 2 and not lit: bad += 1
                              elif e == 0 and lit: bad += 1
                              if bad > 6: break
                          if not ok or bad > 6: break
                      if ok and bad <= 6:
                          results.append((bad, s_mode, p_rev, c_rev, unused,
                                          ca_mode, xn, yn, brev, mirror))
    results.sort(key=lambda r: r[0])
    print(f"tried {tried}, hits: {len(results)}")
    for r in results[:25]:
        print(f"  bad={r[0]} smode={r[1]} prev={r[2]} crev={r[3]} unused={r[4]} "
              f"camode={r[5]} x=[{r[6]}] y=[{r[7]}] brev={r[8]} mir={r[9]}")

if __name__ == "__main__":
    main()
