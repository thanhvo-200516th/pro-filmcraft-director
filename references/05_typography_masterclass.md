# 05 — Masterclass Typography, Text Animation & Text Entrance (`Premiere Pro ↔ AE ↔ FilmCraft v17`)

Tài liệu tổng hợp từ **16 video hướng dẫn thực chiến trên YouTube** (Premiere Pro & After Effects), bóc tách `@__dviet`, và bộ **12 công thức toán học từng frame (`@30fps` / `@60fps`)** bảo vệ tuyệt đối **134/134 dấu tiếng Việt NFC**.

---

## 1. Thư viện 16 Video Hướng dẫn Tham chiếu (YouTube Verified)

### A. Premiere Pro — Kinetic Typography, Text Reveal & Devin Jatho Style
1. **4 Typography Animation Techniques in Premiere Pro** (*SonduckFilm*, `7:45`) — https://www.youtube.com/watch?v=SnF9NkKXc0k
   - *Kỹ thuật:* Background Shape pop trước text (`4–6f` stagger), Staggered Title, Anchor Line Reveal, Border Crop/Linear Wipe (`12–18f`, Ease In mạnh `cubic-bezier(0.16, 1, 0.3, 1)`).
2. **COOL Simple Kinetic Typography Tutorial In Premiere Pro** (*Motion Array*, `5:32`) — https://www.youtube.com/watch?v=Fl9VztW0A8E
   - *Kỹ thuật:* Nhân bản layer chồng track + `Distort > Offset` (`Shift Center To` `±300–500px` trong `10–15f`) tạo chữ chạy lặp vòng.
3. **How to Create Smooth Text Reveal Animation in Premiere Pro** (*Sanjithadesigns*, `2:13`) — https://www.youtube.com/watch?v=TF0aMUManvs
   - *Kỹ thuật:* `Transform` (**bỏ *Use Comp Shutter*, đặt `Shutter Angle = 180°–360°`**) + `Crop` boundary (`12–15f`, handle Ease-Out ~75–80%).
4. **SIMPLE Text REVEAL Tutorial | Premiere Pro** (*KYLER HOLLAND*, `9:29`) — https://www.youtube.com/watch?v=CRxTF3VMblc
   - *Kỹ thuật:* Essential Graphics **Mask with Shape** (`8–12f` mở shape, text trượt ở `F3–F4`), hoặc `Linear Wipe` (`Feather: 20–30`).
5. **Create A Text Reveal Animation In Premiere Pro** (*John The Video Guy*, `4:25`) — https://www.youtube.com/watch?v=wJBCbyGr2C4
   - *Kỹ thuật:* Dùng Shape Layer làm mask nội bộ Essential Graphics (`±120–200px`, `12–16f` Ease In) để đóng gói thành `.MOGRT`.
6. **Smooth Text Animation Reveal in Premiere Pro** (*Anthony Mediaz*, `2:24`) — https://www.youtube.com/watch?v=WpdxKgDuAsc
   - *Kỹ thuật:* Lower-Third / Clean Title (`Opacity 0→100%` `6–8f` + `Scale 90%→100%` / `Pos Y +40→0px` `12–15f`).
7. **Devin Jatho Style Captions in Premiere Pro** (*Usman Explains*, `10:01`) — https://www.youtube.com/watch?v=H4jikCTkaAQ
   - *Kỹ thuật:* Chunk `1–3` từ, `Gaussian Blur 40–60 → 0` + `Scale 80%→103%→100%` + `Opacity 0→100%` trong **`3–6f` (`@30fps`)**.
8. **The Complete Devin Jatho Style Masterclass (Pr & Ae)** (*Vlad Sateev*, `36:40`) — https://www.youtube.com/watch?v=3OwcmhJaj90
   - *Kỹ thuật:* Boxed/Gradient Ramp Captions, Word-by-Word `3–6f` + Deep Glow, `CC Light Sweep` (`15–20f`), Red/Green Highlighting, Velocity Ease `75–85%`.

### B. After Effects — Range Selector, Overshoot, Echo, RGB Split & Behind Subject
9. **Mastering Text Animation with Range Selector** (*SIMPLIFIED*, `Animation`) — https://www.youtube.com/watch?v=46SATtbhWjU
   - *Kỹ thuật:* `Animate > Opacity + Position`, `Range Selector > Advanced > Shape = Ramp Up / Smooth`, `Ease High/Low = 50%`.
10. **After Effects Tutorial - Text Blur Reveal** (*Andy Ford Video*) — https://www.youtube.com/watch?v=9PIn4oja9ak
    - *Kỹ thuật:* `Blur 25–30px` + `Opacity 0%` + `Tracking 150–200`, keyframe `Offset -100% → 100%` (`Shape = Ramp Up`) + `Glow` + `Add Grain`.
11. **How to Edit Viral Talking Head Reels in Pr & AE** (*Vlad Sateev*) — https://www.youtube.com/watch?v=wkWkHwFKcNE
    - *Kỹ thuật:* Bố cục dọc `1080x1920`, kinetic keyword pops + tách nền Rotobrush + Deep Glow.
12. **How to Make Professional Talking Head Reels in AE** (*Usman Explains*) — https://www.youtube.com/watch?v=2ediAEWgncg
    - *Kỹ thuật:* Phối hợp Text Animator (`Scale/Opacity/Tracking`) theo nhịp cắt talking-head.
13. **How to Put Text Behind a Subject Using RotoBrush** (*Elib Filmz*) — https://www.youtube.com/watch?v=1ufGi84pguE
    - *Kỹ thuật:* 3 tầng `BG → Text → FG (RotoBrush + Refine Edge, Feather 0.5–1px, Freeze)`.
14. **Glow Bouncing Text Animation in After Effects** (*Motion Nations*) — https://www.youtube.com/watch?v=VC41WUsBLvg
    - *Kỹ thuật:* Biểu thức **Inertial Bounce** (`freq = 3, decay = 5`) của Dan Ebberts + `Deep Glow` (`Radius 250–400`).
15. **How To Create A Ghost Trail Or Echo Effect** (*SSB Otaru*) — https://www.youtube.com/watch?v=AO942X8yjQA
    - *Kỹ thuật:* `Time > Echo` (`Echoes = 10–20`, `Start Time = -0.016..-0.033s`, `Decay = 0.80`, `Operator = Screen/Maximum`).
16. **RGB Splitting - Glitch Effect (No Plugins)** (*SonduckFilm*) — https://www.youtube.com/watch?v=gV5vlD6Psv0
    - *Kỹ thuật:* 3 layer `Shift Channels` (`R`, `G`, `B`) + `Blend = Screen` + `wiggle(12, 15)` trên `R` và `wiggle(8, 20)` trên `B`.

---

## 2. Nguyên tắc Sống còn cho Tiếng Việt 134/134 NFC
1. **NFC Mandatory:** Mọi chuỗi phải qua `unicodedata.normalize("NFC", text)` trước khi đo hoặc tách từ/ký tự.
2. **Grapheme-Cluster Safe:** Với `per_word_stagger` và `typewriter_cursor`, **cấm** cắt rời dấu khỏi nguyên âm (`\X` / grapheme cluster) để chữ có dấu kép (`ệ, ắ, ồ, ử`) xuất hiện nguyên khối trong 1 tick.
3. **Diacritic Padding:** `padding_top >= 0.30em`, `line_height >= 1.25`, `max_tracking <= +0.18em` (cấm giãn chữ trên font Script).
4. **Thời gian giữ tĩnh tối thiểu:**
   $$T_{\text{hold}} = \text{clamp}(0.45 + 0.24 \cdot N_{\text{words}} + 0.14 \cdot N_{\text{stacked}},\, 0.75,\, 3.20)$$

---

## 3. Bảng 12 Công thức Text Animation & Text Entrance (`@30fps` | `@60fps`)

| # | ID Recipe | Track | Thời lượng (`30fps` \| `60fps`) | Cơ chế Toán học & Keyframe | Bảo vệ 134/134 NFC & Mutex |
|---|---|---|---|---|---|
| 1 | `overshoot_spring_pop` | `V7` | `12f` \| `24f` | Spring $\zeta=0.42, \omega_n=22$: `0% → 108% (F5) → 97% (F9) → 100% (F12)` | `Anchor` tính cả `padding_top 0.30em` |
| 2 | `per_word_stagger` | `V8` | `8f/từ, Δ3f` \| `16f, Δ6f` | `pos_y +36px → 0`, `scale 94→101→100%` | Tách từ sau `NFC`; `word_spacing >= 0.25em` |
| 3 | `mask_line_wipe` | `V8/V7` | `12f` \| `24f` | `pos_y +110px → 0` (`in_inf: 0.82`), `crop.bottom` khóa đáy | `padding_top >= 0.30em`, `line_height >= 1.25` |
| 4 | `gaussian_deblur_in` | `V7` | `10f` \| `20f` | `blur 20px → 0`, `scale 106% → 100%`, `op 10% → 100%` | Giới hạn `blur <= 20px` (`14px` với font mảnh) |
| 5 | `tracking_expand` | `V7/V8` | `16f` \| `32f` | `tracking -0.04em → +0.14em`, `scale 98% → 100%` | Cấm `tracking > +0.18em`; cấm dùng cho Script |
| 6 | `turbulent_organic_jitter` | `V7` | `9f` \| `18f` | Đa tần `7.3/13.7Hz` tắt dần: `±4px X, ±2px Y, ±1.2°` | Khóa `Ay <= 2px`, `|θ| <= 1.2°` |
| 7 | `optical_halation` | `V7` | `12f` \| `24f` | `L_sharp` + `L_bloom` (`blur 32→12px`, `op 85%→22%`) | Kết thúc `L_bloom <= 22%`, `WCAG >= 4.5:1` |
| 8 | `stacked_hollow_echo` | `V7` | `10f` \| `20f` | 2 lớp `Echo` viền rỗng `±42px → 0`, `op 55% → 0%` | `stroke <= 2px`; **Mutex với `stack3_feather`** |
| 9 | `glitch_rgb_split` | `V7` | `6f` \| `12f` | `Hold` steps kênh `R/B`: `±14 → ∓10 → ±5 → 0px` | Chỉ lệch trục ngang `X` (`offset_y = 0`) |
| 10 | `behind_subject_z_depth` | `V2` | `12f` \| `24f` | `pos_x -90 → 0px`, `scale 92% → 100%` dưới `V3` RVM | Che `30–50%`; **Mutex `Blend` + `drop_shadow`** |
| 11 | `typewriter_cursor` | `V8` | `1.5–2 ch/f` | Lộ từng grapheme cluster + con trỏ nháy `8f/16f` | Tách grapheme `\X` trên chuỗi `NFC` |
| 12 | `cross_cut_persistence` | `V7/V8` | `-6f..+12f` \| `-12f..+24f` | Vào trước điểm cắt `-6f`, giữ neo xuyên qua `t_cut` | Bắt buộc kèm `scrim_dark` `35–45%` trên B-Roll |

---

## 4. Bản đồ Kho Tài nguyên Local (`TNEDIT` & `animation_dna_catalog.json`)
- **20 Animation DNA Cards** (`DVIET-01..10` & `MIN-01..10`) từng nằm ở `dviet-filmcraft-director/presets/animation_dna_catalog.json` của skill cũ; file này **không** có trong repo, các khuôn tương ứng hiện là `presets/typography_hierarchy_presets.json` và `presets/visual_archetypes_catalog.json`.
- **TNEDIT Assets:** `16` file `.mogrt` BĐS (`03_TRANSITIONS_PRESETS/Premiere_MOGRT/`), `3` FilmBurn/LightLeak `.mp4` (`05_Hieu_Ung_Chuyen_Canh/Overlay_Video/`), `CO - S1/S2.mov`, và `12` Icon 3D Alpha `60fps` `.mov` (`07_Assets/3D_Icons_Overlays/animated_overlays/`).
