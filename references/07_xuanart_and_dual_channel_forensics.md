# Dual-Channel Frame-by-Frame Forensics: `@__dviet` (N=13) vs `@xuanart.visual` (N=66)

Tài liệu này tổng hợp kết quả đo đạc định lượng và bóc tách từng khung hình (step 1–2 frames @ 24/30/60fps) trên **13 video `@__dviet`** và **66 video `@xuanart.visual`**.

---

## 1. Bảng đối chiếu định lượng 2 kênh

| Chỉ số | `@__dviet` (N=13) | `@xuanart.visual` (N=66) | Ứng dụng vào Skill |
| :--- | :---: | :---: | :--- |
| **ASL (Average Shot Length)** | `2.12s – 5.90s` (montage nhanh `0.40s/shot`) | Trung vị `2.09s` (min `0.63s` montage, max `16.97s` tutorial) | Montage/Visual Reel: `0.63–1.25s`; Talking-Head: `2.1–3.2s`; Tutorial: `4–17s` |
| **Loudness (Integrated LUFS)** | `-10.7` đến `-13.8 LUFS` (explainer `-16.7`) | Trung vị `-12.4 LUFS` (montage `-9.4` đến `-14.4`) | Short-form punchy: `-12.0` đến `-14.0 LUFS`; Explainer sạch: `-16.0 LUFS` |
| **SFX / Transient Onset Rate** | `0.87 – 2.23 onsets/s` | Trung vị `1.17/s` (max `2.21/s`) | Giữ mật độ `1.1 – 2.2 onsets/s` cho nhịp năng lượng cao |
| **Pre-Drop Vacuum** | `0 – 5` lần/video (`80–220ms` ngắt âm) | `41/66` video có vacuum (`0.4–0.75/s` ở tutorial) | Chèn `80–220ms` khoảng lặng trước drop/step card hoặc giữ tự nhiên lúc thao tác UI |
| **Cut-to-Audio Sync** | 2 cực: Pre-lap `-23..-57ms` & Post-cut `+30..+83ms` | Trung vị `+27ms`; montage siêu nhanh `-18..-53ms` | Rapid cut (`<1s/shot`): SFX/cut sớm `-18..-53ms`; Reveal/Film-Burn: `+35..+83ms` |

---

## 2. Công thức Text Typography & Animation mới (`@__dviet` 13-video Forensics)

1. **`dviet_bridge_anchor` (Track T1 Anchor + Track T2 Swap):**
   - Tách cứng **Track T1 (Anchor Text)** kéo dài xuyên qua 2–3 điểm cắt cảnh (ví dụ `"mình không"`) và **Track T2 (Keyword Swap)** thay từ khóa đúng **6 frames @ 60fps (`+100ms`)** sau điểm hard cut, giữ card/text phụ ổn định để mắt không bị hụt nhịp.
2. **`dviet_word_push_up` (4f @ 60fps = 67ms):**
   - Khi từ/dòng mới pop-in (`opacity: 0 → 45% → 100%` trong 4f), đẩy dòng neo phía trên tịnh tiến lên **`Y -25px`** để nhường chỗ tự nhiên.
3. **`dviet_hero_slide_deblur` (8–10f @ 60fps = 133–167ms):**
   - Hero Italic/Script vào với `Y +25..45px → 0` (ease-out), `opacity 25% → 100%`, `blur 4px → 0px`.
4. **`luma_flash_erosion` (Flash-Out Text Erosion):**
   - Ramp radial white/amber glow từ `-100ms` trước cut, đạt peak `#FFFFFF` tại `-50ms` (`Y > 195`) để ánh sáng **ăn mòn nét chữ**, hard cut sang shot mới rồi pop caption đơn ở `+66ms` (`4f @ 60fps`).
5. **`text_layer_isolation` (Miễn nhiễm Invert):**
   - Đặt Layer Text chính/V8 **phía trên Adjustment Layer Invert** để khi nền và chủ thể đảo âm bản, chữ vẫn giữ nguyên màu trắng/vàng đọc rõ.
6. **`typewriter_cursor_flash` (`_` + Subject Flash):**
   - Gõ từng cụm chữ kèm dấu gạch ngang/cursor `_` đồng bộ với nhịp **Subject-Isolated Double Flash**.
7. **`shape_wipe_1f_stagger` (3D Shape Wipe + 1f Stagger @ 30fps):**
   - Khối 3D/chữ lớn quét che khung trong 3–4f chuyển nền đối lập (`Dark Charcoal` ↔ `Cream #EEF2E6`), sau `+100ms` pop-in từng từ cách nhau **1 frame (`33ms @ 30fps`)**.

---

## 3. Công thức Text Typography & Animation mới (`@xuanart.visual` 66-video Forensics)

1. **`xuanart_kinetic_sans` (Geometric Lowercase + Red Micro-Label Overlap):**
   - Dùng **Geometric/Grotesque Sans chữ thường (`lowercase`)**, tracking chặt (`-0.03em`), kết hợp **Micro-Label nhỏ** (`effect`, `transition`, `mask`) màu đỏ đậm (`#E01515`) hoặc trắng đặt đè trực tiếp lên mép dưới hoặc kẹp giữa 2 dòng chính.
2. **`xuanart_blur_amber_glow` (18f @ 60fps = 300ms):**
   - Chữ xuất hiện từ blur nặng + vệt **glow vàng/hổ phách cục bộ** theo từng cụm chữ rồi thu nét sắc thành trắng.
3. **`xuanart_rgb_chromatic_pulse` (12–16f @ 60fps):**
   - Rung ngang tách 3 kênh **RGB (Cyan/Green/Red)** quanh viền chữ trước khi snap về trắng sắc nét.
4. **`xuanart_corner_bracket_wipe` (`[ ]` + 6f Wipe @ 60fps):**
   - Đặt chữ trong khung 4 góc ngoặc vuông `[ ]`, wipe trái-sang-phải trong **6 frames (`100ms`)**, giữ nét 18f rồi thoát bằng horizontal motion blur.
5. **`xuanart_editorial_right_autocontrast` (1/3 Right Serif):**
   - Đặt phụ đề Serif cỡ vừa/nhỏ **lệch 1/3 phải ngang tầm vai/mắt** (thay vì bottom-center), tự động đảo **Trắng ↔ Đen** theo độ sáng nền, tô **Đỏ** từ khóa nhấn (VD: `phán` → `phán xét`).
6. **`xuanart_text_as_video_matte` & `stretch_typography`:**
   - Dùng Serif Bold cỡ lớn làm **Luma/Alpha Matte** lồng video bên trong chữ; hoặc kéo dãn chiều dọc (`Stretch Typography`) cho từ khóa nhấn.
7. **`xuanart_smoky_blur_fade`:**
   - Thoát chữ bằng Gaussian/Smoky Blur tăng dần + opacity fade trước khi chuyển cảnh.

---

## 4. Thư viện Chuyển cảnh & VFX nâng cao (Dual-Channel)

1. **`strobe_invert_bridge` (`@__dviet` 60fps):** Chuỗi 3 nhịp đảo pha `Invert(2f) → Normal(2f) → Invert(2f)` (33ms/pha) vắt ngang điểm cut (`1 nhịp ở shot A → cut → 2 nhịp ở shot B`). Phiên bản 24fps: `1f Invert Outgoing (white vignette) → 2f Invert Incoming (dark vignette) → Normal`.
2. **`subject_isolated_double_flash` (`@__dviet`):** Tách RVM/mask riêng chủ thể, đánh exposure trắng xóa chỉ trên chủ thể **4–5f (`67–83ms`)**, nghỉ 4f, lặp nhịp 2 (4–5f) trong khi nền giữ tối nguyên vẹn.
3. **`invert_strobe_6hz` (`@__dviet`):** Full-frame invert chu kỳ vuông **9–10f/cycle (`4–5f ON / 4–5f OFF @ 60fps` ≈ 6 Hz)** kéo dài 1–2.3s ở đoạn B-roll cao trào.
4. **`pre_cut_roto_silhouette` (`@__dviet` 30fps):** Trước hard cut 4f (`133ms`), nháy mask chủ thể của shot B tô trắng kem `#F5F3EB` (85% opacity) theo nhịp **`1f ON → 2f OFF → 1f ON → CUT`**, khớp audio transient ở `-40ms`.
5. **`xuanart_invert_burst` & `3x3_grid_invert` (`@xuanart.visual`):** Đánh invert burst ngắn **2–6 frames (`33–100ms`)** hoặc đảo màu từng ô trong lưới **3×3 grid** kèm **Directional Blur ngang 4–6f**.
6. **`xuanart_cutout_red_reveal`:** `2f nền đen` → `2f silhouette đỏ rực (#E01515)` → `2f chủ thể thật trên nền đen` → `bung nền cảnh + 4f flash trắng/vàng`.
7. **`xuanart_split_flash` (8f @ 60fps = 133ms):** Ô vuông trắng bung tại tâm (`4f`) → mở rộng full-width whiteout (`4f`) → hard cut.
8. **`xuanart_tracery_echo` / `progressive_echo_clone`:** Roto chủ thể nhân bản thành **5–7 lớp clone** lệch theo vector chuyển động/xếp lớp ngang theo beat, kết bằng `2f` flash hồng/trắng hoặc Mirror Flip trên-dưới.
9. **`halftone_sunburst_lightleak`:** `Halftone Circle Mask` → `White-Gold Lens Bloom` (`~6f`) → `Blue Sunburst Behind Subject` → `Orange/Amber Light Leak` (`10–16f`, peak đặt sau cut `+2..3f`).
10. **`white_canvas_rapid_cut_card`:** Nền `#FAFAFA` giữ cố định header/footer và khung viền glow, cắt B-roll bên trong mỗi **`130–200ms` (`4–6f @ 30fps`)**; swap header bằng horizontal blur `1–2f`.
11. **`tutorial_wrapper_isolation` (`@xuanart.visual` Longform):** Layout 2–3 vùng cố định (Timeline + Preview + Webcam), tắt karaoke trên lớp giảng giải, giữ `flash_count = 0, invert_count = 0` cho wrapper và cô lập mọi VFX trong Preview Player.

---

## 5. Quy tắc SFX & Cut-Sync 2 chế độ

- **Chế độ 1 — Rapid / Strobe Pre-Lap (`-18ms` đến `-57ms`):** Áp dụng khi ASL `< 1.2s` hoặc có whoosh/roto-flash kéo vào cut. Âm thanh/riser đi trước hình 1–3 frames để mắt và tai khóa nhịp.
- **Chế độ 2 — Film-Burn / Reveal Post-Impact (`+35ms` đến `+83ms`):** Áp dụng khi dùng Film Burn, Shape Wipe hoặc Tutorial/Essay. Hình cắt trước vào frame mở, impact/sub-thump đập vào sau **2–5 frames** đúng lúc đỉnh sáng hoặc chữ chính pop-in.
- **Pre-Drop Vacuum (`80–220ms`):** Cắt sạch BGM/nền tạo khoảng lặng ngay trước cụm rapid montage, step card (`1/2/3`) hoặc cú drop chính.
