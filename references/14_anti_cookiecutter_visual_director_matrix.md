# 14 — Anti-Cookie-Cutter Visual Director Matrix (Bespoke Beat-by-Beat Playbook)

> **Prime Directive:** NEVER iterate over beats in a mechanical `for` loop stamping the same 3-row UI card, top banner, or linear zoom onto every sentence. Every beat must earn its visual form from **what the speaker actually means and feels** at that exact timestamp.

---

## 1. Why Videos Become "Cookie-Cutter" (And How to Break It)

| Cookie-Cutter Failure Mode | Why It Hurts Retention | Bespoke Director Fix |
| :--- | :--- | :--- |
| **3+ Checklist Cards in 60s** | Viewer goes blind to identical boxes after Beat 2 (`Banner Blindness`). | Hard cap: **max `1` `checklist_audit_card` per video**. Turn other lists into `flowchart_pipeline`, `versus_split_card`, or sequential `floating_pill_badge`. |
| **Top Text Banner on 100% of Beats** | Suffocates facial acting, eye contact, and emotional vulnerability. | Leave **`≥ 20%` of A-roll frames (`≥ 40%` for Minimal/Story)** completely free of heavy upper banners. Let eyes + room tone breathe. |
| **Uniform `100% → 108%` Linear Zoom** | Feels robotic and weightless; ignores speech prosody. | Alternate **Fast C² Bezier Push** (on punchwords), **Static Tripod Hold** (on deadpan truth), and **Velvet Pull-Out Breath** (on realization). |
| **Random B-Roll Wallpaper** | Generic stock clip with no semantic tie weakens trust. | Inspect `assets_contact_sheet.jpg` first! Pair B-roll with a framing treatment (`clean_alpha_prop`, `polaroid_callout`, or `metric_kpi_hero`) that proves the spoken claim. |
| **Wall-to-Wall Whoosh + Pop SFX** | Auditory fatigue makes *nothing* feel impactful. | Reserve sub-drops/impacts for structural turns; use **250–400ms acoustic silence / J-cut breath** before the single biggest reveal. |

---

## 2. Beat Semantics → Bespoke Treatment Matrix

The ten stateless RGBA primitives of `scripts/tools/visual_blocks.py` named below (`versus_split_card`, `flowchart_pipeline`, `metric_kpi_hero`, `code_terminal_window`, `strike_myth_banner`, `quote_editorial_note`, `checklist_audit_card`, `polaroid_callout`, `floating_pill_badge`, `clean_alpha_prop`) are shown side by side in [`visual_primitives_10_showcase.jpg`](./visual_primitives_10_showcase.jpg).

Read `words_tl.json` sentence-by-sentence, classify the **Beat Intent**, and compose across 4 orthogonal axes (Visual + Camera + Typography + Audio):

| Beat Semantics / Sentence Intent | Primary Visual Treatment (`visual_blocks.py` / NLE) | Camera Choreography (`typography_composer.py`) | Typography Choreography (`V7`/`V8` NFC) | Micro-Audio Cue (`A3`/`A4`) |
| :--- | :--- | :--- | :--- | :--- |
| **1. Contrarian Hook / Myth-Bust** *("90% mọi người hiểu sai...", "Đừng làm cách cũ nữa")* | `strike_myth_banner` or **Polarity Flip** (`#111111` ↔ `#FAFAFA`) over A-Roll | `punch_in_jump` (`6–8f` Bezier snap to eye anchor) | Oversized Condensed/Sans + animated red strike-through or `overshoot_spring_pop` | Crisp `ui_snap_click` (`0f`) or `whip_whoosh` (`-3f`) |
| **2. Pain / Costly Mistake** *("Mất trắng 3 tháng...", "Càng cố càng kiệt sức")* | Tight A-Roll facial close-up OR `checklist_audit_card` *(max 1/video, red theme)* | `pain_emphasis_in` (push in `0.5s`, hold tension, slight settle) | High-contrast 2-tier Chest Lockup (`y = 58%`, Sans Lead + Accent Keyword) | Subtle `sub_thump_low` (`0f`), duck BGM `-3 dB` deeper |
| **3. Mechanism / Workflow / Pipeline** *("Đầu tiên nhận input, qua tầng lọc, xuất kết quả")* | `flowchart_pipeline` (connected nodes/arrows) over dark canvas or blurred B-Roll | `clean_push_hold` or subtle `isometric_card_tilt_3d` (`rot_x: 18° → 0°`) | Step badges `01 → 02 → 03` (`per_word_stagger` or `mask_line_wipe`) | Soft `ui_tick` per node (`+4f` stagger) |
| **4. Code / Prompt / Technical Config** *("Chỉ cần chạy lệnh này...", "Cấu hình JSON như sau")* | `code_terminal_window` (macOS/dark slate header + syntax-highlighted tokens) | Crisp `snap_in_hold` (`shutter_angle: 180°`) | `JetBrains Mono` / `SF Pro Display` clean label; **zero** decorative script font | Tactile `keystroke_burst` or `ui_pop_soft` |
| **5. Hard Proof / ROI / Number Delta** *("Tăng từ 12% lên 68%", "Rút từ 4 giờ xuống 90 giây")* | `metric_kpi_hero` (giant numeric counter/delta card + B-Roll receipt) | Brisk B-Roll drift (`104% → 112%`) or `whip_zoom_blur` entry | Numeric Hero `1.8×` larger than unit label (`Montserrat` / `West West Condensed`) | `riser_short` (`-6f`) → `bass_hit_clean` (`0f` lock-in) |
| **6. Old Way vs. New Way Comparison** *("Trước đây thủ công... giờ tự động hóa")* | `versus_split_card` (Left/Top muted red vs Right/Bottom vibrant emerald/cyan) | Asymmetric 2-stage pan or `polarity_flip` on the "New Way" word | Split header pills (`CŨ` vs `MỚI`) with `pill_unroll_y` | `swoosh_left` (`-2f`) → crisp `chime_positive` on winner |
| **7. Real-World Artifact / Case Study** *("Đây là ca thực tế tuần trước...", "Nhìn bức ảnh này")* | `polaroid_callout` or `clean_alpha_prop` (50/50 Demo + Speaker reaction) | Gentle floating parallax (`rot_z: -1.5° → 0°`, soft drop shadow) | Clean caption tag or handwritten `SVN-Aaron Script` callout note | `camera_shutter_soft` or `paper_slide` (`-2f`) |
| **8. Core Principle / Philosophical Takeaway** *("Bản chất của kỷ luật không phải ép buộc...")* | `quote_editorial_note` (paper/frosted note) OR `text_behind_subject` (`V2` text + `V3` RVM) | `slow_contemplative_push` (`100% → 109%` over `4s`) | `Playfair Display Italic` + `Be Vietnam Pro` (`gaussian_deblur_in` `10f`) | Warm `soft_chime_lock` or pure acoustic resonance |
| **9. Vulnerable Confession / Empathy Beat** *("Thật sự lúc đó mình rất sợ...", "Mình hiểu cảm giác đó")* | **PURE A-ROLL BREATH** — **Zero** top graphic, **Zero** UI card, pure eye contact | `velvet_settle_then_in` or `zoom_out_breath` (`C²` continuous) | Optional quiet lower-third 3-word anchor (`opacity: 85%`) or **no text at all** | **Zero SFX**; J-cut breath preserved; BGM warm pad |
| **10. Actionable CTA / Signature Sign-off** *("Lưu lại để áp dụng ngay", "Comment từ khóa...")* | Clean A-Roll centered + `floating_pill_badge` or Calligraphy CTA lockup | `zoom_out_breath` (`124% → 118%`) signaling conversational closure | Hero keyword in Brand Accent + `optical_halation` soft glow | Clean `sub_impact_soft` + BGM resolve to `-16 dB` |

---

## 3. Pacing Wave & Visual Rhythm Choreography

Never hold a flat Average Shot Length (`ASL`) from start to finish. Sculpt every 30–90s video as an **Asymmetric Contrast Wave**:

1. **0–4s (Hook Velocity):** `1.5–2.2s` cuts. Immediate visual pattern interrupt (`strike_myth_banner`, `metric_kpi_hero`, or `text_behind_subject`) within the first `0.8s`.
2. **4–15s (Context & Empathy Breath):** Widen to `3.0–4.5s`. Pull graphic clutter back so the viewer bonds with the human speaker (`velvet_settle_then_in`, clean A-Roll).
3. **15–45s (Mechanism & Proof Escalation):** Alternate **Structured Graphic Beats** (`flowchart_pipeline`, `versus_split_card`, `code_terminal_window`, `clean_alpha_prop` at `2.0–2.8s`) with **Reaction / Explanation Beats** (`2.8–3.8s`). Never place two identical block types back-to-back!
4. **Final 5–8s (Resolution & Lock):** Decelerate camera (`zoom_out_breath`), strip away secondary badges, leave **1 single Hero CTA focal point**.

---

## 4. Mandatory Pre-Compile Director Self-Audit (7 Gates)

Before saving `<project>.craft.json` and calling `compile_and_verify.py`, verify:

- [ ] **Archetype Declared:** Did I explicitly pick 1 of the 6 archetypes from [visual_archetypes_catalog.json](../presets/visual_archetypes_catalog.json) matching the speaker, industry, and footage mood?
- [ ] **Visual Diversity ≥ 3:** Did I use at least **3 distinct visual treatments** across the timeline (e.g. `strike_myth_banner` + `flowchart_pipeline` + `metric_kpi_hero` + pure A-Roll)?
- [ ] **Checklist Cap ≤ 1:** Is `checklist_audit_card` used **at most once** (or `0` times in `dviet_cinematic_editorial` / `story_confessional_breath`)?
- [ ] **No Back-to-Back Clones:** Are zero adjacent beats using the exact same visual block type or identical camera curve?
- [ ] **Breathing Space ≥ 20%:** Do emotional/human sentences breathe on clean A-Roll without heavy top banners?
- [ ] **Single Focal Point (Rule 1):** At any timestamp `t`, is there strictly **1 Hero element** (never stacking a giant UI card + giant kinetic headline + busy subtitle simultaneously)?
- [ ] **100% Vietnamese NFC + Safe Zone:** Are all strings NFC-normalized with `padding_top >= 0.28em`, zero forbidden fonts, and placed inside [platform_safe_zones.json](../presets/platform_safe_zones.json)?
