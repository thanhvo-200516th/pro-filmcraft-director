# 16 — `v5.2` Multi-Color 6-Hue System, 4-Group Secondary Typography (`S01..S18`) & Seamless Cross-Boundary Flow

> **Historical reference (v5.2).** Kept as design history; the current spec is [reference 21](./21_craft_json_minimal_spec.md) and the current process is [`SKILL.md`](../SKILL.md). Where this file disagrees with them, they win. Rule A1 and its Look S MP4 exception are stated once, in `SKILL.md` section 3.8.1.

`pro-filmcraft-director v5.2` codifies the forensic lessons from the **`V14` flagship Z-depth build** into the new **`dviet_vietanh_zdepth_master`** archetype ([`visual_archetypes_catalog.json`](../presets/visual_archetypes_catalog.json)) and upgrades all 7 archetypes across color contrast, sub-text choreography, and cross-cut velocity continuity.

## Forensic Post-Mortem: What `V14` Proved vs. What `v5.2` Solves
* **Preserved `V14` Core (`4-Layer Z-Depth Timeline Sandwich`; the code compositor has 3 planes, see [reference 13, Law 4](./13_dviet_19_videos_smooth_zoom_and_pacing_mastery.md)):**
  1. **Plane 1 (`V1`) — Living Studio Bokeh (`<= 28%` Luma):** Graded dark studio/bokeh plate clamped near `28%` luminance so skin tones and foreground accents separate cleanly without muddy crushed blacks.
  2. **Plane 2 (`V2–V3`) — `2.5D` Parallax Midground:** Hero display keywords, `clean_alpha_prop`, or structured cards tucked behind the speaker (`30–50%` torso/shoulder occlusion, `0%` `eye_band` collision).
  3. **Plane 3 (`V4–V5`) — Rim-Lit Speaker Cutout:** RVM / Clean Alpha foreground subject anchored to continuous `C²` eye-line camera motion.
  4. **Plane 4 (`V7–V8`) — Crisp Sub-Pixel NFC Overlay:** Sharp `134/134` Vietnamese secondary typography (`0.28–0.30em` top pad) and inline dual-hue spans.
* **Three `V14` Bottlenecks Eliminated in `v5.2`:**
  1. **Warm-on-Warm Monochromacy:** Repeating `#FACC15` Gold / `#FB923C` Peach headlines over warm tungsten bokeh + skin flattened chromatic pop → solved by the **6-Hue Semantic Palette (`<= 35%` hue cap + cool counter-accents)**.
  2. **Bottom-Bar Caption Monotony:** Persistent karaoke-style bottom captions competed with Plane-2 `2.5D` depth → solved by **Contextual 4-Group Secondary Text Rotation (`G1..G4` / `S01..S18`)** and banning raw `S13` karaoke by default.
  3. **Post-Cut Camera Freeze (`ds/dt = 0` at `f=0`) & Abrupt Card Cuts:** Hard-cutting from fullframe speaker to B-roll/PiP or holding static frame-0 scale broke flow → solved by **Seamless Cross-Boundary Transitions & Matched-Velocity Glide**.

---

## 1. 6-Hue Semantic Palette & Inline Dual-Hue Spans

Every Hero display word, visual block accent, and inline highlight draws from **6 calibrated semantic hues** ([`typography_hierarchy_presets.json`](../presets/typography_hierarchy_presets.json)):

| Hue Token | Hex | Semantic Beat Role | Best Background / Skin Pairing | `wonder_glow` (`Add`) |
|---|---|---|---|---|
| **`gold`** | `#FACC15` | Flagship thesis, authority takeaway, core value | Cool dark slate (`#0B0D13`); avoid stacking over warm amber bokeh | `42–56` |
| **`coral`** | `#FF4D5E` | Myth-bust, costly mistake, bottleneck, pain | Matte charcoal (`#0D0D0D` / `#111111`), `strike_myth_banner` | `40–54` |
| **`mint`** | `#2DD4BF` | Structural unlock, clean mechanism, precision fix | **Primary cool counter-accent** over warm skin & tungsten bokeh | `38–52` |
| **`cyan`** | `#38BDF8` | System architecture, AI pipeline, speed/data flow | Deep slate (`#0B0F19`) or warm studio skin for crisp separation | `38–55` |
| **`violet` / `peach`** | `#C084FC` / `#FB923C` | Creative craft, human nuance, emotional pivot | Use `#C084FC` Violet on warm plates; `#FB923C` Peach on cool plates | `40–56` |
| **`lime`** | `#4ADE80` | Verified KPI delta, growth proof, actionable CTA | Dark matte cards (`#111827`) & `metric_kpi_hero` receipts | `38–50` |

### 1.1 Hard Chromatic Diversity Gates (`chromatic_diversity`)
1. **Per-Hue Ceiling (`<= 35%`):** No single accent hue may appear on more than `35%` of emphasized beats in a video (`>= 3` distinct semantic hues required on timelines `>= 6` beats).
2. **Zero Adjacent Hero Repeats (`0`):** Beat `i` and Beat `i+1` must **never** share the same Hero accent hex.
   - *Bad (`V14` Warm Wash):* `Beat 1: #FACC15 Gold` → `Beat 2: #FACC15 Gold` → `Beat 3: #FB923C Peach` (blends into warm skin).
   - *Good (`v5.2` Semantic Arc):* `Beat 1 (Myth): #FF4D5E Coral` → `Beat 2 (Mechanism): #2DD4BF Mint` → `Beat 3 (System): #38BDF8 Cyan` → `Beat 4 (Thesis): #FACC15 Gold` → `Beat 5 (Proof): #4ADE80 Lime`.
3. **Warm-Plate Counter-Contrast:** Whenever `assets_contact_sheet.jpg` shows warm orange/amber background lights or warm skin dominance, at least `50%` of Hero accents must come from the cool triad (`#2DD4BF` Mint, `#38BDF8` Cyan, `#C084FC` Violet).

### 1.2 Inline Dual-Hue Span Markup (`[hue:phrase]`)
* **Syntax:** Embed inline chromatic emphasis inside any single phrase:
  - `"[mint:khóa] [white:kết cấu]"` (cool mechanism verb + crisp white noun)
  - `"[coral:điểm nghẽn] [white:ẩn bên dưới]"` (warning noun + neutral modifier)
  - `"[cyan:luồng tự động] [gold:3 bước]"` (dual-semantic contrast beat)
* **Linguistic & GPU Guardrails:**
  - Cap at **max `2` hues per phrase** (`1` semantic hue + `#FAFAFA` white, or `2` contrasting semantic hues on `versus` beats).
  - Normalize to Unicode `NFC` first and obey `data/text_vi.json` (`1199` `glue` pairs) so color tags never split a bisyllabic compound word across two lines.
  - Whenever parent `opacity.blend != 0`, set `drop_shadow: false` across all spans (`wgpu 0.20.1` guard inside FilmCraft `0.13.0`).

---

## 2. Contextual Rotation of All 4 Secondary Text Groups (`S01..S18`)

Secondary text is **not** a permanent subtitle strip—it is a rhythmic editorial instrument rotated across **4 functional groups**:

### 2.1 Complete `S01..S18` Group Catalog
* **`G1_lead_sub` (`S01..S09` — Lead/Sub Pairings Attached to Hero Display on `V8`):**
  - `s01_accordion_rollout_sub`: Grapheme-safe horizontal character slide (`-34px -> 0`, `32ms` stagger) tucked above/below Hero.
  - `s02_boundary_pinch_sub`: Outer-boundaries-first inward pinch (`24px -> 0` in `23f` @ 60fps) framing centered condensed titles.
  - `s03_stepup_underline_sub`: Bottom-center anchored `38% -> 100%` step-up (`+16px -> 0`) + semantic underline.
  - `s04_baseline_rise_lead`: Cropped baseline rise (`+58px -> 0`) + `16px -> 0` Gaussian deblur for clean `40–48px` lead phrases.
  - `s05_feather_wipe_lead`: `135px` linear feather wipe (`-90°`) for calm luxury/editorial reveals.
  - `s06_swivel_3d_sub`: Crisp `rot_y` `-90° -> 0°` 3D swivel badge synced to punchy Contrast/Proof kicks.
  - `s07_ghost_recede_stack`: 3-layer vertical receding ghost echo (`100% / 38% / 14%` alpha) for tension/emphasis.
  - `s08_poetic_scatter_lead`: Soft tracking expansion (`-0.04em -> +0.14em`, non-script fonts only) on reflective beats.
  - `s09_overlap_script_sub`: `SVN-Aaron Script` or `Playfair Display Italic` overlapping `15–25%` of a Condensed/Sans Hero corner.
* **`G2_quiet_bottom` (`S10..S12` — Quiet `R209` Lower-Third Captions at `Y >= 1360`):**
  - `s10_word_synced_fixed_slot_captions`: `Subtitle.tsx` zero-jump fixed-slot layout—pre-lays the full 1–2 line `text_vi.json`-glued phrase at fixed `(x, y)` coordinates while spoken words illuminate from `48%` muted `#94A3B8` to `100%` `#FAFAFA` (or semantic accent on `1` key word) at exact `words_tl.json` timestamps (`0px` horizontal reflow jump).
  - `s11_conversational_2line`: Standard `R209` top-down 2-line conversational caption (`Y in [1360, 1436]`, `-18px -> 0` rise + continuous hold micro-drift).
  - `s12_minimal_1line_quiet`: Low-profile `38–42px` single-line caption preserving chest/hand gesture breathing room.
  - **Ban `S13` (`s13_raw_karaoke_bounce`):** Bouncy per-word neon boxes/pop-scales are **strictly forbidden** unless the user explicitly asks for karaoke.
* **`G3_spatial_shoulder_arc` (`S14..S17` — Mid-Frame Spatial & Kinetic Lockups):**
  - `s14_shoulder_callout`: Left/right shoulder third (`X=240` or `X=840`, `Y=640..860`) balancing off-center speaker framing with inline `[hue:word]` highlights.
  - `s15_tilted_counter_cluster`: `-4°` to `-7°` counter-tilted kinetic lockup where the bottom sub-line enters **`-6f` before** the Hero impact to create whip anticipation.
  - `s16_bridge_anchor_swap`: Persistent anchor stem holds on `V7` while the right/lower complement swaps on `V8` (`+6f` delay) across parallel clauses (*"Không thiếu công cụ -> Chỉ thiếu cấu trúc"*).
  - `s17_circular_arc_sub_wrap`: Subtle curved halo micro-subtitle framing upper shoulder/head silhouette without touching `eye_band` (mutex with `mask_line_wipe`).
* **`G4_ui_micro_labels` (`S18` — Structured HUD, Step Pills & Authentic Badges):**
  - `s18_typewriter_tech_tag`: `JetBrains Mono` grapheme-safe typewriter tag (`1.5` graphemes/f + `8f` cursor blink) for CLI/version/system tokens.
  - `s18_active_dim_step_pills`: Progressive multi-step pill strip: active step renders at `100%` opacity + semantic hue, while **completed/previous items automatically dim to `46%` opacity** so multi-step explanations read with zero clutter.
  - `viewfinder_raw_card`: 4-corner bracket viewfinder + micro-metadata label grounding authentic camera/case-study plates.
  - `compact_glass_lock_badge`: Frosted dark glass pill locking a concise takeaway or KPI unit.

### 2.2 Genre × Beat Rotation Matrix & Anti-Clutter Mutex Rules
| Video Genre / Archetype | Primary Subtext Groups | Beat-by-Beat Rotation Recipe (`secondary_text_4group_balance`) |
|---|---|---|
| **Z-Depth Flagship (`dviet_vietanh_zdepth_master`)** | `G1` + `G3` + `G4` + `G2` (`>= 3` groups) | Hook: `2.5D` Hero + `G1` (`s01`/`s09`) → Body Contrast: `G3` (`s14`/`s15` `-6f`) → Framework: `G4` (`s18_active_dim_step_pills` `46%` dim) → Breath: `G2` (`s10`/`s12`) |
| **Tech / AI / SaaS (`tech_saas_modular`)** | `G4` + `G1` + `G2` | CLI/Diagram: `G4` (`s18_typewriter_tech_tag`, `s18_active_dim_step_pills`) → Thesis: `G1` (`s01`/`s03`) → Rapid explanation: `G2` (`s10` fixed-slot) |
| **Sales / Case-Study (`high_retention_proof`)** | `G4` + `G3` + `G1` | Receipt plate: `G4` (`viewfinder_raw_card`) → Myth/Delta: `G3` (`s15`/`s16`) + `G1` (`s02`/`s06`) → Trust CTA: `G2` (`s11`) |
| **Minimal Essay / Story (`minimal_*`, `story_*`)** | `G2` + `G1` (sparingly `G3`) | Core flow: `G2` (`s12` 1-line quiet) + `40–65%` pure A-roll silence → Key turn: `G1` (`s04`/`s05`/`s08`) or single `G3` (`s14`) |

* **Anti-Clutter Mutex (`Single Hero = 1`):**
  1. Never stack `G1` + `G3` + `G2` simultaneously on the same frame.
  2. While a heavy `visual_block` (`code_terminal_window`, `flowchart_pipeline`, `versus_split_card`, `metric_kpi_hero`) is on screen, suppress `G1` and `G3` completely; allow at most **one** `G4` micro-label or quiet `G2 s12` caption.
  3. Never repeat the exact same `S01..S18` preset on `> 2` consecutive beats.

---

## 3. Seamless Cross-Boundary Flow, Velocity Continuity & Acoustic Lead

Eliminate robotic cut boundaries by coupling optical spatial transitions, continuous camera derivatives, and pre-leading audio (`motion_continuity_and_jcut`):

### 3.1 Cross-Boundary Keyframe Mechanics (`30fps` / `60fps`)
| Transition / Continuity Primitive | Duration (`30fps` / `60fps`) | Exact Keyframe & Composite Blueprint | When to Deploy |
|---|---|---|---|
| **`PiP <-> Fullframe Smooth Morph`** | **`10–14f`** (`20–28f` @ 60fps) | Speaker cutout (`V4`) interpolates via `C²` Bezier `scale: 100% -> 40%`, `pos: (540,1060) -> (800,1420)` (or `(280,1420)`), subtle corner feather, while Plane-2 card/`screen_rec` scales `92% -> 100%` over `28%`-luma Plane-1 bokeh; reverse `10–14f` back to fullframe | Entering & exiting `screen_rec`, `code_terminal_window`, `flowchart_pipeline`, or `versus_split_card` without jarring hard cuts |
| **`Optical Depth Dissolve`** | **`10–12f`** (`20–24f` @ 60fps) | Outgoing clip blurs `0 -> 14px` + `opacity: 100% -> 0%`; incoming clip deblurs `14px -> 0px` + `scale: 105% -> 100%` (`shutter_override: true`, `180°–300°`) | Smooth spatial plane shifts, reflective B-roll entrances, or polarity transitions where a whip blur feels too harsh |
| **`Matched-Velocity Post-Cut Glide`** | **Immediate at `f=0`** (`0` dead hold frames) | Incoming clip starts with `ds/dt != 0` at `frame 0`: e.g., `scale: 104.5% (f=0) -> 109.5% (end)` (`easeOut` tangent) or `cut_kick` `102.2% (f=0) -> 100.4% (f=5)` feeding into continuous hold drift | **Mandatory on 100% of A-roll & B-roll cuts** — static `0`-velocity frame-0 holds (`100% -> 100%` before zooming) are forbidden |

### 3.2 Acoustic `J-Cut -140ms`, `2-Speed Cadence` & Pre-Swoosh Peak-on-Cut
1. **`J-Cut -140ms` Vocal Pre-Lead (`-120ms..-160ms`):**
   - Advance the incoming speech clause's breath/consonant onset **`~140ms` (`4f` @ 30fps / `8f` @ 60fps) before** the visual cut or `PiP` morph start so the viewer's brain anticipates the visual shift naturally. Use `L-Cut` (`+150..280ms`) room-tone tails when exiting emotional realizations.
2. **`2-Speed Asymmetric Speech Cadence`:**
   - Alternate **Speed A — Brisk Setup / Contrast (`1.8–2.3s` beats)** using tight `-80..120ms` inter-clause trims with **Speed B — Velvet Insight Landing (`3.2–4.2s` holds)** preserving `250–380ms` natural room-tone breath. Never cut every sentence to an identical `2.5s` metronome.
3. **`lag_ms` Pre-Swoosh Peak-on-Cut (`R217` Verified):**
   - Measure every soft air/cloth swoosh's `5ms env5` energy peak `lag_ms` and place `timeline_start = t_transition + (sync_frame / fps) - (lag_ms / 1000)` (`sync_frame = 0f` for cuts/morphs, `5f–6f` for card/Hero settles). The pre-swoosh swell rises *before* the cut, peaks cleanly within `[-1f, +2f]` (`match_at`), and decays with **zero clipped SFX tails**.

---

## 4. `.craft.json` Authoring Blueprint & `v5.2` Pre-Compile Checklist

### 4.1 Representative `dviet_vietanh_zdepth_master` Beat Spec (`.craft.json` Excerpt)
```json
{
  "meta": {
    "archetype": "dviet_vietanh_zdepth_master",
    "tier": "full",
    "claim_gate": false,
    "palette_plan": ["#FF4D5E", "#2DD4BF", "#38BDF8", "#FACC15", "#4ADE80"],
    "secondary_groups_used": ["G1_lead_sub", "G3_spatial_shoulder_arc", "G4_ui_micro_labels", "G2_quiet_bottom"]
  },
  "beat_example_zdepth_handoff": {
    "plane_1_bg": { "track": "V1", "luma_ceiling_pct": 28, "motion": "subtle_bokeh_drift" },
    "plane_2_mid": { "track": "V2", "preset": "behind_subject_z_depth", "text": "[mint:KHÓA] [white:KẾT CẤU]", "occlusion_ratio": 0.38 },
    "plane_3_fg": { "track": "V4", "source": "speaker_rvm_alpha", "camera": "matched_velocity_post_cut_glide", "j_cut_ms": -140 },
    "plane_4_sub": { "track": "V8", "group": "G1_lead_sub", "preset": "s01_accordion_rollout_sub", "text": "Bí quyết giữ chân 3 giây đầu" },
    "next_transition": { "type": "pip_fullframe_smooth_morph", "frames_30fps": 12, "sfx_sync_frame": 0 }
  }
}
```

### 4.2 8-Point `v5.2` Director Self-Audit Before Running `compile_and_verify.py`
1. **Bokeh & Skin Separation:** Is Plane-1 background luma clamped `<= 28%` on Z-depth shots, and are warm skin/amber frames paired with cool `Mint (#2DD4BF)` / `Cyan (#38BDF8)` / `Violet (#C084FC)` accents?
2. **Chromatic Quota (`<= 35%`):** Does every accent hue stay `<= 35%` of total emphasized beats with **`0` adjacent Hero hue repeats**?
3. **Inline Dual-Hue Integrity:** Do all `[hue:phrase]` tags contain `<= 2` hues, normalized `NFC` Vietnamese, `0` fractured `text_vi.json` `glue` compounds, and `drop_shadow: false` if `blend != 0`?
4. **4-Group Subtext Rotation:** Did the timeline rotate across **`>= 2` groups** (`>= 3` for `dviet_vietanh_zdepth_master`) with **`0` raw `S13` karaoke** and `<= 2` consecutive uses of the same `S01..S18` preset?
5. **Step-Pill & Fixed-Slot Polish:** Do `s18_active_dim_step_pills` dim completed items to **`46%` opacity**, and does `s10_word_synced_fixed_slot_captions` hold `0px` horizontal jump at `Y >= 1360` (`R209`)?
6. **Zero Frame-0 Camera Freeze:** Does every post-cut clip launch with non-zero velocity (`ds/dt != 0` at `f=0`) via `matched_velocity_post_cut_glide` or `cut_kick`?
7. **Smooth Spatial Bridges:** Are abrupt card/screen-recording cuts replaced by `10–14f` `PiP <-> Fullframe` `C²` morphs or `10–12f` `Optical Depth Dissolves` (`shutter_override: true`)?
8. **Acoustic Lead & Tail Integrity:** Are incoming thoughts pre-led with `J-Cut -140ms`, paced in `2-speed asymmetric cadence`, and paired with `lag_ms` peak-on-cut swooshes (`R217` `[-1f, +2f]`, `0` clipped tails)?
