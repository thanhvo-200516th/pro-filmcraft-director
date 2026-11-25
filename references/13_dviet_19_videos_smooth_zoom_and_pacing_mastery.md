# 13. Giải Phẫu 19/19 Video `@__dviet`: Quy Luật Zoom-In / Zoom-Out Mượt Như Nhung (`C²` 60fps) & Nhịp Dựng Nhanh – Chậm Đối Xứng

> **Nguồn dữ liệu thực nghiệm:** Phân tích Optical-Flow (RANSAC Affine Inliers `scale(t), dx(t), dy(t)`) trên toàn bộ **19/19 video HD** của kênh `https://www.tiktok.com/@__dviet` (tổng thời lượng **`914.41s`**, **`272` shots**, **`253` điểm cắt**, **`113` đường cong Zoom toàn khung**), kết hợp Hội đồng 3 Agent (Optical-Flow Analyst × Senior Master Editor × 60fps Sub-Pixel Physics Engineer).

---

## 1. Thống Kê Thực Nghiệm Từ Toàn Bộ 19 Video `@__dviet`

| Chỉ số đo đạc (19 Video = `914.41s` / `272` Shots) | Giá trị thực tế của `@__dviet` | Sai lầm phổ biến làm video bị "gắt / giật" (V10–V13 cũ) | Quy chuẩn V14 Smooth Master (`60fps`) |
| :--- | :--- | :--- | :--- |
| **Tỷ trọng Nhịp Nhanh – Chậm (Theo số Shot vs Thời lượng)** | `27.2%` số shot `< 1.0s` (`p10 = 0.233s`), nhưng **`86.9%` tổng thời lượng màn hình** thuộc về các cú trượt êm `≥ 2.2s` (`median = 2.425s`, `mean = 3.36s`, `p90 = 7.06s`). | Nhồi nhét chuyển động gắt ở mọi giây, không có khoảng thở tĩnh tương phản. | Cụm Staccato nhanh (`0.18s–0.35s`) chỉ chiếm `~8–12%` thời lượng để tạo điểm nổ; **`~88%` thời lượng** là các cú lướt mượt `2.6s–6.6s`. |
| **Tỷ lệ Loại Điểm Cắt (`253` Cuts)** | **`61.3%` Clean Cut / Scale-Contrast Cut** (`155/253`), `22.9%` Plate Whip/Blur (`58/253`), và **chỉ `13.8%` Flash/Film-Burn Cut** (`35/253` ≈ `1.8` flash/video). | Dán `whip_zoom + film_burn` lên tất cả `11/11` ranh giới + `12` sub-beat (`23` cú giật sáng trong `40s`). | Giữ **Clean Scale-Contrast Cut** cho đa số cảnh; chỉ đặt **Plate-Only Optical Halation** tại đúng **4 cột mốc chuyển chương lớn** (`5.81s, 12.04s, 14.87s, 34.02s`). |
| **Zoom-In Chủ Đích (`Δscale ≥ +10%`, `n = 22`)** | Thời lượng **`median = 0.583s` (`35f @ 60fps`)**, `mean = 0.756s` (`45f`). Biên độ `+16.1% .. +34.3%` (`median = +20.3%`). Đường cong khớp `R² = 0.9997`: `cubic-bezier(0.32, 0.14, 0.34, 0.87)` (đỉnh vận tốc tại `τ = 0.21–0.33`). `63.6%` đi kèm pan reframe ngang/dọc. | Zoom `0.20s–0.23s` (`12–14f`) với `cubic-bezier(0.16, 1.0, 0.30, 1.0)` (độ dốc đầu `6.25` → giật cục `28,013 /s³` ngay frame 1). | **`0.54s – 0.68s` (`32–41 frames @ 60fps`)** với `C²-Collared` `dviet_zoom_in` (`cubic_bezier(τ(u), 0.14, 0.90, 0.20, 1.00)`), đệm êm 5 frame đầu + trượt đuôi 24 frame. |
| **Zoom-Out Nhung Lụa (`Δscale ≥ -10%`, `n = 58`)** | **`2.6x` nhiều hơn Zoom-In!** Thời lượng **`median = 0.725s` (`43f @ 60fps`)**, `mean = 0.893s` (`53f`). Biên độ `-13.4% .. -27.0%` (`median = -17.7%`), `R² = 0.9999`. **`69.0%` bắt đầu ngay sau nhát cắt** (Post-Cut Velvet Settle `1.20x → 1.02x`); `31.0%` là Mid-Shot S-Curve Release. | Dùng chung hàm Ease-Out nổ ngược của Zoom-In cho Zoom-Out trong `0.23s` → giật lùi khung hình thô bạo rồi đập ngược vào whip-cut kế tiếp. | **`0.62s – 0.78s` (`37–47 frames @ 60fps`)** với đường cong nhung S-Curve `dviet_zoom_out` (`cubic_bezier(τ(u), 0.34, 0.02, 0.16, 1.00)`). |
| **Cô Lập Lớp Chữ (`Layer Isolation`) & Sub-Pixel Float** | Typography (`V7/V8`) **đứng độc lập 100%** trên mặt phẳng riêng, trôi mượt dưới mức hạ điểm ảnh (`0.02–0.04 px/frame`), không bao giờ bị méo khi nền whip/zoom. | Gọi `apply_cut_transition_bridge` sau khi vẽ chữ làm chữ bị kéo giãn `1.18x`, cộng thêm `int(round(...))` + `NEAREST` gây khựng bậc thang `1px` suốt `173/179` frames. | Dựng bằng `LayeredFrameCompositor` 3 mặt phẳng + `SubPixelSprite` Premultiplied `float32` `cv2.warpAffine(INTER_LINEAR)` (`0` frozen frames, `R² = 0.9999995`). |

---

## 2. Bốn Định Luật Vàng Của Chuyển Động Camera Mượt (`@__dviet` Studio Physics)

### Luật 1 — Hai Đường Cong Bezier Riêng Biệt Cho `Zoom-In` Và `Zoom-Out` (Nối Tiếp Đạo Hàm Bậc 2 `C²`)
Không bao giờ dùng chung một đường cong thời gian cho cả phóng vào và thu ra, và không bao giờ cắt cụt thời gian zoom xuống dưới `0.48s`:
1. **Silky Asymmetric Reframe Zoom-In (`0.54s – 0.68s` = `32–41f @ 60fps`):**
   - Khởi đầu bằng đệm gia tốc mượt `C² Collar` (`τ(0)=τ'(0)=τ''(0)=0` trong `5–6 frames` đầu để mắt kịp nhận diện hướng di chuyển), đạt đỉnh vận tốc êm tại `22%–30%` quãng đường, và dành **70% thời gian còn lại (`24–28 frames`)** để phanh nhung tiệm cận vào khung cận (`1.22x – 1.34x`) kèm dịch trục bất đối xứng (`dx = ±85..125px`, `dy = -20..-32px`) mở khoảng trống âm cho Typography.
   - Bàn giao chính xác vận tốc cuối `v₁` sang pha **`drift` nhẹ (`+0.012/s .. +0.016/s`)** thông qua cơ sở đa thức bậc 5 **Quintic Hermite** (`ψ₀(u), ψ₁(u)`), triệt tiêu hoàn toàn điểm gãy vận tốc (`|Δv| < 10⁻⁵`).
2. **Velvet Cushion Zoom-Out (`0.62s – 0.78s` = `37–47f @ 60fps`):**
   - Có **2 vai trò chiến lược** được phát hiện từ 58 mẫu Zoom-Out trên kênh `@__dviet`:
     - **Vai trò A — Post-Cut Velvet Settle (`69%` trường hợp):** Ngay đầu cảnh mới, vào hình ở `1.18x – 1.22x` rồi thả lùi êm ái về `1.02x – 1.04x` trong `0.68s – 0.75s` (`41–45 frames`). Cách này tạo dòng chảy liên tục giữa 2 cảnh cắt mà không cần nháy sáng hay giật lắc.
     - **Vai trò B — Mid-Shot / End-Phrase Breathing Release (`31%` trường hợp):** Khi người nói chuyển từ ý căng sang lời mời nhẹ nhàng hoặc mở sang ý tổng quát, thu camera từ `1.30x → 1.04x` trong `0.65s – 0.78s` theo đường chữ S (`cubic_bezier(τ(u), 0.34, 0.02, 0.16, 1.00)`).
   - **Cấm tuyệt đối lỗi "Whiplash":** Không bao giờ Zoom-Out sát mép cuối cảnh (`< 0.30s` trước nhát cắt) rồi lập tức Whip-Zoom-In ngược lại! Nếu cuối cảnh đã thả `dviet_zoom_out` về `1.03x`, nhát cắt kế tiếp phải là **Clean Cut** sang khung Cận (`1.22x`) hoặc B-Roll toàn màn hình để mắt cảm nhận độ mở êm ái.

### Luật 2 — Xóa Bỏ Mọi Dao Động Con Lắc (`sin/cos` Sway & Yo-Yo Micro-Punches)
- **Cấm `sin(u * π)` Yo-Yo Punches (`0.22s`):** Nhịp nhích vào `+4.5%` trong `6 frames` rồi giật lùi `-4.5%` trong `6 frames` tạo cảm giác "nấc cụt camera" giả tạo. Nếu cần nhấn trọng âm từ khóa mà không đổi bố cục, chỉ dùng xung chuông bậc 6 **`B₆(u) = 64 u³(1-u)³`** kéo dài `0.42s – 0.50s` với biên độ siêu tinh tế (`+0.018 .. +0.024`) và tối đa `1` lần trong một câu dài.
- **Cấm lắc ngang `3.2*sin(2.1t)` & lắc Speaker Cutout `25*sin(1.8t)`:** Thay bằng nhịp thở hữu cơ siêu chậm (`0.55px @ 0.32 Hz` trục X, `0.40px @ 0.26 Hz` trục Y — dưới ngưỡng nhận thức rung lắc nhưng giữ khung hình sống động).

### Luật 3 — Nhòe Chuyển Động Quang Học `180°` Theo Vận Tốc Tức Thời (`True Velocity Shutter Blur`)
- Độ nhòe chuyển động trên Premiere (`Transform -> Shutter Angle = 180°`) tỷ lệ thuận với **đạo hàm vận tốc thực giữa 2 frame liên tiếp** `v_px = |z(t) - z(t - Δt)| * R + hypot(ΔX, ΔY)`, **KHÔNG** tỷ lệ với độ lệch vị trí `|dx|` và **KHÔNG** dùng hàm `sin()` lệch pha.
- Khi camera đang giữ nhịp đọc (`drift` `+0.015/s` → `smear = 0.11px < 0.75px`): chạy đúng **1 phép biến đổi sắc nét**, không chồng blur giả để da mặt và chi tiết sản phẩm trong vắt `100%`. Khi đang lướt Zoom-In/Zoom-Out hoặc Whip Plate (`smear ≥ 0.75px`): tích phân đối xứng `3/5/7` điểm lấy mẫu Hann dọc theo quỹ đạo thực của màn trập `180°`.

### Luật 4 — Kiến Trúc 3 Mặt Phẳng Độc Lập (`LayeredFrameCompositor`) & Sub-Pixel `float32`
```
[Plane 2 - Foreground Clean UI/Typography (V7/V8)]  <-- KHÔNG BAO GIỜ chịu ảnh hưởng của Plate Transition!
        ▲  Premultiplied float32 cv2.warpAffine (0.03px/frame smooth micro-float, R² = 0.9999995)
[Plane 1 - Midground Cutouts & Floating Cards (V3/V6)] <-- Tọa độ float32 liên tục (cấm int() resize/paste)
        ▲
[Plane 0 - Video / 2.5D Plate (V1/V2/V4/V5)]        <-- SmoothCameraTrack 60fps + 4 Chapter Optical Halations
```

---

## 3. Cấu Trúc Nhịp Dựng "Nhanh – Chậm Phù Hợp" (`Musical Tempo Architecture`)

Để video vừa cuốn hút vừa sang trọng như `@__dviet`, bản dựng phải tuân thủ **Đường Cong Tương Phản Nhịp Độ (Tempo Contrast Wave)** thay vì giữ đều một tốc độ:

1. **Pha Dẫn Nhập Êm (`Calm Visual Hook`, `1.3s – 2.0s`):** Mở bằng không gian chiều sâu 2.5D + chữ Hero từ từ hội tụ nét để não người xem định vị chủ đề mà không bị ngợp.
2. **Điểm Nổ Staccato Ngắn (`Fast Rhythmic Burst`, `3` nhịp × `0.22s–0.35s`):** Chèn đúng vào chỗ liệt kê bằng chứng thô (ví dụ: *"3 tấm ảnh chụp vội"* hoặc *"3 thẻ hệ thống"*), khớp tiếng màn trập / click cơ học.
3. **Khoảng Thở Trượt Nhung (`Velvet Glide & Reframe`, `2.6s – 4.2s`):** Sau cụm nhanh bắt buộc trả về A-Roll/2.5D mượt dài tối thiểu `2.6s`, sử dụng **1 cú Silky Zoom-In (`0.58s`)** hoặc **1 cú Velvet Zoom-Out (`0.68s`)** đúng từ khóa chuyển ý.
4. **4 Cột Mốc Chuyển Chương (`Macro Chapter Pivots`):** Chỉ dùng ánh sáng ấm/đỏ thẩm thấu trên nền (`Plate-Only Film-Burn Halation`, cường độ dịu `0.42–0.52` trong `16 frames`) tại 4 nút ngoặt kịch bản:
   - `5.81s` (Hook → Nhân vật xuất hiện),
   - `12.04s` (Nỗi đau → Cận cảnh lỗi *"giả trân"*),
   - `14.87s` (Lỗi → Giải pháp hệ thống OverPower),
   - `34.02s` (Giải pháp → Lời mời nhận quà CTA kết thúc bằng Velvet Zoom-Out ấm áp).

---

## 4. Giải Phẫu Chi Tiết 6 Video Mới Trên Kênh `@__dviet` & Quy Tắc Chọn `Smooth Zoom-Out` (`10 : 1`) vs `Cut-to-Wide`

### 4.1. Sáu Video Mới Bóc Tách Bằng `PyrLK Sub-Pixel Optical Flow` + `SIFT` (`45,582` Frames Tổng)
1. **`7672413018575146261` (`65.13s @ 60fps` — CapCut Backlight Halo):** Mở và kết bằng A-Roll rèm ấm; mọi cú Zoom-In (`+7.7% .. +20.3%` trong `0.38s–0.40s`) đều kết hợp dịch ngang/dọc (`+1.8%..+3.6% X, -3.8%..-4.9% Y`) để nhường vùng trống trên-trái cho Typography. Đoạn tutorial giữa dùng 6 nhát cắt tĩnh đồng tỷ lệ (`|ΔS| < 0.9%`).
2. **`7669758857471741204` (`24.92s @ 60fps` — 8 Sound Effects Pack):** Cả video `24.9s` chỉ có **1 nhát cắt duy nhất** (`t = 7.68s`), nhưng `7.6s` đầu không hề tĩnh nhờ **Slow Breathing Glide** liên tục: đẩy nhẹ `+7.32%` (`0.20s → 2.40s`) nối liền với thu lùi nhung `-16.5%` (`2.40s → 7.60s`).
3. **`7668334908615560469` (`64.67s @ 60fps` — CLONE Effect):** Mở bằng **Post-Cut Velvet Settle-Out** `0.983s` (`59f`, `-27.4%`, `cubic-bezier(0.21, 0.47, 0.51, 0.95)`, `R² = 1.000`), kết hợp UI zoom `0.30s` (`+21.3%`) và nhát cắt cận trục ở câu chốt `t = 59.87s`.
4. **`7666039448039099669` (`40.07s` — VISUAL HOOK + Font/SFX Pack):** Kết hợp mẫu mực giữa `0.70s–1.07s` Velvet Asymmetric S-Curve Zoom-Ins (`+8.4% .. +15.9%`, `cubic-bezier(0.16, 0.00, 0.27, 0.89)`), Mid-Shot Zoom-Out `0.67s` (`-11.7%`) và các nhát Axial Scale Cut tại chỗ ngắt hơi thở.
5. **`7665298781344189716` (`55.27s` — 3 Website Showcase):** Lộ diện kỹ thuật **Adjustment-Layer Cross-Cut Speed-Graph Zoom** (`t = 3.833s → 4.167s`): cảnh A-Roll cuối gia tốc mượt lên đỉnh vận tốc đúng frame cắt `t = 4.000s`, cảnh B-Roll kế tiếp đón quán tính và giảm tốc nhung về `0`. Khép lại bằng Slow Breathing Glide-Out `2.23s` (`-12.94%`).
6. **`7664969137445276949` (`46.47s @ 60fps` — FLICKER Effect):** Mở bằng Post-Cut Velvet Settle-Out `0.783s` (`47f`, `-24.2%`, `R² = 1.000`), giữ nhịp trung vị `2.73s/beat`, và tung cú Asymmetric Velvet Zoom-In + Reframe `0.983s` (`59f`, `+67.4%`, đỉnh vận tốc tại `τ = 0.10` → **90% quãng đường là đuôi phanh nhung**!).

### 4.2. Quy Tắc Quyết Định `Smooth Velvet Zoom-Out` (`68` lần) vs `1-Frame Axial Cut-to-Wide` (`7` lần)
Trên toàn bộ 19 video, `@__dviet` ưu tiên **Zoom-Out mượt gấp gần `10 lần` (`68 : 7`)** so với cắt giật về góc rộng:
- **Dùng `Smooth Velvet Zoom-Out` (`0.60s – 0.85s`, dài hơn Zoom-In `+28%..+33%`):**
  1. **Giữa một mạch nói liên tục không cắt hơi (`frac_in_shot = 0.24–0.62`):** Khi chuyển từ chi tiết vi mô ra bức tranh tổng quát hoặc mở lời mời thân mật mà giọng nói vẫn đang liền mạch.
  2. **Đầu cảnh mới / Hook / B-Roll (`Post-Cut Velvet Settle-Out`, `0.45s–0.75s`):** Vào cảnh ở `1.16x–1.20x` rồi thả nhẹ về `1.00x–1.03x` (`cubic-bezier(0.13, 0.20, 0.35, 0.95)`) để triệt tiêu độ gắt của nhát cắt.
- **Chỉ dùng `1-Frame Cut-to-Wide` (`0f`, giảm `-12% .. -35%`):**
  - Duy nhất tại **điểm cắt bỏ khoảng lặng lấy hơi giữa 2 đoạn văn (`Paragraph Jump-Cut`)**: vì khẩu hình miệng đã nhảy qua khoảng nghỉ bị cắt, việc đổi tỷ lệ khung hình tức thì `≥ 15–20%` giúp giấu vết cắt jump-cut tự nhiên (nếu zoom mượt đè lên chỗ miệng nhảy sẽ làm lộ vết ghép thoại).

### 4.3. Bảng 5 Preset Chuẩn Hóa Cho Premiere Pro / FilmCraft / Python Engine
| Preset | Thời lượng (`60fps`) | Biên độ Scale & Pan | Đường cong `cubic-bezier` chuẩn |
| :--- | :---: | :---: | :--- |
| **P1. Signature Velvet In-Shot Zoom-In** | `0.50s – 0.62s` (`30–37f`) | `+16% .. +24%`, `pan = (±4.5% X, -2.5% Y)` ngược phía chữ | `cubic-bezier(0.24, 0.04, 0.24, 0.92)` / `C²-Collared (0.14, 0.90, 0.20, 1.00)` |
| **P2. Velvet Mid-Shot S-Curve Zoom-Out** | `0.65s – 0.75s` (`39–45f`) | `-14% .. -20%` (`1.24x → 1.03x`) | `cubic-bezier(0.13, 0.00, 0.59, 1.00)` / `C²-Collared (0.34, 0.02, 0.16, 1.00)` |
| **P3. Post-Cut Velvet Settle-Out** | `0.48s – 0.70s` (`29–42f`) | `1.18x → 1.02x` ngay từ frame `0` sau cut | `cubic-bezier(0.13, 0.20, 0.35, 0.95)` |
| **P4. Cross-Cut Speed-Graph Match Zoom** | `16f` ra + `23f` vào | `+15%` gia tốc tới cut → `0.86x → 1.00x` giảm tốc | Ra: `(0.74, 0.13, 0.93, 0.74)` → Vào: `(0.13, 0.20, 0.35, 0.95)` |
| **P5. Slow Breathing Glide (Chống Tĩnh)** | `2.20s – 2.80s` (`132–168f`) | `+1.4%/s .. +4.5%/s` trôi đơn điệu êm | `cubic-bezier(0.42, 0.20, 0.38, 0.85)` + Quintic Hermite `C²` |

---

## 5. Triển Khai Trong Code (`pro-filmcraft-director`)

- **Biểu đồ Atlas Đường Cong & Vận Tốc Thực Nghiệm (19 Video):** [`references/dviet_zoom_bezier_atlas.png`](./dviet_zoom_bezier_atlas.png)
- **Engine vật lý camera & Sub-Pixel Compositor:** [`scripts/dviet_smooth_camera_engine.py`](../scripts/dviet_smooth_camera_engine.py)
  - `configure_worker_simd_threads(2)`: Khóa xung đột luồng OpenMP khi render song song 4 workers (tăng tốc `6.6x`, đạt `~81 FPS` tổng).
  - `SmoothCameraTrack`, `CameraKeyframe`, `render_camera_plate_60fps`: Nội suy `C²` + `180°` Shutter Blur.
  - `SubPixelSprite`, `composite_subpixel_sprite`, `apply_subpixel_micro_float_pil`: Chống rung bậc thang `1px` tuyệt đối cho chữ và thẻ nổi.
  - `render_25d_parallax_smooth` & `LayeredFrameCompositor`: Parallax 2.5D bokeh `shift=4` (`1/16px`) và cô lập hoàn toàn lớp chữ `V7/V8`.
- **Pipeline kết xuất Master V14:** [`scripts/build_v14_dviet_smooth_master.py`](../scripts/build_v14_dviet_smooth_master.py) (tích hợp `ffmpeg-skill v4.5.3`, chuẩn hóa BT.709, âm thanh EBU R128 `-14 LUFS`, và bắt buộc cờ **`-sn`** không nhúng phụ đề chìm `mov_text`).
