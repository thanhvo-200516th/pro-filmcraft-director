# 28 — Hook-first 5 s and the pacing law (v7.7.0, hook text and motion floor v7.8.0, v4-review gates v7.9.0)

Look S doctrine for the first 5 seconds and for the rhythm of the whole video. It sits on top of [`24_studio_look_recipe.md`](./24_studio_look_recipe.md) (V19..V21 scene map) and [`dviet_19/INDEX.md`](./dviet_19/INDEX.md) (the 17 measured `@__dviet` videos). Runnable data: `hook_0_5s`, `pacing` and `camera_punch_caps` in [`presets/studio_scene_recipe.json`](../presets/studio_scene_recipe.json); validators in [`scripts/tools/studio_recipe.py`](../scripts/tools/studio_recipe.py) (`hook_template`, `hook_text_from_words`, `check_hook`, `check_pacing`, `plan_micro_moves`, `check_source_reuse`). The rendered twins of the v7.8.0 plan rules are the gates of `scripts/tools/motion_gate.py` (package S1; named here, not imported by the planner).

Convention: every number is labelled **[ĐO]** (measured on a file or a frame) or **[ƯỚC]** (estimate: guessed, derived, or limited by the measuring method). An unlabelled number is a rule the recipe sets, not a measurement.

---

## 0. Read this first: what the evidence can and cannot say

- **One channel, 17 samples.** All hook statistics come from the 17 `@__dviet` videos plus the three Look S masters (V19, V20, V21) and the v2 build. This is a style study of one channel, not a law of TikTok. Treat each number as "what this channel does", and use it as a target, not as a proof that the target retains viewers.
- **SFX cannot be separated from voice and music.** The mix is one stereo track. A band-energy onset or a 50 ms RMS jump tells you that something loud happened, not which file made it. Every SFX **time** below is [ƯỚC]; every **depth of an audio dip** is [ĐO] (RMS of the mix), but its cause (a deliberate vacuum, a pause, a music edit) is [ƯỚC].
- **Cut, text and voice times are [ĐO]** (frame differencing and scene scores on the 60 fps files, OCR boxes per frame, first sample above -45 dB, ASR word times). Sampling for the motion statistics was done at 30 fps on a 72x128 thumbnail, so every "share of frames in motion" and every "dead-hold share" is [ƯỚC]; hard cuts remain [ĐO].
- **R200 AI B-roll is not proof.** The hook product macro may be AI-made; never let it carry a claim ([`15`](./15_adaptive_tiers_and_epistemic_qa_v51.md)).
- **Measurement method names** (copied here so a reader can reproduce the study; the scripts are scratch research tools and **do not ship with the skill**): `hook_measure` (0-5 s forensics per video: cut and flash events, audio onsets per band, first word, OCR text boxes, zoom series, a 0-5 s strip at 0.1 s and a 0-1 s strip at frame rate), a pacing analysis (resets per 5 s window, text events, beats, active-pixel share, shot-length distribution, an event raster) and an audio-curve comparison (50 ms RMS, sub-bass 35-110 Hz energy).

---

## 1. The measured basis: 17 `@__dviet` hooks

### 1.1 Opening patterns

| Pattern | Count [ĐO] | What it is | Videos (id suffix) |
|---|---|---|---|
| **P1** face-first + keyword pop | 8 | Frame 0 is the presenter mid-gesture; a giant keyword pops at 100-300 ms; often a zoom-out in the first second | 7666801, 7667598, 7669054, 7669758, 7670574, 7677448, 7693026, 7707653 |
| **P2** plate reveal (flicker, clone, vanish) | 4 | Empty plate for 0-380 ms, then the person flickers or whips in | 7664447, 7664969, 7668334, 7672413 |
| **P3** object or cinematic B-roll first | 3 | Top-down desk or macro montage, no face | 7683763, 7688934, 7706183 |
| **P4** text-first, music only | 1 | Back of head, swash script, no voice | 7664835 |
| **P5** breakdown, no hook | 1 | Raw and edited cards side by side | 7664633 |

8 + 4 + 3 + 1 + 1 = 17. Look S keeps the V21 structure (full-screen product B-roll plus a PiP presenter), which is closest to P3 for the picture and P1 for the text and audio.

### 1.2 Statistics

| Fact | Value | Label |
|---|---|---|
| Voice already playing at frame 0 (first sample above -45 dB within about 100 ms) | 15 of 17 videos | [ĐO] |
| The two exceptions | one music-only video (P4) and one whisper at 440 ms | [ĐO] |
| First overlay text appears | median 200 ms (range 0-800 ms, one outlier at 2.8 s) | [ĐO] |
| Hero text box height | 10-21 % of the frame height | [ĐO] (OCR box) |
| First hard transition (cut, flash or zoom jump) | median 3.4 s | [ĐO] |
| Audio vacuum before that transition (RMS dip) | mean about 17 dB, lasting 100-250 ms | depth [ĐO], cause [ƯỚC] |
| Face-first videos (P1) that open with a zoom-out of 0.77-0.86x | 4 of 8 | [ĐO] |
| First SFX onset candidates | 128-313 ms in 8 of the 17 videos (the others: none detected, or later) | [ƯỚC] |

### 1.3 Why a 3.4 s anchor

The median first transition at 3.4 s coincides with the V19..V21 white flash and polaroid trio at 3.39 / 3.65 / 3.89 s (the shutter flashes). Keeping that anchor means the hook is rebuilt **inside** the existing V21 grid and nothing downstream has to move.

---

## 2. Hook recipe v3 (Look S, 60 fps, 1 frame = 16.7 ms)

Structure of V21 kept: full-screen product B-roll plus a PiP presenter. Times in ms from frame 0. Cut, text and voice times are targets taken from the measured hooks [ĐO basis]; SFX, riser and vacuum times are [ƯỚC].

**The hook is built from the voice words (`words_*.json`), not from this table (v7.8.0).** The table gives the structure and the timing; the texts come from `hook_text_from_words(words)`. The voice is never re-cut: the picture follows the voice ("hình đến đâu tiếng đến đó"). Rule: **the first text is a lead line that quotes the first spoken clause (<= 200 ms); the keyword hero comes 150-200 ms before its word; a numeral appears only when the voice says it (within +/-400 ms).** v3 broke this: the hero `3 BƯỚC` stood at 0.17 s while the voice said `Vì trên đây là video sản phẩm...` and said `3` only at 3.48 s (defect D1). The numeral compromise of v7.7.0 is deleted.

| t | What happens | Notes |
|---|---|---|
| 0 | Frame 0 is the real AI-made product macro, already moving. Background scale 1.22x -> 1.00x, ease-out over 500-600 ms. Voice onset <= 40 ms | no black or empty first frame |
| 100 | Presenter PiP pops in, scale 0.92 -> 1.0 over 6 frames | |
| 150 | First text (lead line, <= 200 ms, not counted into the hero tier): the first spoken clause, e.g. `TRÊN ĐÂY LÀ` (voiced 120-860 ms), font >= 64 px, glyph box >= 3.3 % of the frame height. First text may lead its word by -50..+250 ms | `text_voice_sync`, `text_min_size` |
| 700 | Hero lock-up in 2 tiers: the first keyword voiced in 0.3-1.5 s, 150-200 ms ahead of its word (`VIDEO` at 700 for the word at 860, `SẢN PHẨM` in Look S gold `#F5C451` at about 900); exits before the 1330 punch | hero box 12-18 % of the frame height (230-345 px, 15.3 % in the v3 plan [ĐO]), width 60-80 %; entrance blur-in or pop over 3-6 frames; **product-safe zone: the hero sits in the stage above the product and never over it** (`hero_safe_zone`) |
| 1490-1500 | Next spoken clause (`BỌN MÌNH VỪA LÀM`, word at 1660), glyph box >= 4 % of H, exits at about 2300-2550 to hand over | spacing 550-790 ms from the previous text, inside the 500-900 gate |
| 1330 | Punch / layout cut: zoom 1.0 -> 1.15-1.55x within <= 300 ms | whoosh peak within +/-12 ms of the cut |
| 1920 | Back to the serum wide at 1.00x with bloom 1.1 plus a whoosh | |
| 2580 | PiP scale pop 1.00 -> 1.12 over 0.3 s plus a glitch tick | |
| 2900-3200 | Riser builds | |
| 3200-3380 | Vacuum: duck voice and bed by >= 18 dB (to about -35 dBFS) for about 180 ms; no SFX | target dip 17 dB, gate >= 12 dB |
| 3400 | White flash cut, then the polaroid trio. Shutter hits at 3.39 / 3.65 / 3.89 s with a visible 4-frame white flash (opacity 0 -> 60 -> 0 in 0.12 s) at 3.65 and 3.89; pops staggered 0.25 s | |

**Text budget in 0-3 s:** 3-5 events, one every 0.5-0.9 s, each held >= 0.6 s, one accent colour, no karaoke in the hook. **Reset rate:** one visual reset per second in 0-3.4 s.

**Product stage (when the product is the hook picture).** The bottle fills x 0.25-0.77, y 0.05-0.87 of the v3 9:16 crop [ĐO], so a hero over the middle of the frame covers it. Put the macro on a bottom-anchored stage at `s = 0.72` (the cap top at about y 613 of 1920, `0.32 H`; the top 30 % is replicate plus blur), put the hero text in the band y 0.07 H .. cap top, and anchor every zoom at the cap top so the product grows downward and never enters the text band. `check_hook` takes `product_bbox` (x0, y0, x1, y1 in 1080x1920) or `stage={'s': 0.72}`; overlap must be 0 px (2 % of the hero area tolerated). The rendered check is `hero_product_overlap_px` of `motion_gate.py`.

**Text size.** No hook text below a 64 px font or a 3.3 % glyph box (`text_min_size`); the hero tier box is 12-18 % of H, counted per tier. The 31 px whisper `từ 3 ảnh thô` of v3 is dropped. Do not put a word on screen that the user has not confirmed (the ASR `hàng` may be `hãng`).

**Motion floor (D3).** Every 1.0 s window of 0-3.4 s needs at least one **background** reset: a cut, flash, glint, card landing or a zoom step >= 4 %. PiP pops and whisper text are overlay resets and do not count (`hook_motion_floor`). A full-screen B-roll hold longer than 0.8 s inside the hook (1.2 s elsewhere, warn) needs a micro-move: a push >= 10 %/s on average, a pan >= 4 % of the crop per second, or a glint sweep (`bg_static_hold` in `check_pacing`; `plan_micro_moves(shots)` proposes the push). Proof [ĐO, engineer]: a 4 %/s push gives frame diff 1.23, a 14.5 %/s push 2.09. Keep a push inside the +25 % full-screen B-roll cap (section 4.1); a hold too long for one push is split with another background reset. The source clip of v3 is effectively a still (flow 0.05-0.06 px/frame [ĐO]): the fix is camera, light and cards on top of it, not new Flow media (needs user approval).

**Motion bar.** Compare the hook with the 17 `@__dviet` B-roll-first hooks (masked-background frame diff mean 1.9-2.4 [ĐO]), **not with V21**: V21 has a 2.0 s hold at 1.35-3.35 s and is not a motion bar (v3 hook masked mean 2.11 with 50 % of frames < 1.0 [ĐO]).

### 2.1 SFX by file name

Folder: `sfx trends/` (the user's SFX library; not shipped). Shift each file so its **peak** lands on the target time (`at = target - peak`). Peaks are from `DANH_SACH_100_SFX_HOOK_3S.csv`. All times are [ƯỚC].

| Target | File (folder / name) | Peak | Place at |
|---|---|---|---|
| 150 ms (lead line; the only SFX at 150) | `02_Whooshes_Swishes_WhipPans/17_Snap_Whoosh_Micro_Swish.wav` (-14 dB) | 106 ms | 44 ms |
| 700 ms (hero) | `01_Impacts_Booms_SubDrops/03_Soft_Low_End_Thud.wav` | 28 ms | 672 ms |
| 700 ms (hero) | `04_UI_Pops_Clicks_Notifications/43_Clean_Bubble_Pop_A4.wav` | 6 ms | 694 ms |
| 700 ms (optional) | `01_Sub_Bass_Drop_Clean.wav` | -- | 694 ms |
| 900 ms and about 1500 ms | `04_UI_Pops_Clicks_Notifications/45_Crisp_UI_Tick_E6.wav` (-16 dB) | 5 ms | 895 / 1500 ms |
| 2030-2700 ms (glint) | `02_Whooshes_Swishes_WhipPans/21_High_Pitch_Airy_Swoosh.wav` (-19 dB) | 160 ms | 2280 ms |
| 2317 ms (snap-punch) | `04_UI_Pops_Clicks_Notifications/52_UI_Card_Magnetic_Dock.wav` (-14 dB) | 5 ms | 2315 ms |
| 2700 ms (PiP pop) | `02_Whooshes_Swishes_WhipPans/22_Paper_Card_Slide_Swish.wav` (-13 dB) | 137 ms | 2563 ms |
| 2720 / 2920 / 3120 ms (cards) | `04_UI_Pops_Clicks_Notifications/52_UI_Card_Magnetic_Dock.wav` (-14 / -13 / -12 dB; vary with another unused `04_` click if the duplicate-clip gate rejects the repeat) | 5 ms | target - 5 ms |
| 1330 ms | `02_Whooshes_Swishes_WhipPans/16_Clean_Air_Whoosh_Short.wav` | 110 ms | 1.22 s |
| 1330 ms (alternative) | `02_Whooshes_Swishes_WhipPans/19_Whip_Pan_Camera_Swish.wav` | 26 ms | 1.304 s |
| 3400 ms (riser peak) | `03_Risers_Swells_Tension/31_Short_White_Noise_Riser_06s.wav` | 504 ms | 2.896 s |
| riser alternative | `32_Reverse_Cymbal_Suck_In.wav` | -- | 2.60 s |
| 3.20-3.38 s | **no SFX** | | |
| 3400 ms | `06_Camera_Paper_Typing_Foley/70_Vintage_Film_Camera_Flash.wav` | 247 ms | 3.153 s |
| 3400 ms, 3650 ms, 3890 ms | `06_Camera_Paper_Typing_Foley/69_Modern_Mirrorless_Shutter.wav` (shutter hits on the polaroids as in v2) | 108 ms | target - 108 ms |

**When a hook text is retimed, regenerate the SFX list in the same pass** (the SFX follow the text and cut times; do not leave the old 150 ms thud, pop and swish stack behind). Check the mix at 2.3-2.6 s and duck the voice >= 3 dB there.

Avoid `Combo_03_Tech_AI_Pattern_Interrupt` (too glitchy). `Combo_01_Editorial_Slide_Hook_DViet.wav` is the quieter reference.

### 2.2 Gates for a hook

| Gate | Limit | Reference value |
|---|---|---|
| Audio dip at 3.2-3.4 s | >= 12 dB, target 17 dB | v2 4.6 dB, V21 7.4 dB [ĐO] |
| First text | <= 200 ms | dviet median 200 ms [ĐO] |
| Text matches voice | each text onset 0-400 ms before its first spoken word (comfort 100-250 ms; first text -50..+250 ms) | `text_voice_sync`, error |
| Hero over the product | 0 px overlap | `hero_safe_zone` (plan), `hero_product_overlap_px` (rendered) |
| Background motion | a bg reset in every 1.0 s of 0-3.4 s; no full-screen B-roll hold > 0.8 s without a micro-move | `hook_motion_floor`, `bg_static_hold`; rendered mean frame diff 2.03-3.38 s >= 2.0 against the dviet bar 1.9-2.4 |
| Hero text | >= 12 % of the frame height (12-18 % recipe) | v2 7.0 %, V21 4.4 %, V19 4.2 % [ĐO]; dviet 10-21 % [ĐO] |
| Loudness after ducking | -12 LUFS +/-0.5, true peak <= -1.0 dBTP | the hook gate; the master profile `studio_14` stays -14 LUFS |
| Visual check | a 0-5 s strip of the new build next to the best dviet hook (`7666801` or `7669054`) | by eye |
| QA step | **read the words 0-3.5 s next to the text list** (every text must be a word being spoken, none before the voice says it) | by eye, then `check_hook(plan, words=words)` |

`check_hook(plan, words=words)` checks the plan-level parts (first text, text-voice sync, hero box height and safe zone, text size, text budget, text hold, resets, motion floor, vacuum depth, whoosh alignment, voice onset). Without `words` it only warns `no words provided`. The audio dip and the loudness are checked on the rendered file.

### 2.3 v7.9.0 gates (v4 review)

The v4 build passed the v7.8.0 plan checks and still showed six defects on the render [ĐO]; each is now a gate. Limits are [ƯỚC] unless marked.

| Gate | Limit | v4 value | Where |
|---|---|---|---|
| First text before its word (`first_text_late`, default on) | first text on screen at or before its first spoken word; `hook_text_from_words` puts the lead line 20 ms before it | E1 landed 47 ms after the word [ĐO] | `check_hook(plan, words=words)`; `strict_first_text=False` only to read an old plan |
| Text coverage (`text_coverage`) | from the first text to 3.0 s no text-free stretch > 150 ms | 1.30-1.49 s and 2.43-2.73 s empty [ĐO] | `check_hook` |
| Text legibility incl. labels (`text_min_size`) | every overlay text, card label and plate caption >= 64 px after the plate scale (CSS px x `scale`), glyph >= 3.3 % of H; `decorative: true` warns | polaroid labels 10-27 px [ĐO] | `check_hook` (`labels`), `render_web_plates_batch` `text_audit` |
| Word gap (`word_gap_collision`) | adjacent-word gap >= 0.25 em on every visible entrance frame (blur sigma eats 2 sigma, per-word scale eats (s - 1) x word width) | 21 px gap, blur 10 at 1.12x read 'MÌNHVỪA' [ĐO] | `check_hook` (texts with `gap_px`), `motion_gate.check_word_gaps`; kt03 bloom capped by default; `per_word_stagger` clamps to `max_word_scale_pct` 100 |
| Flash cap (`flash_luma_cap`, `flash_rate`) | frame mean luma <= 220 under a flash; <= 3 flashes in any 1 s (WCAG 2.3.1); the 3.4 s white cut is opacity <= 70 over 3 frames | full white 52 -> 248 at 3.40 s, two washes 0.25 s apart [ĐO] | plan `check_hook`; render `motion_gate.py --flash` |
| SFX block rows (Gate 7b) | no `qa_sync` row with `block: true` (sound > 0.1 s before the picture) may remain; such a row is never ĐẠT | - | `qa_sync.py` exit 1, `gate_pass(rows)` |

---

## 3. Gap list: V19 / V20 / V21 and v2 against the channel

v2 keeps V21's cut grid (16 cuts), the shot-length median equals dviet (2.03 s [ƯỚC]), and speech and text density are fine. The gaps:

| Gap | v2 | V21 | dviet | Label |
|---|---|---|---|---|
| Hero text height | 7.0 % | 4.4 % (V19 4.2 %) | 10-21 % | [ĐO] |
| First text | 200 ms tiny sub, hero at 900 ms | 67 ms tiny sub, hero at 700 ms | median 200 ms | [ĐO] |
| First SFX stack | 0 ms | about 801 ms | 128-313 ms in 8 of 17 | [ƯỚC] |
| Audio dip before the 3.4 s transition | 4.6 dB | 7.4 dB | mean about 17 dB | [ĐO] |
| Shutter flashes at 3.4 s | 1 of V21's 3 | 3 | n/a | [ĐO] |
| In-shot punch-ins | 0 | not tabulated | not tabulated | [ĐO] |
| Resets in 0-5 s | 2 | 5 | 4.0 median | [ƯỚC] (30 fps sampling) |
| Frames in motion, 0-10 s and 28-36 s (analysis summary) | 5-20 % | not tabulated | median 38-49 % | [ƯỚC] |
| Shots shorter than 1 s in the tail | 0 % | not tabulated | not tabulated | [ĐO] |
| Dead holds (share of the video) | about 70 % | about 58 % | median about 39 % | [ƯỚC] |
| Static B-roll hold | v3 2.2-3.4 s: macro frame diff < 1.0 from 2.03 to 3.38 s, only a PiP pop at 2.58 s and a 31 px whisper [ĐO] | V21 has a 2.0 s hold at 1.35-3.35 s [ĐO] | B-roll-first hooks: masked mean 1.9-2.4 [ĐO] | [ĐO] |
| Hook text vs voice | v3 hero `3 BƯỚC` at 0.17 s, voice says `3` at 3.48 s [ĐO] | n/a | text follows the voice | [ĐO] |
| Repeated B-roll | the same source seconds twice in 30.65-34.0 s | n/a | n/a | [ĐO] |
| Sub-bass level | 6-12 dB below V21 | reference | n/a | [ĐO] |
| Weak cut hits | 6 of 16 | n/a | n/a | [ĐO] |

The strongest window of v2 is 10-15 s (S06-S08): **keep it unchanged**.

### 3.1 Per-window table (30 fps, 72x128 sampling, all [ƯỚC])

Resets per 5 s window and share of frames in motion (`active`). dviet = median over the sample videos that reach the window (4-5 videos per window).

| Window | v2 resets / active | V21 resets / active | dviet resets / active |
|---|---|---|---|
| 0-5 s | 2 / 14 % | 5 / 19 % | 4.0 / 49 % |
| 5-10 s | 2 / 7 % | 2 / 13 % | 5.0 / 29 % |
| 10-15 s | 5 / 38 % | 5 / 27 % | 3.0 / 27 % |
| 15-20 s | 3 / 13 % | 2 / 13 % | 2.0 / 11 % |
| 20-25 s | 3 / 15 % | 2 / 6 % | 3.0 / 18 % |
| 25-30 s | 3 / 23 % | 3 / 23 % | 2.5 / 19.5 % |
| 30-35 s | 2 / 7 % | 3 / 19 % | 5.0 / 37.5 % |
| 35-40 s | 2 / 11 % | 4 / 11 % | 3.0 / 26.5 % |

The per-window medians differ from the rounded summary above (the summary quotes dviet 38-49 %; the table gives 26-49 % for the same windows); both are [ƯỚC] and neither is a standard. Use the table as the reference for per-window comparisons.

---

## 4. The pacing law

All numbers here are rules of the recipe; the evidence for them is the table above ([ƯỚC] where the sampling was coarse).

1. **Max hold.** No hold longer than **2.0 s** without a reset (a cut, a zoom step, a flash or a new text event). The recipe cap is **2.4 s**: above it `check_pacing` reports an error (`max_hold`), between 2.0 and 2.4 s a warning (`law_hold`).
2. **Visual change per 5 s.** At least **3 resets** in the hook window (0-5 s) and at least **2** in every later 5 s window (`resets_per_5s`). Resets closer than 0.1 s count once (a cut with its text is one change). A last window of at least 2.5 s is checked with the minimum scaled to its length; a shorter tail is not checked.
3. **Short shots.** At least **2 shots under 1 s in each 10 s** (advisory warning `short_shots`, never an error). The "shots under 1 s" share is reported as `short_shot_share`.
4. **Dead holds.** Target **<= 45 %** of the video (v2 about 70 %, V21 about 58 %, dviet median about 39 % [ƯỚC]). `check_pacing` reports `dead_hold_share` as a **plan-level proxy**: the share of time inside stretches without a reset that are longer than 1.0 s [ƯỚC]. It is not the motion-based measure of the research; compare the 45 % target against a motion measurement of the rendered video, and use the proxy only to find the places to add a reset.
5. **Evidence checks for a rebuild:** dead-hold share <= 45 %; frames in motion >= 20 % in every 5 s window (rendered file, not the plan); no window below 3 resets (hook) or 2 (other); every window at least as good as the build it replaces.
6. **Never reuse B-roll source seconds.** The same seconds of the same B-roll clip must not appear twice (v2 showed flow/09 seconds 1.0-3.35 in two scenes: 2.35 s on screen twice). `check_source_reuse` reports shots whose `source` and `src [a, b]` overlap by more than 2 frames. Re-time another clip or cut a different range; do not spend generation credits without approval.
7. **Resets are scene splits.** Implement every fix as a split of a scene into pieces with their own camera (`cam [a, b]` per piece). Speed stays 1.0x. All pacing changes are visual only.

`plan_scenes()` output is a scene grid, not a shot list: run through `check_pacing` unchanged it reports long holds, because a scene of 3-5 s contains no inner reset yet. That is intended; the report is the list of places where the brain must add a zoom step, a cut, a flash or a text event.

### 4.1 Per-layer camera punch-in caps

Maximum punch-in over 1.00 for one camera move (`camera_punch_caps` in the preset; [ƯỚC], set from the V19..V21 and v2 comparison, not measured on the channel).

| Layer | Cap | Why |
|---|---|---|
| B cutout | +5 to +6 % | the 720p A-roll is already about 1.5x upscaled in the cutout |
| A1 card | +10 to +12 % | the card photo has a fixed crop |
| PiP inner zoom | +8 % | |
| Full-screen B-roll | +25 % | native 720p B-roll |
| Velvet settle | 1.20 -> 1.02 over 0.7 s | the arrival move after a cut |

---

## 5. What NOT to change

- **Speech density.** v2's words per second are fine; do not retime, cut pauses or speed up the voice. Speed stays 1.0x.
- **Text density.** v2's text events per 5 s window (3-7) are in the range of V21 (4-7) and dviet (4.5-6) [ƯỚC]; adding more text raises the reset count only until the hook budget (max 5 events in 0-3 s) is hit. Use a zoom step, a flash or a cut for the missing resets first.
- **Loudness.** Keep the master at the `studio_14` target and the hook gate above (-12 LUFS +/-0.5, true peak <= -1.0 dBTP after ducking). Raise weak SFX by level and layering, not by pushing the master.
- **The 10-15 s window and the V21 cut grid.** They are the strongest part of v2 and the reason it passes the pacing law there.
- **Never change a claim's source.** AI B-roll stays illustrative (R200).

---

## 6. How to use this in a build

1. Read the hook template: `studio_recipe.hook_template()` returns the events with ms offsets. Build the texts from the voice with `hook_text_from_words(words)` (lead, hero, one clause; the template texts are `null` bindings), keep the structure, never re-cut the voice.
2. Check the plan: `check_hook(plan, words=words)` (no error findings = clean) and list the product box or the stage for `hero_safe_zone`.
3. After splitting scenes into shots, check the rhythm: `check_pacing(shots, resets, duration)`; add a reset where a `max_hold` finding points.
4. Check the sources: `check_source_reuse(shots)`.
5. Render, then measure the file (audio dip, first text, hero height, motion share per 5 s) and compare with section 3. Report the measured numbers with their labels; do not report a plan check as a measurement.
