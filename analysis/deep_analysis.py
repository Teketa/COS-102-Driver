#!/usr/bin/env python3
"""Deep structural analysis of COS-102 captures.

Modes:
  timeline <csv> [fs]   - interleaved event timeline (GCLK bursts, addr, latches, CLK windows)
  payload <csv> [fs]    - full 800-bit payload per latch as 50x 16-bit words
  init <csv> [fs]       - exact init sequence: codes, widths, gaps, config words
  vsync <csv> [fs]      - hunt for wide LAT pulses in low-rate captures
  edges <csv> [fs]      - data-transition alignment relative to CLK edges
"""
import sys
import bisect
from collections import Counter
from capture_lib import parse_capture, decode, rising_edges, falling_edges, fmt_bits, CLK, LAT, GCLK, R, G, B


def gclk_bursts(gclk_edges, dom=8):
    bursts = []
    if not gclk_edges:
        return bursts
    start = gclk_edges[0]
    count = 1
    last = gclk_edges[0]
    for e in gclk_edges[1:]:
        if e - last > 3 * dom:
            bursts.append((start, last, count))
            start = e
            count = 1
        else:
            count += 1
        last = e
    bursts.append((start, last, count))
    return bursts


def clk_windows(clk_edges, gap=100):
    """Contiguous CLK activity windows separated by > gap samples."""
    wins = []
    start = clk_edges[0]
    n = 1
    last = clk_edges[0]
    for e in clk_edges[1:]:
        if e - last > gap:
            wins.append((start, last, n))
            start = e
            n = 1
        else:
            n += 1
        last = e
    wins.append((start, last, n))
    return wins


def mode_timeline(path, fs):
    d = decode(path)
    events = []
    for s, e, c in gclk_bursts(d.gclk_edges):
        events.append((s, f"GCLK burst start ({c} pulses, ends {e/fs*1e6:.1f}us)"))
        events.append((e, "GCLK burst end"))
    for s, v in d.addr_changes:
        events.append((s, f"ADDR -> {v}"))
    for L in d.latches:
        events.append((L.start_sample, f"LATCH code {L.code}"))
    for s, e, n in clk_windows(d.clk_edges):
        events.append((s, f"CLK window start ({n} edges, ends {e/fs*1e6:.1f}us)"))
    events.sort()
    for s, txt in events:
        print(f"{s/fs*1e6:10.2f}us  {txt}")


def words16(bits):
    return [int("".join(map(str, bits[i:i+16])), 2) for i in range(0, len(bits) - 15, 16)]


def mode_payload(path, fs):
    d = decode(path)
    for i, L in enumerate(d.latches):
        # bits shifted since previous latch end (incl. bits during LE high)
        prev_end = d.latches[i-1].clk_index_end + 1 if i > 0 else max(0, L.clk_index_end + 1 - 800)
        # take the last 800 bits before latch end (data in shift register at latch)
        lo = max(0, L.clk_index_end + 1 - 800)
        for name, bits in (("R", d.r_bits), ("G", d.g_bits), ("B", d.b_bits)):
            w = words16(bits[lo:L.clk_index_end + 1])
            print(f"latch{i:3d} code{L.code:2d} t={L.start_sample/fs*1e3:8.4f}ms {name}: " +
                  " ".join(f"{x:04x}" for x in w))
        print()


def mode_init(path, fs):
    d = decode(path)
    print(f"CLK edges total: {len(d.clk_edges)}")
    print("\n--- latch events (exact) ---")
    print("idx code  width_samp  width_ns  clk_start clk_end  gap_clks  t_us")
    prev = None
    for i, L in enumerate(d.latches):
        gap = L.clk_index_start - (prev.clk_index_end + 1) if prev else -1
        print(f"{i:3d} {L.code:4d}  {L.end_sample-L.start_sample:9d}  {(L.end_sample-L.start_sample)*1e9/fs:8.0f}"
              f"  {L.clk_index_start:8d} {L.clk_index_end:7d}  {gap:8d}  {L.start_sample/fs*1e6:9.2f}")
        prev = L

    # For command latches (code > 1): dump data words in the 800 bits before latch end
    print("\n--- data around command latches ---")
    for i, L in enumerate(d.latches):
        if L.code == 1:
            continue
        lo = max(0, L.clk_index_end + 1 - 800)
        for name, bits in (("R", d.r_bits), ("G", d.g_bits), ("B", d.b_bits)):
            w = words16(bits[lo:L.clk_index_end + 1])
            c = Counter(w)
            print(f"latch{i} code{L.code} {name}: {len(w)} words, distinct={dict(c) if len(c)<=6 else c.most_common(6)}")
        print()

    # bits between consecutive latches (to see structure of command block)
    print("--- inter-latch bit windows (first 8 latches) ---")
    for i in range(min(8, len(d.latches))):
        L = d.latches[i]
        lo = d.latches[i-1].clk_index_end + 1 if i > 0 else 0
        hi = L.clk_index_end + 1
        rb = d.r_bits[lo:hi]
        print(f"[{i}] code{L.code}: {hi-lo} bits R={fmt_bits(rb[:64])}{'...' if len(rb)>64 else ''}")


def mode_vsync(path, fs):
    chans = parse_capture(path)
    lat = chans[LAT]
    rises = rising_edges(lat)
    falls = falling_edges(lat)
    fi = 0
    widths = []
    for rs in rises:
        while fi < len(falls) and falls[fi] <= rs:
            fi += 1
        if fi >= len(falls):
            break
        widths.append((rs, falls[fi] - rs))
    wc = Counter(w for _, w in widths)
    print(f"samples: {len(lat)} ({len(lat)/fs*1e3:.1f} ms)")
    print(f"LAT pulses seen: {len(widths)}, width histogram (samples): {dict(sorted(wc.items()))}")
    wide = [(s, w) for s, w in widths if w >= 2]
    print(f"pulses >= 2 samples: {len(wide)}")
    for s, w in wide[:80]:
        print(f"  t={s/fs*1e3:9.4f} ms width={w}")
    if len(wide) > 1:
        gaps = [(wide[i+1][0] - wide[i][0]) / fs * 1e3 for i in range(len(wide) - 1)]
        print("gaps between wide pulses (ms): " + " ".join(f"{g:.3f}" for g in gaps[:40]))
    # narrow pulse spacing (data latches)
    if len(widths) > 2:
        gaps = [(widths[i+1][0] - widths[i][0]) / fs * 1e3 for i in range(min(len(widths)-1, 60))]
        print("all-pulse spacing (ms): " + " ".join(f"{g:.3f}" for g in gaps))


def mode_edges(path, fs):
    chans = parse_capture(path)
    clk, r = chans[CLK], chans[R]
    ce = rising_edges(clk)
    cf = falling_edges(clk)
    rt = rising_edges(r) + falling_edges(r)
    rt.sort()
    # for each R transition, distance to nearest CLK rising and falling edge
    dr, df = Counter(), Counter()
    for t in rt:
        i = bisect.bisect_left(ce, t)
        best_r = min([abs(t - ce[j]) for j in (i-1, i) if 0 <= j < len(ce)], default=None)
        i = bisect.bisect_left(cf, t)
        best_f = min([abs(t - cf[j]) for j in (i-1, i) if 0 <= j < len(cf)], default=None)
        if best_r is not None:
            dr[best_r] += 1
        if best_f is not None:
            df[best_f] += 1
    print(f"R transitions: {len(rt)}")
    print(f"distance to nearest CLK rise (samples): {dict(sorted(dr.items())[:8])}")
    print(f"distance to nearest CLK fall (samples): {dict(sorted(df.items())[:8])}")


MODES = {"timeline": mode_timeline, "payload": mode_payload, "init": mode_init,
         "vsync": mode_vsync, "edges": mode_edges}

if __name__ == "__main__":
    mode = sys.argv[1]
    path = sys.argv[2]
    fs = float(sys.argv[3]) if len(sys.argv) > 3 else 100e6
    MODES[mode](path, fs)
