# 17 — `v6.0` `@__dviet` Era-2 Manifesto Architecture (`7707` Forensics, Color-World Polarity, 4-Cut Grammar & `MAX_ZONES = 2`)

`pro-filmcraft-director v6.0` codifies the **4-Agent Forensic Audit of `@__dviet` `7707653827016674580` (*MagentX Era-2 Manifesto*)** alongside the 19-video corpus (`7706`, `7693`, `7688`), introducing flagship archetype **`dviet_era2_7707_manifesto`** ([`visual_archetypes_catalog.json`](../presets/visual_archetypes_catalog.json)) and upgrading [`compile_and_verify.py`](../scripts/tools/compile_and_verify.py) to `v6.0`.

### Forensic Post-Mortem: The 4 Validator Anti-Patterns Fixed in `v6.0`
| `v5.2` Validator Anti-Pattern | Why It Outlawed `@__dviet` `7707` Mastery | `v6.0` Compiler & Director Law |
|---|---|---|
| **1. `100%` `wgpu` Transition Mandate** (`edit_rules` C1) | Forced artificial wipes/flashes onto every V1 cut, creating `OVER_TRANSITIONED_SPAM` | **`4-Cut Grammar` (`dviet_4cut`):** `40%–75%` intentional `0f` Clean Hard Cuts; cap heavy `wgpu` transitions at `<= 45%` |
| **2. Monomodal `C7` (`[0ms..+90ms]` only)** | Outlawed `@__dviet`'s signature `-250ms..-650ms` vocal pre-leads across camera/canvas cuts | **Bimodal `C7` Adjudicator:** Passes `[0..+120ms]` post-cut leads **AND** `[-850ms..-140ms]` True Vocal `J-Cuts` (still fails `[-130ms..-10ms]` sloppy chops!) |
| **3. Mandatory `6-Hue <= 35%` Rotation** | Forced 4–6 competing neon colors into one short (`RAINBOW_HUE_SOUP`) | **`color_world_polarity` (Default):** **1 Primary Signature Hue (`55%–100%`) + `0–1` Pain Hue (`0%–45%`)** + Light/Dark Polarity Flips (`multi_hue_6` is opt-in) |
| **4. `4/4` Subtext Quota & Unchecked Card Overlap** | Stacked Hero + Shoulder + Bottom Caption + Graphic Card simultaneously | **`MAX_ZONES = 2` (`3` w/ `<= 30pt` Whisper `G2`), `CARD_TEXT_COLLISION = 0`**, `1–3` curated secondary groups, `>= 12%` clean breathing frames |

---

## 1. Asymmetric 3-Cam `1/3` Framing & Full-Screen Motion Canvases

Era-2 `@__dviet` replaces boxed PNG stickers over centered talking heads with **architectural negative space** and **100% full-screen tactile motion stages** ([`dviet_motion_canvas_engine.py`](../scripts/dviet_motion_canvas_engine.py)):

1. **Asymmetric 3-Camera Spatial Grammar ([`dviet_smooth_camera_engine.py`](../scripts/dviet_smooth_camera_engine.py)):**
   - **Cam A — Center Authority (`X = 540`):** Reserved for opening hooks, emotional vulnerability, and final thesis landings (`0` heavy side clutter).
   - **Cam B — Left-`1/3` Speaker (`X ≈ 300..360`) + Right-`2/3` Open Wall (`X ≈ 640..880`):** Dedicates two-thirds of the frame to lowercase wall micro-word pops (`dviet_wall_microword_pop`).
   - **Cam C — Right-`1/3` Speaker (`X ≈ 720..780`) + Left-`2/3` Open Wall (`X ≈ 200..440`):** Counter-balances Cam B across crisp `0`-frame hard cuts or vocal `J-Cuts`.
2. **4 Full-Screen Living Motion-Design Stages (`dviet_motion_canvas_engine.py`):**
   - `render_timeline_playhead_stage`: 3D glass NLE timeline + live waveform + sweeping playhead + optional `1x -> 24x` iris polarity flip.
   - `render_concentric_lock_lab_stage`: Tactile `#EEF4EA` mint-cream / archival paper lab with CAD hairlines and concentric specimen lock at `(540, 920)`.
   - `render_giant_numeral_3d_ui_stage`: Wavy obsidian silk + `210px` structural numeral + `rotY=-11°, rotX=+5°` 3D glass prompt window + optical edge DoF.
   - `render_bento_kinetic_matrix_stage`: Perspective 3D frosted bento grid illuminating active beat tiles at `100%` against `32%` depth-dimmed siblings.
   - All 4 stages embed a `6%–9%` opacity blurred kinetic watermark (`180–280px` lowercase geometric sans drifting `-18px`) and stream in `< 150MB` RAM.

---

## 2. `1 Color World + Polarity Flip` (`DVIET_COLOR_WORLDS`)

Every `v6.0` video commits to **one cohesive Color World** ([`typography_hierarchy_presets.json`](../presets/typography_hierarchy_presets.json) & [`typography_composer.py`](../scripts/tools/typography_composer.py)):

| Color World ID | Primary Signature (`55–100%`) | Pain / Contrast (`0–45%`) | Dark Canvas (`Luma 8–12%`) | Polarity Light Canvas (`Luma 88–94%`) | Dark Ink on Light |
|---|---|---|---|---|---|
| **`emerald_cream_7707`** | `#2EE86E` Emerald | `#FF4D5E` Coral | `#081C15` Deep Forest | `#EEF4EA` Mint-Cream | `#111827` / `#166534` |
| **`amber_cinema_7706`** | `#F5B932` Warm Gold | `#FF4D5E` Coral | `#120E0A` Espresso Silk | `#FAF6EC` Archival Cream | `#1C1917` / `#92400E` |
| **`violet_aurora_7693`** | `#A855F7` Violet | `#F43F5E` Rose | `#120924` Midnight Violet | `#F5F3FF` Lavender Paper | `#1E1B4B` / `#4C1D95` |
| **`obsidian_cyan_7688`** | `#38BDF8` Ice Cyan | `#F43F5E` Rose | `#0B0D11` Obsidian Slate | `#F1F5F9` Cool Alabaster | `#0F172A` / `#0369A1` |

* **Chromatic Compiler Gates (`audit_chromatic_diversity`):**
  - **Default (`color_policy: "color_world_polarity"`):** `PASS` when accented Heroes stay in `1` Primary Hue (`55%–100%`) + `0–1` Pain Hue (`0%–45%`). Flags **`RAINBOW_HUE_SOUP`** whenever `>= 5` distinct neon hue buckets appear in a single video (`COLOR_WORLD_FRAGMENTED` if `3–4` Hero hues dilute primary `< 55%`), and logs `polarity_light_clips_or_frames`.
  - **Legacy Opt-In (`color_policy: "multi_hue_6"`):** Preserves `v5.2` `<= 42%` multi-hue rotation only when explicitly requested by the user.

---

## 3. Lowercase Negative-Leading Typography & `MAX_ZONES = 2` Spatial Cap

1. **Lowercase `0.78` Kiss Mode, 3D Bevel & `>= 2.6x` Scale Ratio:**
   - At least **`70%` of Hero display beats** in `dviet_era2_7707_manifesto` use **editorial lowercase or sentence case** (`100%` ALL-CAPS triggers `ALL_CAPS_HERO_OVERUSE`).
   - Pair oversized Hero words (`78–138px`, `line_height: 0.78` tight kiss mode with `padding_top_em: 0.30` NFC diacritic guard + subtle 3D bevel highlight) against micro leads/captions (`26–44px`, **`scale_ratio >= 2.6x`**).
   - Deploy `dviet_wall_microword_pop` (`1–3` lowercase words popping into the open `2/3` wall) and `dviet_two_point_wall_hop` for brisk clause pairs.
2. **`100ms` Spatial Density & Card-Text Mutex (`audit_secondary_text_groups`):**
   - **Hard Cap `MAX_ZONES = 2`:** Across every `100ms` slice of the timeline, at most **`2` distinct overlay zones** may be active simultaneously (`3` allowed **only** when `G2_quiet_bottom` uses whisper `<= 26–30pt` `s12_whisper_26pt_sub`). Exceeding this for `> 15%` of duration triggers **`FRAME_CLUTTER_OVERLOAD`**.
   - **`CARD_TEXT_COLLISION = 0`:** Graphic `card*` / `gfx*` / `prop*` bounding boxes are checked against `Hero`, `G1`, `G2`, `G3`, and `G4` text ink boxes; any collision triggers `CARD_TEXT_COLLISION`.
   - **Curated `1–3` Secondary Groups & `>= 12%` Breathing Room:** Select `1–3` secondary groups that fit the script (never force `4/4` groups) and leave `>= 12%` of frames completely free of overlays.

---

## 4. `4-Cut Grammar`, Bimodal `C7` `True Vocal J-Cut` & `Music Stop Vacuums`

### 4.1 Cut-Lead Bimodal Adjudication Windows (`t_voice_in - t_visual_cut`)
| Acoustic-Visual Cut Window | Offset (`t_voice_in - t_visual_cut`) | `v6.0` Compiler Verdict | Editorial Meaning |
|---|---|---|---|
| **True Vocal `J-Cut`** | **`[-850ms, -140ms]`** *(target `-250..-650ms`)* | **`PASS`** *(re-adjudicates `edit_rules` C1 & C7)* | Incoming thought begins over outgoing visual, pulling eye cleanly across cut |
| **Sloppy Mid-Syllable Chop** | **`[-130ms, -10ms]`** | **`FAIL / WARN`** (`SLOPPY_MID_SYLLABLE_CUT`) | Accidental mid-consonant clip chop — never forgiven |
| **Standard Post-Cut Lead** | **`[0ms, +120ms]`** | **`PASS`** | Crisp new-act entrance right after visual cut |

### 4.2 4-Cut Quota, `meta.bgm_stops` Vacuums & Audio Restraint
1. **`4-Cut Grammar` (`dviet_4cut`):** `55%–75%` (`40%–75%` gate) Clean `0`-Frame Hard Cuts + True Vocal `J-Cuts` + `1–3` Polarity/Canvas Cuts + `<= 35%–45%` `wgpu` transitions (`> 45%` triggers `OVER_TRANSITIONED_SPAM`).
2. **Music Stop Vacuum Windows (`meta.bgm_stops`):** Gate 1 automatically splits/carves `bgm` & `drone` clips around every `[start_s, end_s]` window (`>= 0.50s` true `-inf dB` digital silence vacuum with a crisp `35ms` pre-stop fade-out and beat-aligned re-entry).
3. **Whoosh Restraint (`<= 5/min`) & Vocal Warmth (`+2.2 dB @ 185Hz`):** Heavy whoosh/impact SFX `> 6/min` triggers `WHOOSH_OVERLOAD`; set `meta.vocal_chest_warmth: true` (or `--vocal-chest-warmth`) for `75Hz` HPF + `+2.2 dB @ 185Hz` (`Q=1.15`) vocal body.

---

## 5. `v6.0` `.craft.json` Blueprint & 8-Point Pre-Compile Checklist

```json
{
  "meta": {
    "archetype": "dviet_era2_7707_manifesto",
    "tier": "full",
    "color_policy": "color_world_polarity",
    "color_world": "emerald_cream_7707",
    "cut_grammar": "dviet_4cut",
    "bgm_stops": [[6.80, 7.45], [18.20, 18.90]],
    "polarity_flips": [[11.40, 14.10]],
    "vocal_chest_warmth": true,
    "claim_gate": false
  },
  "beat_example_era2_wall_pop": {
    "framing": "left_third_speaker_x330",
    "wall_pop": { "preset": "dviet_wall_microword_pop", "text": "[#2EE86E:không thiếu]\ncông cụ", "line_height": 0.78, "size": 92 },
    "whisper_sub": { "group": "G2_quiet_bottom", "preset": "s12_whisper_26pt_sub", "size": 26, "y": 1440 },
    "cut_bridge": { "type": "clean_0f_hard_cut", "true_vocal_jcut_ms": -340 }
  }
}
```

### 8-Point `v6.0` Director Self-Audit
1. **1 Color World:** `55%–100%` Primary Signature Hue + `<= 45%` Pain Hue (`< 5` buckets; `0` `RAINBOW_HUE_SOUP`)?
2. **Polarity Contrast:** `1–3` full-screen `#EEF4EA` / `#FAFAFA` polarity flips or living motion stages from [`dviet_motion_canvas_engine.py`](../scripts/dviet_motion_canvas_engine.py)?
3. **Lowercase Kiss Hierarchy:** `>= 70%` lowercase/mixed-case Heroes (`line_height: 0.78`, `scale_ratio >= 2.6x`, `0` `ALL_CAPS_HERO_OVERUSE`)?
4. **Spatial Density (`MAX_ZONES <= 2`):** `<= 2` active overlay zones (`3` only w/ `<= 26–30pt` whisper `G2`) and `0` `CARD_TEXT_COLLISION`?
5. **Curated Subtext & Breathing:** `1–3` secondary groups (never forced `4/4`) + `>= 12%` zero-overlay breathing frames?
6. **4-Cut Quota:** `40%–75%` clean `0`-frame hard cuts (`<= 45%` `wgpu` transitions; `0` `OVER_TRANSITIONED_SPAM`)?
7. **Bimodal `C7` J-Cuts:** Vocal pre-leads cleanly in `[-850ms, -140ms]` (`0` sloppy chops in `[-130ms, -10ms]`)?
8. **Music Stops & Restraint:** `1–2` `meta.bgm_stops` (`>= 0.50s` `-inf dB` vacuum), `<= 5` heavy whooshes/min, and `.fcproj` native handoff (Rule A1)?

---

## 6. `v6.0` Compiler Gate Diagnostic Codes & Self-Repair Matrix

| Diagnostic Code | Trigger Condition in `compile_and_verify.py` (`v6.0`) | Immediate Self-Repair Fix |
|---|---|---|
| **`RAINBOW_HUE_SOUP`** | `>= 5` distinct neon/accent hue buckets under `color_world_polarity` | Re-tint accents into `1` Primary Signature Hue (`55%–100%`) + `<= 1` Pain Hue (`<= 45%`) |
| **`COLOR_WORLD_FRAGMENTED`** | `3–4` Hero accent buckets dilute primary hue `< 55%` in `dviet_*`/`minimal_*`/`story_*` | Collapse extra Hero hues into your chosen `DVIET_COLOR_WORLDS` primary + pain pair |
| **`OVER_TRANSITIONED_SPAM`** | `> 45%` of V1 cuts carry heavy `wgpu` transitions in Era-2 / Z-Depth master modes | Strip wipes on intra-thought cuts; let `55%–75%` breathe as `0f` hard cuts or vocal `J-Cuts` |
| **`SLOPPY_MID_SYLLABLE_CUT`** | Voice clip or unbridged word onset lands in `[-130ms, -10ms]` relative to V1 cut | Shift cut `1–2f` earlier (`0..+90ms` post-cut) or extend pre-lead to `[-650ms..-140ms]` |
| **`WHOOSH_OVERLOAD`** | Heavy whoosh/impact SFX exceed `6.0/min` in `dviet_era2` mode | Delete filler whooshes; reserve `<= 5/min` hits for polarity flips and Music Stop drops |
| **`CARD_TEXT_COLLISION`** | Active `card*`/`gfx*`/`prop*` bbox overlaps any `Hero`/`G1..G4` text ink bbox | Suppress `G1/G3` text during graphic cards or drop whisper `G2` below card bottom |
| **`FRAME_CLUTTER_OVERLOAD`** | Active overlay zones exceed `2` (`3` w/ `<= 30pt` whisper `G2`) for `> 15%` of duration | Trim overlapping layers so every `100ms` slice holds `<= 2` distinct visual zones |
| **`ALL_CAPS_HERO_OVERUSE`** | `100%` of Hero display clips are ALL-CAPS in `dviet_era2` mode | Convert `>= 70%` of Hero phrases to editorial lowercase/mixed case (`line_height: 0.78`) |

### `v6.0` CLI Invocation (`compile_and_verify.py`)
```bash
~/.venvs/video-skills/bin/python3 ./scripts/tools/compile_and_verify.py \
  --spec work/project.craft.json --out out/project.fcproj --work work \
  --words work/words_tl.json --archetype dviet_era2_7707_manifesto \
  --color-policy color_world_polarity --vocal-chest-warmth --tier full
```
