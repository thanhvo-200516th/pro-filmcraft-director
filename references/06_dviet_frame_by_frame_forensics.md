# 06 — Forensics 4 Tầng Từng Frame: `@__dviet` & Video Mẫu (`7706183278461570356` & `7707599674923896070`)

Tài liệu tổng hợp dữ liệu đo kiểm định từng frame từ 2 video mẫu thực tế:
- **`@__dviet` Story (`7706183278461570356`):** `1440×1080`, `24fps` (`41.67ms/frame`), `61.125s` (`1467 frames`), `-11.3 LUFS`, `LRA 1.7 LU`, `23` transitions.
- **`Arthur Brooks Minimal` / `KAIRO AI` (`7707599674923896070`):** `1080×1920`, `30fps` (`33.33ms/frame`), `344.13s` (`10,324 frames`), `-14.5 LUFS`, `LRA 2.3 LU`.

---

## TẦNG 1 — Từng Frame Xuất Hiện của Text (`Word-by-Word Staggered De-Blur` vs `Slow Text`)

### 1.1. Công thức Từng Frame (`30fps` = `33.33ms/f`) trong `7707599674923896070`
- **Entrance mỗi từ (`3–4 frames = 100–133ms`):**
  - `F0`: `opacity ~25–30%`, `Gaussian/Directional Blur` mạnh, `pos_y +15px`.
  - `F1–F2`: `opacity 45–85%`, trượt lên về `0px`, giảm blur.
  - `F3` (`100ms` hoặc `133ms`): **Khóa nét 100%**.
- **Stagger giữa các từ:** Đúng **`4 frames` (`133ms`)** từ điểm khởi phát từ trước sang từ sau.
- **Exit:** **Hard cut tại điểm cắt (0 frame fade-out)** hoặc **xóa sạch trước cut 2 frames (`67ms`)** (`f10242` xóa trước `f10244`).
- **Quy tắc 75% & Tỉ lệ:** Lead-in `Sans Light` nhỏ + Keyword `Sans Bold` / `Serif Italic` lớn; khoảng cách dòng = **75% chiều cao chữ lớn**; đặt ở vùng tối / negative space `y = 60%..78%` (tránh mặt).

### 1.2. Công thức `Slow Text` & `Cross-Cut Persistence` (`@__dviet` `7706183278461570356`)
- Tách nhịp chữ khỏi nhịp nói (`279.2 WPM`): gom cụm `2–3` tầng giữ lâu `phrase_dwell_s` median **`2.25s` (`1.5–2.7s`)**, sống xuyên qua điểm cắt cảnh (`Cross-Cut Persistence`).
- **Blur Ramp vào/ra:** `slow_opacity_bloom` (`0.33–0.45s`, `opacity 0.15 → 1.0`, `gaussian_blur 14px → 0px`, `cubic-bezier(0.22, 1, 0.36, 1)`) và `blur_out_clean` (`0.17s`).
- **Vị trí Negative Space:** Dời chữ talking-head khỏi ngực giữa sang vùng trống âm trái/phải mặt (`x = 12–42%` hoặc `58–88%`, `y = 22–52%`).

---

## TẦNG 2 — Pixel-Exact Text FX, Optical Halation, Behind-Head & Flash/VFX

### 2.1. Z-Index & `2-Font Overlapping` (0% Drop-Shadow Đen Cứng)
- **Z-Stack chuẩn:** `Z=10 bg_footage` → `Z=20 bg_ghost_text` → `Z=30 subject_roto` → `Z=40 primary_yellow_glow` (`110–180px`, `tracking -0.05em`, **Dual Optical Bloom `12–26px`**) → `Z=50 white_caption_overlap` (`37–85px`, `100% lowercase`, outer glow `8–12px`, `σ=0.9–1.5px`) → `Z=60 tertiary_muted_blur` (`σ ≈ 2.4px`).
- **Tỉ lệ & Overlap:** `Y/W = 1.29x–4.08x` (đa số `1.6x–2.8x`), `X-overlap = 62.2%–100%`, `Y-overlap = 0%–18.5%` (ôm viền) hoặc `26.3%–93.8%` (đè trực diện).
- **Behind-Head (`f0336`):** Chữ vàng `144px` ở `Z=20` áp **Anisotropic Blur (`σX ≈ 5.3px`, `σY ≈ 3.9px`, tỉ lệ `1.36:1`, `alpha 50–65%`)** sau `Z=30` chủ thể (`~20–25%` che mép trong).

### 2.2. Đo Luma Từng Frame của 3 Loại Flash/Flicker (`@__dviet`, `24fps`)
1. **Negative / Invert Flash (3f = `125ms`):** `-1f Y=17.1` → **`F0 Y=178.4`**, **`F+1 Y=169.9`**, **`F+2 Y=170.2`** (`W=0%`, đảo âm bản) → **`F+3 Y=18.9`** (hard cut sang shot mới).
2. **Golden Sun-Flare White-Out (`10f`):** Ramp `-3f..-1f` (`Y=193.4 → 217.0 → 224.7`) → Peak **`F0..F+2` (`Y=234.9 → 235.3 → 231.0`, `W=66%`)** → Decay `F+3..F+5` (`214.3 → 172.5`) → `F+6 Y=50.7` (lộ studio mới).
3. **Text/Exposure Flicker (`2f`):** `-1f Y=16.3` → **`F0 Y=37.2 (+20.9 luma)`** → **`F+1 Y=27.9 (+11.6)`** → **`F+2 Y=16.1`**.

---

## TẦNG 3 — Chuyển cảnh & SFX Micro-Timing (Chống Bội thực Âm thanh)

### 3.1. 4 Pha Micro-Timing theo `t_peak`
1. **Pre-Roll (`-2f..-5f` / `-50..-210ms`):** `start = t_cut - t_peak` (ví dụ punch-in `135%`: shimmer/click đánh trước `-210ms`, sub-thump `-140ms`).
2. **Frame `0f` Lock:** Organic Wipe / Golden Sun-Flare (`luma=235.3`).
3. **Post-Cut Sub-Thump (`+40..+80ms`):** Warm `<120Hz` sub-thump (`-10.8..-12.1 dB`) rơi sau Flash/Whip/Shake.
4. **Pre-Drop Vacuum (`-40..-48 dBFS` trong `80–120ms`):** Kéo BGM (`A6/A7`) và Sub-Bass xuống `-40..-48 dBFS` ngay trước đỉnh Flash/Sun-Halation để cú nổ ánh sáng + air shimmer bật sạch sẽ.

### 3.2. Phân bổ SFX & Spectral Anti-Fatigue
- **Mật độ chuẩn `@__dviet`:** `~0.42–0.46 SFX/s` (**`1` SFX chính mỗi `2.2–2.5s`**) + **`17%` Silent Cuts (`0 SFX`)** khi chuyển trên khoảng nghỉ thoại hoặc có action foley tự nhiên (`laptop`, `footstep`, `camera focus`).
- **Tỷ lệ loại SFX:** Sub-Impact/Thump (`40%`), Flare/Shimmer (`22%`), Muted/LPF Whoosh `120–500Hz` (`22%`), Tactile Click/Foley (`15%`).
- **Spectral Anti-Fatigue:** Khóa dải `>6 kHz` ở `-45..-65 dBFS` trong 90% thời lượng; cấm auto-pick SFX gamey/chói (`BDE-Sonar*`, `Pop Flash*`, `Glitch*` chưa EQ). Giữ `A8` Organic Ambient Bed (`LPF 600Hz`, `-26..-30 dB`) và dùng `J-Cut` (`5–10f`) để nối mượt.

---

## TẦNG 4 — Guardrails Áp dụng ngay khi Audit `OPA_AI_SanPham`
1. **5-Frame Micro-Kick + Scale Contrast:** Jump cut đổi `camera.scale >= ±10%` kèm `5f Micro-Kick` (`+1.8% scale +3.6% brightness + cutBlur 5px`).
2. **Bỏ Drop-Shadow đen cứng & Hộp bo góc lặp lại:** Ưu tiên **Optical Halation + Blur Ramp** ở vùng Negative Space; không để 2–3 cụm chữ cạnh tranh cùng lúc (`Cognitive Load = 1`).
3. **Chủ động khoảng thở âm thanh:** Không nhồi SFX mọi beat; kết hợp `Silent Cuts`, `Pre-Drop Vacuum`, `J-Cut`, và `A8` Ambient Bed.
