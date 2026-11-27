# 29 — Pop-out card: Premiere and CapCut recipe mapped to FilmCraft (v7.7.0, defaults v7.8.0, clean edge and crown v7.9.0)

The **pop-out card**: the presenter's head crown rises above a rounded light card while the body stays inside the card. It is a Look S variant of the A1 card (`render_full_head_studio_card`) for light (polarity) scenes and headline beats. This note gives the editor's recipe (Premiere, CapCut), classifies each step as **A / B / C** by the rules of [`27_premiere_recipes_to_filmcraft.md`](./27_premiere_recipes_to_filmcraft.md) (checked against FilmCraft 0.13.0), and says what the skill ships.

Labels: **[ĐO]** measured, **[ƯỚC]** estimate. Classes: **A** native on the FilmCraft timeline, **A-** native but the effect only approximates the look, **B** pre-rendered RGBA plate, **C** not feasible. See the promise table in `SKILL.md` section 3.

---

## 1. The editor's recipe

### 1.1 Premiere Pro

1. Put the A-roll on V1 and **duplicate it** onto V2 (same timecode).
2. On V1 (the card): add a **rounded rectangle mask** with **feather**; scale and position the picture inside it. Fill the rest of the frame with a **paper background** (light lavender / white) and a gradient italic headline.
3. On V2 (the head): cut the person out with **Object Mask** (select the subject, Track forward and backward), then add **Expansion about -3** plus a little **feather** to clean the edge (Adobe's background-replacement recipe).
4. Cut the head mask **below the top of the card**, so the head fades into the card photo instead of ending in a hard line; the card photo and the head share one position and scale, so the seam is invisible.
5. On the card: add **Spherize** or a **bulge pillow** so the card photo bulges slightly outward (a bottom-weighted pillow, see 3.1).
6. Add a soft **drop shadow** under the card.
7. Headline: big italic serif with a vertical **gradient** (colour at the top fading to near white), a small sub-word beside it. Keep it clear of the crown.

### 1.2 CapCut

1. Put the clip on the main track and a **copy on an overlay track**.
2. Overlay copy: **Remove background > Auto removal** (the person only).
3. Main-track copy: a **rounded mask** (mask shape rectangle, corner radius, feather); **keyframes** for the card scale and the head position when the card moves.
4. Paper background and headline as a text or sticker layer above the card, below the head.

---

## 2. Mapping to FilmCraft (A / B / C)

Checked live on FilmCraft 0.13.0 in the research pass. FilmCraft has **no AI roto** and **no AI Object Mask**.

| Editor step | FilmCraft | Class |
|---|---|---|
| Rounded rectangle mask with feather on the card | `rounded_crop` (+ feather) | **A** |
| Drop shadow under the card | `drop_shadow` | **A** |
| Head above the card (V3 over V2) | track order, the head clip on a higher video track | **A** |
| Track matte with a plate | `track_matte` (the matte clip must sit on Video 1-5) | **A** |
| Pillow / bulge warp on the card | `spherize`, `lens_distortion` or `turbulent_displace` (Bulge) | **A-**: they bulge the **whole** clip, not the bottom, so they cannot match a bottom-weighted pillow |
| Head cutout with a clean alpha (Object Mask, CapCut Auto removal) | an RGBA `.mov` made by the skill's matte tools (RVM, or `u2netp` for objects) and placed as a clip | **B** |
| Exact seam between the head and the card, exact pillow | pre-rendered in the plates (one shared affine for the card photo and the cutout) | **B** |
| Paper background + gradient italic headline | a rendered plate (Playfair Display Italic, vertical gradient) | **B** |
| Mask that tracks the subject over time (Object Mask with tracking, Roto Brush) | not available in FilmCraft | **C** |

**Decision: ship as B.** Two RGBA plates, one of the card and one of the head, rendered with the backdrop set to transparent, and the master MP4 gets the same composite. The mirror `.fcproj` uses the two plates (card plate on a lower video track, head plate above it). The native A effects (`rounded_crop`, `drop_shadow`) stay available for a quick approximation but do not reproduce the seam or the pillow.

---

## 3. What the skill ships

Reference by name only; the function is written in `scripts/tools/fast_studio_compositor.py` (package S1 of v7.7.0; defaults updated in v7.8.0) and flagged **Look S pop-out**. The default Look S rounded card (`render_full_head_studio_card`) is unchanged: with the flag off the card render is bit-identical to the one before the change.

`render_popout_studio_card(backdrop_bgr, aroll_bgr, person_alpha_u8, *, ...) -> (out_bgr, meta)` with `meta = {card_rect, pop_height_px, pop_bbox_y}`. Inputs are BGR `uint8` for the picture and a `uint8` person alpha; output is BGR `uint8`, like the other compositor renderers.

### 3.1 Parameter table (defaults of the prototype, 1080x1920 output)

| Parameter | Default | Meaning |
|---|---|---|
| `card_rect` | `(90, 1030, 990, 1700)` | card x0, y0, x1, y1 in output px |
| `rx` | `84` | corner radius of the card |
| `head_anchor` | `(340, 549)` | the crown point in **source** px |
| `head_out_xy` | `(540, 900)` | where that crown lands in **output** px; `pop_height = card_y0 - head_out_y = 130` |
| `photo_scale` | `1.36` | one scale for the card photo and the cutout |
| `pop_feather` | `46` | px below the card top where the cutout fades into the card photo |
| `pop_alpha_feather` | `1.3` | alpha softening |
| `pop_alpha_choke` | `2` | alpha erosion in px (does not clear the RVM fringe alone, see 4.2) |
| `edge_feather` / `edge_blur` | `7` / `7` | card edge softness |
| `bulge` | `0.075` | bottom-weighted outward pillow, fraction of the half-width |
| `sag` | `0.045` | slight droop of the pillow |
| `rim_px` / `rim_alpha` | `0` / `0.0` | optional rim light, off |
| `shadow_rgb` | `(110, 80, 150)` | shadow colour |
| `shadow_alpha` | `0.20` | |
| `shadow_dy` / `shadow_sigma` | `30` / `34` | shadow offset and blur |
| `pad` | `150` | working margin |

### 3.1a v7.8.0 defaults: crisp card (defect D2)

v3 rendered the pop-out card soft: the card was small, the edge blurry (10-90 % rise 19-21 px [ĐO]), the sides bowed out too much, and the whole-frame Laplacian of the scene was 8-34 against about 430 elsewhere. The 720p 30 fps source is upscaled by the compositor; a prototype with a 7 px edge blur and a 1.36 photo scale cannot look like the user's reference still. The Look S pop-out defaults since v7.8.0 (measured on the real S09 frames and the RVM alpha [ĐO]; the compositor package S1 owns the code, a build that calls it passes them explicitly):

| Parameter | v7.8.0 | Was |
|---|---|---|
| `card_rect` | `(70, 1065, 1010, 1705)` (87 % wide, 33 % tall) | `(90, 1030, 990, 1700)` |
| `rx` | `64` | `84` |
| `edge_feather` / `edge_blur` | `1.6` / `0` (skip the blur band when 0) | `7` / `7` |
| `bulge` / `sag` | `0.03` / `0.015` | `0.075` / `0.045` |
| `shadow_alpha` / `shadow_dy` / `shadow_sigma` | `0.16` / `22` / `26` | `0.20` / `30` / `34` |
| `head_out_xy` | `(540, 900)`: pop about 165 px = 8.6 % of H | pop 130 px |
| `photo_scale` | `1.05` | `1.36` |
| sharpen | one unsharp, amount `0.7`, sigma `1.3`, on the shared photo array **before** the card remap and the crown cut-out (not on the paper, not on the matte) | none |
| interpolation | `INTER_LANCZOS4` for the card warp and the bulge remap | cubic / bilinear |

Result [ĐO]: card edge 4-5 px against 19-21 px (the user's reference: about 3-5 px); face Laplacian ratio about 2.2x the plain Lanczos source (13.5 against 6.0).

**Upscale ladder** (this CPU has no neural SR: OpenCV 5.1.0 without `dnn_superres`, no `realesrgan`, `waifu2x`, torch or SR ONNX on disk, so future runs must not look for `realesrgan`):

1. Lanczos (`INTER_LANCZOS4`) plus one controlled unsharp. Do not claim added detail.
2. 2x Lanczos, then unsharp (USM), then area down-sample.
3. Optional neural x2 through an ONNX SR model: **not shipped**; it needs a download and the user's approval.

**Single-resample rule.** The photo must be resampled once. v3 resampled it three times (scale, card warp, bulge remap), which is the root of the soft face; the follow-up is one `cv2.remap` with `INTER_LANCZOS4` from the 720p source. Build it only if the face is still soft after the parameter change.

**Gates** (replacing the whole-frame Laplacian bar of 430):

| Gate | Limit |
|---|---|
| Card top-edge 10-90 % rise (1080 px width) | <= 6 px |
| Face-ROI Laplacian | >= 1.8x the plain-Lanczos source in the same crop |
| Side bow | <= 12 px per side |
| Pop height | 7-11 % of H |
| Face Laplacian at 685 px width (informative) | 18-33 (V21 A1 17.9-23.4, reference face 32.7) |

The whole-frame Laplacian 430 is **not** a valid bar: V21 whole-frame 454 against v3 59 at 16.0 s is text and graphics, not face sharpness; the face-ROI source is 35, the v3 card 53 [ĐO]. If the face gate is still missed, add a second USM (sigma 2.0, amount 0.35) or 1 % luminance grain on the card interior; for a softer edge use `edge_feather` 2.5 with `edge_blur` 0. A hairline dark rim at the left edge comes from the dark wall of the A-roll, not from the sharpen. Halo at the crown: try `pop_alpha_feather` 0.6, `pop_alpha_choke` 1 and a steeper smoothstep (0.25, 0.75) on the RVM alpha [ƯỚC, untested]; check the crown seam on the light paper at 100 %.

The mask and the remap maps are cached by `(card_rect, rx, bulge, sag)`, like the existing full-card rig cache. Hold `head_anchor` per segment, or derive it from the alpha per frame; a jittering anchor moves the seam.

Companion helpers: `render_lavender_paper(W, H, tint_rgb, seed_glow_y)` (paper backdrop) and `render_gradient_italic_headline(backdrop, text, sub, center_xy, target_w, top_rgb, bottom_rgb, fade_start, ...)` in Playfair Display Italic (an installed font; never substitute a paid font that is not installed).

Prototype cost (CPU, numpy / OpenCV / PIL, existing RVM alpha): about 0.42 s per frame [ĐO, one 1080x1920 proof frame]. A 60 fps master is therefore a segment-cached plate render, not a live preview.

### 3.1b v7.9.0 clean edge and crown (v4 review K2 / K4)

The v4 card at 17.0 s showed a dark strip of 24-30 px along its inner edge (luma 13-21 against a 43-50 wall), a 17x14 px dark wall dot and a blocky crown [ĐO]. The cause is the source, not the warp: a letterbox or dark wall edge in the A-roll is sampled into the card. Three steps now run by default in `render_popout_studio_card`:

| Step | Argument (default) | What it does | Gate (`motion_gate.py`) |
|---|---|---|---|
| Band clean | `clean_source_bands=True` | dark source side bands are painted with the adjacent clean wall before the warp; meta `source_bands_px`, `card_src_rect`, `card_outside_source` | `popout_inner_edge_dark_strip_px <= 4 px` |
| Despeckle | `despeckle_wall=True` | small dark wall specks inside the card are filled from the local wall | `card_dark_speck_count == 0` |
| Crown refine | `crown_refine=True` | guided filter on the photo plus edge contrast on the crown matte (`False` = the v7.8.0 matte); meta `crown_alpha` | `crown_edge_metrics(meta['crown_alpha'])`: jaggedness <= 1.2 px, 10-90 % rise <= 4 px |

These gates sit next to the 3.1a gates (edge, face Laplacian, bow, pop height); all of them must pass on the rendered frame. Turning a step off is for an A/B check only, never to make a gate pass. A flash or snap punch over the card also obeys the v7.9.0 flash cap (frame mean luma <= 220, `snap_punch` scales the flash down).

### 3.2 Use in a Look S build

- At least one light-card scene per video is a good fit (the polarity scenes, for example the 15.05-19.0 s paper card, or a text card such as the 5.8 s one in the v2 build).
- **Safe zone:** the head crown must stay inside the top safe zone, crown y >= 130 px. With `head_out_y` 900 and `pop_height` 130 the crown is well below that; if you move the card up, re-check.
- The gradient headline must not collide with the crown (Cranial Lock: 0 % face / hair overlap with text). Place it in the upper editorial stage, clear of `head_out_xy` and the pop height.
- Pillow, seam and shadow are pre-rendered: say so (class B) and do not promise native tracking.

---

## 4. Warnings

### 4.1 The spec has no `masks` key (gap H5)

The `fc_build` spec has **no `masks` key**: Mask Path, Expansion and Feather as in Premiere cannot be written from a `.craft.json` (reference 27, gap **H5**: `masks.*` exist only as app commands). Do not promise a native mask in the `.fcproj`. Use `rounded_crop` + feather for the card edge and the B plates for the head cut. A hand-drawn or tracked mask stays class C until H5 is built.

### 4.2 RVM fringe

> The skill ships **no RVM model**. The person matte it can make itself is `u2netp` / `birefnet-portrait` (rembg, `scripts/tools/fast_studio_compositor.py`); "RVM alpha" in this file means any person matte passed as `person_alpha_u8`, e.g. one made by the RVM tool of another skill.

The RVM alpha leaves a **grey halo** (a fringe) left of the hair in the proof frame [ĐO, one frame]; it is most visible on a light card, and the likely cause is leftover wall colour in the semi-transparent edge pixels [ƯỚC]. A choke of 2 px (`pop_alpha_choke`) alone does **not** clear it. Before shipping a pop-out plate, apply one of:

1. **Decontaminate the colour with the alpha** (estimate the foreground colour from the alpha and replace the edge colour; do not just erode).
2. **Run RVM at a lower downsample ratio (0.5)** for a sharper hair edge.
3. **Run `birefnet-portrait` only on the crown region** (the matte model of the env check) and take the alpha from it for the crown.

Check the result on the light card at 100 % zoom, on the side with the hair, and on the paper colour you ship (a lavender or ivory paper shows a different fringe than white).

### 4.3 Other limits

- Moving presenter: `head_anchor` changes every frame; derive it from the alpha or hold it per segment and keep the move small.
- Source quality: a 720p A-roll is upscaled by `photo_scale` 1.36 in the card; do not add a FilmCraft scale on top (see the framing note in Step 3b of `SKILL.md`).
- The tests specified for the compositor package (`tests/test_skill_v77.py`) cover: the head lies above the card top (output differs from the backdrop at y0 - 5 over the head), the card photo is continuous at y0 + 80 (seam), the default card path is unchanged with the flag off, and a synthetic alpha with no person puts no head pixels above the card. A pop-out in a real build still needs a look at a real frame.
