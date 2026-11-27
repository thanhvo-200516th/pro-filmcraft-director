# 09 — `@__dviet` `7706183278461570356` Master Blueprint: 7 Typography Entrances, Asymmetric Bezier Zoom & 53-Event Multi-Layer SFX

Tài liệu này đúc kết toàn bộ công thức toán học từng frame (`24fps`/`60fps`) từ video chuẩn mực `7706183278461570356` và `7666801391284964628` của `@__dviet`, giải quyết triệt để 3 trụ cột của một Video Editor chuyên nghiệp:
1. **Hiệu ứng xuất hiện của từng chữ (7 Typography Entrance & Build-Up Choreography)**
2. **Đường cong Asymmetric Bezier Zoom-In / Zoom-Out & 2.5D Image Parallax**
3. **Nhịp đặt SFX Đa Tầng (53 Events Pre-Trimmed `t_peak` + Warm Organic Drone `177Hz`)**

---

## 1. 7 Kiểu Xuất Hiện Chữ (`scripts/dviet_7706_typography_choreography.py`)

Gia tốc chuẩn cho mọi chuyển động chữ:
$$E(p) = 1 - (1 - p)^{3.4} \approx \text{cubic-bezier}(0.16, 1.0, 0.3, 1.0)$$

1. **Kiểu 1 — Ghost-to-Focus Progressive Stack (`render_style1_ghost_to_focus_stack`):**
   - Dòng dẫn trắng nhỏ trồi từ `y +14px -> 0, blur 8px -> 0` trong `8 frames (0.33s)`.
   - Từ khóa Hero vàng (`#FACC15` core + `#F59E0B` warm amber halation) bung từ `y +22px -> 0, blur 12px -> 0` trong `9 frames (0.375s)`.
   - Khi chuyển sang cụm mới, cụm cũ **không tắt đột ngột** mà lùi về làm **Ghost Layer (`opacity = 0.22, blur = 6px`)** trong `8–12 frames` để tạo chiều sâu Z-depth.
2. **Kiểu 2 — Letter-Scatter 2D Convergence (`render_style2_letter_scatter_convergence`):**
   - Từng ký tự lẻ/chẵn xuất phát trên 2 rãnh dọc đối xứng (`dy0 = +24px` và `-20px`) kèm độ dãn ngang `dx0`, trượt hội tụ về baseline trong `11 frames (0.458s)` với độ trễ mỗi ký tự `delay(i) = 0.032*(i%4) + 0.06*(i/N)`.
3. **Kiểu 3 — Non-Linear Per-Word Staggered De-Blur (`render_style3_per_word_staggered_deblur`):**
   - Thứ tự xuất hiện phi tuyến (`entry_order = [1, 2, 0]` — từ ở giữa hiện trước, sau 3f đến từ phải, 1f sau đến từ trái).
   - Mỗi từ đi từ `blur 14px -> 0, y +24px -> 0, scale 0.92 -> 1.0`, kèm xung sáng **Warm Amber Halation Surge** đạt đỉnh `1.45x` tại `p = 0.35` (frame 3–4) rồi dịu về `0.85x`.
4. **Kiểu 4 — Tilted Multi-Cluster Balance & Bottom-Before-Top Counter-Reveal (`render_style4_tilted_multi_cluster`):**
   - Hai cụm chữ nghiêng góc `+7.5°` (vai trái) và `+4.5°` (vai phải).
   - Ở cụm phải, chữ phụ nhỏ màu trắng (`"và mất"`) hiện ra trước `6 frames`, sau đó chữ Hero vàng (`"định hướng"`) mới trồi lên **ngay phía trên** với negative leading `-14%`.
5. **Kiểu 5 — Circular Arc Word-by-Word Wrap (`render_style5_circular_arc_wrap`):**
   - Các ký tự quét dọc cung tròn bán kính `R ≈ 235–250px` ôm quanh đầu chủ thể, góc xoay tiếp tuyến $\phi = -(\theta + 90^\circ)$, bán kính thu từ `R + 14px -> R` kèm radial de-blur.
6. **Kiểu 6 — Overlap Negative-Leading Lockup (`render_style6_overlap_negative_leading_lockup`):**
   - Từ khóa vàng lớn (kèm dấu `+` sparkle ở góc trên trái) trồi lên **đè chồng 1/3 dưới** của dòng chữ trắng phía trên (`dy = +0.58 * H_sans, dx = -48px`), có lớp bóng tối mỏng `rgba(15,10,5,0.6)` tách lớp.
7. **Kiểu 7 — Continuous Micro-Float (`apply_style7_continuous_micro_float`):**
   - Suốt thời gian giữ chữ cho người xem đọc, cả cụm chữ tiếp tục nở nhẹ `+3.0%` scale và trôi `-5.5px` theo nhịp thở sin/cos để không bao giờ đứng chết cứng.

---

## 2. Đường Cong Asymmetric Bezier Zoom-In / Zoom-Out & 2.5D Parallax

- **Rule 1 — Asymmetric Reframe Zoom trên A-Roll:**
  - Cấm zoom tuyến tính đều đều giữ mặt ở chính giữa!
  - Đứng ở `1.02x`, khi chạm từ khóa trọng tâm thì **Whip-Zoom In trong `14 frames (0.233s @ 60fps)`** theo `cubic-bezier(0.16, 1, 0.3, 1)` lên `1.34x–1.40x`, **ĐỒNG THỜI dịch tâm crop ngang `dx = ±120..145px`** và bật **Radial Zoom Blur (`8 frames` đầu)**:
    - `dx = -135px`: Đẩy mặt nhân vật sang **1/3 Phải (`x ≈ 720px`)**, mở toàn bộ khoảng trống âm bên **Trái (`x = 80..540px, y = 820..1180px`)** ngang tầm má/vai cho Typography.
    - `dx = +130px`: Đẩy mặt nhân vật sang **1/3 Trái (`x ≈ 360px`)**, mở khoảng trống âm bên **Phải (`x = 520..1000px, y = 820..1180px`)**.
  - Kết hợp **Double-Step Punch Zoom (`1.02x -> 1.26x -> 1.40x`)**, **14-frame Bezier Zoom-Out (`1.40x -> 1.05x`)**, và **Handheld Micro-Sway (`±3px`)**.
- **Rule 2 — True 2.5D Image Parallax cho B-Roll:**
  - Tách ảnh tĩnh bằng `rembg` + `cv2.inpaint` thành **Foreground Subject** (`scale 1.00 -> 1.18..1.22x`, xoay nghiêng `±1.5°`) và **Depth-Blurred Background** (`scale 1.00 -> 1.05x`, trượt ngược chiều), chèn hạt bụi sáng **Bokeh Dust** ở lớp giữa và **6-frame Whip-Zoom Radial Blur** ở đầu/cuối cảnh.

---

## 3. Nhịp Đặt SFX Đa Tầng & Pre-Trimming `t_peak` (`1.30–1.60 SFX/s`)

- **Pre-Trimming `t_peak` bắt buộc:** Mọi file WAV whoosh/hit có đoạn lấy đà dài (`0.30s–1.04s`) phải được cắt `atrim=start=...` sao cho đỉnh năng lượng `t_peak` rơi vào đúng `0.03s–0.06s` đầu tiên của mẫu trước khi đặt `adelay`.
- **4 Tầng Âm thanh đồng bộ:**
  1. **Tầng 1 (`[L1-ZOOM]` — Low/Soft Air & Fabric Swooshes, `LPF 1000–1250Hz`, `-7.5..-9.0 dB`):** Đặt pre-lap `-30ms` tại mọi cú Asymmetric Zoom-In, Zoom-Out, Whip-Pan.
  2. **Tầng 2 (`[L2-TYPO]` — Paper Brush / Cloth Rub / Damped Shutter / Analog Film Burn / Shimmer, `-9.5..-12.0 dB`):** Đặt đúng frame 1–2 của mọi cụm Hero Keyword de-blur, word stagger, thẻ ảnh Polaroid, thẻ Bento và Pill.
  3. **Tầng 3 (`[L3-IMPACT/RISER]` — Sub-Thump `<160Hz` & Pre-Vacuum Riser, `-4.5..-6.5 dB`):** Đặt tại các điểm mở chương, đảo cực sáng/tối và ngay trước/sau `Pre-Drop Vacuum` (`90ms`).
  4. **Tầng 4 (`[L4-BED]` — Voice Compressor + 2-Stem BGM 4-Act Ducking + Warm Organic Drone `177Hz` `-27 dB`):** Giữ không gian âm thanh dày, ấm và liền mạch xuyên suốt video.
