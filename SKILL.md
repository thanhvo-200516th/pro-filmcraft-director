---
name: pro-filmcraft-director
description: >-
  Use when the user wants to direct, edit, rebuild or polish talking-head footage (one raw video, a multi-slice folder or an existing FilmCraft .fcproj) into a studio-grade, non-template 9:16 video (or 16:9 opt-in). v8.1.0 Universal Multi-Industry Cinema Director. Unifies 4 reference channel grammars (@tng.vinhomes8, @vuotaiai, @__dviet, @xuanart.visual) with Zero-Voice-Loss audio preservation, 100% Verbatim Caption Rail, L-Shaped TikTok Safe Zone, Typography v8.1 (FP1..FP6, PAL_*, sub_01..sub_10), 17-Industry 3D Asset Catalog (local_3d_props.py + flow_3d_assets.py), RVM/u2netp foreground matting for text-behind-subject, Full-Head Studio Rounded Cards & Squircle PiP, damped-spring parallax, and Dual-Deliverable FilmCraft .fcproj Bridge. Look S Studio is the default for product, brand and explainer video; Look D (@__dviet screen-strip tutorials) only on explicit request. Covers 10 Format Modes x 17 Universal Industry Skins (non-SaaS & creative craft), 60fps kinetic typography plates, Vietnamese NFC typography, hook, pacing and text-legibility gates, and an 8-gate FilmCraft compiler.
---

# Pro FilmCraft Director (`v8.1.0`) — Universal Multi-Industry Cinema Director

## 1. Overview

### 1.1. Purpose, inputs and outputs

- **Purpose:** turn talking-head footage into a bespoke, studio-grade vertical video (`1080x1920`, strict default; `1920x1080` `16:9` opt-in only when explicitly requested) and an editable FilmCraft project. The agent (the brain) makes every creative decision; the tools are stateless and only build, render and measure.
- **Core v8 Invariant (Zero-Voice-Loss + Verbatim Rail + Co-Layered Craft):**
  1. **Zero-Voice-Loss:** NEVER cut, drop, or mute spoken voice during B-roll or stage inserts (`abs(out_dur - in_dur) <= 0.15 s` enforced by `v8_compositor_fx.py`).
  2. **100% Verbatim Caption Rail:** every spoken word is represented cleanly on the synced Vietnamese NFC caption rail (`verbatim_caption_rail.py`), co-existing without colliding with hero typography or face safe-boxes.
  3. **Co-Layered 3D / Icon / B-Roll:** pair real/AI B-roll inserts, floating 3D badges (`flow_3d_assets.py`), glass/vector widgets (`cinema_widgets_v8.py`, `vector_shape_plates.py`), and behind-subject 3D titles (`extract_subject_matte`) over continuous speech.
- **4-Channel Reference Grammar:**
  - `@tng.vinhomes8`: warm architectural real-estate/property craft, price/spec odometers, clean B-roll inserts over continuous narration.
  - `@vuotaiai`: dark studio stage, giant neon hollow backdrop text + `glowing_squircle_pip`, crisp glass step pills & kinetic beat sync.
  - `@__dviet`: editorial talking-head pacing, `kt01..kt12` kinetic typography, polarity flips, optical bridges (`light_burst`, `film_burn`, `whip_blur`).
  - `@xuanart.visual`: subject-tracked parallax (`subject_tracker.py`), text-behind-subject (`kt17`, `w06`), layered 3D badges & craft showcases.
- **Inputs:** **1 raw video**, a **multi-slice footage folder**, or an **existing `.fcproj`**; optional script, B-roll, SFX folder, `<workspace>/feedback_log.jsonl`.
- **Outputs:** the `.fcproj` (always), `EDITOR-REPORT.md` with the gate verdicts, a `1440x2560` QA contact sheet, and for Look S / v8 Cinema the compositor MP4 master (section 3.8.1, metadata-stripped).
- **Never:** static `mode="still"` hero `.png` stamps, `PIL/OpenCV` 3D plastic bevels, `— ALL CAPS KICKER` or duplicate pill spam (section 4.1).
- **Release history** (what each of v7.4.0 .. v8.1.0 added): [`README.md`](./README.md) section 1 and [`docs/TIEN_DO_SKILL.md`](./docs/TIEN_DO_SKILL.md). This file states only the current rules.

### 1.2. Look S and Look D (the one canonical statement)

Choose the look first (section 3.4.1) and say it to the user.

| | **Look S (Studio): the DEFAULT** | **Look D (`@__dviet` channel)** |
|---|---|---|
| Use for | product, brand and explainer talking-head video | plain screen-strip tutorials, **only on explicit request** ("làm giống kênh dviet") |
| Reference | the V19..V21 masters, [`24_studio_look_recipe.md`](./references/24_studio_look_recipe.md) | [`references/dviet_19/INDEX.md`](./references/dviet_19/INDEX.md), [`23_dviet_profile_decisions_and_backlog.md`](./references/23_dviet_profile_decisions_and_backlog.md) |
| Scenes | Full-Head Cards (A1), Squircle PiP (A2), Bottom-Flush cutouts (B), polarity paper, neon blackout, silk numeral stage, B-roll hook (section 3.5) | `screen_strip` / `card_916` / `profile_card` layouts |
| Profile / colour | `default`; chapter colour wins (`accent_policy: color_world`) | `dviet`; one accent per video from the tokens (`accent_policy: tokens`, default `#F1C711`) |
| Typography | `Swash-Initial Hybrid` | condensed sans (`Barlow Condensed`); swash only for role `script_accent` |
| Audio profile | `studio_14` (`-14.0 LUFS`, `-1.2 dBTP`, ducking on, `bgm_stops` allowed, up to `72` SFX cues) | `tiktok_loud` (`-12 LUFS`, `-1.0 dBTP`, BGM `14 dB` under the voice; UNVALIDATED on real speech) |
| Frame rate | `60fps` | `30` or `60fps` per canvas |
| Deliverable | **MP4 master + `.fcproj` mirror** (the Rule A1 exception, section 3.8.1) | `.fcproj` (Rule A1) |

### 1.3. Architecture

Three render lanes: **Lane A** NLE-native FilmCraft clips; **Lane B** [`web_plate_builder.py`](./scripts/tools/web_plate_builder.py) `60fps` HTML5/CSS3/SVG `@2x` plates (ProRes 4444 / `qtrle` RGBA `.mov`, `kt01..kt12`); **Lane C** [`dviet_motion_canvas_engine.py`](./scripts/dviet_motion_canvas_engine.py) full-screen motion canvases (HyperFrames / EffectCraft optional). Look S adds the single-stream plate compositor (`fast_studio_compositor.py`, numpy/OpenCV plates + one FFmpeg filtergraph; about `35 s` draft / `90 s` `60fps` master).

#### 1.3.1. The brain (you)

- Inspect `assets_contact_sheet.jpg`, read `words_tl.json` word by word, consult `feedback_log.jsonl` when present.
- Pair **1 Format Mode (`F1..F10`) x 1 Industry Skin** ([`industry_profiles.json`](./presets/industry_profiles.json) v8.0.0: 17 flagship skins spanning 16 non-SaaS & creative craft verticals — `luxury_skincare`, `dental_clinic`, `nail_hair_salon`, `tactile_review`, `course_edtech`, `personal_brand`, `cinematic_vlog`, `real_estate_interior`, `fnb_culinary`, `fashion_lookbook`, `fitness_wellness`, `finance_legal_advisory`, `automotive_hardware`, `healthcare_medical`, `travel_hospitality`, `creative_media_agency`, plus `b2b_saas_realestate` for backwards compat) + **1 Archetype** ([`visual_archetypes_catalog.json`](./presets/visual_archetypes_catalog.json)).
- Choose the look, profile, chromatic policy, scene modes, typography beats, bridges and SFX; enforce the iron laws (4.1) and call the plan-level gate functions (4.2) yourself.
- A tool result is a measurement, not a decision: when a gate fails, fix the cause (never loosen the limit) or tell the user.

## 2. Requirements and resources

### 2.1. Environment

Check with `python3 ./scripts/env_status.py [--json] [--strict]` (section 3.1).

| Item | Minimum | Required for |
|---|---|---|
| Python venv | 3.10+, `~/.venvs/video-skills`, [`requirements.txt`](./requirements.txt) (pins `opencv-python-headless` 4.x) | every `.py` tool |
| Node.js | `>= 22` (`NODE_BIN`) | `web_cinema_plate_engine.mjs` (Lane B plates) |
| Chrome / Chromium | any headless build (`CHROME_BIN`) | Lane B plates |
| FFmpeg + ffprobe | 6.1+ | ingest, render, loudness |
| FilmCraft | `>= 0.13.0` (it ships `wgpu 0.20.1`) | compile (Gate 4) and export |
| Xvfb (or Xephyr) | any | FilmCraft runs on a virtual display, never on `:0` |
| Person matte | `u2netp` (`~/.rembg/models/u2netp/u2netp.onnx`, or `PFD_MATTE_MODEL` / `U2NETP_ONNX_PATH`); `birefnet-portrait` is the slow fallback (~30 s/frame) | cutouts, pop-out card, Cranial Lock sandwich |
| Fonts | Be Vietnam Pro, Playfair Display (fallback chain in [`26_dviet_fonts.md`](./references/26_dviet_fonts.md)) | Vietnamese NFC text |

**RVM is not shipped.** The person matte this skill can make is `u2netp` / `birefnet-portrait`. Wherever a doc or a parameter says "RVM alpha" (`person_alpha_u8`), read "a person matte": the skill's own `u2netp` matte, or an RVM matte made by another tool. The skill's cache root (SFX acoustic cache, `.fcproj` backups) is `PFD_CACHE_DIR` (default `~/.cache/pro-filmcraft-director`); Look S segment plates are cached in the `--work` folder; the other environment variables are listed in [`README.md`](./README.md) section 3.

### 2.2. Six stateless core tools

1. [`probe_and_align.py`](./scripts/tools/probe_and_align.py) — ingest (`--tier fast|studio|full|auto`) -> `workspace_context.json`, `media_probe.json`, `words_tl.json`, `assets_contact_sheet.jpg` (+ `textnorm`, `20 ms` RMS pause onsets and Haar `eye_band` / `mouth_band` via [`haarcascade_frontalface_default.xml`](./data/haarcascade_frontalface_default.xml) in `full`). Flags: `--whisper-threads N` (or `PFD_WHISPER_THREADS`), `--timeout SECONDS`, `--force` (overrides the lock file of another or a crashed run in `--work`; it does **not** discard cached results), `--music-only` (no ASR). Rejects a 0-byte or corrupt video; always writes `words_tl.json` (empty plus a warning when there is no audio).
2. [`web_plate_builder.py`](./scripts/tools/web_plate_builder.py) *(Lane B)* — headless Chrome `@2x`, `60fps` engine via [`web_cinema_plate_engine.mjs`](./scripts/web_cinema_plate_engine.mjs) (Node `>= 22`, no npm dependencies): `render_kinetic_typo_batch(...)` (`kt01..kt12` RGBA `.mov` synced to syllable onsets, `0 px` hard stroke), the 3D studio plates (`frosted_glass_bento_steps`, `skewed_3d_polaroid_trio`, `isometric_3d_prompt_browser`, `clinical_before_after_1_to_28`) and three layout templates with role-named slots (`screen_strip`, `card_916`, `profile_card`). `render_web_plates_batch` hard-blocks text under the legibility floor (4.2.3). A missing font falls back to Be Vietnam Pro / Playfair Display with a warning.
3. [`dviet_motion_canvas_engine.py`](./scripts/dviet_motion_canvas_engine.py) *(Lane C)* and [`visual_blocks.py`](./scripts/tools/visual_blocks.py) — four full-screen `60fps` canvases (`timeline_playhead`, `concentric_lock_lab`, `giant_numeral_3d_ui`, `bento_kinetic_matrix`), ten RGBA visual primitives (see [reference 14](./references/14_anti_cookiecutter_visual_director_matrix.md)), `clean_broll_plate`, and `lint_broll_prompt` (the plate-level face of the one B-roll prompt contract of 3.8.3: same word range and rules, no `anchor_quote` check).
4. [`typography_composer.py`](./scripts/tools/typography_composer.py) *(Lane A+B)* — `plan_dviet_kinetic_beat_schedule(...)` (`kt01..kt12` anti-monotony router, `35% Hero / 35% Whisper & Counterpoint / 30% Studio 3D Plates`, `Swash-Initial Hybrid`), `Dual-Rail 9:16` + `Cranial Lock`, `DVIET_COLOR_WORLDS` + `semantic_4act_jewel`, whisper `G2` (`S01..S18`, at least `64 px` on the canvas like every overlay text), and the bridge helpers. Companion [`dviet_text.py`](./scripts/tools/dviet_text.py) turns role-tagged events (`caption`, `keyword_sans`, `script_accent`, `number`, `header`, `cta`, `bilingual_sub`, `lockup_sub`, `lockup_hero`, `constellation`, `font_specimen`) into text tracks whose `y%`, size, entrance and font come from [`dviet_style_tokens.json`](./presets/dviet_style_tokens.json).
5. [`compile_and_verify.py`](./scripts/tools/compile_and_verify.py) — stateless 8-gate compiler (catalogue in 5.1): `.craft.json` -> `.fcproj` + 16 QA frames + `EDITOR-REPORT.md`. Flags: `--tier auto|fast|full`, `--profile default|dviet`, `--audio-profile platform|studio_14|tiktok_loud` (default `platform` = `-16 LUFS`, `-1.5 dBTP`), `--auto-sfx-dir DIR` (resolves `src: "AUTO:<keyword>"` SFX clips, one MD5-unique file per clip; compile fails if `AUTO:` clips exist without it), `--words`, `--manifest`, `--context`, `--strict-rules`, `--hook-gates --preview MP4`. It never exports `.mp4` (3.8.1).
6. [`fast_studio_compositor.py`](./scripts/tools/fast_studio_compositor.py) — the Look S compositor: `init_hair_safe_wall_reference`, `clean_aroll_preserve_hair_crown` (scale-space opening; keeps rounded hair crowns, optional `person_alpha_u8`), `render_full_head_studio_card` (A1), `render_squircle_pip_window` (A2), `render_bottom_flush_cutout` (B, full width `x = 0..1080`, bottom-locked, `1.5 px` jewel rim), `render_popout_studio_card`, `apply_fullwidth_neon_rim_blackout`, `verify_audio_voice_sync_guard` (rejects uncut or drifted voice takes), `pipe_encode_single_plate_fast`, `compose_master_mp4_via_ffmpeg`. Its CLI `--draft` / `--master` is **only a plain re-encode** (scale, crop, fps) of one input video, not a studio render; the studio render is `look_s_render.py` (3.5.3).

### 2.3. Helper CLIs (stateless; the brain decides, the tool measures)

| Tool | Does | Step |
|---|---|---|
| [`env_status.py`](./scripts/env_status.py) `[--json] [--strict]` | preflight of 2.1 | 3.1 |
| [`silence_cut.py`](./scripts/tools/silence_cut.py) `plan\|apply`, [`speed_media.py`](./scripts/tools/speed_media.py) `plan\|apply\|check` | pre-ingest cuts and speed | 3.2 |
| [`studio_recipe.py`](./scripts/tools/studio_recipe.py) | Look S scene planner + hook / pacing / legibility check functions (data: [`studio_scene_recipe.json`](./presets/studio_scene_recipe.json)) | 3.5, 4.2 |
| [`look_s_render.py`](./scripts/tools/look_s_render.py) | renders Look S from `scenes.json` through the compositor | 3.5.3 |
| [`motion_gate.py`](./scripts/tools/motion_gate.py) | measures a rendered MP4 (motion, flashes) + pop-out / text metric functions | 4.2, 5.2 |
| [`dviet_text.py`](./scripts/tools/dviet_text.py) | role events -> text tracks | 3.6 |
| [`spec_from_plan.py`](./scripts/tools/spec_from_plan.py) | plan -> compile-ready `.craft.json` ([reference 21](./references/21_craft_json_minimal_spec.md)) | 3.6 |
| [`sfx_auto.py`](./scripts/tools/sfx_auto.py) `plan` | events -> SFX cues from [`sfx_catalog.json`](./presets/sfx_catalog.json) | 3.4.4 |
| [`duck_keyframes.py`](./scripts/tools/duck_keyframes.py) | word spans -> 4-point BGM duck keys (`0.35 s` pre-roll, `0.25 s` ramp, `8 dB`, hold across gaps `< 1.5 s`, `0.7 s` release; optional vacuum `-32 dB` for `0.4 s`, at most one per `20 s`); `tiktok_loud` keeps `no_ducking: true` until wired into the compiler | 3.4.4 |
| [`flicker_schedule.py`](./scripts/tools/flicker_schedule.py) | silhouette-flicker frames for the `flicker` opener (class A+B, 4.3) | 3.4.5 |
| [`qa_sync.py`](./scripts/tools/qa_sync.py), [`sfx_shift.py`](./scripts/tools/sfx_shift.py) | Gate 7b: measure SFX vs picture on an exported MP4, shift once | 3.8.2 |
| [`broll_from_video.py`](./scripts/tools/broll_from_video.py) `analyze\|check-prompts` | B-roll slot planner + the one prompt linter | 3.8.3 |
| [`fc_export.py`](./scripts/tools/fc_export.py) `IN.fcproj OUT.mp4` | export (Rule A1 cases only); polls for the file | 3.8.1 |
| [`filmcraft_cli.py`](./scripts/tools/filmcraft_cli.py) | drives a running FilmCraft through `filmcraft --control` on Xvfb; skips loudly, never fakes a render; the `filmcraft-cli` binary of old docs never existed ([`30_filmcraft_control_bridge.md`](./references/30_filmcraft_control_bridge.md)) | 3.7, 5.4 |
| [`subject_tracker.py`](./scripts/tools/subject_tracker.py) | tracks speaker face, crown & shoulders per frame -> `subject_track.json` for damped-spring parallax | 3.3, 3.6 |
| [`verbatim_caption_rail.py`](./scripts/tools/verbatim_caption_rail.py) | builds 100% verbatim synced Vietnamese NFC caption rail (never drops spoken words) | 3.6 |
| [`cinema_widgets_v8.py`](./scripts/tools/cinema_widgets_v8.py) | renders multi-industry glass pills, price/metric odometers, charts & callout widgets | 3.6 |
| [`vector_shape_plates.py`](./scripts/tools/vector_shape_plates.py) | renders crisp SVG/vector shape plates, frames & behind-subject geometric backdrops | 3.6 |
| [`local_3d_props.py`](./scripts/tools/local_3d_props.py) | instant local 3D PBR turntable prop renderer (from [`assets_3d_catalog.json`](./presets/assets_3d_catalog.json), zero cloud wait) | 3.6 |
| [`flow_3d_assets.py`](./scripts/tools/flow_3d_assets.py) | Google Flow photoreal 3D asset tier: generates & caches floating 3D badges/icons from [`assets_3d_catalog.json`](./presets/assets_3d_catalog.json) | 3.6, 3.8.3 |
| [`v8_to_craft_spec.py`](./scripts/tools/v8_to_craft_spec.py) | converts `v8_edit_plan.json` -> strictly compliant `.craft.json` (7 rules of ref 21, non-overlapping `V4a/V4b` lanes, 48kHz PCM `.wav` voice) | 3.6, 3.8.1 |
| [`v8_compositor_fx.py`](./scripts/tools/v8_compositor_fx.py) | v8.1 60fps multi-layer compositor (`9:16` default / `16:9` opt-in): RVM CUDA -> u2netp -> GrabCut matting, spring parallax, `light_burst`, `film_burn`, `whip_blur`, `glowing_squircle_pip`, `broll_insert`, Zero-Voice-Loss guard (`<= 0.15 s`), metadata stripping, and `--export-fcproj` / `--craft-spec` Dual-Deliverable FilmCraft Bridge | 3.5, 3.8.1 |

### 2.4. CLI cheat-sheet (numbers match section 3; run `--help` before the first call)

- **3.1 Preflight:** `python3 ./scripts/env_status.py --strict`
- **3.2 Pre-ingest (optional):** `python3 ./scripts/tools/silence_cut.py plan --input <a_roll.mp4> --fps 60` · `python3 ./scripts/tools/speed_media.py plan --input <media> --fps 60` (`--fps 60` for Look S; default `30`)
- **3.3 Probe:** `python3 ./scripts/tools/probe_and_align.py --input <video_or_dir> --work <work> --tier auto` (`--tier studio` for P0+P1)
- **3.5 Look S plan and render:** `python3 ./scripts/tools/studio_recipe.py --words <work>/words_tl.json --duration <s> --out <work>/scenes.json` then `python3 ./scripts/tools/look_s_render.py --scenes <work>/scenes.json --words <work>/words_tl.json --aroll <video> --work <work> --out <master.mp4> --master [--broll-dir DIR] [--overlays-from-plan <work>/plan.json] [--emit-overlays <work>/overlays_final.json --emit-scenes <work>/scenes_final.json] [--dry-run]` (full order: 3.5.3 "Look S full run")
- **3.6 Typography:** `python3 ./scripts/tools/web_plate_builder.py --help` · `--list` · `python3 ./scripts/tools/typography_composer.py --help` · `python3 ./scripts/tools/dviet_text.py --events events.json --tokens presets/dviet_style_tokens.json --out tracks.json` · `python3 ./scripts/dviet_motion_canvas_engine.py --help` · `python3 ./scripts/tools/visual_blocks.py --list`
- **3.7 Compile (Look S):** `python3 ./scripts/tools/compile_and_verify.py --spec <p>.craft.json --out <p>.fcproj --work <work> --words <work>/words_tl.json --context <work>/workspace_context.json --scenes <work>/scenes.json --tier full --audio-profile studio_14 --strict-rules --hook-gates --preview <master.mp4> [--auto-sfx-dir <sfx_dir>]`
- **3.7 Compile (Look D):** same with `--profile dviet --audio-profile tiktok_loud` and without `--hook-gates` / `--scenes`
- **3.8 Hand-off:** `python3 ./scripts/tools/fc_export.py IN.fcproj OUT.mp4` · `python3 ./scripts/tools/qa_sync.py --video EXPORTED.mp4 --spec X.craft.json` · `python3 ./scripts/tools/broll_from_video.py analyze --transcript words_tl.json --out broll_plan.json`

### 2.5. Execution tiers (`--tier fast | studio | full | auto`)

Timings and RAM come from [`execution_tiers.json`](./presets/execution_tiers.json) (`[ƯỚC]` on the reference i5-12450H host).

| Tier | Time | RAM | Probe / compile flags | Adds |
|---|---|---|---|---|
| `fast` (P0) | `45–60 s` | `1.8 GB`, no Chrome | `probe --tier fast` · `compile --tier fast` | `text_vi.json` (`1199` glue pairs), Gate 3C, Dual-Rail Cranial Lock, colour-world polarity / 4-act jewel, 4-Cut Grammar + `C7` J-cut, `MAX_ZONES <= 2`, `bgm_stops`, `R217` SFX, closed-loop loudness, 16 QA frames; skips textnorm, RMS onsets, 24-frame Haar tracking, projected face-safe ink |
| `studio` (P0+P1) | `55–68 s` | `3.9 GB`, `<= 2` Chrome workers | `probe --tier studio` · `compile --tier full` | industry `HARD VETO` guards ([`industry_profiles.json`](./presets/industry_profiles.json)), 16-frame Haar dual rail, macro safe zones, Lane B plates. Because it compiles with `--tier full`, the `bgm_lra` optimizer and the `R35` post-AAC true-peak guard **do run** (the JSON lists them as skipped; the compiler does not) |
| `full` (P0+P1+P2) | `68–82 s` | `4.5 GB`, `<= 2` Chrome workers | `probe --tier full` · `compile --tier full` | domain vetoes (`CRI-100 Tooth Lock`, `Skin-Tone Guard`, `Hand Safe-Box`, `R200`), syllable-lock spoiler audit `<= 180 ms`, `Sub-layer Feather = 29`, projected face-safe, `V8` liveness, `R35`, Gate 3C codes raised to ERROR |
| `auto` (default) | by input | | `--tier auto` | probe: a raw video -> `full`; a project bundle -> `fast` when cleanly pre-sliced, else `full`; **auto never picks `studio`**. Compile: `full` with `--strict-rules` or an active claim gate, else the context's `recommended_compile_tier`, else `fast` |

### 2.6. Presets and data (`./presets/`, `./data/`, `./templates/`)

- Matrix, vetoes, bridges: [`format_modes_catalog.json`](./presets/format_modes_catalog.json) (`F1..F10`, `S1..S8`, `profile_vetoes`, `native_frame_14_micro_bridges`) · [`visual_archetypes_catalog.json`](./presets/visual_archetypes_catalog.json) (8 archetypes, Lane B contract, Gate 3C, archetype bridges) · [`industry_profiles.json`](./presets/industry_profiles.json) · interactive viewer [`edit_plan_viewer.html`](./templates/edit_plan_viewer.html)
- Tiers: [`execution_tiers.json`](./presets/execution_tiers.json)
- Typography: [`typography_v81_presets.json`](./presets/typography_v81_presets.json) (v8.1: 6 font pairings `FP1..FP6`, 8 gradient+glow palettes `PAL_*`, 10 rotating multi-font/multi-color Text Phụ modes `sub_01..sub_10`, `max_consecutive = 1`, zero black strokes) · [`typography_hierarchy_presets.json`](./presets/typography_hierarchy_presets.json) (`kt01..kt12`, Gate 3C quotas, `S01..S18`, caption-`y` keys) · [`dviet_style_tokens.json`](./presets/dviet_style_tokens.json) (Look D palette, font roles, tiers, caption `y`, lock-up, canvases, audio; `measured` / `estimate` flags) · [`text_vi.json`](./data/text_vi.json)
- 3D Assets: [`assets_3d_catalog.json`](./presets/assets_3d_catalog.json) (17-Industry 3D Asset Catalog for `local_3d_props.py` instant PBR turntables & `flow_3d_assets.py` Google Flow photoreal tier)
- Canvas and safe zones: [`canvas_presets.json`](./presets/canvas_presets.json) (`9x16_1080_60` strict default; `9x16_1080_30`, `16x9_1920_60` / `16x9_1920_30` opt-in only via `v8_compositor_fx.py`, `1440x1080@24|30`, `1332x720@30`) · [`platform_safe_zones.json`](./presets/platform_safe_zones.json)
- Motion: [`atomic_motion_library.json`](./presets/atomic_motion_library.json) (zoom presets, scoped `dviet` transitions with caps) · [`dviet_pattern_catalog.json`](./presets/dviet_pattern_catalog.json)
- Look S: [`studio_scene_recipe.json`](./presets/studio_scene_recipe.json) (V21 grid, hook `0–5 s`, pacing, motion and text limits)
- Audio and SFX: [`profile_overrides.json`](./presets/profile_overrides.json) (`platform`, `studio_14`, `tiktok_loud`) · [`sfx_catalog.json`](./presets/sfx_catalog.json) · [`sfx_micro_sync_rules.json`](./presets/sfx_micro_sync_rules.json) · [`pain_keywords.json`](./presets/pain_keywords.json)
- B-roll: [`broll_lint_contract.json`](./presets/broll_lint_contract.json) (the single prompt-lint contract, 3.8.3)
- Face cascade: [`haarcascade_frontalface_default.xml`](./data/haarcascade_frontalface_default.xml)

### 2.7. Reference manuals (`./references/`, read on demand)

- **Core:** [01 director & retention](./references/01_director_and_retention.md) · [02 Premiere ↔ FilmCraft tracks & keyframes](./references/02_nle_premiere_filmcraft.md) · [03 micro-timing recipes](./references/03_micro_timing_recipes.md) · [14 anti-cookie-cutter visual matrix](./references/14_anti_cookiecutter_visual_director_matrix.md) · [15 adaptive tiers & epistemic QA (historical v5.1)](./references/15_adaptive_tiers_and_epistemic_qa_v51.md)
- **Look S:** [24 studio look recipe (V21 map, VFX-01..08, cut times, 4-act colours, audio)](./references/24_studio_look_recipe.md) · [20 hybrid A×B, voice-sync & hair-safe compositor](./references/20_v73_hybrid_ab_voicesync_and_hairsafe_compositor.md) · [28 hook-first 5 s & pacing law](./references/28_hook_first_5s_and_pacing.md) · [29 pop-out card → FilmCraft A/B/C](./references/29_popout_card_premiere_to_filmcraft.md) · [25 loudness TikTok vs NLE](./references/25_loudness_tiktok_vs_nle.md)
- **Typography:** [04 `@__dviet` & Vietnamese NFC](./references/04_dviet_and_vi_typography.md) · [26 `@__dviet` fonts](./references/26_dviet_fonts.md) · [05 text-animation masterclass](./references/05_typography_masterclass.md) · [10 35 `@vietanh` text presets](./references/10_vietanh_35_text_animation_presets_premiere_filmcraft.md) · [09 blueprint 7706](./references/09_dviet_7706_typography_zoom_sfx_mastery.md) · [19 kinetic typography bible](./references/19_v71_dviet_19videos_kinetic_typography_bible.md) · [16 multicolour, `S01..S18`, seamless flow (historical v5.2)](./references/16_v52_multicolor_4group_subtext_and_seamless_flow.md)
- **Motion:** [11 fluid rhythm & Z-depth sandwich (4 timeline layers = 3 compositor planes)](./references/11_talking_head_fluid_rhythm_and_signature_style.md) · [13 smooth zoom & pacing (17 videos)](./references/13_dviet_19_videos_smooth_zoom_and_pacing_mastery.md)
- **Spec & pipeline:** [21 minimal `.craft.json` spec (current)](./references/21_craft_json_minimal_spec.md) · [22 Flow B-roll](./references/22_flow_broll.md) · [12 `ffmpeg-skill` integration](./references/12_ffmpeg_skill_42_tools_integration.md) · [30 FilmCraft control bridge](./references/30_filmcraft_control_bridge.md) · [27 Premiere recipes → FilmCraft A/B/C](./references/27_premiere_recipes_to_filmcraft.md) · [23 `dviet` decisions & BACKLOG](./references/23_dviet_profile_decisions_and_backlog.md)
- **Evidence (read-only):** [06 frame-by-frame forensics](./references/06_dviet_frame_by_frame_forensics.md) · [07 dual-channel forensics](./references/07_xuanart_and_dual_channel_forensics.md) · [08 `@haihoang` pattern catalog](./references/08_haihoang_pattern_catalog_dviet.md) · [17 Era-2 manifesto (historical v6.0)](./references/17_v60_dviet_era2_manifesto_architecture.md) · [18 `10×8` matrix & micro-bridges (historical v7.0)](./references/18_v70_universal_studio_10x8_and_45582_microbridges.md) · [`references/dviet_19/INDEX.md`](./references/dviet_19/INDEX.md) (17 videos, 4.4)

References 15–18 are historical; reference 21 and this file are the current spec.

### 2.8. Scripts index (`./scripts/`)

- **Core:** [`probe_and_align.py`](./scripts/tools/probe_and_align.py) · [`web_plate_builder.py`](./scripts/tools/web_plate_builder.py) · [`visual_blocks.py`](./scripts/tools/visual_blocks.py) · [`typography_composer.py`](./scripts/tools/typography_composer.py) · [`fast_studio_compositor.py`](./scripts/tools/fast_studio_compositor.py) · [`compile_and_verify.py`](./scripts/tools/compile_and_verify.py)
- **Helpers:** the table in 2.3.
- **Engines:** [`web_cinema_plate_engine.mjs`](./scripts/web_cinema_plate_engine.mjs) (Node, headless Chrome CDP pool) · [`dviet_motion_canvas_engine.py`](./scripts/dviet_motion_canvas_engine.py) · [`dviet_smooth_camera_engine.py`](./scripts/dviet_smooth_camera_engine.py) (zoom presets, `LayeredFrameCompositor` 3 planes) · [`dviet_7706_typography_choreography.py`](./scripts/dviet_7706_typography_choreography.py) · [`vietanh_35_typography_engine.py`](./scripts/vietanh_35_typography_engine.py) · [`ffskill_bridge.py`](./scripts/ffskill_bridge.py) (optional)
- **Vendored:** `scripts/vendor/ovs_core/` (`edit_rules.py`, `spec_lint.py`, `audio_levels.py`, `audit_sfx.py`, `apps/craft-handoff/tools/fc_build.py`, `fc_build_fast.py`, `fc_export.py`, `craftctl.py`; provenance in [`PROVENANCE.md`](./scripts/vendor/ovs_core/PROVENANCE.md))

## 3. Step-by-step process

### 3.1. Preflight (`~2 s`)

Run `env_status.py` (`--json` for machines, `--strict` exits `1` when a required item is missing). Required: `node >= 22`, headless Chrome, `ffmpeg` / `ffprobe` with the `libx264`, `prores_ks` and `qtrle` encoders, FilmCraft `>= 0.13.0` and Xvfb / Xephyr (both needed to compile), the venv packages (checked by import), the default whisper model in the Hugging Face cache (`HF_HOME`), the required fonts; a missing `u2netp` is reported as blocking for Look S cutouts. Optional items (fallback fonts, `ffmpeg-skill`) are reported, never fatal. `install.sh` runs it too. On a failure, follow 5.4.

### 3.2. Pre-ingest cuts, only if needed (before the probe)

1. `silence_cut.py plan --input <a_roll>` then `apply --input <a_roll> --out <cut.mp4>` (frame-snapped keep segments, constant frame rate).
2. `speed_media.py plan --input <media>`, then `apply` (policy `1.10 -> 1.05 -> 1.0`, result `>= 45 s`; `1.15x` / `1.25x` banned) and `check`.
3. Both default to a `30 fps` grid: **pass `--fps 60` for Look S**.
4. Never run them after a spec exists (every timestamp would shift). Feed the result to 3.3 so `words_tl.json` is built on the final timeline.

### 3.3. Probe footage and inspect the visual context (`~15–22 s`)

1. Run `probe_and_align.py` with the tier of 2.5 (`--whisper-threads`, `--timeout`, `--music-only` as needed; `--force` only to override a stale lock file).
2. Open `assets_contact_sheet.jpg` with your image-viewing tool and look at the headroom above the hair crown, the chest / hand zone, skin tone and wall luma; read `workspace_context.json`, `media_probe.json` and `words_tl.json`. An empty `words_tl.json` with a warning means no audio: stop and ask before planning text.
3. Look S needs a 9:16 portrait A-roll: `1080x1920` is used as is, another 9:16 size is scaled (warning), anything else is **refused** by `look_s_render.py` (exit `2`); the skill has **no reframe step**, so reframe a landscape A-roll to 9:16 yourself before 3.5. A phone clip stored landscape with a container rotation (`rotate 90`) is read at its display size (v7.9.4) and counts as portrait.

### 3.4. Choose the look and lock the `10×8` cell (brain)

#### 3.4.1. Choose the look

Apply 1.2: Look S unless the user explicitly asks for the `@__dviet` look. Iron law 6 versus the `dviet` typography: the swash hybrid is Look S, the condensed sans is Look D ([reference 23](./references/23_dviet_profile_decisions_and_backlog.md), decision a).

#### 3.4.2. Format x Skin, profile and canvas

Select `F1..F10` x `S1..S8` ([`format_modes_catalog.json`](./presets/format_modes_catalog.json), [reference 18](./references/18_v70_universal_studio_10x8_and_45582_microbridges.md)) and the primary archetype; optionally show [`edit_plan_viewer.html`](./templates/edit_plan_viewer.html). Profile `default` (Look S) or `dviet` (Look D). For `dviet`, take the canvas from [`canvas_presets.json`](./presets/canvas_presets.json) (`1080x1920@60` default; the others are data only). A skin `HARD VETO` (`warm_film_burn_veto` on `luxury_skincare`, `dental_clinic`, `beauty_spa`) always beats the profile.

#### 3.4.3. Safety, Dual-Rail and chromatic policy

- **Domain `HARD VETO` guards:** `CRI-100 Tooth Lock` (`S2`: pure `D65`, no yellow LUT on enamel), `Skin-Tone Guard` (`S1..S7`: no swamp-green wall tint), `Hand Safe-Box` (`S3/S4`: no overlay on nails or the held product), `R200 Claim-Gate` (`S1/S2/S4/S5/S8`).
- **Dual-Rail `9:16` + Cranial Lock (`0 %` face / hair contact) + L-Shaped TikTok Safe Zone (v8.1):** keep all hero text, widgets, 3D props and captions inside the **L-Shaped TikTok Safe Zone** at `1080×1920` — main safe box **`x: 120..840, y: 252..1216`** (clears TikTok right action rail `x > 840` and bottom caption/CTA chrome `y > 1216`), with top-right notch extension **`x: 120..960` for `y: 252..360`** where no right-rail icon sits. Place plates in the **Upper Editorial Stage** (`Y 252–520`, above the crown) or the **Chest Tactile Rail** (`Y 960–1216`, behind the person matte with `Sub-layer Feather = 29`, `0 px` hard stroke); `MAX_ZONES <= 2`; `>= 12 %` clean breathing frames (`20–30 %` emotional / vlog). Text *under* the person layer counts as sandwiched, not overlap (reference 23, decision c).
- **Chromatic policy:** `color_world_polarity` (one signature hue `55–100 %` + `<= 45 %` pain hue + `#EEF4EA` / `#FAFAFA` flips) **or** `semantic_4act_jewel` (`#059669` / `#2563EB` / `#E11D48` / `#D97706` on `#FAFAFA`, `<= 1` jewel hue per beat). Look S: chapter colour wins; Look D: one token accent.

#### 3.4.4. Micro-bridges and SFX

- **14 native-frame micro-bridges** (`native_frame_14_micro_bridges` in [`format_modes_catalog.json`](./presets/format_modes_catalog.json), each format lists its recommended six): `clean_0f_hard_cut`, `true_vocal_jcut_prelead` (`-850..-140 ms`), `acoustic_lcut_room_tail`, `concentric_geometric_match_cut`, `polarity_canvas_snap_1f`, `c2_velocity_push_handoff`, `whip_pan_directional_330`, `whip_zoom_optical_bridge`, `rvm_foreground_wipe_pass`, `split_diopter_50_50_slide`, `flash_halation_2f_pop`, `iris_mask_expand_stage`, `bgm_vacuum_drop_reentry`, `tactile_asmr_foley_pivot`.
- **Archetype bridges** (frame-count recipes in [`visual_archetypes_catalog.json`](./presets/visual_archetypes_catalog.json)): `player3_air_cushion_20f`, `rack_focus_13f`, `persistent_text_bridge_11f`, `exposure_bloom_3f`, `optical_flow_morph_6f`, `mirror_tile_whip_3d_ui_19f`, `halation_decay_4_28f`.
- **4-Cut Grammar:** `40–75 %` clean `0f` cuts, vocal J-cuts `-850..-140 ms`, `meta.bgm_stops` (`>= 0.50 s` at `-inf dB`), `<= 5` heavy whooshes per minute, 7 organic foley SFX (`R217`).
- Plan SFX with `sfx_auto.py plan`, or write `AUTO:<keyword>` clips (`spec_from_plan.py --auto-sfx KEYWORD`) and compile with `--auto-sfx-dir`. BGM ducks with `duck_keyframes.py`; a vacuum dip at most once per `20 s`.

#### 3.4.5. Look D zoom and scoped transitions

- **Zoom** ([`dviet_smooth_camera_engine.py`](./scripts/dviet_smooth_camera_engine.py)): `punch_220_q25`, `push_130_long` (`16 s`), `step_zoom_13_8_9`, `jc_reset_push_4_10`, `dolly_out_12_16` (estimates rounded to tiers), scale-driven radial blur (`apply_scale_radial_blur`), a head-top safe-box clamp (source `>= 1080p`) and **Rule C4** (a spoken run `>= 4 s` gets zoom keys, `c4_zoom_keys`). `--self-test` measures the scale curve on a 5 s synthetic clip.
- **Transitions** (`profile_scope: ["dviet"]`, [`atomic_motion_library.json`](./presets/atomic_motion_library.json)): `color_wash_multi_0p6s`, `film_burn_perf_5f`, `light_leak_overlay`, `white_flash_0p25s`, `vertical_roll_slide`, `orange_ghost_pre_cut_5f`, `vacuum_32db_0p4s`, each with `max_duration` and `caps`. Flash presets obey the photosensitivity caps of 4.2.1. Enforcement: `compile_and_verify.py --profile dviet`.
- **Opener flicker:** `flicker_schedule.py` plans the silhouette-flicker frames (a matte plate on the timeline; arbitrary-object masks and handheld tracking are out of scope, 4.3).

### 3.5. Look S recipe (brain + compositor)

Look S is built scene by scene. The V21 12-scene map, cut times, VFX-01..08 and the audio structure are in [`24_studio_look_recipe.md`](./references/24_studio_look_recipe.md).

#### 3.5.1. Scene matrix

Draft it with `studio_recipe.py --words words_tl.json --duration D --out scenes.json` (lays the V21 pattern on the transcript: mode per beat, polarity minimum, no adjacent same colour world, jewel hex per act; accepts the probe doc or a bare array of `[word, t0, t1]` / whisper `{word, start, end}`; exits `2` on an empty transcript or a `--duration` that ends before the last word), then edit it. One row per beat:

| Mode | Scene | Use for |
|---|---|---|
| **A1** | Full-Head Studio Card (`render_full_head_studio_card`) | text beats, claims, kinetic `kt` plate on a card |
| **A2** | Squircle PiP (`render_squircle_pip_window`) | B-roll, product, lens / macro, UI plate (presenter shrinks to the PiP) |
| **B** | Bottom-Flush Cutout (`render_bottom_flush_cutout`) | depth beats, polaroid trio, CTA, dark silk |
| **P** | Polarity paper: A1 on `#FAFAFA` | light scene, chapter ink on paper |
| **N** | Neon blackout (`apply_fullwidth_neon_rim_blackout`) | tension beat ("the problem is...") |
| **S** | Silk numeral stage (B cutout on dark silk + giant glowing numeral) | steps 1 / 2 / 3 |
| **H** | Hook: full-screen B-roll with the presenter in a PiP | the first beat |

#### 3.5.2. Scene type -> template

| Scene type | Template |
|---|---|
| hero B-roll hook | `H` + PiP |
| polaroid trio | `skewed_3d_polaroid_trio` |
| steps 1 / 2 / 3 | numeral plate + `A1` or `B` |
| bento | `frosted_glass_bento_steps` |
| prompt | `isometric_3d_prompt_browser` |
| lens or macro | `A2` PiP |
| arc text around the head | `kt11` |

#### 3.5.3. Render with `look_s_render.py`

`look_s_render.py --scenes scenes.json --words words_tl.json --aroll <video> --work <dir> --out <master.mp4> [--draft|--master] [--broll-dir DIR] [--dry-run]` renders the edited `scenes.json`; you do not write your own driver. `--dry-run` validates every input and prints the per-scene plan; `--draft` (default) is `540x960 @ 30`, `--master` is `1080x1920 @ 60fps`. Optional: `--alpha-npy` + `--alpha-fps` (a person matte cache, else the matte model; the fps is part of the segment hash and a matte whose frames / fps does not cover the A-roll is a warning), `--audio`, `--overlays` (the `kt` `.mov` plates and screen VFX as JSON) **or** `--overlays-from-plan <work>/plan.json` (v7.9.4: builds them from the `plan_dviet_kinetic_beat_schedule` plan of 3.6 after the plates are rendered: `src`, `at`, `dur`, `motion.position` -> `cx, cy`, plate size from the rendered `.typo_meta.json` -> `orig_w, orig_h`, `motion.scale / 100` -> `scale`; library `look_s_render.overlays_from_plan(plan, base_dir)`), `--clean-wall` + `--wall-ref-t <s>` (the low-head wall reference frame time, default `0`), `--jobs`, `--no-voice-guard`. **B-roll (v7.9.3):** each `H` / `A2` scene gets the file with the most remaining seconds that fits; showing the same source seconds twice is **exit `2`** unless `--allow-broll-reuse` (then a warning); short-lived stray blobs are scanned and `broll_ss` moves past them (`--no-broll-artifact-scan` turns the scan off). **Mirror (v7.9.4):** `--emit-overlays OUT.json` writes the final placed overlays (after the product-safe moves, `--overlays` format) and `--emit-scenes OUT.json` the resolved scenes (`broll` absolute, `broll_ss`, `stage`, effective `cam`, `hook_motion`); build the `.fcproj` spec from these so it mirrors the master, and re-render from the original `scenes.json` (an explicit `cam` turns hook auto off; the segment cache keys stay valid). Exit codes: `0` ok, `2` invalid input, `3` voice guard rejected, `4` render / compose failure; a JSON summary goes to stdout. A scene with `popout: true` on a `P` paper card renders the pop-out card. Underneath it runs the compositor call order: `init_hair_safe_wall_reference` once on a low-head frame -> `clean_aroll_preserve_hair_crown` per frame -> the scene's `render_full_head_studio_card` / `render_squircle_pip_window` / `render_bottom_flush_cutout` / `apply_fullwidth_neon_rim_blackout` -> `pipe_encode_single_plate_fast` (one cached plate MP4 per segment) -> `compose_master_mp4_via_ffmpeg` with the `kt` `.mov` plates and the flash clips as overlays. The compositor's own CLI renders no studio plates (2.2 item 6).

**Hook auto (v7.9.2, on by default).** An `H` / `A2` B-roll scene that starts inside `0–3.4 s`, holds `> 0.8 s` and whose source window is static (`motion_gate` frame diff `< 2.0`) gets a product-anchored ease-in-out push (`<= +25 %`) + pan + one `glint_sweep` (`fast_studio_compositor.hook_push_params`; an explicit `cam` is kept); `--no-hook-motion` turns it off. The product box comes from `fast_studio_compositor.product_bbox_from_frame` (u2netp saliency, luma / edge fallback); every `kt` overlay inside such a scene whose glyph box overlaps it moves to the nearest clear band (no product, no PiP, safe zone `50..1030 x 140..1760`, size unchanged); `--no-product-safe-text` turns it off. The summary reports `hook_auto` (per scene `source_mean_diff`, `motion`, moved / unresolved overlays) and `product_bbox` for `check_hook`; an overlay with no clear band (product taller than the frame) switches that hook scene to the product stage (`render_product_stage`, `s 0.72`, cap at `y ≈ 613`, text band `96–593`; push / pan anchored on the cap top, product box re-detected on the staged frame) and is placed again (`--no-stage-fallback`: it stays put with a warning). When the planned move is predicted under the `2.0` floor (270x480 probe render), `snap_punch` zoom steps are added about once per `0.8 s` on word onsets (`+10 %` snap, `0.35 s` settle, slow push shrunk so push x punch `<= +25 %`, product kept in frame, no flash by default); each counts as a `hook_motion_floor` background reset. If the prediction is still under `2.0` after the steps, the scene is listed in `hook_auto.below_floor_scenes` (`motion_below_floor: true`) with a warning: use a moving B-roll or set `stage` / `cam`.

**Look S full run (in this order).** 1. `probe_and_align.py` (3.3) -> 2. `studio_recipe.py --out <work>/scenes.json` (3.5) -> 3. `plan_dviet_kinetic_beat_schedule(..., workspace_context=, scenes=)` saved as `<work>/plan.json`, then `render_kinetic_typo_batch(plan["batch_jobs"])` (3.6) -> 4. `look_s_render.py --master --overlays-from-plan <work>/plan.json --emit-overlays <work>/overlays_final.json --emit-scenes <work>/scenes_final.json` (voice = the A-roll audio) -> 5. `spec_from_plan.py --plan <work>/plan.json --fps 60 ...` then point the overlay clips at `overlays_final.json`, the B-roll clips at `scenes_final.json`, and add the SFX / BGM tracks (3.4.4) -> 6. `compile_and_verify.py ... --scenes <work>/scenes.json --audio-profile studio_14` (3.7; writes `<work>/mix.wav`) -> 7. `look_s_render.py` again with the same arguments plus `--audio <work>/mix.wav` (segments come from the cache; only the compose re-runs) -> 8. the gates of 5.2.

#### 3.5.4. Look S rules

At least **2 light `#FAFAFA` polarity scenes (about `14 %` of the duration)**; **plain full-frame A-roll `<= 25 %`**; **no two adjacent beats in the same colour world**; B-roll is **full-screen and clean** with a PiP presenter, **never covering the face**, and matches the meaning of the beat; **md5-dedup the downloaded Flow assets** (the same clip never twice).

#### 3.5.5. Framing and source

Master gear `--master` (`1080x1920 @ 60fps`). A `720p` source: **pre-upscale inside the card** (resize the A-roll once to the card size) and **do not use FilmCraft scale `150-168%`** (it softens and bloats the head). Framing from the V14 look: face low at `y ~ 62 %`, headroom `105-115 px`; the **Left-Third `136%` crop is rejected** unless the source is `>= 1080p` and the head scale stays `<= 1.18x`. For the cranial audit pass `compile_and_verify.py --context workspace_context.json` (`subject_framing.face_bbox_norm`, `cranial_zone`) so Gate 3B knows where the head is when the V1 clip carries no face box.

#### 3.5.6. Hook and pacing

Build the first `3.4 s` from `studio_recipe.hook_template()` and the voice words (`hook_text_from_words(words)`: the text follows the voice, the voice is never re-cut), put the hero in the stage above the product, give every `1.0 s` a background reset, then split long scenes so no hold exceeds `2.4 s`. Implement every pacing fix as a scene split with its own `cam [a, b]`, visual only, speed `1.0x`; keep speech density, text density and loudness. When a text is retimed, regenerate the SFX in the same pass. Run the plan gates of 4.2.1 and 4.2.2, then measure the render (5.2); report plan checks and measurements separately, labelled `[ĐO]` (measured) / `[ƯỚC]` (estimate). Details: [`28_hook_first_5s_and_pacing.md`](./references/28_hook_first_5s_and_pacing.md).

#### 3.5.7. Pop-out card (optional light-card scene)

`render_popout_studio_card` (flag **Look S pop-out**, `PFD_LOOK_S_POPOUT`), class **B** (two RGBA plates + the master composite): crown `y >= 130 px`, headline clear of the crown, the matte fringe fixed first; limits in 4.2.3. The spec has no `masks` key (gap H5). Recipe: [`29_popout_card_premiere_to_filmcraft.md`](./references/29_popout_card_premiere_to_filmcraft.md).

#### 3.5.8. Deliverables

Look S is **mp4-first**: the `look_s_render.py --master` MP4 plus the `.fcproj` mirror compiled from the same plan (3.7). The rule is stated in 3.8.1.

### 3.6. Typography and web-cinema plates

1. **Schedule beats:** `typography_composer.plan_dviet_kinetic_beat_schedule(beats, words, ..., workspace_context=<work>/workspace_context.json, scenes=<work>/scenes.json)` (v7.9.3: the measured face, and per beat face-visible or not from the scene mode; a dropped `accent_text` raises unless the beat sets `allow_drop_accent: true`; dropped text is listed in `stats.dropped_text`) against `words_tl.json` (onsets `Δf = 8..16f @ 60fps`), `35 / 35 / 30` rhythm, `Swash-Initial Hybrid` (`[0]` ASCII swash `ℒ, 𝒩, 𝒬, ℋ, ℳ` + `[1..n]` NFC italic), no `— ALL CAPS KICKER`, no duplicate pills (`<= 30 %` pill share), `<= 2` consecutive identical silhouettes / entrances, `>= 4` distinct templates when `>= 8` beats.
2. **Role text (Look D):** `dviet_text.py`: caption `y` by layout (`talking 52–58 %`, `panel 67 %`, `hero 27 %`, bilingual EN line `80–85 %` yellow italic), two-tier lock-ups, swash only for `script_accent`.
3. **Render plates:** `web_plate_builder.render_kinetic_typo_batch(...)` (`kt01..kt12`, `60fps` RGBA `.mov`, never `mode="still"` `.png`), the 3D studio plates, the layout templates, and / or Lane C canvases. Every text obeys the `64 px` floor (4.2.3).
4. **Typography v8.1 (`presets/typography_v81_presets.json`):** pair 1 of **6 font pairings (`FP1..FP6`)** with 1 of **8 gradient+glow palettes (`PAL_*`)** and rotate through **10 multi-font/multi-color Text Phụ modes (`sub_01..sub_10`)** enforcing **`max_consecutive = 1`** and **zero black strokes** (soft directional drop-shadow / multi-pass glow only), all clamped to the L-Shaped TikTok Safe Zone (`x: 120..840, y: 252..1216`; top-right notch `x: 120..960` for `y: 252..360`).
5. **17-Industry 3D Asset Catalog (`presets/assets_3d_catalog.json`):** use [`local_3d_props.py`](./scripts/tools/local_3d_props.py) for instant local 3D PBR turntable props (RGBA `.mov`/`.png`) or [`flow_3d_assets.py`](./scripts/tools/flow_3d_assets.py) for the Google Flow photoreal 3D tier, mapped per industry skin and co-layered on `V4 · 3D & Widgets`.
6. **Assemble `<project>.craft.json`** (via [`v8_to_craft_spec.py`](./scripts/tools/v8_to_craft_spec.py) for `v8_edit_plan.json`, or `spec_from_plan.py` for kinetic plans, [reference 21](./references/21_craft_json_minimal_spec.md); Look S: `--fps 60`): `.mov` overlays, non-overlapping lanes (`V4a`, `V4b`, ...), 48kHz stereo PCM `.wav` voice, single-stem bridges (`kt06`, no unspoken `0.5–4.8 s` spoilers, no bridge-plate collisions), `meta.format_mode`, `meta.industry_skin`, `meta.active_safety_guards`, `sub_layer_feather_px: 29`, unclipped SFX tails.

### 3.7. Compile and verify (`~55–95 s`)

1. Run `compile_and_verify.py` (commands in 2.4). **Look S must pass `--audio-profile studio_14`**; without it the default `platform` masters to `-16 LUFS`. Look S also passes `--scenes <work>/scenes.json` so Gate 5 FACE_ROOM checks the face only where it is visible (the PiP rect on `H` / `A2`). Look D: `--profile dviet --audio-profile tiktok_loud`.
2. Pass `--words` (or `--manifest`): without them Gate 3 reports **SKIPPED**, not PASS. If `edit_rules.py` crashes, Gate 3 FAILS.
3. Pass `--strict-rules` for delivery: without it, `edit_rules` errors (`LỖI`) and Cranial / CRI-100 findings stay **WARN** and the verdict is `DONE_WITH_CONCERNS`. Pass `--hook-gates --preview <master.mp4>` (Look S): without it the rendered hook motion is not measured at compile time; with it a motion failure is a concern in the report.
4. Read `EDITOR-REPORT.md` and open `qa_contact_sheet.jpg` (`1440x2560`) with your image-viewing tool: `0` Gate 3C vetoes (`STATIC_HERO_PNG_STAMP`, `LAYOUT_SILHOUETTE_MONOTONY`, `PILL_BADGE_OVERUSE`, `ENTRANCE_STYLE_MONOTONY`), `0` `CRANIAL_LOCK` / `HARD VETO` / `CARD_TEXT_COLLISION` / `RAINBOW_HUE_SOUP`. Repair surgically and recompile; gate meanings in 5.1.

### 3.8. Hand-off

#### 3.8.1. Rule A1

**Rule A1:** deliver the editable `.fcproj`; export an `.mp4` only when the user asks or in draft mode, via `python3 ./scripts/tools/fc_export.py IN.fcproj OUT.mp4` (FilmCraft + Xvfb; `-sn`, no metadata). **Look S & v8.1 Dual-Deliverable FilmCraft Bridge:** deliver the `60fps` MP4 master (`1080x1920 @ 60fps`, `-14 LUFS`, `-sn`, no metadata) **and** the editable `.fcproj` mirror in one command via `v8_compositor_fx.py --plan v8_edit_plan.json --out master.mp4 --export-fcproj project.fcproj [--craft-spec project.craft.json]` (converts via `v8_to_craft_spec.py` and compiles via `compile_and_verify.py --tier fast --audio-profile studio_14`; if FilmCraft/Xvfb is unavailable, preserves `.craft.json` with `fcproj_status: "spec_ready_filmcraft_unavailable"` without failing the MP4 master). Look D and every other run follow Rule A1. A failed gate means no delivery (5.4).

#### 3.8.2. Gate 7b (brain-triggered, shift once)

On an already exported MP4: `qa_sync.py --video EXPORTED.mp4 --spec X.craft.json` -> `sfx_shifts.json`. If you agree, `sfx_shift.py --spec X.craft.json --shifts sfx_shifts.json --out NEW.craft.json` **once** (`meta.sfx_shifted_once`), recompile, measure again, decide the rest by hand. No automatic loop. Blocking rows: 5.3.

#### 3.8.3. B-roll

`broll_from_video.py analyze --transcript words_tl.json --out broll_plan.json`, write the English prompts, then `check-prompts`. There is one prompt lint contract, [`broll_lint_contract.json`](./presets/broll_lint_contract.json), the source of truth for both `broll_from_video.py check-prompts` (ingest) and `visual_blocks.lint_broll_prompt` (plates, no anchor check) (English, `8–60` words, an `anchor_quote` that appears in the slot text; rules `NOT_ENGLISH`, `WORDS`, `EMPTY`, `ANCHOR_MISSING`, `ANCHOR_NOT_IN_TEXT`, `TEXT_IN_IMAGE`, `BRAND`, `FACE`, `R200`). AI B-roll is never proof (`R200`). Google Flow workflow: [`22_flow_broll.md`](./references/22_flow_broll.md).

## 4. Rules and guardrails

### 4.1. Iron laws

1. **Syllable-locked `60fps` kinetic typography + Cranial Lock:** schedule with `plan_dviet_kinetic_beat_schedule`, render with `render_kinetic_typo_batch`. Never static `mode="still"` hero `.png` (`STATIC_HERO_PNG_STAMP`), `PIL/OpenCV` 3D bevels, `— ALL CAPS KICKER`, duplicate pills, or `> 2` consecutive identical silhouettes / entrances; keep `35 / 35 / 30`, `0 %` face / hair contact, `MAX_ZONES <= 2`, `CARD_TEXT_COLLISION = 0`. The 4-Cut Grammar is a hard law in every profile. Never stamp `S13` raw karaoke.
2. **Domain `HARD VETO` circuit breakers and `R200`:** never tint enamel yellow (`CRI-100`), never swamp-green walls on skin (`Skin-Tone Guard`), never occlude nails / product (`Hand Safe-Box`), never fake proof with AI B-roll (`R200`), never let profile `dviet` unlock film-burn / light-leak on a skin with `warm_film_burn_veto`.
3. **Chromatic integrity:** one colour world + polarity flips **or** the 4-act jewel inks on `#FAFAFA` (`<= 1` jewel hue per beat, no rainbow soup, no default `S13` karaoke).
4. **Micro-bridges, bimodal `C7`, no `f = 0` freeze:** never chop syllables in `[-130, -10] ms`, launch post-cut clips with `ds/dt != 0` (`player3_air_cushion_20f`), whisper `G2` at `Y >= 1360` (`R209`), `shutter_override: true` (`180–300°`) on whips and morphs.
5. **Rule A1 and the wgpu guard:** hand-off per 3.8.1; whenever `opacity.blend != 0`, disable `drop_shadow` (FilmCraft `0.13.0`'s `wgpu 0.20.1` falls back to CPU otherwise).
6. **Vietnamese NFC, `Swash-Initial Hybrid`, compound glue (`R55` / `R30`):** Unicode NFC; swash hybrid for Look S, condensed sans for Look D (swash only for `script_accent`); `padding_top >= 0.28–0.30 em` on `0.78` line-height; the `1199` glue pairs of [`text_vi.json`](./data/text_vi.json); `>= 3f` last-word hold (`R30`); banned fonts `Anton`, `Bebas Neue`, `Instrument Serif`, `Great Vibes` (`Instrument Serif` / `De Fonte` only for role `font_specimen` under profile `dviet`).
7. **Zero-Voice-Loss + 100% Verbatim Caption Rail + Co-Layered Craft (v8):** never truncate or mute spoken voice across B-roll or stage inserts (`abs(out_dur - in_dur) <= 0.15 s`); keep every spoken word on the verbatim caption rail (`verbatim_caption_rail.py`); default to `9:16` (`1080x1920@60`) and use `16:9` (`1920x1080@60`) strictly on explicit user request; strip all EXIF/XMP/C2PA metadata on delivered MP4s.

### 4.2. Gates and where each is enforced

An error blocks delivery until the cause is fixed; never loosen a limit. **Enforced by** says who stops the run:

- **compile** = `compile_and_verify.py` gate (FAIL stops the build);
- **library** = a function the brain must call on the plan and act on (nothing calls it for you);
- **qa_sync** = `qa_sync.py` exits `1`;
- **motion_gate CLI** = `motion_gate.py` exits `1` (also via `compile --hook-gates`, where it becomes a report concern);
- **plate block** = `web_plate_builder.render_web_plates_batch` raises and renders nothing.

Basis: one user build plus 17 `@__dviet` samples of one channel; thresholds are `[ƯỚC]` unless marked `[ĐO]` ([reference 28](./references/28_hook_first_5s_and_pacing.md)).

#### 4.2.1. Hook (`0–3.4 s`)

| Gate | Limit | Enforced by |
|---|---|---|
| `first_text` | first text at `<= 200 ms` | library: `studio_recipe.check_hook(plan, words=words)` |
| `first_text_late` (the one first-text rule, default on) | the first text is on screen at or before its first spoken word and leads it by `<= 250 ms` (`first_text_lead_ms` upper bound; its `-50 ms` lower bound applies only with `strict_first_text=False`); `hook_text_from_words` places the lead line `20 ms` before the word | library: `check_hook` |
| `text_voice_sync` | every later text `0–400 ms` before its first spoken word (warn outside `100–250 ms`); a numeral only within `±400 ms` of its voice; `words=None` only warns | library: `check_hook` |
| `hero_safe_zone` | hero box overlaps `product_bbox` (or the stage cap-top line `0.32 H`) by `0 px`; hero tier box `12–18 %` of H | library: `check_hook` (pass the `product_bbox` of the `look_s_render.py` summary); rendered twin `motion_gate.hero_product_overlap_px`; `look_s_render.py` moves hook overlays off the detected product automatically (3.5.3) |
| `text_coverage` | from the first text to `3.0 s` no stretch `> 150 ms` without text | library: `check_hook` |
| `hook_motion_floor` | a **background** reset (cut, flash, glint, card landing, zoom step `>= 4 %`) in every `1.0 s` of `0–3.4 s`; PiP pops and text do not count | library: `check_hook`, `hook_motion_floor()`; `look_s_render.py` adds a push + pan + glint to a static hook B-roll automatically (3.5.3) |
| `flash_luma_cap`, `flash_rate` | a flash never lifts the frame mean luma above `220` (0..255); `<= 3` flashes in any 1 s (WCAG 2.3.1); a white cut is `opacity <= 70`, ramped over 3 frames; the `dviet` flash presets carry the same caps | library: `check_hook` -> `motion_gate.check_flash_plan`; render: motion_gate CLI `--flash` |
| Rendered motion | masked frame-diff mean `>= 2.0` and no run `< 1.0` longer than `0.6 s`, over the `motion_gate.py` default window `--t0 0 --t1 3.4` sampled at `--fps 30` (the `@__dviet` B-roll-first bar is `1.9–2.4`, not V21) | motion_gate CLI (`check_motion`); `compile --hook-gates --preview` |
| Hook loudness | `-12 LUFS ±0.5`, `<= -1.0 dBTP` after ducking (`hook_0_5s.loudness` in `studio_scene_recipe.json`) | **advisory, not enforced**: no gate reads it; the master stays `studio_14` |

#### 4.2.2. Pacing

| Gate | Limit | Enforced by |
|---|---|---|
| max hold | no hold `> 2.0 s` without a reset (cut, zoom step, flash, new text); recipe cap `2.4 s` (error) | library: `studio_recipe.check_pacing(shots, resets, duration)` (`hold_s`, `dead_hold_share` per window) |
| resets per window | `>= 3` resets in `0–5 s`, `>= 2` in every later `5 s`; `>= 2` shots under `1 s` per `10 s` (advisory); dead holds `<= 45 %` (plan proxy `[ƯỚC]`) | library: `check_pacing` |
| `bg_static_hold` | full-screen B-roll hold `> 0.8 s` in the hook (`> 1.2 s` elsewhere, warn) needs a push `>= 10 %/s`, a pan `>= 4 %` of the crop per second or a glint | library: `check_pacing`; remedy `plan_micro_moves(shots)` |
| source reuse | the same B-roll source seconds never twice | library: `check_source_reuse(shots)` |
| punch-in caps | B cutout `+6 %`, A1 card `+12 %`, PiP inner `+8 %`, full-screen B-roll `+25 %` | brain (reference 28) |

#### 4.2.3. Pop-out card and text

| Gate | Limit | Enforced by |
|---|---|---|
| `text_min_size` / legibility | EVERY overlay text, card label, plate caption and whisper `G2` line: CSS px x plate scale `>= 64 px` on the canvas, glyph `>= 3.3 %` of H; secondary plate text at `SECONDARY_TEXT_PX` `70 px`; `decorative: true` only warns; `enforce_min_text_px(forced=True)` with an illegible size raises | plate block (`UndersizedTextError`: CSS audit before Chrome, rendered sizes after); library: `check_hook` (`labels`), `check_text_legibility`; rendered twin `motion_gate.text_glyph_height_frac` |
| `word_gap_collision` | adjacent-word gap `>= 0.25 em` on every visible frame of a blur-in / scale-in; line-level blur-ins widen word spacing with the blur (`entrance_word_spacing_em`) | library: `motion_gate.check_word_gaps`, `check_hook`; kt02/04/05/07/08/09/11 plates guard `[data-ws-nat0]` every frame; FilmCraft tracking keys via `typography_composer.apply_entrance_word_spacing` |
| pop-out sharpness | edge 10–90 % `<= 6 px` `[ĐO]`; face-ROI Laplacian `>= 1.8x` plain Lanczos (not the whole-frame `430`); side bow `<= 12 px`; pop `7–11 %` of H | library: `motion_gate.popout_edge_width_px`, `face_laplacian_ratio` |
| pop-out clean edge | inner dark strip `<= 4 px`, `0` wall specks, crown jaggedness `<= 1.2 px`, crown rise `<= 4 px` | defaults of `render_popout_studio_card(clean_source_bands, despeckle_wall, crown_refine)`; library: `motion_gate.popout_inner_edge_dark_strip_px`, `card_dark_speck_count`, `crown_edge_metrics` |
| SFX block rows (Gate 7b) | a row with sound `> 0.1 s` before the picture is `block: true`, never ĐẠT | qa_sync (5.3) |

### 4.3. Promise classes A / B / C (what the director may promise) and backlog

Classification of [`27_premiere_recipes_to_filmcraft.md`](./references/27_premiere_recipes_to_filmcraft.md); the ranked list of what is NOT implemented is in [`23_dviet_profile_decisions_and_backlog.md`](./references/23_dviet_profile_decisions_and_backlog.md). Promise only what the class allows.

| Class | Meaning | May promise | Examples |
|---|---|---|---|
| **A** native | built on the FilmCraft timeline from clips, effects, motion, opacity, blend, transitions, text clips | yes, in the spec | RGB fringe, vertical flip, warp, sticker sparkle (given a PNG), static wall text via `corner_pin`, raw card layouts |
| **B** pre-rendered plate | needs a plate / asset with alpha made by the skill's tools (ffmpeg, OpenCV, `web_plate_builder.py`, the `u2netp` person matte), then placed as a clip | yes, as a plate; say it is pre-rendered and approximate | silhouette flicker, vanish, clone with a static camera, slit-scan approximation, the pop-out card |
| **C** not feasible | needs a model or tool the skill does not have | **no**; say so, offer the B approximation | arbitrary Object Mask quality (`u2netp` is salient-object only; no RVM shipped), occlusion-aware planar tracking (Mocha-class), true 3D keycap lighting, native Time Displacement |

**BACKLOG (do not promise yet):** waveform SFX tile, keycap tile, NLE-timeline tile, wall-pasted text on a **handheld** shot (needs the tracker, H4 in reference 27), the spec `masks` key (H5). Loudness: `tiktok_loud` numbers are labelled measured vs derived in [`25_loudness_tiktok_vs_nle.md`](./references/25_loudness_tiktok_vs_nle.md); never quote an official TikTok normalization figure, none is published.

### 4.4. `@__dviet` evidence rules

- The truth source is **17 measured videos**, indexed in [`references/dviet_19/INDEX.md`](./references/dviet_19/INDEX.md) (table, recurring signatures with counts, gap table *observed -> done / backlog*). The folder keeps its old name `dviet_19` but holds 17 videos; older references that say "19" counted two videos without evidence files.
- Decisions with provenance and the ranked BACKLOG: [reference 23](./references/23_dviet_profile_decisions_and_backlog.md); runnable tokens: [`dviet_style_tokens.json`](./presets/dviet_style_tokens.json).
- Numbers flagged *estimate* / `[ƯỚC]` are not standards. It is one channel: never present a `@__dviet` number as a platform rule. The per-video files are read-only evidence.

## 5. QA and error handling

### 5.1. Gate catalogue

| Gate | What | Fails the build (verdict `REJECTED`) when |
|---|---|---|
| 1 Mechanical sanitizer | `bgm_stops`, `lag_ms`, micro-fades, MD5 dedup, `AUTO:` SFX resolution | `AUTO:` clips exist without `--auto-sfx-dir` |
| 2 Spec lint | vendored `spec_lint.py` | any hard lint item |
| 3 Editorial rules | vendored `edit_rules.py` + 4-Cut / `C7` adjudicator; Gate 3B Cranial Lock, colour / density; Gate 3C anti-template vetoes; CRI-100 | `edit_rules` crashes; a Gate 3C veto, a Cranial or CRI-100 audit `FAIL`; with `--strict-rules` also any `LỖI` and any Cranial / CRI-100 violation. **SKIPPED** (not PASS) without `--words` / `--manifest` |
| 4 FilmCraft compile | `fc_build` parity, keyframes, `AdjustmentLayer` micro-bridges, 1-frame render smoke | the build fails or mismatches, or media is offline. Without FilmCraft or X the smoke is reported SKIPPED, never PASS |
| 5 Post-FX + contact sheet | 16 QA frames, pixel / face-room audit | QA frames or `mix.wav` missing, blank frames |
| 6 Loudness | closed-loop EBU R128 to the `--audio-profile` target, `R35` post-AAC true peak (tier `full`) | integrated loudness off target by `> 0.55 LU`, or true peak (also after AAC) above the ceiling |
| 7 SFX integrity | vendored `audit_sfx.py`, `R217` `match_at` NCC sync | the audit fails, a take repeats, an SFX file is missing |
| 8 Epistemic verdict | `R200` `claim_gate`, tri-state verdict | any earlier gate raised (`REJECTED`); open concerns give `DONE_WITH_CONCERNS`, a clean run `VERIFIED` |

The plan-level gates of 4.2 are not in this list: call them yourself.

### 5.2. Rendered gates (`motion_gate.py`)

`python3 ./scripts/tools/motion_gate.py VIDEO [--mask x0,y0,x1,y1] [--t0 0 --t1 3.4] [--fps 30] [--flash]` prints JSON and exits `1` when not ok. Without `--flash` it runs `check_motion` (4.2.1); with `--flash` it checks flashes over `--t0..--t1` (the whole video when `--t1` is negative) at 60 fps. The default window is the whole hook; `--t0 2.03 --t1 3.38` gates only the late-hook sub-window. Mask the PiP and text boxes so only the background is measured. The single-frame metrics (`popout_edge_width_px`, `face_laplacian_ratio`, `hero_product_overlap_px`, `text_glyph_height_frac`, `popout_inner_edge_dark_strip_px`, `card_dark_speck_count`, `crown_edge_metrics`, `check_word_gaps`) are library functions; the plan-level twins live in `studio_recipe.py`. Report the plan check and the measurement separately.

### 5.3. Sync QA (Gate 7b)

`qa_sync.py` measures SFX against the picture on an *already exported* MP4 and writes `sfx_shifts.json`. A row with `block: true` (sound `> 0.1 s` before the picture) is never ĐẠT and keeps the gate failing (exit `1`) while it remains; `sfx_shift.py` applies the shifts once to a NEW spec (3.8.2).

### 5.4. Error handling and escalation

- **Preflight:** `env_status.py --strict` exits `1` when a required item is missing; fix it (the `remedy` field says how) before ingest. Do not start a compile without FilmCraft `>= 0.13.0` and Xvfb.
- **A failed gate means no delivery.** Read the gate's `Fix:` line in `EDITOR-REPORT.md`, repair the cause in the plan or spec, recompile and re-measure. Never loosen a limit, never deliver a `REJECTED` or unverified build, and say plainly what is still `DONE_WITH_CONCERNS`.
- **Chrome / Node fails** (Lane B): check `CHROME_BIN` / `NODE_BIN`, lower the worker count, keep the person-matte pass and Chrome sequential (execution_tiers `sequential_rvm_then_chrome_max2`); an `UndersizedTextError` is a design error: enlarge the text, do not force it.
- **FilmCraft fails:** `filmcraft_cli.py` and the Gate 4 smoke skip loudly (`SMOKE SKIPPED`, exit `2` with `skipped: true`) and never fake a render; never use the user's display `:0`. Start Xvfb (or set `CRAFT_DISPLAY`), check `filmcraft --version`, rerun. Without FilmCraft you may hand off the spec and the Look S MP4, stating that the `.fcproj` was not verified.
- **ffmpeg fails:** check `ffmpeg -version` (6.1+) and the input (`probe_and_align` rejects 0-byte / corrupt video); a loudness miss in Gate 6 is fixed by levels in the mix, never by raising the master.
- **Escalate to the user** when the footage cannot meet a veto (face too close to the frame edge, no audio, a claim without proof) instead of working around it.
