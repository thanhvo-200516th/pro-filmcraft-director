# Quy chuẩn `@__dviet` & Typography Tiếng Việt 134/134 NFC

## 1. Hệ thống Màu Tối giản (`#FAFAFA` + 1 Màu Nhấn)
- **Gallery Off-White (`#FAFAFA`):** Màu chữ chính & nền thẻ sáng (tránh `#FFFFFF` gắt toàn thẻ).
- **Matte Studio Dark (`#111111`):** Nền thẻ tối, chữ trên nền sáng, vignette đáy.
- **Single Accent:** Tối đa **1 màu nhấn chủ đạo** theo ngành cho 1–2 từ khóa đinh (`WCAG >= 4.5:1`).

## 2. Bộ Font Chuẩn 134/134 NFC & Danh sách Cấm (`Rule of Two`)
Mọi text bắt buộc chuẩn hóa `unicodedata.normalize("NFC", text)`. Tối đa **2 họ font** trong 1 video (1 font tạo lực cho **Hero**, 1 font sạch dễ đọc nhanh cho **Lead/Long-Speech**):
- **Được phép:**
  - *Sans-Serif Hiện đại:* `Be Vietnam Pro` (`Medium`, `Bold`, `ExtraBold`, `Black`)
  - *Geometric Sans:* `Montserrat Static` (`SemiBold`, `Bold`, `ExtraBold`)
  - *Script / Calligraphy (chỉ cho Hero 1–2 từ cảm xúc):* `SVN-Blog Script`, `Instagram Sans Script`
  - *Condensed Impact (thay thế bắt buộc cho `Anton`):* `DFVN West West Condensed`
- **CẤM TUYỆT ĐỐI:** `Anton` (`0/134` dấu), `Bebas` / `Bebas Neue`, `Instrument Serif`, `Great Vibes`, `Montserrat-Variable`.

## 3. Luật Layout Tiếng Việt & Triple Mutex
- **`padding_top >= 0.28em` & `line_height >= 1.22`:** Bắt buộc khi dùng `Crop`/`Mask` Slide-Up Reveal để không xén mất dấu mũ chữ hoa và dấu chồng kép (`Ắ, Ế, Ộ, Ứ`).
- **`min_static_hold_sec`:** `clamp(0.45 + 0.24 * word_count + 0.14 * stacked_diacritics, 0.75, 3.20)` — giữ lâu hơn cho câu có nhiều chữ dấu chồng kép (`ệ, ậ, ồ, ứ...`).
- **`Single Hero = 1` & `Triple Mutex`:** Mỗi beat tối đa 1 hiệu ứng chữ hero. Cấm kết hợp:
  - `Behind-Head` + `Blend Overlay` / `Dual Polarity Card`
  - `Flicker 2f` + `Flash Out 4f`
  - `Stack3 Feather` + `Stacked Hollow Echo`
  - `Slide Reveal` + `Curved Arc`
- **Behind-Head (`V2` Text sau `V3` RVM):** Tỷ lệ đầu/vai che chữ lý tưởng **`30%–50%`**, khóa đồng bộ transform `V1 === V3`.

## 4. Phân tầng Layer Chữ Talking-Head (`Hero` vs `Lead` vs `Long-Speech`)
Trong video Talking Head, chữ xuất hiện gần như xuyên suốt. Phải tách rạch ròi 3 tầng để không bị rối hoặc thiếu thông tin:
- **Tầng 1 — Hero / Keyword (`V7` hoặc `V2` Behind-Subject):** `72–130 px`, chỉ `1–3` từ khóa đinh / con số `Proof` / từ `Contrast`. Tỷ lệ kích thước so với Lead tối thiểu **`1.8x – 2.5x`**.
- **Tầng 2 — Lead / Context (`V8`):** `40–52 px`, cụm dẫn `3–6` từ, vào/ra lệch pha Hero `2–4 frames`.
- **Tầng 3 — Micro Sub-caption (`Sub1` / `V8` đáy):** `36–42 px`, tối đa `18–24` ký tự/dòng (`<= 2` dòng) khi cần giữ nguyên văn câu nói dài. **Bắt buộc tắt hoặc ẩn Sub-caption** khi đang chạy Motion Card / B-Roll toàn màn hình (`Cognitive Load = 1`).
- **Phrase Chunking:** Ngắt cụm nghĩa `3–6` từ/beat; tự động gộp orphan beat `<= 2` từ hoặc `< 0.7s`.

## 5. 7 Kiểu Text Entrance / Exit (Premiere Pro ↔ `.fcproj v17`, `@30fps`)
*(Nhân đôi số frame khi compile `60fps`; `Transform` luôn bật `shutter_override: true`.)*
1. **Slide-Up Crop Reveal:** `pos_y +110px -> 0` (`12f` Bezier `in_inf: 0.82`), `opacity 0 -> 100%` (`4f`), `crop.bottom` giữ tại đường đáy; `padding_top >= 0.28em`.
2. **Gaussian De-Blur Focus Pull:** `gaussian_blur` (`repeat_edge: true`) `20 -> 0` + `scale 106% -> 100%` + `opacity 10% -> 100%` (`10f`).
3. **Overshoot Spring Pop (Hero):** `F0: scale 0%, op 0%` → `F5: scale 108%, op 100%` → `F9: scale 97%` → `F12: scale 100%` (4 keyframes vì `influence` kẹp `[0..1]`).
4. **Kinetic Slide + Directional Blur:** `pos_x -160px -> 0` + `directional_blur 24 -> 0` (`10f`, `shutter_angle: 270°`), khớp `whoosh` ở `F-2`.
5. **Pill Badge Unroll-Y:** `graphic_shape` (`Anchor = bottom_edge`) `scale_w 85% -> 103% -> 100%` đi trước `scale_h 10% -> 106% -> 100%` `2f`, text fade-in trễ `2f`.
6. **Flicker Strobe / Ghost Trail:** `Hold` keyframes `6f` (`[100, 0, 100, 0, 100, 100]`) hoặc layer echo `scale 100% -> 114%, op 55% -> 0%` (`4f`).
7. **Behind-Subject Depth + Difference:** Đặt ở `V2` dưới `V3` RVM (`30–50%` occlusion). **Cấm bật `drop_shadow`** nếu `opacity.blend != 0`.
