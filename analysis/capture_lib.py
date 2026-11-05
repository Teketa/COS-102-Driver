"""Parser + event extraction for gusmanb LogicAnalyzer CSV exports of the
Delta COS-102 LED sign control bus.

CSV format: header "CLK,LAT,GCLK,R,G,B,Addr A,Addr B,Addr C", then one row of
0/1 per sample, no timestamps. Pure stdlib, no numpy required.
"""

from dataclasses import dataclass, field

CHANNELS = ["CLK", "LAT", "GCLK", "R", "G", "B", "ADDR_A", "ADDR_B", "ADDR_C"]
CLK, LAT, GCLK, R, G, B, ADDR_A, ADDR_B, ADDR_C = range(9)


def parse_capture(path):
    """Return list of per-channel bit lists: chans[ch][sample] in {0,1}."""
    chans = [[] for _ in CHANNELS]
    appends = [c.append for c in chans]
    with open(path) as f:
        header = f.readline().strip()
        if not header.startswith("CLK"):
            raise ValueError(f"unexpected header: {header!r}")
        for line in f:
            line = line.rstrip("\n").rstrip(",")  # some rows have trailing comma
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 9:
                continue  # truncated final row
            for i in range(9):
                appends[i](1 if parts[i] == "1" else 0)
    return chans


def rising_edges(sig):
    """Sample indices where sig goes 0 -> 1."""
    return [i for i in range(1, len(sig)) if sig[i] and not sig[i - 1]]


def falling_edges(sig):
    return [i for i in range(1, len(sig)) if not sig[i] and sig[i - 1]]


@dataclass
class LatchEvent:
    code: int              # number of CLK rising edges while LAT high
    start_sample: int      # sample index where LAT went high
    end_sample: int        # sample index where LAT went low
    clk_index_start: int   # index into clk_edges of first CLK edge with LAT high
    clk_index_end: int     # index of last CLK edge with LAT high (inclusive)


@dataclass
class Decoded:
    path: str
    n_samples: int = 0
    clk_edges: list = field(default_factory=list)   # sample idx of CLK rising
    # bits sampled on each CLK rising edge:
    r_bits: list = field(default_factory=list)
    g_bits: list = field(default_factory=list)
    b_bits: list = field(default_factory=list)
    lat_bits: list = field(default_factory=list)
    addr_bits: list = field(default_factory=list)   # 0..7 at each CLK edge
    latches: list = field(default_factory=list)     # [LatchEvent]
    addr_changes: list = field(default_factory=list)  # (sample_idx, new_addr)
    gclk_edges: list = field(default_factory=list)  # sample idx of GCLK rising


def decode(path):
    chans = parse_capture(path)
    d = Decoded(path=path)
    d.n_samples = len(chans[CLK])
    clk, lat = chans[CLK], chans[LAT]
    r, g, b = chans[R], chans[G], chans[B]
    aa, ab, ac = chans[ADDR_A], chans[ADDR_B], chans[ADDR_C]

    d.clk_edges = rising_edges(clk)
    d.gclk_edges = rising_edges(chans[GCLK])

    for i in d.clk_edges:
        d.r_bits.append(r[i])
        d.g_bits.append(g[i])
        d.b_bits.append(b[i])
        d.lat_bits.append(lat[i])
        d.addr_bits.append(aa[i] | (ab[i] << 1) | (ac[i] << 2))

    # Address changes over raw samples
    prev = aa[0] | (ab[0] << 1) | (ac[0] << 2)
    for i in range(1, d.n_samples):
        cur = aa[i] | (ab[i] << 1) | (ac[i] << 2)
        if cur != prev:
            d.addr_changes.append((i, cur))
            prev = cur

    # Latch events: LAT high periods, code = CLK rising edges inside
    lat_rise = rising_edges(lat)
    lat_fall = falling_edges(lat)
    # pair rises with falls
    fi = 0
    import bisect
    for rs in lat_rise:
        while fi < len(lat_fall) and lat_fall[fi] <= rs:
            fi += 1
        if fi >= len(lat_fall):
            break  # LAT still high at end of capture
        fs = lat_fall[fi]
        lo = bisect.bisect_left(d.clk_edges, rs)
        hi = bisect.bisect_left(d.clk_edges, fs)  # edges in [rs, fs)
        d.latches.append(LatchEvent(
            code=hi - lo, start_sample=rs, end_sample=fs,
            clk_index_start=lo, clk_index_end=hi - 1))
    return d


def bits_to_words(bits, msb_first=True):
    """Group a bit list into 16-bit words."""
    words = []
    for i in range(0, len(bits) - 15, 16):
        w = 0
        for bit in bits[i:i + 16]:
            w = (w << 1) | bit
        if not msb_first:
            w = int(f"{w:016b}"[::-1], 2)
        words.append(w)
    return words


def fmt_bits(bits):
    return "".join(str(x) for x in bits)
