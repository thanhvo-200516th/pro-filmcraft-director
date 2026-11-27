# 15 — Adaptive Execution Tiers (`fast` vs `full`) & Epistemic QA Physics (`v5.1`)

> **Historical reference (v5.1).** Kept as design history; the current spec is [reference 21](./21_craft_json_minimal_spec.md) and the current process is [`SKILL.md`](../SKILL.md). Where this file disagrees with them, they win. Rule A1 and its Look S MP4 exception are stated once, in `SKILL.md` section 3.8.1.

`pro-filmcraft-director v5.1` distills the highest-signal linguistic, optical, acoustic, and epistemic invariants from `dung-video-talking-head@1.2.3` into **stateless helper functions and configurable QA tiers**—preserving 100% bespoke Creative Director Judgment (`BRAIN`) without locking videos into a rigid batch pipeline.

---

## 1. Dual-Tier Execution Policy (`--tier fast | full | auto`)

Configure tool depth in [`execution_tiers.json`](../presets/execution_tiers.json) so mechanical latency scales with footage complexity and factual stakes:

| Dimension | `fast` (Gói Nhanh — `P0` Core Physics) | `full` (Gói Toàn diện — `P0 + P1 + P2` Studio Proof) |
|---|---|---|
| **Runtime Target** | **~55–60s** end-to-end | **~68–75s** end-to-end |
| **CLI Flags** | `probe_and_align.py --tier fast`<br>`compile_and_verify.py --tier fast` | `probe_and_align.py --tier full`<br>`compile_and_verify.py --tier full` |
| **Ingest (`probe_and_align`)** | Media probe, Whisper word timestamps (`NFC`), slice alignment, `assets_contact_sheet.jpg` | + `textnorm` spoken-number/unit alignment, `20ms` RMS pause-end onset refinement (`-35/-45 dBFS`), `270×480` Viola-Jones `eye_band` & `mouth_band` tracking |
| **Typography & Face Safety** | `text_vi.json` (`1199` `glue` pairs + `leads`/`trails` via `split_phrase_2line`), `R209` bottom-edge drop (`Y >= 1360`), `R30` `>= 3f` last-word readability + `0.95` ink-width fit | + Projected `facesafe` Eye/Mouth vs Glyph Ink-Box (`0.30em` pad + `0.01em` margin, `8px` clearance), `R26` no-glow over face, `R208` `< 1.5s` hook exemption |
| **B-Roll & Visual Hygiene** | On-demand `visual_blocks.py` generators + 16-frame QA contact sheet | + `clean_broll_plate` border stripper, `lint_broll_prompt` (46 tokens historically; since v7.9.1 it reads `presets/broll_lint_contract.json`) hygiene (`F2`), `V8` Frozen/Blank B-roll detector (`std >= 30/255`, diff `> 20/255`) |
| **Audio & Loudness** | `5ms env5` `lag_ms` + `sync_frame` peak-on-cut SFX aligner, MD5 dedup, `R217` `match_at` normalized xcorr, closed-loop `-16/-14 LUFS` | + `0.5s`-step BGM offset optimizer (`LRA <= 5.0 LU`, `voice - bed >= 10 LU` short-term floor), `R35` `4x` True-Peak post-AAC encode-measure-ratchet guard |
| **Epistemic & Handoff** | Rule A1 native `.fcproj` + `-sn` guard (Look S exception: `SKILL.md` section 3.8.1) | + `R200` `claim_gate` audit + `EDITOR-REPORT.md` (`VERIFIED \| DONE_WITH_CONCERNS \| REJECTED`) |
| **Select When** | Daily opinion talking-heads, clean pre-sliced folders, philosophical essays, founder stories, rapid Option A/B/C drafts | Uncut raw camera takes (`soucre quay`), E-com / Real-Estate / Clinic / SaaS proof videos (`claim_gate: true`), defective `.fcproj` rebuilds, client handoffs |

### Rule Confidence Hierarchy (`high` vs `medium` vs `low`)
Every entry in `execution_tiers.json -> rule_provenance` carries an empirical confidence tag:
* **`high` (Immutable Physics & Ethics):** `wgpu 0.20.1` blend+shadow guard, Unicode `NFC` + `0.28em` pad, `text_vi.json` compound glue (`R55`), `R209` bottom-edge drop, `R30` 3-frame readability, `R217` normalized xcorr (`[-1f, +2f]`), BS.1770-4 + `R35` True-Peak, and `R200` `claim_gate`. **Never violate.**
* **`medium` (Calibrated Empirical Invariants):** Projected `facesafe` eye/mouth clearance (`R26`/`R208`), 46-token B-roll prompt hygiene (now `presets/broll_lint_contract.json`) (`F2`), `V8` frame-delta liveness, and BGM `LRA <= 5.0 LU`. Override only with explicit justification logged in `EDITOR-REPORT.md`.
* **`low` (Bendable Aesthetic Heuristics):** Archetype ASL windows (`1.8–5.5s`), zoom amplitudes (`1.06–1.22x`), and SFX density presets (`calm`/`standard`/`punchy`). **Bend freely** whenever Walter Murch's Rule of Six #1 (**51% Emotion**) demands stillness or breath.

---

## 2. Epistemic Integrity (`Ruling R200 — claim_gate`) & B-Roll Hygiene

### 2.1 `Ruling R200` — AI B-Roll Is NEVER Empirical Proof
Classify every non-A-roll visual slot into one of two epistemic classes before generating or placing media:

1. **`light` (Illustrative / Atmospheric — `claim_gate: false`):**
   - Metaphors, general workflow atmosphere, conceptual objects, mood context (e.g., *"AI giống như một người trợ lý cần brief rõ"*).
   - **Allowed:** Clean AI stills/clips (via `clean_broll_plate` + `lint_broll_prompt`), licensed `stock_context`, or bespoke editorial blocks.
2. **`heavy` (Empirical / Verifiable Proof — `claim_gate: true`):**
   - Triggered whenever spoken narration asserts:
     - Concrete ROI, revenue, conversion, price, or yield numbers without public citation;
     - Real product/tool tests (e.g., comparing *"bản miễn phí vs trả phí"*, benchmark latency, live coding output);
     - Real client/patient/student case studies or community posts requiring consent;
     - Time-sensitive AI/industry news requiring date & source verification.
   - **Mandatory Director Action:**
     - **NEVER** fabricate fake before/after photos, fake UI screenshots, or fake analytics charts with an image/video generator.
     - Use real user-supplied footage (`screen_rec`, `real_output`), or present the spoken figures transparently as deterministic typographic/diagrammatic graphics via `visual_blocks.py` (`metric_kpi_hero`, `versus_split_card`, `code_terminal_window`, `flowchart_pipeline`).
     - Set `"claim_gate": true` and list exact quoted sentences in `"claim_reasons"` inside `.craft.json` metadata so `EDITOR-REPORT.md` flags **human verification required before publishing**.

### 2.2 46-Token AI B-Roll Prompt Hygiene Banlist (historical; superseded by `presets/broll_lint_contract.json`) (`1.2.2 / 1.2.3 F2`)
When authoring English prompts (8–60 words, realistic physical scene description) for `light` illustrative AI B-roll, pass every prompt through `visual_blocks.py --lint-prompt` (`lint_broll_prompt`). The following **46 lexical forms (45 stem families)** are strictly banned because diffusion/video models hallucinate garbled text, fake charts, copyrighted logos, or messy chat UIs:

* **Text / Watermarks (4):** `logo`, `watermark`, `text`, `subtitle`
* **Split-Screen & Callout Labels (9):** `side-by-side`, `split screen`, `comparison`, `label`, `labels`, `caption`, `captions`, `annotation`, `annotations`
* **Fake Charts & Analytics (7):** `notes`, `graph`, `chart`, `metrics`, `analytics`, `statistics`, `engagement`
* **Branded Platforms, Devices & IP (10):** `youtube`, `tiktok`, `facebook`, `instagram`, `iphone`, `macbook`, `apple`, `samsung`, `google`, `game character`
* **Paper Notes, Checklists & Chat Screens (16):** `note`, `checklist`, `checklists`, `checkbox`, `checkboxes`, `written`, `bullet`, `bullets`, `handwritten`, `handwriting`, `chat`, `chatting`, `message`, `messages`, `messaging`, `texting`

Always append neutral physical framing (`Vertical 9:16 realistic photo, natural light, shallow depth of field, unbranded generic objects, no text, no logos, no watermark`), run `clean_broll_plate` to strip letterbox bars, and verify `V8` (`luminance std >= 30/255`, mid-slot motion/master diff `> 20/255`).

---

## 3. Vietnamese Linguistic & Subtitle Micro-Physics

1. **Compound Lexicon (`data/text_vi.json`, `R55`):** `typography_composer.py::split_phrase_2line` loads `1199` inseparable Vietnamese compound `glue` pairs (e.g., *chuyển đổi*, *thương hiệu*, *khách hàng*) plus closed-class `leads` (prepositions/determiners forbidden at line end) and `trails` (particles forbidden at line start) so 2-line wraps read with native editorial phrasing.
2. **`R209` Bottom-Edge Top-Down Anchor (`Y >= 1360`):** Anchor lower-third subtitles at `Y >= 1360` (`1080×1920`) and expand 2nd lines **downward** (`top-down`) within `Y <= 1436` (`sub_bottom_px = 484`), never pushing line 1 upward onto the speaker's chin/lips. Use `hook_drop_handoff` when transitioning from a center/upper Hook stomp into standard `R209` captions.
3. **`R30` Last-Word Readability & `0.95` Ink Fit:** Every block's final spoken word must remain at `>= 90%` opacity for **`>= 3` consecutive frames** before exit; if the next cut/card gate is tight, switch from a `6f` ease-out to a **`2f` quick-exit** finishing cleanly on `gate`. Auto-scale font size when rendered glyph ink width (`0.30em` pad + `0.01em` margin) exceeds `0.95 * 800px` (`X in [140, 940]`).
4. **Projected `facesafe` (`R26`, `R208` — `full` tier):** `probe_and_align.py --tier full` tracks faces via `data/haarcascade_frontalface_default.xml` (`5`-frame median, `0.2s` window). `compile_and_verify.py --tier full` projects `eye_band` (`[0.10, 0.30, 0.90, 0.50]`) and `mouth_band` (`[0.25, 0.70, 0.75, 0.90]`) through active `C²` zoom/pan keyframes to verify `>= 8px` clearance from non-exempt glyph ink boxes (`R208` exempts `< 1.5s` opening hooks; `R26` forbids optical glow overlapping the face).

---

## 4. Acoustic Peak-Sync, `R217` XCorr & `R35` True-Peak Physics

1. **Envelope `lag_ms` & `sync_frame` Alignment:** Measure each SFX WAV's energy peak `lag_ms` via a `5ms` moving average (`240` samples @ `48kHz` after `120Hz` HPF). Place clip `timeline_start = target_event_s + (sync_frame / fps) - (lag_ms / 1000)` where `sync_frame` matches the visual 90%-easing land frame (`cut` / `broll_in`: `0f`, `cta_pill`: `4f`, `block` / `item`: `5f`, `card` / `hook_title`: `6f`). Pair hard B-roll/angle cuts with `cut_kick` (`1.018x` 4-frame settle) and enforce `>= 5.0s` spacing before reusing the same SFX MD5.
2. **`R217` Normalized `match_at` Cross-Correlation:** Verify mixed SFX timing using energy-normalized sliding dot-product (`match_at`) inside the local cue window (`[-1f, +2f]` ITU-R BT.1359 tolerance). Raw unnormalized cross-correlation is forbidden because loud vowels adjacent to a pause pull the peak by up to `+8.7f`.
3. **BGM `LRA <= 5.0 LU` & `R35` Post-AAC True-Peak Loop (`full` tier):**
   - Scan BGM start offsets in `0.5s` increments to pick the window with minimal Loudness Range (`LRA <= 5.0 LU`, EBU Tech 3342) and guarantee `voice - bed >= 10.0 LU` on every `3s` short-term speech window.
   - Because AAC lossy encoding adds `+0.1` to `+0.4 dB` inter-sample peak overshoot, `--tier full` measures `4x` oversampled True-Peak post-encode and ratchets the limiter ceiling down until both PCM and AAC streams pass `<= -1.5 dBTP` (`<= -1.0 dBTP` hard ceiling).

---

## 5. `EDITOR-REPORT.md` Verdicts & Creator Memory (`feedback_log.jsonl`)

* **Tri-State Verdict (`--tier full`):**
  - `VERIFIED` — All P0+P1+P2 gates pass (`0` face collisions, `0` SFX drift/clipping, loudness & post-AAC TP in spec, `V8` B-roll live, `claim_gate == false`).
  - `DONE_WITH_CONCERNS` — Technical physics pass, but `claim_gate == true` awaits human factual sign-off or a medium-confidence stylistic override is noted for review.
  - `REJECTED` — Any `high`-confidence physics/integrity failure (clipped Vietnamese diacritics, mouth occlusion, clipped SFX tail, LUFS/TP out of spec, frozen/blank B-roll, or `mov_text` contamination). Fix surgically and re-run `compile_and_verify.py`.
* **Optional Creator Memory (`feedback_log.jsonl`):** When the user corrects a stylistic choice (e.g., preferred font size, BGM warmth, zoom restraint, or banned SFX file), append a single JSON line `{"ts", "project", "archetype", "preference_key", "rule", "confidence": "user_override"}` to `<workspace>/feedback_log.jsonl` and consult it on future sessions before proposing Options A/B/C.
