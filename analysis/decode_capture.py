#!/usr/bin/env python3
"""Per-capture structural report: CLK rate, latch codes, gaps, address
sequencing, GCLK burst structure. Usage: decode_capture.py <capture.csv> [sample_rate_hz]
"""
import sys
from collections import Counter
from capture_lib import decode, fmt_bits

def main():
    path = sys.argv[1]
    fs = float(sys.argv[2]) if len(sys.argv) > 2 else 100e6
    d = decode(path)
    n = d.n_samples
    print(f"=== {path}")
    print(f"samples: {n}  ({n / fs * 1e3:.3f} ms @ {fs/1e6:.0f} MS/s)")
    print(f"CLK rising edges: {len(d.clk_edges)}")
    if len(d.clk_edges) > 100:
        # median CLK period over the busiest stretch
        periods = [d.clk_edges[i+1] - d.clk_edges[i] for i in range(len(d.clk_edges)-1)]
        pc = Counter(periods)
        common = pc.most_common(5)
        print(f"CLK period histogram (samples): {common}")
        med = common[0][0]
        print(f"dominant CLK period: {med} samples = {fs/med/1e6:.3f} MHz")
    print(f"GCLK rising edges: {len(d.gclk_edges)}")
    print(f"address changes: {len(d.addr_changes)}")
    seq = [v for _, v in d.addr_changes]
    print(f"address sequence: {seq[:40]}{'...' if len(seq) > 40 else ''}")

    print(f"latch events: {len(d.latches)}")
    codes = Counter(l.code for l in d.latches)
    print(f"latch code histogram: {dict(sorted(codes.items()))}")

    # per-latch detail: code, CLK-count gap since previous latch end, addr at latch
    print("\nidx  code  clkgap  addr  t_ms      RGB_equal_16b_before")
    prev_end = None
    for i, L in enumerate(d.latches):
        gap = L.clk_index_start - prev_end if prev_end is not None else -1
        prev_end = L.clk_index_end + 1
        # addr at time of latch start
        import bisect
        ai = bisect.bisect_right([s for s, _ in d.addr_changes], L.start_sample) - 1
        addr = d.addr_changes[ai][1] if ai >= 0 else (d.addr_bits[L.clk_index_start] if d.addr_bits else -1)
        if not d.addr_changes:
            addr = d.addr_bits[L.clk_index_start] if L.clk_index_start < len(d.addr_bits) else -1
        # 16 bits before the latch on each data line
        s = max(0, L.clk_index_start - 16)
        rb = fmt_bits(d.r_bits[s:L.clk_index_start])
        gb = fmt_bits(d.g_bits[s:L.clk_index_start])
        bb = fmt_bits(d.b_bits[s:L.clk_index_start])
        same = "SAME" if rb == gb == bb else "diff"
        print(f"{i:3d}  {L.code:4d}  {gap:6d}  {addr:4d}  {L.start_sample/fs*1e3:8.4f}  {same} R={rb}")

    # GCLK burst structure: gaps > 3x dominant GCLK period
    if len(d.gclk_edges) > 10:
        gp = Counter(d.gclk_edges[i+1] - d.gclk_edges[i] for i in range(len(d.gclk_edges)-1))
        dom = gp.most_common(1)[0][0]
        print(f"\nGCLK dominant period: {dom} samples = {fs/dom/1e6:.3f} MHz")
        bursts = []
        start = d.gclk_edges[0]
        count = 1
        for i in range(1, len(d.gclk_edges)):
            if d.gclk_edges[i] - d.gclk_edges[i-1] > 3 * dom:
                bursts.append((start, d.gclk_edges[i-1], count))
                start = d.gclk_edges[i]
                count = 1
            else:
                count += 1
        bursts.append((start, d.gclk_edges[-1], count))
        print(f"GCLK bursts (gap>3x period): {len(bursts)}")
        print("burst pulse counts: " + " ".join(str(c) for _, _, c in bursts[:60]) + ("..." if len(bursts) > 60 else ""))

if __name__ == "__main__":
    main()
