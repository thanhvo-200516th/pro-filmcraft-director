# 10 — Giải Phẫu 35 Preset Text Animation (`@vietanh.videoeditor/video/7686349228712512788`) — Từ Adobe Premiere Pro sang FilmCraft (`.fcproj` v17 & Python Engine)

Tài liệu này bóc tách chi tiết từng khung hình (`1080x1920 @ 30fps`, `470 frames`) của bộ **35 Preset Text Animation / Caption Typography** từ video mẫu `@vietanh.videoeditor/video/7686349228712512788` (*"PRESET CAPTION — Kéo thả là sử dụng"*), chỉ rõ:
1. **Giải phẫu Chuyển động từng Frame (Frame-by-Frame Motion Anatomy)**
2. **Cách dựng gốc trên Adobe Premiere Pro (Effects, Keyframes, Masks, Blending)**
3. **Cách ánh xạ & triển khai trên FilmCraft (`.fcproj` v17 Native JSON & Python/OpenCV Render Engine)**

---

## Phần I. Bảng 1 — 18 Preset Đầu Tiên (`00:00.00` – `00:04.27`, Frames `001`–`128`)

### 1. `Minimal Style` (Hàng 1, Cột 1)
- **Giải phẫu từng Frame (`f=0..30`):**
  - Bố cục 2 dòng lệch trục: dòng trên `"Minimal"` (Sans-Serif Bold trắng `#FFFFFF`, lệch trái), dòng dưới `"style"` (Serif Italic trắng `#FFFFFF`, lệch phải).
  - `f=0..2`: Cả hai dòng ẩn hoàn toàn (`Opacity = 0%`).
  - `f=4..8`: Dòng trên `"Minimal"` xuất hiện trước với `Gaussian Blur = 28px`, trượt từ dưới lên (`dy: +24px -> 0px`). Dòng dưới `"style"` vẫn ẩn (`Stagger Delay = 5 frames / 167ms`).
  - `f=9..16`: `"Minimal"` lấy nét rõ hoàn toàn (`Blur -> 0px`); đồng thời `"style"` bắt đầu hiện mờ (`Blur = 24px -> 0px`) và trượt nhẹ từ dưới lên (`dy: +18px -> 0px`).
- **Cách làm trên Adobe Premiere Pro:**
  - Tách 2 Graphic Layers (`Layer 1: Minimal`, `Layer 2: style` đặt lệch phải bên dưới).
  - Gắn `Transform` (`Position Y: +24px -> 0px` trong `12 frames`, Ease Out Bezier, `Use Composition's Shutter Angle = Off`, `Shutter Angle = 180°`) + `Gaussian Blur` (`Blurriness: 30 -> 0`) + `Opacity` (`0% -> 100%` trong `6 frames`).
  - Kéo `Layer 2 (style)` trễ hơn `Layer 1` đúng `5 frames`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - 2 clip `graphic_text` trên `V7` và `V8` lệch nhau `167ms`; mỗi clip gắn `Transform` (`pos_y`, `shutter_override: true`, `shutter_angle: 180`) + `GaussianBlur` (`radius: 28 -> 0`).
  - Trong Python Engine: `u1 = clamp(t/0.35, 0, 1)`, `u2 = clamp((t-0.16)/0.35, 0, 1)`, vẽ từng dòng với `cv2.GaussianBlur(sigma = 14*(1 - ease_out_cubic(u)))` và `dy = int(24*(1 - ease_out_cubic(u)))`.

---

### 2. `Orange` (Hàng 1, Cột 2)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 1 từ đơn `"Orange"` cỡ lớn, font Geometric Sans-Serif Bold màu cam rực (`#FF5E1A`) có hào quang cam (`Outer Glow`).
  - `f=3..6`: Chữ phóng từ lớn về nhỏ (`Scale: 148% -> 100%`), đồng thời **xoay nghiêng chéo** từ góc âm về ngang (`Rotation: -18° -> 0°`) kèm vệt nhòe quang học (`Blur = 35px`, `Glow Radius = 45px`).
  - `f=9..15`: Đạt độ nét tại `Scale = 96%` (hơi thu nhỏ nhẹ) rồi hồi về `100%` ở `f=18`, lớp hào quang cam hạ dần về mức viền dịu.
- **Cách làm trên Adobe Premiere Pro:**
  - Trên `Graphic Layer "Orange"`: Đặt `Anchor Point` vào chính giữa chữ.
  - Gắn `Transform`: `Scale` (`150%` tại `f=0` -> `96%` tại `f=10` -> `100%` tại `f=16`), `Rotation` (`-20°` tại `f=0` -> `+1.5°` tại `f=10` -> `0°` tại `f=16`), `Shutter Angle = 270°`.
  - Nhân đôi layer xuống dưới, đặt Blend Mode `Screen` / `Linear Dodge (Add)` + `Gaussian Blur = 35` (`Opacity: 90% -> 35%`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dùng `Transform` với keyframe `scale` overshoot (`1.50 -> 0.96 -> 1.00`) và `rotation` (`-20 -> 0`).
  - Trong Python Engine: Dùng `cv2.getRotationMatrix2D(center, angle, scale)` kết hợp lớp bloom `Screen` (`1 - (1-A)*(1-B)`).

---

### 3. `Clear Green` (Hàng 1, Cột 3)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 2 tầng chữ tương phản kích thước: dòng trên `"CLEAR"` rất nhỏ, tracking rộng (`+300`), màu trắng (`#FFFFFF`); dòng dưới `"Green"` chữ lớn gấp 3 lần, font Sans-Serif ExtraBold màu xanh lá neon (`#1EE86C`).
  - `f=2..6`: Dòng nhỏ `"CLEAR"` hiện rõ ra trước ở phía trên.
  - `f=5..14`: Từ `"Green"` **trồi từ dưới một đường cắt vô hình (Invisible Baseline Mask)** đi lên (`dy: +48px -> 0px`) kèm `Gaussian Blur: 22px -> 0px`. Khi ở `f=6`, nửa dưới của chữ `"Green"` bị cắt phẳng bởi mặt nạ ngang.
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo 2 Graphic Layers. Trên `Layer "Green"`, gắn `Transform` **trước** hiệu ứng `Crop` trong bảng Effect Controls (`Transform` nằm trên `Crop`).
  - Trong `Crop`: Tăng `Bottom` lên sao cho đường cắt nằm ngay sát chân chữ `"Green"` ở vị trí đích.
  - Trong `Transform`: Keyframe `Position Y` từ `+55px` (nằm khuất dưới đường `Crop Bottom`) lên `0px` trong `12 frames` (Bezier Ease-Out) + `Gaussian Blur (25 -> 0)`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Render `"Green"` vào canvas đệm, dịch `dy = +55 * (1 - ease_out_cubic(u))`, áp `GaussianBlur`, sau đó cắt bỏ toàn bộ vùng pixel có `y > baseline_y + 8` (`canvas[baseline_y+8:, :] = 0`) trước khi alpha-composite lên frame.

---

### 4. `Text Focused` — `| text focused |` (Hàng 2, Cột 1)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Cụm chữ `"text focused"` màu trắng nằm giữa **2 thanh dọc màu xanh dương phát sáng (`#2979FF`)**. Thanh dọc bên trái có chấm tròn ở đỉnh trên, thanh dọc bên phải có chấm tròn ở đáy dưới. Toàn bộ cụm chữ có luồng sáng xanh dương (`Blue Glow Band`) phủ ngang phía sau.
  - `f=0..3`: 2 thanh dọc xanh dương xuất phát sát nhau ở chính giữa tâm (`Center X`). Chữ chưa hiện.
  - `f=4..14`: Thanh trái trượt sang trái (`Center_X -> Left_X`), thanh phải trượt sang phải (`Center_X -> Right_X`). Hai thanh đi đến đâu thì **mở mặt nạ (Center-Out Wipe)** để lộ chữ `"text focused"` và dải sáng xanh dương đến đó (`f=6` lộ `"xt foc"`, `f=9` lộ `"ext focuse"`, `f=14` lộ toàn bộ `"text focused"`).
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo 3 Layers:
    1. `Layer 1 (Text + Blue Glow)`: Gắn hiệu ứng `Crop` với `Left = 50% -> 0%` và `Right = 50% -> 0%` từ `f=2` đến `f=14` (`Edge Feather = 15`).
    2. `Layer 2 (Left Cursor Bar)`: Thanh shape dọc màu `#2979FF` có đầu tròn ở trên, keyframe `Position X` từ `Center_X` sang `Center_X - TextWidth/2 - 20px` khớp tuyệt đối với tốc độ `Crop Left`.
    3. `Layer 3 (Right Cursor Bar)`: Thanh shape dọc màu `#2979FF` có đầu tròn ở dưới, keyframe `Position X` từ `Center_X` sang `Center_X + TextWidth/2 + 20px` khớp với `Crop Right`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Tính `half_w = (text_w // 2 + 24) * ease_out_expo(u)`.
  - Mặt nạ chữ chỉ hiển thị trong dải `[cx - half_w : cx + half_w]`, đồng thời vẽ 2 thanh cursor neon tại đúng tọa độ `cx - half_w` và `cx + half_w` kèm lớp bloom xanh `#2979FF`.

---

### 5. `Modern Vibrant` (Hàng 2, Cột 2)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Dòng trên `"Modern"` màu trắng (`#FFFFFF`), dòng dưới `"Vibrant"` màu xanh cobalt phát sáng (`#1E6BFF`).
  - **Cơ chế đặc trưng: Chuyển động Đổi chỗ Xuyên qua nhau theo trục dọc (Vertical Pass-Through Crossover):**
    - Tại `f=2..4`: Chữ `"Modern"` (trắng) lại xuất phát ở **vị trí bên dưới** (`Y_bottom`), trong khi chữ `"Vibrant"` (xanh dương) xuất phát ở **vị trí bên trên** (`Y_top`) với độ nhòe lớn (`Gaussian Blur = 30px`).
    - Tại `f=5..8`: Hai dòng chữ **lao ngược chiều và đi xuyên qua nhau ở chính giữa tâm** (`"Modern"` bay từ dưới lên trên, `"Vibrant"` bay từ trên xuống dưới), tạo thành một đám sáng giao thoa Trắng - Xanh ở `f=6`.
    - Tại `f=10..16`: `"Modern"` đáp lên tầng trên, `"Vibrant"` đáp xuống tầng dưới và đồng thời lấy nét sắc cạnh (`Blur -> 0px`).
- **Cách làm trên Adobe Premiere Pro:**
  - Tách 2 Graphic Layers (`Layer 1: Modern`, `Layer 2: Vibrant`).
  - Trên `Layer 1 ("Modern" - Trắng)`: Keyframe `Position Y` từ `Y_top + 42px` (vị trí của dòng dưới) lên `Y_top` trong `14 frames` (Bezier Ease-In-Out) + `Gaussian Blur (32 -> 0)`.
  - Trên `Layer 2 ("Vibrant" - Xanh dương)`: Keyframe `Position Y` từ `Y_bottom - 42px` (vị trí của dòng trên) xuống `Y_bottom` trong cùng `14 frames` + `Gaussian Blur (32 -> 0)` + Blend Mode `Screen` ở lớp glow phụ.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - `y_modern = lerp(y_bot, y_top, ease_in_out_cubic(u))`
  - `y_vibrant = lerp(y_top, y_bot, ease_in_out_cubic(u))`
  - Cả 2 lớp cùng giảm `sigma = 16 * (1 - u)` và cộng hưởng lớp glow xanh dương khi giao nhau ở `u = 0.5`.

---

### 6. `Soft Motion` (Hàng 2, Cột 3)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 1 dòng chữ `"Soft Motion"` font Sans-Serif Medium màu trắng ấm (`#FFFDF9`), hiệu ứng tối giản thanh lịch.
  - `f=3..15`: Chữ xuất hiện mượt từ **Trái sang Phải** bằng một mặt nạ chuyển sắc cực mềm (`Soft Gradient Wipe`) kết hợp với độ nhòe giảm dần theo chiều ngang: khi đầu chữ `"Soft "` ở bên trái đã rõ nét (`Opacity 100%, Blur 0`), thì phần giữa `"Mo"` đang mờ sương (`Opacity 50%, Blur 18px`) và đuôi `"tion"` ở bên phải vẫn đang ẩn (`Opacity 0%`).
- **Cách làm trên Adobe Premiere Pro:**
  - Gắn `Linear Wipe`: `Wipe Angle = -90°` (quét từ trái sang phải), `Transition Completion: 100% -> 0%` trong `15 frames`, **`Feather = 45..60`** (feather thật rộng để mép quét êm như sương).
  - Kết hợp `Transform` (`Position X: -12px -> 0px`) và 1 lớp nhân đôi phía dưới có `Gaussian Blur = 25` + `Linear Wipe` đi trước lớp chính `3 frames` để tạo mép đầu phát sáng mờ (`Glowing Leading Edge`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Tạo mặt nạ gradient 1D dọc theo trục X: `mask_x(x, t) = clamp((u * (W + feather) - (x - x0)) / feather, 0, 1)`.
  - Trộn giữa bản chữ sắc nét `img_sharp` và bản chữ nhòe `img_blur`: tại vùng mép đang xuất hiện (`0 < mask_x < 1`), tỷ lệ `img_blur` cao hơn giúp chữ hiện ra như tan sương.

---

### 7. `Central Focus` (Hàng 3, Cột 1)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 2 dòng căn giữa: dòng trên `"Central"` cỡ vừa, dòng dưới `"Focus"` cỡ lớn (`1.8x`), đều dùng font Sans-Serif Bold màu trắng (`#FFFFFF`).
  - `f=3..6`: Chữ mọc theo từng ký tự (`Per-Character Scale & Opacity`) kèm ánh sáng bloom trắng mạnh: ở dòng trên chỉ mới thấy `"C e n t r"`, dòng dưới mới thấy các nét mảnh của `"F o c u"`.
  - `f=8..14`: Từng chữ cái nở đầy độ dày nét (`Scale: 60% -> 100%` tại tâm từng ký tự, `Blur: 18px -> 0px`) từ trái sang phải.
- **Cách làm trên Adobe Premiere Pro:**
  - Dùng Text Animator (MOGRT) hoặc tách ký tự với `Scale` từng chữ cái từ `40% -> 100%`, `Opacity: 0% -> 100%`, `Gaussian Blur: 20 -> 0`, `Range Selector: Start 0% -> 100%` trong `12 frames`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Duyệt từng cụm ký tự tiếng Việt NFC `i`: `u_i = clamp((t - i*0.03)/0.18, 0, 1)`, scale từng ký tự quanh tâm của chính nó `s_i = 0.45 + 0.55*ease_out_back(u_i)` kèm bloom trắng.

---

### 8. `Error` — `̶E̶r̶r̶o̶r̶` (Hàng 3, Cột 2)
- **Giải phẫu từng Frame (`f=0..28`):**
  - Chữ `"Error"` màu trắng (`#FFFFFF`), chính giữa thân chữ có **một thanh gạch ngang màu đỏ neon (`#FF1E27`)** đâm xuyên qua và tỏa ánh sáng đỏ hồng nhuộm lên các chữ cái trắng.
  - **Cơ chế 2 pha cực kỳ bắt mắt:**
    - **Pha 1 (`f=2..10`):** Chỉ có chữ `"Error"` màu trắng thuần khiết hiện ra từ mờ đến rõ (`Gaussian Blur: 28px -> 0px`, `Scale: 92% -> 100%`). Lúc này **chưa hề có thanh gạch ngang màu đỏ** và chưa có ánh đỏ!
    - **Pha 2 (`f=12..22`):** Khi chữ `"Error"` trắng đã đứng yên sắc nét, tại `f=12`, một thanh laser đỏ neon (`#FF1E27`, cao `6px`) bắt đầu **phóng ngang từ mép trái chữ `"E"` sang mép phải chữ `"r"`** (`Crop Right: 100% -> 0%` trong `10 frames`). Thanh đỏ phóng tới đâu, hào quang đỏ (`Red Linear Dodge Glow`) bừng sáng nhuộm đỏ thân chữ `"Error"` tới đó!
- **Cách làm trên Adobe Premiere Pro:**
  - `Layer 1 (Text "Error" Trắng)`: `f=0..10` chạy `Gaussian Blur (28 -> 0)` + `Opacity (0% -> 100%)`.
  - `Layer 2 (Red Strikethrough Bar)`: Tạo Rectangle Shape màu `#FF1E27` cao `6px`, rộng bằng chữ `"Error" + 16px`, đặt `Anchor Point` tại **mép trái** của thanh. Đặt điểm bắt đầu tại `f=11`: keyframe `Scale X` (bỏ chọn `Uniform Scale`) từ `0%` (`f=11`) -> `100%` (`f=21`, Ease Out Cubic).
  - `Layer 3 (Red Glow Duplicate)`: Nhân đôi `Layer 2`, gắn `Gaussian Blur = 35`, Blend Mode `Linear Dodge (Add)` để ánh sáng đỏ hắt trực tiếp lên các chữ cái trắng bên dưới.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Pha 1 (`t = 0.00..0.33s`): Render chữ `"Error"` trắng với `sigma = 14*(1 - clamp(t/0.30, 0, 1))`.
  - Pha 2 (`t = 0.36..0.72s`): Tính `u_bar = ease_out_cubic(clamp((t - 0.36)/0.32, 0, 1))`, vẽ thanh chữ nhật đỏ `#FF1E27` từ `x_left` tới `x_left + bar_w * u_bar` tại `y_mid`, nhân đôi thanh đỏ qua `cv2.GaussianBlur(sigma=18)` rồi cộng `Linear Dodge (Add)` (`cv2.add`) lên chữ trắng.

---

### 9. `Fresh Simple` (Hàng 3, Cột 3)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Bố cục 2 dòng lệch trục: dòng trên `"Fresh"` màu xanh lá tươi (`#68E359`, lệch trái), dòng dưới `"Simple"` màu trắng (`#FFFFFF`, lệch phải).
  - `f=3..8`: Chữ `"Fresh"` màu xanh lá mọc từ đường cắt đáy đi lên (`Bottom Mask Slide-Up`, `dy: +32px -> 0px`) sắc nét, ít blur.
  - `f=7..15`: Trễ hơn `4 frames`, chữ `"Simple"` màu trắng ở dòng dưới cũng mọc từ đường cắt đáy riêng của nó đi lên (`dy: +32px -> 0px`).
- **Cách làm trên Adobe Premiere Pro:**
  - 2 Graphic Layers (`Layer 1: Fresh`, `Layer 2: Simple` đặt trễ `4 frames`).
  - Mỗi layer dùng cặp `Transform` (đặt trên) + `Crop` (đặt dưới, cắt sát chân dòng chữ): keyframe `Transform > Position Y` từ `+36px -> 0px` trong `9 frames` (`Bezier Ease-Out`, `Shutter Angle = 180°`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Mỗi dòng được render trong một bounding box cố định `[y_top : y_baseline + 6]`; bên trong box đó chữ trượt từ `dy = +36` về `0` với `u1 = clamp(t/0.28, 0, 1)` và `u2 = clamp((t-0.13)/0.28, 0, 1)`.

---

### 10. `Wave` (Hàng 4, Cột 1)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 1 từ `"Wave"` font Sans-Serif Bold màu xanh cyan sáng (`#5CE1E6`).
  - `f=2..14`: Các chữ cái `"W - a - v - e"` trồi từ dưới đường mặt nạ ngang đi lên theo **đường lượn sóng hình Sin (Sine Wave Roll-Up)**: chữ `"W"` nhô lên trước (`f=3`), tiếp theo chữ `"a"` và `"v"` uốn cong nhô lên (`f=6`, thân chữ hơi uốn lượn như mặt nước nhờ `Wave Warp`), và chữ `"e"` nhô lên cuối cùng (`f=10`), trước khi cả từ phẳng lại ở `f=15`.
- **Cách làm trên Adobe Premiere Pro:**
  - Trên `Graphic Layer "Wave"`:
    1. Gắn `Transform` (`Position Y: +45px -> 0px` từ `f=0..14`).
    2. Gắn `Wave Warp` (`Wave Type: Sine`, `Wave Width: 120`, `Wave Direction: 90°`, keyframe `Wave Height` từ `18 -> 0` trong `15 frames` để chữ vừa trồi lên vừa uốn sóng rồi phẳng lại).
    3. Đặt `Crop` ở cuối cùng (`Bottom` cắt sát chân chữ).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Áp dụng biến dạng lưới 2D (`cv2.remap`) theo hàm sóng ngang tắt dần:
    `dy(x, t) = 38*(1 - u) + 14*(1 - u)*sin(2*pi*x/140 - 6*t)`
    rồi cắt phẳng theo đường `y > baseline_y + 6`.

---

### 11. `Fully Customizable` (Hàng 4, Cột 2)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Bố cục 3 tầng: góc trên-trái là `"Fully"` (cỡ nhỏ, màu trắng), chính giữa là `"CUSTOM"` (in hoa cỡ lớn, màu cam đỏ `#FF511A` phát sáng), góc dưới-phải là `"izable"` (cỡ nhỏ, màu trắng).
  - **Cơ chế đặc trưng: Đổi màu từ Đỏ Cam Sẫm sang Trắng (`Color Tint Lerp`) kết hợp Staggered Character Pop:**
    - `f=2..5`: Chữ `"Fully"` ở góc trên và `"izable"` ở góc dưới xuất hiện trước theo từng ký tự từ trái sang phải, nhưng **lúc mới hiện ra chúng có màu Đỏ Cam Sẫm (`#9E3814`)** chứ chưa phải màu trắng! Đồng thời ở tầng giữa, chữ `"CUSTOM"` mới chỉ hiện chữ `"C"` và `"U"` mờ.
    - `f=6..10`: Chữ `"Fully"` và `"izable"` chuyển dần màu từ Đỏ Cam Sẫm (`#9E3814`) sang Trắng sáng (`#FFFFFF`); đồng thời `"CUSTOM"` ở giữa bung tiếp các chữ `"S - T - O - M"` từ trái sang phải kèm hào quang cam.
- **Cách làm trên Adobe Premiere Pro:**
  - `Layer 1 ("Fully")` & `Layer 3 ("izable")`: Gắn `Linear Wipe (-90°, Feather 15)` trong `8 frames` + hiệu ứng `Tint` (keyframe `Map White To` từ màu Cam đất `#9E3814` tại `f=0` sang Trắng `#FFFFFF` tại `f=12`).
  - `Layer 2 ("CUSTOM")`: Gắn `Linear Wipe (-90°, Feather 25)` từ `f=3` đến `f=15` + lớp duplicate `Gaussian Blur = 30` (`Screen`) màu cam `#FF511A`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Với mỗi ký tự `i` của `"Fully"` và `"izable"`: `u_i = clamp((t - i*0.035)/0.22, 0, 1)`, nội suy màu RGB trực tiếp `color_i = lerp_rgb((158, 56, 20), (255, 255, 255), u_i)`.
  - Với `"CUSTOM"`: trượt mở từng ký tự kèm bloom cam `#FF511A`.

---

### 12. `Colorful Text` (Hàng 4, Cột 3)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 2 dòng căn giữa: `"Colorful"` ở trên, `"Text"` ở dưới. Mặt chữ chính màu trắng tinh (`#FFFFFF`), nhưng phía sau lưng chữ là một **đám mây hào quang đa sắc cầu vồng (Rainbow / Multi-Hue Aura: Đỏ - Vàng - Xanh lá - Tím)** xoay chuyển liên tục.
  - `f=3..12`: Đám mây cầu vồng bùng sáng trước (`Blur = 65px`), chữ trắng `"Colorful / Text"` trượt nhẹ từ dưới lên (`dy: +16px -> 0px`) và lấy nét (`Blur: 22px -> 0px`). Ngay cả sau khi chữ đã đứng yên (`f=15..45`), vầng hào quang cầu vồng phía sau vẫn liên tục đổi màu (`Hue Rotation`).
- **Cách làm trên Adobe Premiere Pro:**
  - `Layer 2 (Top - Sharp White Text)`: `"Colorful / Text"` màu trắng, `Transform (Position Y: +16px -> 0px)` + `Gaussian Blur (22 -> 0)`.
  - `Layer 1 (Bottom - Rainbow Aura)`: Tạo 4 chấm màu (Đỏ `#FF2A55`, Vàng `#FFD600`, Xanh lá `#00E676`, Tím `#AA00FF`) hoặc dùng `4-Color Gradient` đặt dưới chữ, dùng `Track Matte Key` theo Alpha của chữ (đã phóng to/dilate), gắn `Gaussian Blur = 75` và `Color Balance (HLS)` với keyframe `Hue: 0° -> 360°` xoay liên tục.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Tạo bản đồ góc màu `hue_map(x, y, t) = (atan2(y - cy, x - cx) + 2.5*t) % (2*pi)` chuyển sang RGB, nhân với alpha của chữ đã làm phồng (`cv2.dilate` + `cv2.GaussianBlur(sigma=32)`), trộn `Screen` phía dưới lớp chữ trắng sắc nét.

---

### 13. `VHS` (Hàng 5, Cột 1)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Chữ `"VHS"` in hoa cỡ lớn, phong cách băng từ Retro thập niên 90.
  - `f=2..8`: Chữ xuất hiện với hiệu ứng **Tách kênh màu RGB (Chromatic Aberration)** cực mạnh kèm nhòe ngang (`Horizontal Directional Blur = 35px`): kênh Đỏ (`Red`) lệch hẳn sang trái `-10px`, kênh Xanh dương/Cyan (`Blue/Cyan`) lệch hẳn sang phải `+10px`, ở giữa tạo thành lõi trắng ngà.
  - `f=10..18`: Độ nhòe ngang thu hẹp về `0`, nhưng chữ vẫn giữ **viền tách màu RGB cố định (`±3.5px`)** và độ rung nhẹ kiểu băng từ (`Scanline / Jitter`).
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo 3 Graphic Layers giống hệt nhau (`"VHS"`), tất cả đặt Blend Mode = **`Linear Dodge (Add)`** (hoặc `Screen`):
    - `Layer R`: Dùng `Channel Mixer` (chỉ giữ `Red = 100%`, `Green = 0`, `Blue = 0`), keyframe `Position X` từ `-14px -> -3.5px`.
    - `Layer G`: Chỉ giữ `Green = 100%`, `Position X = 0px`.
    - `Layer B`: Chỉ giữ `Blue = 100%`, keyframe `Position X` từ `+14px -> +3.5px`.
  - Gắn `Directional Blur` (`Direction = 90°` ngang, `Blur Length: 35 -> 1.5`) lên Adjustment Layer hoặc Nest chứa cả 3 kênh.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Render mask chữ trắng `M`, dịch kênh `B = shift_x(M, +dx)`, `G = M`, `R = shift_x(M, -dx)` với `dx = 14*(1 - u) + 3.5`, áp kernel blur ngang `cv2.blur(img, (k_x, 1))` với `k_x = int(35*(1 - u)) + 1`.

---

### 14. `Premium Text` (Hàng 5, Cột 2)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 2 dòng căn giữa: `"Premium"` ở trên, `"Text"` ở dưới, tô **Gradient Vàng Kim Loại sang trọng (Metallic Champagne Gold: `#FFF3B0 -> #E6B84D -> #9E6F12`)**.
  - **Cơ chế đặc trưng: Gom tụ Hạt Bokeh Vàng (Golden Bokeh Collapse / Morphological De-Blur):**
    - Tại `f=2..5`: Chữ không phải là một đám mờ phẳng thông thường, mà biến thành **5–6 quả cầu ánh sáng vàng tròn trịa (Golden Bokeh Orbs)** rực rỡ dính cạnh nhau!
    - Tại `f=6..12`: Các quả cầu bokeh vàng này thu nhỏ bán kính và gom tụ dần vào khung xương chữ cái (`"Premium / Text"`).
    - Tại `f=14..18`: Chữ vàng kim loại hiện rõ sắc cạnh cùng ánh kim loại lấp lánh.
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo Graphic Layer `"Premium / Text"` tô `Linear Gradient` vàng kim loại (`#FFF2A6` -> `#D4AF37`).
  - Чтобы tạo hiệu ứng quả cầu Bokeh ở `f=0..8`: Gắn **`Gaussian Blur` (`Blurriness: 60 -> 0`)** đặt **TRƯỚC** hiệu ứng **`Levels` (hoặc `Alpha Adjust` / `Brightness & Contrast`)** trên kênh Alpha: khi chữ bị làm mờ lớn (`Blur 60`) rồi dùng `Levels (Alpha Input White = 40 -> 255)` để khuếch đại và bo tròn ngưỡng Alpha, các nét chữ biến thành những đốm tròn Bokeh vàng đặc biệt, sau đó thu gọn về nét chữ thật khi `Blur -> 0`!
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Khi `u < 1`: Làm phồng mask chữ bằng `cv2.dilate` với kernel hình tròn `cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r))`, áp `cv2.GaussianBlur(sigma = 24*(1-u))`, rồi khuếch đại độ sáng HDR `gain = 1.0 + 1.8*(1-u)` trước khi nhân với texture gradient vàng kim `#FFF3B0 -> #D4AF37`.

---

### 15. `Subtitles` (Hàng 5, Cột 3)
- **Giải phẫu từng Frame (`f=0..24`):**
  - 1 từ `"Subtitles"` font Sans-Serif Bold màu trắng (`#FFFFFF`).
  - **Cơ chế đặc trưng: Chữ cái sau trượt tách ra từ lưng chữ cái trước (Overlapping Character Roll-Out / Telescoping Reveal):**
    - `f=2`: Chỉ có chữ `"S"` và chữ `"u"` đang nằm đè một nửa lên chữ `"S"`.
    - `f=4`: Hiện `"Sub"`, tiếp theo chữ `"t"` đang mọc đè ngay sát mép phải của chữ `"b"`.
    - `f=6`: Hiện `"Subti"`, chữ `"t"` thứ hai đang tách ra từ chữ `"i"`.
    - `f=8`: Hiện `"Subtitl"`, nhìn cực rõ chữ `"l"` và chữ `"e"` đang **đè chồng lên nhau (`l+e`)** ở đầu mũi bên phải!
    - `f=10..14`: Chữ `"e"` và `"s"` trượt hẳn sang phải về đúng vị trí kerning chuẩn, hoàn tất từ `"Subtitles"`.
- **Cách làm trên Adobe Premiere Pro:**
  - Dùng Text Animator (MOGRT từ After Effects) hoặc tách từng chữ cái thành layer riêng:
  - Với mỗi chữ cái thứ `i`: Đặt keyframe `Position X` từ **`x_target - 28px`** (tức là nằm đè lên vị trí của chữ cái `i-1` liền trước) trượt sang **`x_target`** trong `6 frames` (`Ease Out Cubic`), đồng thời `Opacity` tăng nhanh từ `0% -> 100%` chỉ trong `3 frames` đầu. Vì chữ `i` đã đạt `100% Opacity` khi vẫn còn đang trượt qua chữ `i-1`, mắt người xem sẽ thấy hiệu ứng các chữ cái "đẻ" ra từ chữ trước và chồng nhẹ lên nhau ở đầu mũi!
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Với mỗi cụm ký tự tiếng Việt NFC thứ `i` (`i = 0..N-1`) có tọa độ đích `x_i`:
    - `u_i = clamp((t - i * 0.04) / 0.16, 0, 1)`
    - `x_draw = x_i - 28 * (1.0 - ease_out_cubic(u_i))`
    - `alpha_i = clamp(u_i * 2.5, 0, 1)` (đạt `alpha = 1.0` ngay tại `u_i = 0.4` để tạo hiện tượng chồng chữ `l+e` ở đầu sóng chuyển động).

---

### 16. `Movement Fluid` (Hàng 6, Cột 1)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Dòng trên `"MOVEMENT"` in hoa toàn bộ, font Sans-Serif ExtraBold màu tím Lavender-Violet (`#9D5CFF`); dòng dưới `"fluid"` chữ thường cỡ nhỏ, màu trắng (`#FFFFFF`), tracking rộng (`+150`).
  - **Cơ chế đặc trưng: Dòng phụ gõ trước, dòng chính lao từ mép trái vào và dồn toa như lò xo (Accordion / Telescoping Spring):**
    - `f=0..4`: Dòng chính `"MOVEMENT"` **chưa xuất hiện**! Dòng nhỏ `"fluid"` ở bên dưới bắt đầu hiện từng chữ cái từ trái sang phải (`"f"` -> `"fl"` -> `"flu"`).
    - `f=6..12`: Khi dòng dưới hiện tới `"flui"`, dòng trên `"MOVEMENT"` mới bắt đầu lao từ mép trái vào: `"M"` -> `"MOV"` -> `"MOVEM"` (tại `f=12`, chữ `"E"` và `"M"` ở đầu mũi đang ép sát chồng lên nhau) -> `"MOVEMEN"` -> `"MOVEMENT"`.
- **Cách làm trên Adobe Premiere Pro:**
  - `Layer 1 ("fluid" - Trắng, dòng dưới)`: Chạy từ `f=0..12` với `Linear Wipe (-90°, Feather 5)`.
  - `Layer 2 ("MOVEMENT" - Tím, dòng trên)`: Bắt đầu trễ từ `f=5..20`. Dùng Text Animator `Position X = -75px -> 0px`, `Opacity = 0% -> 100%`, `Range Selector (Start 0% -> 100%, Shape: Ramp Up, Ease High: 70%)` kết hợp `Crop Left` tại mép khung chữ.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dòng 2 (`"fluid"`): `alpha_j = clamp((t - j*0.05)/0.08, 0, 1)`.
  - Dòng 1 (`"MOVEMENT"`): Bắt đầu tại `t = 0.16s`, với mỗi ký tự `i`: `u_i = clamp((t - 0.16 - i*0.045)/0.22, 0, 1)`, `x_draw = x_i - 75*(1 - ease_out_cubic(u_i))`, `alpha_i = clamp(u_i*3.0, 0, 1)`.

---

### 17. `Next Chapter` (Hàng 6, Cột 2)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Dòng trên `"Next"` cỡ nhỏ, màu trắng (`#FFFFFF`), đặt lệch về nửa phải; dòng dưới `"chapter"` cỡ lớn gấp `2.1x`, font Sans-Serif Bold màu xanh lá cây tươi (`#44C84A`).
  - **Cơ chế đặc trưng trên `"Next"`: Bỏ khuyết chữ cái giữa rồi mới điền vào (`Non-linear Letter Fill: N_t -> Nxt -> Next`):**
    - `f=2`: Ở dòng trên, chữ `"N"` (đầu) và chữ `"t"` (cuối) hiện ra trước (`"N  t"`), bỏ trống hoàn toàn khoảng giữa!
    - `f=5`: Chữ `"x"` hiện thêm vào, tạo thành **`"Nxt"`** (vẫn khuyết chữ `"e"`).
    - `f=8`: Chữ `"e"` cuối cùng mới bật sáng điền vào chỗ trống, hoàn chỉnh từ **`"Next"`**!
  - **Cơ chế trên `"chapter"` (Xanh lá):** Chạy hiệu ứng Overlapping Character Roll-Out từ trái sang phải (`"c"` -> `"cha"` -> `"chap"` -> `"chapte"` -> `"chapter"`).
- **Cách làm trên Adobe Premiere Pro:**
  - Trên dòng `"Next"`: Dùng Text Animator `Opacity (0% -> 100%)` với **`Randomize Order = On`** (thứ tự xuất hiện các ký tự: ký tự 1 & 4 -> ký tự 3 -> ký tự 2).
  - Trên dòng `"chapter"`: Dùng Overlapping Character Slide-Out (`Position X: -26px -> 0px`, `Opacity: 0% -> 100%` tuần tự từ trái sang phải).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dòng 1 (`"Next"`): Hoán vị thứ tự delay của các cụm ký tự NFC theo mảng `perm_order = [0, 3, 2, 1]` (2 biên hiện trước, ruột điền vào sau).
  - Dòng 2 (`"chapter"`): Duyệt tuần tự `i = 0..N-1` với `x_draw = x_i - 26*(1 - ease_out_cubic(u_i))`.

---

### 18. `New Creative Today` (Hàng 6, Cột 3)
- **Giải phẫu từng Frame (`f=0..24`):**
  - Bố cục 3 tầng: góc trên-trái `"New"` (trắng, nhỏ), chính giữa `"creative"` (xanh lá chanh `#80FF2B`, cỡ lớn), góc dưới-phải `"today."` (trắng, nhỏ, có dấu chấm câu).
  - **Cơ chế đặc trưng: Cả 3 tầng chữ cùng mọc đồng thời từ Trái sang Phải theo bậc thang nhô lên Baseline (`Per-Character Bottom-Anchored Scale + Baseline Step-Up`):**
    - `f=2`: Tầng trên hiện `"N"`, tầng giữa hiện `"c"`, tầng dưới hiện `"tod"` nhỏ (`Scale ~60%`).
    - `f=5`: Tầng trên hiện `"Ne"`, tầng giữa hiện `"crea"` (chữ `"a"` đang mờ và thấp hơn baseline), tầng dưới hiện `"toda y"` (chữ `"y"` ở cuối rất nhỏ và tụt thấp).
    - `f=8`: Tầng trên hoàn tất `"New"`, tầng dưới hoàn tất `"today."`, còn tầng giữa `"creativ e"` có các chữ cuối `"i - v - e"` tạo thành **đường bậc thang nhấp nhô từ dưới lên** (`chữ "v" thấp hơn và nhỏ hơn "i", chữ "e" thấp hơn và nhỏ hơn "v"`).
    - `f=12`: Các chữ cuối `"v - e"` nảy lên đúng baseline và đạt `Scale 100%`.
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo 3 Graphic Layers (`New`, `creative`, `today.`) bắt đầu cùng lúc tại `f=0`.
  - Trên cả 3 layers, gắn Text Animator theo từng ký tự từ Trái sang Phải: `Anchor Point` đặt ở đáy mỗi ký tự, `Scale: 0% -> 100%`, `Position Y: +14px -> 0px`, `Opacity: 0% -> 100%`, `Range Selector: Start 0% -> 100%` (`Shape: Ramp Up`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Với mỗi dòng và mỗi cụm ký tự NFC thứ `i`:
    - `u_i = clamp((t - i * 0.045) / 0.16, 0, 1)`
    - `scale_i = clamp(ease_out_back(u_i, 1.1), 0.05, 1.08)`
    - `dy_i = int(14 * (1.0 - min(1.0, u_i * 1.2)))`
    - Neo điểm phóng `scale_i` tại tâm đáy (`bottom-center`) của từng ký tự.

---

## Phần II. Bảng 2 — 17 Preset Tiếp Theo (`00:04.30` – `00:15.67`, Frames `129`–`470`)

### 19. `Simple Type / DYNAMIC FLOW` (Hàng 1, Cột 1)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 2 dòng: dòng trên `"Simple Type"` (Sans-Serif Regular màu trắng `#FFFFFF`), dòng dưới `"DYNAMIC FLOW"` (Sans-Serif Black Italic in hoa màu trắng `#FFFFFF`).
  - `f=129..139`: Cả hai dòng cùng mở từ **Trái sang Phải** bằng mặt nạ mờ mềm (`Soft Left-to-Right Wipe`), kèm một vệt sáng trắng (`Gaussian Blur = 25px`) đi ngay ở mép đầu mặt nạ đang quét. Dòng dưới chạy trễ hơn dòng trên `2 frames`.
- **Cách làm trên Adobe Premiere Pro:**
  - 2 Graphic Layers, mỗi layer gắn `Linear Wipe` (`Wipe Angle = -90°`, `Feather = 35`, `Completion: 100% -> 0%` trong `10 frames`) + `Transform` (`Position X: -14px -> 0px`) + lớp glow phụ ở mép wipe.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Quét mặt nạ gradient ngang `mask_x` từ trái sang phải trong `10 frames` (`0.33s`), dòng dưới trễ `67ms`, trộn thêm bloom trắng tại dải biên `0.15 < mask_x < 0.85`.

---

### 20. `Bright Silver` (Hàng 1, Cột 2)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"Bright"` (cỡ nhỏ, màu xám bạc `#C0C5CE`), dòng dưới `"Silver"` (cỡ lớn gấp `2.5x`, font Sans-Serif Black phủ **Gradient Bạc Kim Loại Sáng Loáng `#FFFFFF -> #9EA7B8 -> #E8ECF2`**).
  - `f=131..141`: Dòng nhỏ `"Bright"` mở từ trái sang phải trước (`f=131..136`). Dòng lớn `"Silver"` mở từng ký tự từ trái sang phải (`"S" -> "Si" -> "Silv" -> "Silver"`), mỗi ký tự vừa trượt nhẹ từ dưới lên (`dy: +12px -> 0px`) vừa có một luồng sáng trắng bạc (`Specular Sheen Highlight`) quét chéo qua bề mặt kim loại.
- **Cách làm trên Adobe Premiere Pro:**
  - Trên `"Silver"`: Tô `Linear Gradient` bạc kim loại, gắn `Linear Wipe (-90°, Feather 20)` + `Transform (Position Y: +12px -> 0px)` + hiệu ứng ánh kim `Lambert / Specular Highlight` (hoặc một thanh trắng nghiêng `45°` có `Gaussian Blur = 20`, đặt `Track Matte Key` vào chữ `"Silver"` với Blend Mode `Overlay`/`Add` quét ngang qua chữ từ `f=133..143`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Tô texture gradient bạc dọc + cộng thêm dải sáng chéo động `sheen(x, y, t) = exp(-((x + 0.5*y - v*t)^2) / (2*18^2))` nhân với alpha chữ `"Silver"`.

---

### 21. `New Creative today.` — Bố cục Chéo Có Chân Đế (Hàng 1, Cột 3)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Bố cục 3 phần: góc trên-trái `"New"` (trắng, nhỏ), giữa `"Creative"` (xanh lá neon `#39FF14`, kèm **1 thanh gạch dưới màu xanh lá** dưới chữ `"Cre"`), góc dưới-phải `"today."` (trắng, nhỏ).
  - `f=131..140`: Chữ `"New"` hiện trước (`f=131..134`), tiếp theo chữ `"Creative"` cùng thanh gạch dưới màu xanh lá bung từ trái sang phải (`f=132..138`), và `"today."` bung nối tiếp ở góc dưới phải (`f=134..140`).
- **Cách làm trên Adobe Premiere Pro:**
  - 3 Graphic Layers + 1 Shape Layer (thanh underline xanh lá dưới `"Cre"`).
  - Xếp lệch bậc thang trên Timeline (`Stagger = 2 frames`), mỗi layer dùng Per-Character Scale-Up (`Scale: 30% -> 100%`, `Position X: -18px -> 0px`) còn thanh underline dùng `Crop Right (100% -> 0%)`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Kết hợp Per-Grapheme Slide-Scale trên 3 tầng chữ với `underline_w = target_w * ease_out_cubic(u)` tại đáy chữ `"Cre"`.

---

### 22. `Create Freely` (Hàng 2, Cột 1)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 2 dòng căn giữa: `"Create"` ở trên, `"Freely"` ở dưới, font Geometric Sans-Serif Bold màu trắng (`#FFFFFF`).
  - **Cơ chế đặc trưng: Hai dòng cùng bung đàn hồi chữ cái từ Trái sang Phải kèm Đè Chữ Ở Đầu Mũi (`Dual-Line Telescoping Accordion`):**
    - `f=131`: Dòng trên hiện `"Cr"`, dòng dưới hiện `"Fr"`.
    - `f=133`: Dòng trên hiện `"Crea"`, dòng dưới hiện `"Free"`.
    - `f=135`: Tại đầu mũi bên phải, dòng trên có chữ `"t"` và `"e"` đang đè khít lên nhau (`"Creat+e"`), dòng dưới có chữ `"l"` và `"y"` đang đè khít lên nhau (`"Freel+y"`) kèm nhòe chuyển động ngang (`Horizontal Motion Blur`).
    - `f=139`: Cả hai dòng giãn hết cỡ về kerning chuẩn `"Create / Freely"`.
- **Cách làm trên Adobe Premiere Pro:**
  - 2 Graphic Layers chạy song song (dòng dưới trễ `1 frame`). Mỗi dòng dùng Text Animator: `Position X: -45px -> 0px`, `Opacity: 0% -> 100%` (đạt 100% sớm ở 40% quãng đường), `Range Selector: Start 0% -> 100%` trong `10 frames` + `Directional Blur (90°, Length: 12 -> 0)`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Áp dụng công thức Overlapping Character Roll-Out đồng thời cho cả 2 dòng với `offset_x = -45 * (1 - ease_out_cubic(u_i))` và `alpha_i = clamp(u_i * 2.8, 0, 1)`.

---

### 23. `Stay stunning` (Hàng 2, Cột 2)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 1 dòng kết hợp 2 màu (Dual-Tone Inline): từ `"Stay"` màu trắng (`#FFFFFF`), từ `"stunning"` màu hồng tím Magenta-Pink (`#FF44CC`) phát sáng nhẹ.
  - `f=131..141`: Mở tuần tự từ trái sang phải xuyên suốt cả câu: `"St"` (`f=131`) -> `"Stay"` (`f=133`, trắng) -> `"Stay st"` (`f=135`, bắt đầu chuyển sang hồng tím) -> `"Stay stunni"` (`f=137`, các chữ cuối `"n-i-n-g"` trượt tách từ lưng chữ trước) -> `"Stay stunning"` (`f=141`).
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo 1 dòng chữ có 2 vùng màu (`"Stay "` trắng, `"stunning"` hồng `#FF44CC`), áp dụng Per-Character Horizontal Slide-Out (`Position X: -30px -> 0px`, `Opacity: 0% -> 100%`) chạy liền mạch từ ký tự đầu đến ký tự cuối trong `12 frames`, kèm lớp duplicate `Gaussian Blur = 25` (`Screen`) chỉ cắt riêng cho phần chữ màu hồng `"stunning"`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Duyệt chuỗi NFC liền mạch qua cả 2 từ, đổi bảng màu tại ranh giới từ thứ 2 (`color = WHITE if idx < 5 else MAGENTA_PINK`) và cộng lớp bloom hồng cho phần `"stunning"`.

---

### 24. `Made Simple` (Hàng 2, Cột 3)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"Made"` (cỡ nhỏ, màu trắng `#FFFFFF`), dòng dưới `"Simple"` (cỡ lớn gấp `2.2x`, font Sans-Serif Bold màu cam vàng ấm `#FF8C24`).
  - `f=131..141`: Cả hai dòng cùng chạy cơ chế Overlapping Character Roll-Out từ trái sang phải: ở `f=131` hiện `"Ma"` và `"Si"`; ở `f=133` hiện `"Made"` (chữ `"d"` và `"e"` đang tách nhau) và `"Simp"` (chữ `"m"` và `"p"` đang chồng nhẹ ở mép phải); ở `f=137` chữ `"l"` và `"e"` của `"Simple"` tách ra hoàn tất.
- **Cách làm trên Adobe Premiere Pro:**
  - 2 Graphic Layers (`Made` hoàn tất trong `7 frames`, `Simple` hoàn tất trong `11 frames`), dùng cùng bộ Text Animator `Position X: -35px -> 0px` + `Opacity: 0% -> 100%` + hào quang cam ấm dưới chữ `"Simple"`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dùng Overlapping Character Roll-Out với `dx_start = -24px` cho dòng nhỏ `"Made"` và `dx_start = -42px` cho dòng lớn `"Simple"`.

---

### 25. `Clean style / TEXT MOTION` (Hàng 3, Cột 1)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"Clean style"` (font Sans-Serif Bold cỡ lớn màu trắng `#FFFFFF`), dòng dưới `"TEXT MOTION"` (in hoa cỡ rất nhỏ, tracking cực rộng `+400`, màu xám trắng).
  - **Cơ chế đặc trưng: Hai đầu chữ cái xuất hiện trước và ép vào trong, sau đó các chữ cái ở giữa bung ra đẩy hai đầu về đúng vị trí (`Center-Gap / Boundary-Inward Interleaved Unfold`):**
    - `f=131`: Chưa hiện theo thứ tự trái-phải thông thường, mà hiện cụm đầu **`"Cle"`** và cụm đuôi **`"yle"`** nằm xích lại gần nhau, bỏ khuyết phần giữa `"an st"`!
    - `f=133`: Các chữ ở giữa bắt đầu mọc chen vào khe hở (`"Clean tyle"`), đẩy cụm `"yle"` dịch dần sang phải.
    - `f=135..139`: Chữ `"s"` và `"t"` bung nốt ở tâm, hoàn chỉnh `"Clean style"`; đồng thời dòng nhỏ `"TEXT MOTION"` ở dưới trượt nhẹ từ dưới lên (`dy: +10px -> 0px`, `Opacity: 0% -> 100%`).
- **Cách làm trên Adobe Premiere Pro:**
  - Chia dòng `"Clean style"` thành các nhóm ký tự ngoài biên (`"Cle"`, `"yle"`) và nhóm ký tự tâm (`"an st"`):
    - Nhóm biên xuất hiện ngay ở `f=0..3` tại vị trí dịch về phía tâm (`"Cle"` dịch phải `+18px`, `"yle"` dịch trái `-18px`).
    - Từ `f=3..10`, nhóm tâm `"an st"` bung `Scale: 0% -> 100%` & `Opacity: 0% -> 100%`, đồng thời nhóm biên trượt trả về `0px` (`Ease Out Cubic`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Với mỗi ký tự `i` có khoảng cách chuẩn hóa tới tâm từ `d_i = (i - (N-1)/2) / ((N-1)/2)` (`d_i in [-1, 1]`):
    - Các ký tự ở biên (`|d_i|` lớn) có `delay_i = (1 - |d_i|) * 0.14s` (hiện ra trước) và lúc đầu bị kéo xích về tâm `x_draw = x_i - sign(d_i) * 22 * (1 - ease_out_cubic(u_center))`.
    - Các ký tự ở tâm (`|d_i|` nhỏ) hiện ra sau và đẩy toàn bộ hàng chữ giãn ra chiều rộng chuẩn.

---

### 26. `Speed Up` (Hàng 3, Cột 2)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 1 dòng chữ `"Speed Up"` font Sans-Serif Bold Italic (nghiêng tốc độ cao) màu xanh lá mạ điện quang (`#66FF33`) có hào quang xanh lá.
  - `f=131..138`: Toàn bộ cụm chữ hoặc từng cụm ký tự **phóng vút từ trái sang phải ở tốc độ rất cao (`High-Velocity Whip Slide`)** kèm vệt nhòe ngang dài (`Directional Blur 90° = 45px`), hãm phanh gấp ở tâm với một nhịp nảy nhẹ (`Elastic Overshoot +6px -> 0px`).
- **Cách làm trên Adobe Premiere Pro:**
  - Gắn `Transform` (`Position X: -140px -> +6px -> 0px` chỉ trong `8 frames`, `Skew = -12° -> 0°`, `Shutter Angle = 360°`) + `Directional Blur` (`Direction = 90°`, `Blur Length: 40 -> 0`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dùng `ease_out_back(u, overshoot=1.15)` trên `dx = -140 * (1 - eased)`, kết hợp biến dạng nghiêng động `shear_x = -0.22 * (1 - u)` và kernel motion blur ngang tỷ lệ với vận tốc tức thời.

---

### 27. `Edit Customize Presets` (Hàng 3, Cột 3)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Bố cục 3 dòng căn giữa có phân cấp rõ rệt:
    1. Dòng 1: `"Edit"` (cỡ nhỏ, màu trắng `#FFFFFF`).
    2. Dòng 2: `"Customize"` (cỡ lớn gấp `2.2x`, font Sans-Serif ExtraBold màu hồng phấn `#FF77A9`).
    3. Dòng 3: `"Presets"` (cỡ nhỏ, màu trắng `#FFFFFF`).
  - `f=131..141`: Cả 3 dòng cùng chạy hiệu ứng Overlapping Character Roll-Out từ trái sang phải đồng thời: tại `f=133`, dòng 1 đã hiện xong `"Edit"`, dòng 2 hiện `"Custo"` (chữ `"t"` và `"o"` đang chồng lên nhau ở mép phải), dòng 3 hiện `"Prese"` (chữ `"s"` và `"e"` đang chồng nhau). Tại `f=139`, dòng 2 hoàn tất `"Customize"` và dòng 3 hoàn tất `"Presets"`.
- **Cách làm trên Adobe Premiere Pro:**
  - Tạo 3 Graphic Layers (`Edit`, `Customize`, `Presets`), cả 3 bắt đầu cùng lúc tại `f=0` với bộ Text Animator Overlapping Character Slide (`Position X: -32px -> 0px`, `Opacity: 0% -> 100%`). Do `"Edit"` ngắn nhất nên kết thúc trước, tạo nhịp điệu 3 tầng tự nhiên.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Chạy song song 3 bộ `OverlappingCharacterRollOut` trên 3 dòng với cùng tốc độ `0.038s/ký tự`.

---

### 28. `Text Spotlight` (Hàng 4, Cột 1)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 2 dòng căn giữa: `"Text"` ở trên, `"Spotlight"` ở dưới, font Sans-Serif Bold màu trắng (`#FFFFFF`) đặt trên một vầng sáng trắng mờ ở tâm (`Radial Spotlight Glow`).
  - `f=131..141`: Chạy hiệu ứng Overlapping Character Roll-Out trên cả 2 dòng, nhìn rõ nhất ở từ `"Spotlight"`: tại `f=133` hiện `"Spotl"`, tại `f=135` hiện `"Spotlig"` với chữ `"g"` và `"h"` đang chồng khít lên nhau (`g+h`) và tỏa sáng mạnh như đèn rọi chiếu qua từng chữ cái đang tách ra.
- **Cách làm trên Adobe Premiere Pro:**
  - 2 Graphic Layers dùng Overlapping Character Slide (`Position X: -30px -> 0px`, `Opacity: 0% -> 100%`) + 1 lớp `Gaussian Blur = 40` (`Screen`) đi kèm theo đúng vị trí chữ cái đầu mũi đang bung ra để tạo hiệu ứng đèn rọi (`Moving Spotlight Head`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Tại mỗi thời điểm `t`, xác định vị trí ngang của ký tự đang bung `x_head(t)` và cộng một đốm sáng Gaussian trắng (`sigma = 45px`) tập trung ngay tại `(x_head(t), cy)`.

---

### 29. `Energy Rising` (Hàng 4, Cột 2)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"ENERGY"` (in hoa cỡ nhỏ, tracking rộng `+250`, màu trắng `#FFFFFF`); dòng dưới `"rising"` (chữ thường cỡ cực lớn, font Sans-Serif Black).
  - **Thiết kế màu sắc đặc trưng của `"rising"`:** Thân chữ `"rising"` không tô màu phẳng mà được phủ một **Gradient Dọc từ Cam Rực ở đỉnh chữ xuống Đen Sẫm ở đáy chữ (`Vertical Flame/Horizon Gradient: #FF9A00 -> #CC3300 -> #1A0600`)**, khiến phần chân chữ hòa lẫn vào nền tối còn phần đỉnh chữ rực sáng như mặt trời mọc!
  - `f=131..141`: Dòng `"ENERGY"` mở từ trái sang phải; đồng thời từng chữ cái của `"rising"` (`"r - i - s - i - n - g"`) vừa trượt mở từ trái sang phải vừa **trồi từ dưới bóng tối đi lên (`dy: +16px -> 0px`)**, đón ánh sáng cam ở nửa trên thân chữ.
- **Cách làm trên Adobe Premiere Pro:**
  - Trên `Graphic Layer "rising"`: Trong `Essential Graphics > Fill`, chọn **`Linear Gradient`** góc `90°` (dọc): điểm đầu (đỉnh chữ) màu Cam vàng `#FF9A00`, điểm giữa màu Đỏ cam `#D93800`, điểm cuối (chân chữ) màu Nâu đen `#140500` (hoặc dùng `Ramp` effect với `Track Matte Key`).
  - Gắn Text Animator theo từng ký tự: `Position Y: +18px -> 0px`, `Position X: -22px -> 0px`, `Opacity: 0% -> 100%` từ trái sang phải.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Tạo mảng gradient dọc `grad_y` có màu từ `(255, 154, 0)` ở `y_top` xuống `(20, 5, 0)` ở `y_bottom`; khi từng ký tự `i` của `"rising"` trồi từ `dy = +18*(1-u_i)` lên `0`, nhân mask ký tự với `grad_y` cố định trong không gian màn hình để chữ trồi lên tới đâu thì đỉnh chữ bắt sáng cam tới đó!

---

### 30. `Dynamic Rotating` (Hàng 4, Cột 3)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 2 dòng căn giữa: `"Dynamic"` ở trên, `"Rotating"` ở dưới, font Sans-Serif Bold màu trắng (`#FFFFFF`).
  - **Cơ chế đặc trưng: Lật chữ 3D quanh trục dọc Y từng ký tự (`Per-Character 3D Y-Axis Swivel / Flip`):**
    - `f=131`: Các chữ cái đầu `"Dyn"` và `"Rot"` đang xoay lật từ góc nghiêng 3D (`Swivel Y = -90°`, lúc này bề ngang chữ mỏng dẹt như lưỡi dao) về mặt phẳng chính diện (`0°`).
    - `f=133`: Hiện `"Dynam"` và `"Rotat"`, trong đó chữ `"m"` và chữ `"t"` ở đầu mũi đang ở góc xoay `~45°` (bề ngang hẹp chỉ bằng 50% bình thường).
    - `f=137..141`: Các chữ cuối `"i - c"` và `"i - n - g"` xoay lật nốt về `0°`, hoàn tất cả 2 dòng.
- **Cách làm trên Adobe Premiere Pro:**
  - Nếu làm từng ký tự hoặc cụm ký tự trên Premiere: Gắn hiệu ứng **`Basic 3D`**, keyframe **`Swivel`** từ **`-90° -> 0°`** trong `8 frames` (hoặc dùng `Transform` bỏ chọn `Uniform Scale`, keyframe **`Scale Width (Scale X): 0% -> 100%`** kèm `Position X: -15px -> 0px` để giả lập hoàn hảo phép chiếu xoay trục Y 3D!).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Với mỗi cụm ký tự NFC thứ `i`:
    - `u_i = clamp((t - i * 0.04) / 0.18, 0, 1)`
    - Góc xoay 3D quanh trục Y: `theta_i = (1.0 - ease_out_cubic(u_i)) * (pi / 2)`
    - Phép chiếu trực giao / phối cảnh lên trục X: **`scale_x = max(0.04, cos(theta_i))`**, **`dx = -18 * sin(theta_i)`**, **`alpha_i = clamp(u_i * 2.0, 0, 1)`**.

---

### 31. `Future Digital` (Hàng 5, Cột 1)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"FUTURE"` (in hoa cỡ nhỏ, tracking rộng `+250`, màu trắng `#FFFFFF`); dòng dưới `"Digital"` (cỡ lớn gấp `2.3x`, font Sans-Serif Black).
  - **Thiết kế màu sắc đặc trưng của `"Digital"`:** Giống kỹ thuật của mẫu `#29 Energy Rising` nhưng đổi sang tông **Xanh Lam Điện Tử (`Vertical Cyber-Blue Gradient: #4DA6FF ở đỉnh chữ -> #0044CC ở giữa -> #050C1A đen xanh ở chân chữ`)** kèm ánh sáng xanh dương lan tỏa ở đỉnh chữ.
  - `f=131..141`: `"FUTURE"` mở từ trái sang phải ở trên; ở dưới từng chữ cái của `"Digital"` (`"D - i - g - i - t - a - l"`) trượt mở từ trái sang phải và trồi nhẹ từ vùng tối dưới đáy lên vùng sáng xanh lam ở đỉnh.
- **Cách làm trên Adobe Premiere Pro:**
  - Tô `Linear Gradient` dọc (`90°`) cho `"Digital"` từ Xanh băng `#4DA6FF` (đỉnh) xuống Đen xanh `#050C1A` (đáy), kết hợp Per-Character Slide & Rise (`Position X: -24px -> 0px`, `Position Y: +14px -> 0px`, `Opacity: 0% -> 100%`) + lớp glow xanh dương ở nửa trên chữ.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Áp dụng shader `VerticalGradientRise` giống mẫu `#29` với bảng màu Cyber-Blue `(77, 166, 255) -> (0, 68, 204) -> (5, 12, 26)`.

---

### 32. `MONEY $100` — Kèm Lớp Chữ Chìm `$$$$` Phía Sau (Hàng 5, Cột 2)
- **Giải phẫu từng Frame (`f=129..145`):**
  - **Cấu trúc 2 lớp chiều sâu (Foreground + Background Watermark):**
    1. **Lớp tiền cảnh (Foreground):** Dòng trên `"MONEY"` (trắng `#FFFFFF`), dòng dưới `"$100"` (vàng kim `#FFD700` rực sáng).
    2. **Lớp hậu cảnh chìm (Background Watermark):** Phía sau lưng chữ `"MONEY / $100"` có một dãy ký hiệu đô-la khổng lồ **`"$$$$"`** màu vàng xanh mờ (`Opacity ~ 14%`, cỡ chữ cao bằng cả 2 dòng cộng lại).
  - `f=131..141`: Cả lớp chữ tiền cảnh (`"MONEY / $100"`) lẫn lớp watermark `"$$$$"` phía sau cùng mở từ **Trái sang Phải** bằng mặt nạ mờ mềm (`Soft Linear Wipe + Gaussian Blur Leading Edge`), trong đó con số `"$100"` phát sáng vàng kim mạnh khi quét qua.
- **Cách làm trên Adobe Premiere Pro:**
  - `Layer 1 (Background Watermark "$$$$")`: Font Sans-Serif Black cỡ cực lớn (`Scale ~ 220%`), màu vàng `#FFD700`, **`Opacity = 14%`**, gắn `Linear Wipe (-90°, Feather 40)`.
  - `Layer 2 ("MONEY" - Trắng)` & `Layer 3 ("$100" - Vàng kim #FFD700 + Glow)`: Gắn cùng bộ `Linear Wipe (-90°, Feather 35)` đồng bộ với lớp watermark phía sau + `Transform (Position X: -16px -> 0px)`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Render lớp watermark `"$$$$"` ở `alpha = 0.14` phía dưới, lớp `"MONEY"` (trắng) và `"$100"` (vàng `#FFD700` + bloom vàng) ở phía trên, rồi áp cùng một mặt nạ quét ngang `mask_x(x, t)` có mép đầu làm mờ nhẹ.

---

### 33. `fresh / MINT` (Hàng 5, Cột 3)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"fresh"` (chữ thường cỡ lớn, font Geometric Sans-Serif Bold màu trắng `#FFFFFF`), dòng dưới `"MINT"` (in hoa cỡ nhỏ, tracking rộng `+250`, màu xanh bạc hà `#4CE6A6`).
  - **Cơ chế đặc trưng trên `"fresh"`: Hai chữ cái ngoài biên (`f` và `h`) xuất hiện trước, chữ cái giữa (`r, e, s`) mọc điền vào tâm và đẩy hai biên giãn ra (`Boundary-First Center Expansion: f_h -> frsh -> fresh`):**
    - `f=131`: Chỉ thấy chữ **`"f"`** (đầu) và chữ **`"h"`** (cuối) đứng gần nhau, cùng một nét mờ ở giữa!
    - `f=133`: Chữ `"r"` và `"s"` hiện rõ thêm vào giữa, tạo thành **`"frsh"`** (chữ `"e"` ở chính giữa tâm mới chỉ là một chấm nhỏ mờ).
    - `f=135..139`: Chữ **`"e"`** ở chính giữa bung to ra 100%, đẩy `"fr"` sang trái và `"sh"` sang phải về đúng chữ **`"fresh"`**; đồng thời dòng dưới `"MINT"` màu xanh bạc hà bung hoàn tất.
- **Cách làm trên Adobe Premiere Pro:**
  - Tách 5 chữ cái `"f"`, `"r"`, `"e"`, `"s"`, `"h"`:
    - `"f"` và `"h"` hiện ngay từ `f=0..3` ở vị trí dịch vào tâm (`"f"` tại `+16px`, `"h"` tại `-16px`), sau đó trượt về `0px` tại `f=10`.
    - `"r"` và `"s"` hiện từ `f=2..7` (`Scale: 0% -> 100%`, dịch nhẹ từ tâm ra).
    - `"e"` (ký tự tâm) hiện từ `f=4..10` (`Scale: 0% -> 100%`, `Opacity: 0% -> 100%`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dùng thuật toán **Boundary-Inward Interleaved Unfold** (cùng họ với mẫu `#25 Clean style`): xếp hạng thứ tự xuất hiện theo khoảng cách từ biên vào tâm (`rank = min(i, N - 1 - i)`), đồng thời cộng độ dịch co cụm về tâm `dx_i = -sign(i - mid) * 18 * (1 - ease_out_cubic(u_center))`.

---

### 34. `THE / ESSENTIAL` (Hàng 6, Cột 1)
- **Giải phẫu từng Frame (`f=129..145`):**
  - Dòng trên `"THE"` (in hoa cỡ nhỏ, màu trắng `#FFFFFF`, căn giữa), dòng dưới `"ESSENTIAL"` (in hoa cỡ lớn, font Sans-Serif ExtraBold màu xanh lá ngọc `#2EE68A`).
  - `f=131..141`: Chữ `"THE"` ở trên hiện rõ rất nhanh ngay từ `f=131..133`. Ở dòng dưới, `"ESSENTIAL"` chạy cơ chế Overlapping Character Roll-Out từ trái sang phải: `"ES"` (`f=131`) -> `"ESSEN"` (`f=133`, chữ `"E"` và `"N"` chồng nhau ở đầu mũi) -> `"ESSENTI"` (`f=135`, chữ `"T"` và `"I"` chồng nhau) -> `"ESSENTIAL"` (`f=139`).
- **Cách làm trên Adobe Premiere Pro:**
  - `Layer 1 ("THE")`: Fade & Pop nhanh trong `5 frames` đầu.
  - `Layer 2 ("ESSENTIAL")`: Dùng Text Animator Overlapping Character Slide (`Position X: -38px -> 0px`, `Opacity: 0% -> 100%`, `Range Selector: Start 0% -> 100%` trong `12 frames`) kèm hào quang xanh ngọc `#2EE68A`.
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Dòng 1 (`"THE"`): `u_top = clamp(t/0.15, 0, 1)`.
  - Dòng 2 (`"ESSENTIAL"`): Overlapping Character Roll-Out với `dx_start = -38px` và `stagger = 0.032s/ký tự`.

---

### 35. `Instant / upgrades` (Hàng 6, Cột 2)
- **Giải phẫu từng Frame (`f=129..145`):**
  - 2 dòng chữ: dòng trên `"Instant"` (cỡ vừa), dòng dưới `"upgrades"` (cỡ lớn hơn `1.35x`), cả hai đều dùng font Sans-Serif Bold màu **Xanh Dương Điện Quang (`#2979FF`)** có hào quang xanh dương dịu.
  - **Cơ chế đặc trưng: Dòng dưới xuất phát sớm hơn dòng trên 2 frames, cả 2 dòng cùng chạy Overlapping Character Roll-Out (`Bottom-Lead Dual Telescoping Slide`):**
    - `f=131`: Dòng dưới đã hiện `"upga"` (chữ `"g"` và `"a"` đang chồng nhau), trong khi dòng trên mới chỉ nhú chữ `"I"` mờ!
    - `f=133`: Dòng trên hiện `"Inst"` (chữ `"s"` và `"t"` đang chồng nhau ở mép phải), dòng dưới đã hiện gần xong `"upgrades"`.
    - `f=137..141`: Dòng trên bung nốt `"a - n - t"` hoàn tất `"Instant / upgrades"`.
- **Cách làm trên Adobe Premiere Pro:**
  - 2 Graphic Layers màu `#2979FF` + lớp duplicate `Gaussian Blur = 28` (`Screen`).
  - Đặt `Layer 2 ("upgrades" - Dòng dưới)` bắt đầu tại `f=0`, còn `Layer 1 ("Instant" - Dòng trên)` bắt đầu trễ hơn tại `f=2`. Cả hai dùng cùng bộ Text Animator Overlapping Character Slide (`Position X: -32px -> 0px`, `Opacity: 0% -> 100%`).
- **Cách làm trên FilmCraft (`.fcproj` v17 & Python Engine):**
  - Chạy `OverlappingCharacterRollOut` cho dòng dưới từ `t = 0.00s` và cho dòng trên từ `t = 0.07s` với màu `#2979FF` kèm lớp bloom xanh dương.

---

## Phần III. Tổng Hợp 10 Họ Cơ Chế Chuyển Động Cốt Lõi (Premiere Pro ↔ FilmCraft Engine)

Toàn bộ 35 Preset trên được tổng quát hóa thành **10 Họ Kỹ Thuật (Mechanical Families)** để gọi trực tiếp trong `pro-filmcraft-director`:

| Mã Họ | Tên Kỹ Thuật | Các Preset Đại Diện | Công Thức Premiere Pro | Công Thức FilmCraft (`.fcproj` & Python) |
| :--- | :--- | :--- | :--- | :--- |
| **`FAM_01`** | **Staggered Slide + De-Blur & Invisible Baseline Mask** | `#1 Minimal Style`, `#3 Clear Green`, `#9 Fresh Simple`, `#10 Wave` | `Transform (Position Y: +35px -> 0, Shutter 180°)` đặt **trên** `Crop (Bottom)` + `Gaussian Blur (28 -> 0)` (+ `Wave Warp` cho `#10`). | Dịch `dy = +35*(1-ease_out_cubic(u))`, áp `GaussianBlur`, cắt mặt nạ phẳng `canvas[baseline_y+6:, :] = 0`. |
| **`FAM_02`** | **Diagonal Rotation Whip + HDR Glow Decay** | `#2 Orange`, `#26 Speed Up` | `Transform (Scale 150%->96%->100%, Rotation -20°->0° hoặc Skew -12°->0°, Shutter 270°-360°)` + lớp `Screen` Blur 35. | `cv2.getRotationMatrix2D` với `ease_out_back(u)` + lớp bloom HDR `Screen`. |
| **`FAM_03`** | **Center-Out Dual Cursor Bars + Mask Expand** | `#4 Text Focused \| text focused \|` | 2 Shape Bars trượt từ `Center_X` ra 2 biên `±(W/2 + 20px)` đồng bộ với `Crop Left/Right (50% -> 0%)`. | Mở mặt nạ `[cx - half_w(t) : cx + half_w(t)]`, vẽ 2 thanh cursor neon kèm chấm tròn tại đúng `cx ± half_w(t)`. |
| **`FAM_04`** | **Vertical Pass-Through Crossover** | `#5 Modern Vibrant` | Dòng trên xuất phát từ `Y_bot -> Y_top`, dòng dưới xuất phát từ `Y_top -> Y_bot`, đi xuyên qua nhau ở `f=6` kèm `Gaussian Blur (32 -> 0)`. | Nội suy chéo `y1 = lerp(y_bot, y_top, u)`, `y2 = lerp(y_top, y_bot, u)` với `ease_in_out_cubic(u)` và cộng hưởng glow tại tâm. |
| **`FAM_05`** | **Soft Gradient Wipe + Glowing Leading Edge (& Watermark)** | `#6 Soft Motion`, `#19 Simple Type`, `#20 Bright Silver`, `#32 Money $100` | `Linear Wipe (-90°, Feather 35..50)` + lớp blur đi trước `3 frames` ở mép wipe (+ lớp nền `"$$$$"` `Opacity 14%` cho `#32`). | Mặt nạ chuyển sắc ngang `mask_x(x, t)` trộn giữa `img_sharp` và `img_blur` tại dải biên `0 < mask_x < 1`. |
| **`FAM_06`** | **Overlapping Character Roll-Out (Telescoping Accordion)** | `#15 Subtitles`, `#16 Movement Fluid`, `#22 Create Freely`, `#23 Stay stunning`, `#24 Made Simple`, `#27 Edit Customize`, `#28 Text Spotlight`, `#34 THE ESSENTIAL`, `#35 Instant upgrades` | Mỗi chữ cái `i` trượt từ `x_i - 32px` (đè lên chữ `i-1`) về `x_i` trong `6 frames`, nhưng `Opacity` đạt `100%` ngay ở `frame 2..3` để thấy rõ 2 chữ cái chồng lên nhau ở đầu mũi (`l+e`, `t+o`, `g+h`). | Với mỗi cụm ký tự NFC `i`: `u_i = clamp((t - i*0.04)/0.16, 0, 1)`, `x_draw = x_i - 32*(1 - ease_out_cubic(u_i))`, `alpha_i = clamp(u_i * 2.6, 0, 1)`. |
| **`FAM_07`** | **Boundary-First / Non-Linear Interleaved Unfold** | `#17 Next Chapter (N_t -> Nxt -> Next)`, `#25 Clean style`, `#33 fresh (f_h -> frsh -> fresh)` | Các chữ cái ở 2 đầu biên (`N..t`, `Cle..yle`, `f..h`) hiện ra trước và đứng xích vào tâm (`±18px`), sau đó các chữ cái ở ruột bung ra đẩy 2 đầu giãn về đúng vị trí. | Xếp thứ tự delay theo khoảng cách từ biên vào tâm `rank = min(i, N-1-i)` kết hợp độ dịch co cụm về tâm `dx_i = -sign(i-mid)*18*(1 - u_center)`. |
| **`FAM_08`** | **Per-Character Bottom-Anchored Step-Up & Color Lerp** | `#7 Central Focus`, `#11 Fully Customizable`, `#18 New Creative Today`, `#21 New Creative (Underline)` | Mỗi chữ cái phóng `Scale: 0% -> 100%` từ đáy ký tự kèm `Position Y: +14px -> 0px` tạo bậc thang nhấp nhô (`#18`), hoặc đổi màu `Tint` từ Cam đất `#9E3814 -> #FFFFFF` (`#11`). | Neo `scale_i` tại `bottom-center`, `dy_i = 14*(1 - u_i)`, và `lerp_rgb(start_rgb, end_rgb, u_i)`. |
| **`FAM_09`** | **Delayed Neon Strikethrough / VHS RGB Split / Golden Bokeh Collapse / Rainbow Cloud** | `#8 Error`, `#12 Colorful Text`, `#13 VHS`, `#14 Premium Text` | `#8`: Chữ trắng hiện xong (`f=0..10`) rồi thanh đỏ `#FF1E27` mới phóng ngang `Scale X: 0->100%` (`f=12..22`) + `Linear Dodge` đỏ. `#13`: Tách 3 kênh R/G/B `±14px -> ±3.5px`. `#14`: `Blur 60` + `Alpha Levels` gom hạt Bokeh vàng. | `#8`: 2 pha tách biệt (White Text -> Red Laser Bar + Add Glow). `#13`: Dịch kênh R/B + horizontal blur. `#14`: Morphological dilation + HDR golden bokeh collapse. |
| **`FAM_10`** | **3D Y-Axis Character Swivel & Vertical Horizon Gradient Rise** | `#29 Energy Rising`, `#30 Dynamic Rotating`, `#31 Future Digital` | `#30`: `Basic 3D > Swivel (-90° -> 0°)` (hoặc `Scale X: 0% -> 100%`) từng chữ cái. `#29 & #31`: Tô `Linear Gradient 90°` (Cam/Xanh ở đỉnh -> Đen ở đáy) + chữ trồi từ bóng tối lên ánh sáng. | `#30`: `scale_x = cos(theta_i)`, `dx = -18*sin(theta_i)`. `#29 & #31`: Nhân mask chữ đang trồi lên (`dy: +18 -> 0`) với trường gradient dọc cố định. |
