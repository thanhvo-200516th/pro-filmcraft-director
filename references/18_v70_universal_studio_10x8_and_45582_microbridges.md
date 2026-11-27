# 18 — `v7.0` Universal Studio Director: `45,582`-Frame `@__dviet` Micro-Bridges, 3-Lane Web-Cinema Orchestration & Orthogonal `10×8` Matrix

> **Historical reference (v7.0).** Kept as design history; the current spec is [reference 21](./21_craft_json_minimal_spec.md) and the current process is [`SKILL.md`](../SKILL.md). Where this file disagrees with them, they win. Rule A1 and its Look S MP4 exception are stated once, in `SKILL.md` section 3.8.1.

`pro-filmcraft-director v7.0` (**Universal Studio Director**) synthesizes the native-frame forensic audit of **`45,582` frames across the 19 `@__dviet` master videos of the v7.1 pass** (17 have evidence files in [`dviet_19/`](./dviet_19/INDEX.md)) (`60fps` & `30fps` native streams) with a **3-Lane Render Architecture** and an **Orthogonal `10 Format Modes × 8 Industry Skins` Matrix** (`80` canonical studio profiles & `240+` hybrid variants).

## Forensic Post-Mortem: What `v7.0` Permanently Abolishes from `v6.0`
| `v6.0` Failure Mode | Why It Failed Studio Quality Inspection | `v7.0` Universal Studio Director Law |
|---|---|---|
| **1. `PIL/OpenCV` 3D Bevel Extrusion & Flat Box Cards** | Raster pixel-offset "3D bevels" and `cv2.rectangle` cards look like cheap plastic stickers with jagged kerning and dead edges | **PERMANENT BAN (`NO_PIL_PLASTIC_BEVEL`).** Route typography/UI plates to **Lane B** ([`web_plate_builder.py`](../scripts/tools/web_plate_builder.py): Headless Chrome `HTML5/CSS3/SVG @2x DPR` → RGBA PNG / ProRes 4444) with `0px` hard stroke |
| **2. Swampy Green Wall LUT Poisoning Skin Tones** | Pushing global emerald/green tint onto warm indoor walls dragged Asian skin tones into sickly olive/swamp-green | **PERMANENT BAN (`Skin-Tone Guard`).** Protect skin vectorscope line (`105°–135°`); separate subject from clean `#081C15` / `#FAFAFA` / `#EEF4EA` plates or neutral architectural walls |
| **3. Floating Mid-Face / Crown-Clipping Text** | Center-floating Heroes grazed hair crowns, foreheads, or gesturing fingers with harsh cutout halos | **`Cranial Lock` (`0%` face/hair overlap) + `Dual-Rail 9:16`** (`Upper Editorial Stage` × `Chest Tactile Rail` tucked behind RVM hands with **`Sub-layer Feather Mask = 29`**, `0px` hard stroke) |
| **4. Rigid Single-Hue Lock Blocking Clean `#FAFAFA` Chapter Videos** | Strict 1-hue lock prevented high-trust white-paper/educational videos from color-coding 4 distinct narrative chapters | **Dual Chromatic Policy:** **`color_world_polarity`** *AND* **`semantic_4act_jewel`** (4-Act Emotional Jewel Palette on `#FAFAFA` — 1 jewel ink per chapter, `0` intra-sentence rainbow soup) |
| **5. Coupled Genre Archetypes** | Pacing/cut topology was glued to a single aesthetic palette, causing cross-industry friction (e.g., moody dark LUTs on Dental or Nail reels) | **Orthogonal `10×8` Matrix:** Decouple **`Format Mode (F1..F10)`** from **`Industry Skin (S1..S8)`** ([`format_modes_catalog.json`](../presets/format_modes_catalog.json)) with domain **`HARD VETO`** circuit breakers |

---

## 1. Six Laws of Professional Editorial Thinking (`45,582`-Frame Forensics)

1. **Law 1 — Invisible Continuity Over Decorative Transition Spam (`Che Vết Cắt Bằng Quang Học & Điểm Neo Mắt`):**
   Great cuts hide inside human perception rather than advertising themselves with `wgpu` wipes. Combine `0f` clean hard cuts (`40%–75%`), `[-850ms..-140ms]` vocal `J-Cuts`, `13f` rack-focus bridges, `5–6f` optical flow morphs, and `2f/11f` persistent text anchors so the viewer's fovea stays locked while camera scale or canvas polarity flips underneath.
2. **Law 2 — `Cranial Lock` & `Dual-Rail 9:16` Z-Depth Sandwich (`Khóa Đỉnh Đầu & Đường Ray Kép`):**
   Typography **never** touches the speaker's face, eyes, mouth, or hair crown (`CRANIAL_LOCK = 0%` overlap). Every `9:16` (`1080×1920`) overlay commits to one of two physical rails:
   - **Rail 1 — `Upper Editorial Stage` (`Y ∈ [220, 520]`):** Strictly above the crown of the head inside clean architectural headroom (or open `2/3` wall when speaker is framed at `1/3` `X ≈ 320` or `760`).
   - **Rail 2 — `Chest Tactile Rail + RVM Hand-Over-Text` (`Y ∈ [960, 1340]`):** Tucked at sternum/chest level *behind* gesturing hands/forearms via RVM foreground alpha (`Sub-layer Feather Mask = 29`, `0px` hard stroke), paired with quiet whisper `G2` at `Y ∈ [1360, 1460]` (`R209`).
3. **Law 3 — Physical Optics & Web-Vector Typography Over Raster Tricks (`Quang Học Vật Lý & Vector @2x DPR`):**
   Authenticity comes from browser-grade optical kerning (`CSS3` `font-feature-settings`, `SVG` hairlines, backdrop blur, subtle multi-stop ambient occlusion shadows rendered at `@2x DPR` `2160×3840`), `4f+28f` filmic halation decay, and `3f` exposure bloom landings — **never** `PIL/OpenCV` extruded plastic bevels or hard `stroke_width > 0` cartoon outlines.
4. **Law 4 — Asymmetric Air-Cushion Kinematics (`Đệm Khí Bất Đối Xứng Player-3 20f`):**
   Every camera reframe, PiP morph, and plate entrance launches with non-zero initial velocity at `f=0` (`ds/dt != 0`) and decelerates along the **`Player 3 20f Air-Cushion Bezier`** (`72%` travel in the first `6f`, `28%` feather-soft settle over the remaining `14f` @ 60fps). Linear pans and dead `f=0` static holds are forbidden.
5. **Law 5 — Acoustic Vacuum Contrast & Organic Foley Tactility (`Chân Không Âm Thanh & 7 Foley Hữu Cơ`):**
   Perceived punch comes from **silence before impact**, not louder compression. Carve `-inf dB` BGM vacuums (`>= 0.50s`, `35ms` pre-fade) ahead of thesis landings or `140+ BPM` beat drops, and anchor motion in **7 Organic Foley SFX** rather than synthetic laser/whoosh spam (`<= 5` heavy whooshes/min).
6. **Law 6 — Orthogonal `Format × Skin` Decoupling & Domain `HARD VETO` Gates (`Kiến Trúc Trực Giao 10×8`):**
   Narrative cut structure (`F1..F10`) and industry optical/compliance rules (`S1..S8`) are independent axes. Domain safety guards (`CRI-100 Tooth Lock`, `Skin-Tone Guard`, `Hand Safe-Box`, `Cranial Lock`, `R200 Claim-Gate`) hold absolute **HARD VETO** authority over any aesthetic preset.

---

## 2. The 14 Frame-Exact Micro-Bridge & Optical Formulas (`45,582` Native Frames)

All frame counts below are specified at **native `60fps`** (`1f = 16.67ms`), with exact **`30fps` equivalents** (`1f = 33.33ms`) in parentheses:

| # | Micro-Bridge ID (`micro_bridges_v70`) | Frame Math (`60fps` / `30fps`) | Exact Physics, Curve & Layer Execution | When to Deploy |
|---|---|---|---|---|
| **01** | **`player3_air_cushion_20f`** *(Player 3 20f Air-Cushion Bezier)* | **`20f`** (`333ms`) / `10f` | `cubic-bezier(0.16, 1.0, 0.30, 1.0)`: `f0→f6` covers `72%` of scale/Y delta; `f6→f20` glides the final `28%` on an asymptotic air cushion (`ds/dt != 0` at `f=0`) | Default arrival curve for Lane-B Web Plates, asymmetric `1/3` camera reframes, and `Chest Tactile Rail` hero entrances |
| **02** | **`rack_focus_13f`** *(13f Camera Rack-Focus Hidden Cut)* | **`5f` pre + `8f` post = `13f`** (`217ms`) / `2f+4f` | Outgoing clip ramps lens blur `0 → 18px` + scale `1.00 → 1.055x` over `5f`; `0f` cut fires at peak defocus; incoming clip snaps `18 → 0px` blur + settles `1.04 → 1.00x` over `8f` | Hiding A-roll jump cuts or bridging A-roll into macro product/clinic B-roll without `wgpu` wipe spam |
| **03** | **`persistent_text_bridge_11f`** *(2f/11f Persistent Text Bridge)* | **`-2f` pre-lead → `+11f` post-hold** / `-1f → +6f` | Anchor keyword/plate spawns **`2f` before** the V1 cut (or persists across the cut for **`+11f`** into the incoming shot) at identical `(X, Y)` screen coordinates | Cross-cam (`Cam B ↔ Cam C`) cuts and Dark ↔ `#FAFAFA` Polarity Flips so eye fixation masks the cut |
| **04** | **`exposure_bloom_3f`** *(3f Exposure Bloom Landing)* | **`1f` rise + `2f` decay = `3f`** (`50ms`) / `1f+1f` | Soft highlight-shoulder exposure lift (`+0.38 EV` peak at `f=0`, `+0.18 EV` at `f+1`, `0.0 EV` at `f+2`) restricted to luma `> 0.65` (never full-frame whiteout) | Sealing high-contrast polarity flips, `Before -> After` reveals, and key KPI receipts |
| **05** | **`sublayer_feather_mask_29`** *(Sub-layer Feather Mask = 29)* | Continuous spatial alpha (`r = 29px` @ `1080p`) | RVM foreground occlusion mask feathered at **`29px` Gaussian/guided radius** on `1080×1920` with **`0px` hard stroke** (`stroke_width = 0`) on sandwiched typography | Every `Chest Tactile Rail` (`Hand-Over-Text`) and `Upper Stage` depth sandwich — eliminates cardboard cutout edges |
| **06** | **`pre_echo_rotoscope_strobe_2f`** *(33.3ms Pre-Echo Rotoscope Strobe)* | **`2f` (`33.3ms`)** @ 60fps / `1f` @ 30fps | At `t_cut - 33.3ms`, composite incoming RVM subject silhouette (`32%–38%` alpha, `+1.04x` scale or rim outline) over outgoing background for `2f`, then lock `100%` solid subject at `t_cut` | Hook transitions (`< 3.0s`), beat-drop entries (`F10`), and dynamic creator authority entrances (`S6`) |
| **07** | **`optical_flow_morph_6f`** *(5–6f Optical Flow Morph)* | **`5–6f`** (`83–100ms`) / `3f` | Bidirectional optical-flow pixel interpolation across `5–6f` when speaker head yaw/pitch delta `< 12°` and torso translation `< 45px` | Eliminating micro-breath / filler-removal jump cuts (`ờ/à`) in continuous single-cam monologues (`F1`, `F6`, `F7`) |
| **08** | **`mirror_tile_whip_3d_ui_19f`** *(19f Mirror-Tile Whip -> 3D UI)* | **`7f` whip + `12f` 3D settle = `19f`** / `3f+6f` | `7f` exponential lateral/zoom whip with mirrored edge tiles + `270°` directional blur → cut into `12f` perspective `rotY=-11°→-6°, rotX=+5°→+2°` Lane-B/C 3D UI stage | Transitioning from talking-head claim into SaaS dashboard, BĐS floorplan, or curriculum module (`F9`, `S5`, `S8`) |
| **09** | **`halation_decay_4_28f`** *(4f+28f Halation Decay)* | **`4f` attack + `28f` decay = `32f`** (`533ms`) / `2f+14f` | Warm/signature optical halation blooms around high-contrast Hero glyphs or specular highlights over `4f` (`67ms`), then decays exponentially across `28f` (`467ms`) | Poetic manifestos (`F1`), luxury skincare/salon gloss (`S1`, `S3`), and cinematic short vlogs (`F8`, `S7`) |
| **10** | **`concentric_negative_bridge`** *(Concentric Match + Negative Bridge)* | **`1–2f` negative flash + `18f` lock** | Lock focal geometry at `(540, 920)` across shot A → invert luma (`Difference`/`Negative` polarity bridge) for `1–2f` → resolve onto `#EEF4EA` / `#FAFAFA` light lab plate | High-retention pattern interrupts and `Concentric Lock Lab` thesis pivots (`dviet_era2_7707_manifesto`) |
| **11** | **`silence_vacuum_140bpm_drop`** *(Silence Vacuum -> 140+ BPM Beat Drop)* | **`>= 30f` (`0.50s`) `-inf dB` → `f=0` drop** | `35ms` (`2f`) clean cosine pre-fade into true `-inf dB` BGM/drone digital vacuum during setup clause → `140+ BPM` downbeat slams back at `f=0` of visual reveal | Kinetic reels (`F10`), contrarian myth-bust reveals (`F3`), and flagship hook-to-thesis drops |
| **12** | **`organic_foley_7_pack`** *(7 Organic Foley SFX)* | `5ms` `env5` `lag_ms` (`[-1f, +2f]` `R217`) | **7 Tactile Foley Archetypes:** (1) `archival_paper_slide`, (2) `mech_key_tactile_tick`, (3) `leica_shutter_click`, (4) `muted_felt_thud`, (5) `crystal_glass_ping`, (6) `linen_cloth_brush`, (7) `soft_air_puff` — `100%` unclipped natural tails | Replacing synthetic sci-fi whooshes across Web-Cinema card entrances, step pills, and micro-word pops |
| **13** | **`bimodal_vocal_jcut_deep`** *(Deep Vocal J-Cut Bridge)* | **`-15f .. -39f`** (`-250ms .. -650ms`) | Incoming audio thought starts `250–650ms` over outgoing shot; visual `0f` cut lands precisely on incoming stressed noun/verb (`[-130ms, -10ms]` mid-syllable chops banned) | Seamless narrative momentum across `4-Cut Grammar` (`F1`, `F2`, `F7`) |
| **14** | **`dual_rail_hand_parallax`** *(RVM Hand-Over-Text Parallax)* | Continuous `C²` `-14px..+14px` counter-drift | `Plane-2` Lane-B plate in `Y ∈ [960, 1340]` counter-drifts `0.35×` inverse camera pan underneath `Plane-3` RVM hands (`Feather = 29`), while `Cranial Lock` guards `Y_head` | Studio authority reels (`S6`, `F1`, `F2`) where tactile depth replaces top-heavy banner clutter |

---

## 3. Three-Lane Render Orchestration (`Lane A` + `Lane B` + `Lane C`)

`v7.0` routes every visual element to the exact rendering engine built for its physics — **never forcing NLE text nodes to fake complex UI, and never using `PIL/OpenCV` to draw fake 3D typography**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                        UNIVERSAL STUDIO DIRECTOR v7.0 — 3-LANE ROUTER                    │
├───────────────────────────┬───────────────────────────────┬──────────────────────────────┤
│ LANE A — NLE Native       │ LANE B — Web-Cinema Plates    │ LANE C — Motion Stages       │
│ (FilmCraft .fcproj wgpu)  │ (web_plate_builder.py @2x)    │ (HyperFrames / EffectCraft)  │
├───────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ • V1–V8 / A1–A8 timeline  │ • Headless Chrome HTML5 +     │ • Full-screen 60fps living   │
│ • C² Air-Cushion zooms    │   CSS3 + Inline SVG @2x DPR   │   stages (dviet_motion_      │
│ • 13f Rack-Focus & 0f cut │   (2160×3840 → 1080×1920)     │   canvas_engine / .ecproj /  │
│ • RVM Feather=29 sandwich │ • RGBA PNG / ProRes 4444      │   HyperFrames GSAP/WebGL)    │
│ • Whisper G2 & S01..S18   │   (yuva444p10le) alpha plates │ • 19f Mirror-Tile -> 3D UI   │
│ • BGM vacuum & -14/-16LUFS│ • Editorial Kiss Type, Bento  │ • Concentric Lock Lab &      │
│ • 7 Organic Foley sync    │   Glass Cards, KPI & SVG Flow │   Timeline Playhead Stages   │
└───────────────────────────┴───────────────────────────────┴──────────────────────────────┘
```

### 3.1 Chromatic Architecture: `color_world_polarity` + `semantic_4act_jewel`
1. **Mode 1 — `color_world_polarity` (Signature Dark ↔ Cream Polarity):**
   - `55%–100%` Primary Signature Hue + `0%–45%` Pain/Contrast Hue from `DVIET_COLOR_WORLDS` (`emerald_cream_7707`, `amber_cinema_7706`, `violet_aurora_7693`, `obsidian_cyan_7688`) + `1–3` full-screen `#EEF4EA` / `#FAFAFA` polarity flips.
2. **Mode 2 — `semantic_4act_jewel` (4-Act Emotional Jewel Palette on `#FAFAFA` / Archival Light):**
   - Designed for clean editorial, educational, medical, and personal-brand chapter videos on crisp `#FAFAFA` / `#F8FAFC` light surfaces (or clean studio A-roll) with `#0F172A` primary ink:
     - **Act I (Hook / Curiosity):** Deep Emerald / Teal (`#059669` / `#0D9488`)
     - **Act II (Mechanism / Logic):** Royal Sapphire / Cobalt (`#2563EB` / `#1D4ED8`)
     - **Act III (Friction / Warning / Myth):** Crimson Ruby / Rose (`#E11D48` / `#BE123C`)
     - **Act IV (Resolution / Proof / CTA):** Warm Amber / Burnished Gold (`#D97706` / `#B45309`)
   - **Anti-Soup Invariant:** Colors shift **strictly across narrative acts/chapters (`<= 1` jewel accent per beat)** — **never** 4–6 neon hues inside the same sentence!

---

## 4. Orthogonal `10 Format Modes × 8 Industry Skins` Matrix (`80` Canonical / `240+` Hybrids)

### 4.1 Axis 1 — `10 Format Modes` (`F1..F10` in [`format_modes_catalog.json`](../presets/format_modes_catalog.json))
| ID | Format Mode Slug (`format_modes_catalog.json`) | ASL (`s`) | Default / Compatible Lanes | Core Cut & Micro-Bridge Signature |
|---|---|---|---|---|
| **`F1`** | `expert_talking_head` | `1.8–3.8` | `lane_a_native` (+ `B`) | Asymmetric 3-Cam `1/3`, `4-Cut Grammar`, `bimodal_vocal_jcut_deep`, `persistent_text_bridge_11f`, `player3_air_cushion_20f` |
| **`F2`** | `pas_bab_ecom_conversion` | `1.4–2.6` | `lane_b_web_plates` (+ `A`) | Direct-response PAS/BAB, `exposure_bloom_3f`, `concentric_negative_bridge`, `rack_focus_13f`, `organic_foley_7_pack` |
| **`F3`** | `tactile_review_testing` | `1.2–2.2` | `lane_b_web_plates` (+ `A`) | Sensory ASMR unbox/swatch, `organic_foley_7_pack`, `silence_vacuum_140bpm_drop`, Pros/Cons `@2x` scorecards |
| **`F4`** | `clinical_aesthetic_before_after` | `1.9–3.5` | `lane_a_native` (+ `B`) | 50/50 Split Before/After Receipt, `exposure_bloom_3f`, `rack_focus_13f`, strict `CRI-100` & `R200` authentic plate lock |
| **`F5`** | `course_lead_magnet_funnel` | `1.8–3.4` | `lane_b_web_plates` (+ `A`) | `semantic_4act_jewel` `#FAFAFA` chapter cards, SVG 3-step maps, `optical_flow_morph_6f`, 3D Deliverable mockup CTA |
| **`F6`** | `cinematic_vlog_storytelling` | `2.4–5.2` | `lane_a_native` | `51%` Emotion craft storytelling, `optical_flow_morph_6f`, `halation_decay_4_28f`, `-34..-28 dBFS` room tone, `>= 30%` breathing |
| **`F7`** | `tutorial_ui_walkthrough` | `1.7–3.2` | `lane_b_web_plates` (+ `C`) | `mirror_tile_whip_3d_ui_19f`, `@2x` HTML/CSS glass browser/terminal plates, 50/50 split + PiP speaker, `R200` screen-rec |
| **`F8`** | `fast_paced_listicle_top_n` | `1.3–2.5` | `lane_b_web_plates` (+ `A`) | Rapid Top-N / X-Mistakes anchor, active-dim step pills (`S18b`), `pre_echo_rotoscope_strobe_2f`, `silence_vacuum_140bpm_drop` |
| **`F9`** | `spatial_vfx_clone_storefront_tour` | `1.8–3.6` | `lane_a_native` (+ `B`) | Clone visual hook, RVM foreground wipe pass, planar architectural callouts for Clinic/Salon/Property tours |
| **`F10`** | `faceless_motion_explainer` | `1.5–3.0` | `lane_c_hyperframes` (+ `B`) | `0–15%` A-roll kinetic system film, `silence_vacuum_140bpm_drop`, `concentric_negative_bridge`, `< 4.5GB` 2-worker Chrome cap |

### 4.2 Axis 2 — `8 Industry Skins` (`S1..S8` in [`industry_profiles.json`](../presets/industry_profiles.json)) & `HARD VETO` Circuit Breakers
| Skin ID | Canonical Profile Slug | Chromatic & Optical Signature | Mandatory Active Safety Guards | Domain `HARD VETO` Circuit Breaker (Immediate Reject if Violated) |
|---|---|---|---|---|
| **`S1`** | **`luxury_skincare`** *(Mỹ phẩm / Skincare)* | Luminous porcelain `#FAFAFA` / `#FAF6F2` + champagne `#F5C451` / rose-gold `#E29587`; `halation_decay_4_28f` | `Skin-Tone Guard`, `Cranial Lock`, `R200 Claim-Gate` | **VETO:** Swamp-green/muddy cast on skin vectorscope; warm film-burn tint; plastic PIL bevels; AI-generated "after" skin plates |
| **`S2`** | **`dental_clinic`** *(Nha khoa `CRI-100`)* | Pure clinical `D65 / CRI-100` porcelain (`#FAFAFA`) + clinical ice-blue `#0EA5E9` / mint `#14B8A6` (`#0F172A` ink) | **`CRI-100 Tooth Lock`**, `Skin-Tone Guard`, `Cranial Lock`, `R200 Claim-Gate` | **VETO:** Warm yellow/amber LUTs or film-burns tinting enamel (`CIE Lab Δb* > +2.0`); text/glow crossing `mouth_enamel_safebox`; bone/drill SFX |
| **`S3`** | **`nail_hair_salon`** *(Nail / Hair / Salon)* | Lifted velvet shadows, true swatch fidelity; `#FDF8F5` soft cream, blush `#F4A6B8`, mocha `#6D4C41` | **`Hand Safe-Box`**, `Skin-Tone Guard`, `Cranial Lock` | **VETO:** Captions, badges, or crushed shadows overlapping manicured hands/nails or hair swatches; neon oversaturation warping gel shade |
| **`S4`** | **`tactile_review`** *(Review / Unbox / E-com)* | True-to-life product color + crisp Lane-B `@2x` Pros/Cons/Score & price-delta plates + ASMR foley | `Skin-Tone Guard`, `Hand Safe-Box`, `Cranial Lock`, `R200 Claim-Gate` | **VETO:** Text/stickers occluding `macro_subject_bbox`; AI B-roll disguised as product test proof; `S13` cheap bouncy neon karaoke |
| **`S5`** | **`course_edtech`** *(Bán khóa học / Coaching)* | High-trust `#FAFAFA` archival light + `semantic_4act_jewel` 4-chapter inks (`#0F172A` body) + SVG maps | `Cranial Lock`, `Skin-Tone Guard`, `R200 Claim-Gate` | **VETO:** Casino/get-rich-quick neon rainbow flashing; `> 2` concurrent text zones (`FRAME_CLUTTER_OVERLOAD`); unverified outcome screenshots |
| **`S6`** | **`personal_brand`** *(Nhân hiệu `@__dviet`)* | `@__dviet` Era-2 `color_world_polarity` (`emerald_cream_7707` / `amber_cinema_7706`) OR `semantic_4act_jewel` | **`Cranial Lock`**, **`Skin-Tone Guard`**, `Sub-layer Feather=29` | **VETO:** Swampy green wall cast poisoning skin; `PIL/OpenCV` 3D plastic bevel text; any glyph inside `cranial_exclusion_band` |
| **`S7`** | **`cinematic_vlog`** *(Vlog Short / Lifestyle)* | Warm natural Kodak skin, clean highlights, `halation_decay_4_28f`, `7 Organic Foley SFX`, ambient room bed | `Skin-Tone Guard`, `Cranial Lock` | **VETO:** Corporate KPI/checklist boxes (`max_checklist_audit_card = 0`); heavy cyber whoosh spam (`> 3/min`); `< 30%` clean breathing frames |
| **`S8`** | **`b2b_saas_realestate`** *(B2B / SaaS / BĐS)* | Architectural obsidian `#0B0F19` or travertine `#F8FAFC` + brass/cyan; `@2x` HTML/CSS UI, chart & floorplan plates | `Cranial Lock`, **`R200 Claim-Gate`**, `R35 True-Peak` | **VETO:** Spoken prices/yields/benchmarks mismatched with `textnorm` or backed by AI hallucinations instead of authentic `screen_rec`/property plates |

> **Combinatorial Scaling (`80` → `240+`):** Pairing any `Format Mode (F1..F10)` with any `Industry Skin (S1..S8)` yields **`80` orthogonal studio configurations** (e.g., `F3 × S2` = *Contrarian Dental Myth-Debunk under CRI-100 Lock*; `F5 × S3` = *Tactile Macro Nail Gel Review under Hand Safe-Box*; `F6 × S6` = *4-Act Jewel Personal-Brand Framework*). Crossing those `80` cells with the **3 Chromatic/Polarity Modes** (`color_world_polarity`, `semantic_4act_jewel`, `hybrid_polarity_jewel`) unlocks **`240+` non-repetitive studio looks**.

---

## 5. `v7.0` `.craft.json` Blueprint & Pre-Compile Director Checklist

```json
{
  "meta": {
    "schema_version": "7.0.0",
    "archetype": "dviet_era2_7707_manifesto",
    "format_mode": "expert_talking_head",
    "industry_skin": "personal_brand",
    "tier": "full",
    "color_policy": "semantic_4act_jewel",
    "canvas_light": "#FAFAFA",
    "active_safety_guards": ["cranial_lock", "skin_tone_guard", "no_pil_plastic_bevel"],
    "render_lanes": ["A", "B", "C"],
    "cut_grammar": "dviet_4cut",
    "bgm_stops": [[6.80, 7.45]],
    "claim_gate": false
  },
  "beat_example_v70_dual_rail": {
    "render_lane": "B",
    "placement_rail": "chest_tactile_rail",
    "web_plate": {
      "tool": "web_plate_builder.py",
      "dpr": 2,
      "format": "prores_4444_or_rgba_png",
      "act_jewel_hue": "#2563EB",
      "line_height": 0.78,
      "hard_stroke_px": 0
    },
    "rvm_sandwich": {
      "enabled": true,
      "sub_layer_feather_px": 29,
      "cranial_lock_zero_overlap": true
    },
    "micro_bridges": ["player3_air_cushion_20f", "persistent_text_bridge_11f", "organic_foley_7_pack"]
  }
}
```

### 7-Point `v7.0` Pre-Handoff Verification
1. **Zero `PIL` Plastic:** Are `100%` of hero graphic cards, badges, and display plates rendered via **Lane B** ([`web_plate_builder.py`](../scripts/tools/web_plate_builder.py) `HTML5/CSS3/SVG @2x DPR`) or **Lane C** with `0px` hard stroke?
2. **`Cranial Lock` & `Dual-Rail 9:16`:** Is `0%` of text touching face/hair, placed cleanly in `Upper Editorial Stage` (`Y ∈ [220, 520]`) or `Chest Tactile Rail` (`Y ∈ [960, 1340]`, `Sub-layer Feather = 29`)?
3. **Domain `HARD VETO` Guards:** Are `CRI-100 Tooth Lock` (`S2`), `Skin-Tone Guard` (`S1..S7`, zero swamp-green wall cast), `Hand Safe-Box` (`S3/S4`), and `R200 Claim-Gate` (`S1/S2/S4/S5/S8`) satisfied?
4. **Chromatic Discipline:** Does the timeline follow `color_world_polarity` OR chapter-clean `semantic_4act_jewel` (`<= 1` jewel hue per act, `0` intra-sentence rainbow soup)?
5. **14 Micro-Bridges:** Are cuts smoothed with `player3_air_cushion_20f`, `rack_focus_13f`, `persistent_text_bridge_11f`, `optical_flow_morph_6f`, `exposure_bloom_3f`, and `bimodal_vocal_jcut_deep` (`<= 45%` `wgpu` transitions)?
6. **Acoustic Contrast & 7 Organic Foley:** Are `meta.bgm_stops` (`>= 0.50s` `-inf dB`) and `organic_foley_7_pack` (`R217` `[-1f, +2f]`, `-16/-14 LUFS`, `R35` TP) verified?
7. **Rule A1 Native Handoff:** Does compilation output an editable `.fcproj` + `1440×2560` QA contact sheet without exporting `.mp4` unless requested (Look S exception: MP4 master plus the `.fcproj` mirror, `SKILL.md` section 3.8.1)?
