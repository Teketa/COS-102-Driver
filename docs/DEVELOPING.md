# COS-102 Controller — How It Works & How To Extend It

A guide to the firmware: how a pixel gets from an effect function onto the
sign, and how to write your own effects and text animations.

Companion documents: [PROTOCOL.md](PROTOCOL.md) (the reverse-engineered bus
protocol) and [HARDWARE.md](HARDWARE.md) (wiring, level shifting, supply).

---

## 1. The whole path, top to bottom

```
   effects.c            canvas.c              framebuf.c           protocol.c
 ┌────────────┐     ┌──────────────┐     ┌────────────────┐    ┌─────────────┐
 │ your effect│ ──▶ │ g_canvas     │ ──▶ │ pixel mapping  │──▶ │ 128 latches │──▶ panel
 │ draws RGB  │     │ 200×30 RGB888│     │ + gamma/bright │    │ + vsync     │
 └────────────┘     └──────────────┘     └────────────────┘    └─────────────┘
      core 0              copy               core 1                core 1
```

1. **Your effect** draws into `g_canvas`, a plain 200×30 array of RGB888
   pixels. Nothing else in the pipeline cares how you produce them.
2. **`canvas_publish()`** copies the finished canvas to `g_canvas_show`.
3. **`canvas_pack_slots()`** converts that to the drivers' native format:
   for each of 6400 (slot, word) positions it looks up which pixel feeds it,
   applies brightness and gamma, and writes a 16-bit greyscale value.
4. **`proto_send_frame_paced()`** shifts the 128 slots out over quad-SPI and
   emits the vsync at a precise moment.

### The two cores, and why it matters

| Core | Task | Deadline |
| --- | --- | --- |
| 0 | `content` (your effect), WiFi, lwIP, HTTP | none |
| 1 | `display` (pack + send + vsync), DMA feeder + its ISR | **hard** |

The display side must emit frames on a rigid cadence. Every vsync briefly
stops the drivers' grayscale clock, and while GCLK is stopped the PWM counter
**freezes** — holding each LED at whatever state it was in. A constant interval
freezes identically every frame (invisible); a varying one modulates brightness
(visible pulsing). This single fact explains almost every display artifact you
will hit.

Consequence for you: **your effect has no deadline**. It runs on core 0, one
frame ahead. If it takes too long, the previous frame is simply shown again.
You cannot break the panel's timing by writing a slow effect — but a
consistently slow one lowers the frame rate (see §6).

---

## 2. The canvas API

Everything lives in `canvas.h`. Coordinates: **x = 0..199 left to right,
y = 0..29 top to bottom**. Colours are `rgb_t {r,g,b}`, 0–255 per channel;
gamma correction and brightness scaling happen later, so just write the colour
you want to see.

```c
canvas_clear();                         // all black
canvas_fill(c);                         // flood
canvas_px(x, y, c);                     // set a pixel (bounds-checked)
canvas_blend(x, y, c, alpha);           // alpha 0..255 over what's there
canvas_add(x, y, c);                    // additive, saturating
canvas_fade(amount);                    // scale everything toward black
canvas_hline(y, x0, x1, c);
canvas_vline(x, y0, y1, c);
canvas_rect(x, y, w, h, c, fill);
canvas_text(x, y, "hi", scale, c);      // 5x7 font, integer scale
canvas_text_sub(fx, y, "hi", scale, c); // fractional x — smooth scrolling
canvas_char(x, y, codepoint, scale, c);
rgb_t c = hsv(hue, sat, val);           // all 0..255
rgb_t d = rgb_scale(c, v);              // brightness scale, v 0..255
```

Helpers you will want from `effects.c`:

```c
static int8_t SIN[256];                 // sine table, phase 0..255 → −127..127
static int dist_approx(int dx, int dy); // cheap distance, no sqrtf
uint8_t rnd8(void);  uint32_t rnd32(void);   // fast PRNG
```

The font covers ASCII plus **Æ Ø Å æ ø å**; strings are UTF-8.

---

## 3. Writing an effect

An effect is one function:

```c
void my_effect(uint32_t st, uint32_t frame);
```

- **`st`** — the animation clock in milliseconds, already scaled by the user's
  speed setting. **Drive all motion from this**, never from `frame`, so that
  changing the frame rate doesn't change how fast things move.
- **`frame`** — a frame counter. Use it only for things that should happen
  per-frame regardless of time.

### Worked example

Add to `effects.c`, above the `g_effects[]` table:

```c
// A comet that flies left to right, leaving a fading trail.
static void fx_my_comet(uint32_t st, uint32_t f)
{
    canvas_fade(30);                         // dim what's already there

    int x = (st / 20) % CW;                  // 1 px per 20 ms of animation time
    int y = CH / 2 + SIN[(uint8_t)(st / 12)] * 8 / 127;   // gentle bob

    rgb_t head = FG();                       // user's chosen colour
    canvas_px(x, y, head);
    canvas_px(x, y - 1, rgb_scale(head, 90));
    canvas_px(x, y + 1, rgb_scale(head, 90));
}
```

Register it in the table at the bottom of `effects.c`:

```c
const effect_t g_effects[] = {
    ...
    { "My Comet", fx_my_comet },
};
```

That's all. The web UI builds its effect grid from this table at runtime, so
your effect appears in the gallery, works with the playlist, and is reachable
over the REST API — no UI changes needed.

Rebuild and flash:

```bash
pio run -t upload
```

### Using the user's settings

```c
FG()                  // foreground colour picked in the UI
BG()                  // background colour
g_set.font_scale      // 1..4
g_set.speed           // already folded into `st`; rarely needed directly
CW, CH                // 200, 30
```

### Effects that read the previous frame

`canvas_fade()`, fire, and comet trails all read back what they drew last
frame. That works: the double buffering is a **copy**, not a pointer swap, so
`g_canvas` always still holds your own previous output.

### Per-effect state

If you need persistent state (particles, drop positions, a heat map), add a
member to the union `S` near the top of `effects.c` and guard initialisation
with `s_init`:

```c
static union {
    uint8_t heat[CH][CW];
    struct { float x, y, vx, vy; } mine[32];
    ...
} S;
```

The union means all effects share one allocation — only the active effect's
member is valid. `fx_reset()` zeroes it and clears `s_init` whenever the effect
changes, so initialise like this:

```c
if (!s_init) { /* seed your state */ s_init = true; }
```

---

## 4. Writing a text animation

Same idea, different signature — you also get the message:

```c
void my_text_anim(const char *s, uint32_t st, uint32_t frame);
```

Helpers available in `effects.c`:

```c
bg_fill();            // fill with the background colour
text_w(s)             // pixel width at the current font scale
text_h()              // pixel height
centered_y()          // y that vertically centres one line
scroll_phase(st, span) // float position that wraps over `span`, for smooth scroll
```

Example — text that slides in from the left and stops:

```c
static void tf_my_slide(const char *s, uint32_t st, uint32_t f)
{
    bg_fill();
    int target = (CW - text_w(s)) / 2;
    float x = (float)st / 15.0f - 40.0f;      // continuous, sub-pixel
    if (x > target) x = target;
    canvas_text_sub(x, centered_y(), s, g_set.font_scale, FG());
}
```

Register it:

```c
const textanim_t g_textanims[] = {
    ...
    { "My Slide", tf_my_slide },
};
```

**Always use `canvas_text_sub()` for anything that moves horizontally.**
`canvas_text()` snaps to whole pixels, so a scroll of 0.76 px/frame steps
1,1,0,1,1,0… — visible judder. `canvas_text_sub()` splits each column's
intensity across two panel columns using the panel's 16-bit greyscale, giving
continuous motion at any speed and frame rate.

---

## 5. Rules that prevent the classic bugs

Each of these caused a real, hunted-down artifact on this sign:

1. **Drive motion from `st`, not `frame`.** Otherwise speed changes with the
   frame rate.
2. **Draw the full scene every frame.** Fading on frames where you draw
   nothing produces a strobe. (The original Matrix Rain faded every frame but
   only drew on even ones — a 15 Hz flicker.)
3. **Advance discrete state on a time grid, not per frame:**
   ```c
   uint32_t step = st / 55;
   while ((int32_t)(step - S.mine.step) > 0) { S.mine.step++; advance(); }
   ```
4. **Use `canvas_text_sub()` for horizontal motion** (see §4).
5. **Avoid per-pixel `sinf`/`sqrtf`.** 6000 pixels × a few transcendentals is
   milliseconds per frame. Use `SIN[]` and `dist_approx()`; plasma went from
   ~15 ms to well under 1 ms this way.
6. **Don't allocate.** No `malloc` in an effect — use the `S` union.

---

## 6. Performance and the frame budget

The Advanced tab reports it live:

```
core 1 (panel) : 8.9 ms of 16.7 ms slot  (pack 0.7 + send 8.2)
core 0 (content): 2.9 ms  (runs in parallel; no deadline)
late vsyncs    : 0 of 45231 frames
```

- **core 1** is the one with the deadline. It's dominated by the data send,
  which is fixed by the data clock: 128 slots × 800 bits. At 20 MHz that's
  ~8 ms, so ~100 fps is the ceiling regardless of your effect.
- **core 0** is your effect. It runs in parallel, so it only matters if it
  exceeds the frame slot.
- **late vsyncs** should stay at 0. If it climbs, the engine auto-limits the
  frame rate (shown as `target 60, auto-limited to 45`) rather than dropping
  frames — regular pacing looks far better than a nominal rate with drops.

If you want more headroom: raise the data clock (`oc data 20`), lower the frame
rate, or make the effect cheaper.

---

## 7. Tuning and debugging tools

Everything is reachable from the Advanced tab's terminal or the serial console
(`pio device monitor`, type `help`):

```
ui off / ui on            # release/take the panel (needed for test patterns)
pat border|checker|gradx  # geometry test patterns
ws <0-127> / ww <0-49>    # walk one SRAM slot / one driver — mapping probes
oc gclk 20 / oc data 20   # bus clocks (MHz); `oc status` shows everything
oc fast / oc reset        # 20 MHz preset / back to OEM 12.5 MHz
set nlat 128              # latches per frame
map set mirrorx 1         # orientation
status                    # full protocol state
wifi txpower 8            # lower = smaller supply spikes
```

Test patterns need `ui off` first — otherwise the render engine overwrites the
panel on the next frame.

---

## 8. Project layout

```
firmware/src/
  main.c            bring-up order (panel init runs on core 1 — see below)
  settings.[ch]     NVS-persisted configuration
  canvas.[ch]       RGB drawing surface + gamma/brightness + slot packing
  font.[ch]         5x7 font, UTF-8, Danish characters
  effects.c         ← effects and text animations live here
  render.[ch]       the two-core pipeline
  framebuf.[ch]     the decoded pixel mapping (slot,word) → (x,y)
  protocol.[ch]     frame structure: latches, vsync, config, pacing
  datapath*.c       data bus: bit-bang and quad-SPI DMA backends
  scanout*.c        scan engine: bit-bang and LCD_CAM DMA backends
  webserver.c       REST + WebSocket state push
  web/index.html    the UI  (run tools/gen_web.py after editing!)
```

Two non-obvious things worth knowing before you move code around:

- **`tools/gen_web.py` must be re-run after editing `web/index.html`** — the
  page is compiled in as a C array because PlatformIO mishandles CMake's
  `EMBED_FILES`.
- **Panel bring-up happens in a task pinned to core 1** (`main.c`). ESP-IDF
  binds an interrupt to whichever core registers it, and the LCD DMA
  completion ISR is what starts each scan cycle — it must not share a core
  with WiFi.

---

## 9. REST API

For scripting or home automation:

```bash
curl http://<ip>/api/state                              # everything
curl -X POST http://<ip>/api/state -d '{"mode":1,"text":"HELLO"}'
curl -X POST http://<ip>/api/state -d '{"mode":0,"effect":30}'
curl -X POST http://<ip>/api/action -d '{"action":"pause"}'
curl -X POST http://<ip>/api/cmd  -d '{"cmd":"oc status"}'
```

`mode`: 0 = effect, 1 = text, 2 = clock, 3 = off. Actions: `play`, `pause`,
`toggle`, `next`, `prev`, `save`, `blank`, `defaults`, `reboot`.
