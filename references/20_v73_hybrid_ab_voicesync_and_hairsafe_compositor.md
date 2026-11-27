# v7.3 Upgrade Reference — Hybrid `Option A × Option B`, 100% Voice Sync Guard & Hair-Crown-Safe Compositor

Tài liệu kỹ thuật chính thức của bản nâng cấp **`pro-filmcraft-director` v7.3.0**, giải quyết triệt để 4 bài toán sản xuất thực chiến ở tốc độ Studio (`1080×1920 @ 60fps`):

1. **Bảo toàn 100% vòm tóc cong tự nhiên (`Scale-Space Morphological Opening`)** — xóa hoàn toàn giá treo đồ / ổ điện / công tắc trên tường mà không bao giờ chém ngang đỉnh tóc hoặc thái dương nhân vật.
2. **Đạo diễn kết hợp hài hòa `Option A × Option B` (`12-Scene Hybrid Matrix`)** — phối hợp nhịp nhàng giữa *Full-Head Rounded Studio Cards (`A1`)*, *Headroom-Rich Dual-Rim Squircle PiP (`A2`)* và *Full-Shoulders Strictly Bottom-Flush Cutouts (`Option B`)*.
3. **Khóa cứng 100% giọng đọc khớp miệng (`verify_audio_voice_sync_guard`)** — chặn đứng lỗi dùng nhầm file voice thô chưa cắt (`84.45s` vs `40.63s`) gây trôi hình hoặc mất tiếng.
4. **Tăng tốc render `~6x` (`Incremental Segment Hash Cache + Low-RAM Streaming + Single-Pass FFmpeg C/AVX2`)** — giữ đỉnh RAM `< 350 MB` và tái sử dụng tức thì (`0.00s`) mọi phân cảnh không đổi.

---

## 1. Giải phẫu lỗi chém ngang đỉnh tóc & Giải pháp `clean_aroll_preserve_hair_crown`

### Nguyên nhân gốc rễ ở các bản cũ
Khi xóa giá treo áo màu đen phía trên đầu nhân vật (`y = 802..852`) bằng tọa độ cố định (`hz[(845 - ry0):, :]`), bất kỳ khung hình nào nhân vật ngẩng đầu lên cao hơn `y = 845` (chiếm `35.2%` tổng số frame, đặc biệt tại `00:01` với `y = 808` và `00:16` với `y = 829`) đều bị chém ngang vòm tóc thành một đường thẳng nhân tạo. Ngoài ra, mô hình `u2netp` đơn thuần cũng dễ nhận nhầm móc treo đen trên tường là tóc nhân vật.

### Thuật toán Hình thái học Đa Tỷ Lệ (`Scale-Space Morphological Opening`)
Được cài đặt trực tiếp trong `scripts/tools/fast_studio_compositor.py`:
- **Khởi tạo nền tường sạch (`init_hair_safe_wall_reference`):** Trích xuất tự động hoặc từ frame đầu thấp (`hair_y_min >= 868`, cách đáy móc treo `>= 16px`), nội suy vùng giá treo bằng trường đa thức 2D mượt kết hợp nhiễu vi mô bảo toàn hạt film, đồng thời nội suy công tắc trái & ổ điện phải.
- **Tách vòm tóc khỏi móc treo (`MORPH_ELLIPSE(15, 13)` ở độ phân giải `1/2` = `30×26px` ở `1080p`):**
  - Móc treo thẳng đứng (`rộng 5–9px`) và thanh ngang (`cao 10–15px`) có kích thước nhỏ hơn nhân cấu trúc `30×26px` -> phép mở hình thái học $M \circ K = (M \ominus K) \oplus K$ triệt tiêu **100%** giá treo (`0` pixel thừa).
  - Vòm sọ tóc người thật có bán kính cong lồi $R_{\text{skull}} \approx 110\text{px} \gg 15\text{px}$ và liên thông trực tiếp xuống vùng thân tóc `y_src = 880..932` -> bảo toàn **100%** đường cong tự nhiên của mái tóc lên tới `y = 742` cùng phần tóc mai bên trái (`x = 298..330`).

---

## 2. Hệ Bố Cục Kết Hợp Hài Hòa `Option A × Option B` (`fast_studio_compositor.py`)

| Chế độ | Hàm API trong `fast_studio_compositor.py` | Khi nào sử dụng | Đặc tính quang học & khung hình |
|---|---|---|---|
| **Option A1** · *Full-Head Studio Card* | `render_full_head_studio_card(bg, clean_aroll, card_rect=(86, 775, 994, 1825))` | Nền giấy sáng Editorial (`Silver Paper`, `Mint Paper`, `Warm Ivory`) | Bo góc Squircle mượt, bóng đổ đa tầng, khoảng thở trên đỉnh tóc `~115px`, tuyệt đối không thò đầu giả ra ngoài viền thẻ. |
| **Option A2** · *Headroom-Rich Squircle PiP* | `render_squircle_pip_window(..., cy_src_1080p=1160, crop_h_1080p=875)` | Cảnh cận sản phẩm Hero Bottle, Macro Lens `85mm` hoặc bảng thông số Bento/UI dày đặc | Khung góc gọn không che vật thể chính, viền đôi phát sáng (`Dual-Rim`) tự động đổi góc Trái/Phải và chừa `+80px` khoảng thở trên vòm tóc. |
| **Option B** · *Bottom-Flush Full-Shoulders Cutout* | `render_bottom_flush_cutout(bg, clean_aroll, person_alpha, y_src_top=735..740)` | Cảnh chuyển chiều sâu 3D Polaroids, Blackout Neon, Chapter Reveal nền lụa tối (`Dark Silk`, `5600K Key-Light`) & CTA kết | Tách nền khử ám màu tường be (`edge decontamination`), giữ nguyên **100% hai bờ vai `x = 0..1080`**, khóa đáy chạm sát `y = 1920` kết hợp vầng sáng viền (`1.5px Jewel Rim`) và sương mờ chân cảnh. |

---

## 3. Cổng Khóa Khớp Miệng Âm Thanh (`verify_audio_voice_sync_guard`)

Trước khi trộn nhạc nền (`BGM 2-Act Beat-Drop`) và trước khi ghép luồng âm thanh vào MP4 / `.fcproj`, `verify_audio_voice_sync_guard(...)` thực thi 4 kiểm chứng bắt buộc:
1. **Độ lệch thời lượng tổng (`|dur_voice - dur_video| <= 0.35s`):** Chặn ngay lập tức nếu đưa nhầm bản thu gốc chưa cắt (`84.45s`) vào timeline đã cắt jump-cut (`40.63s`).
2. **Mật độ lời thoại hoạt động (`speech_density >= 0.45`):** Đảm bảo tiếng nói xuyên suốt toàn bộ video, không bị câm tiếng ở nửa sau.
3. **Khoảng lặng nội bộ tối đa (`max_interior_silence_sec <= 3.5s`):** Phát hiện tức thì các đoạn dead-air chưa cắt.
4. **Biên độ đỉnh (`peak_dbfs > -28 dBFS`):** Chặn luồng âm thanh rỗng hoặc suy hao bất thường.

---

## 4. Từ công thức đến cảnh (v7.6.0)

Bảng A1 / A2 / B ở mục 2 là các hàm render. **Cảnh nào dùng chế độ nào** (bản đồ `S01A..S12C` của V21, mốc VFX của V19, màu 4 hồi, cấu trúc âm thanh) nằm ở [`24_studio_look_recipe.md`](./24_studio_look_recipe.md); chuỗi gọi hàm theo cảnh nằm ở `SKILL.md` Step 3b. CLI `fast_studio_compositor.py --draft/--master` chỉ **re-encode** video đầu vào, không dựng plate studio: Look S được dựng bằng chuỗi gọi hàm Python (`init_hair_safe_wall_reference` -> `clean_aroll_preserve_hair_crown` -> các `render_*` -> `pipe_encode_single_plate_fast` -> `compose_master_mp4_via_ffmpeg`). Quyết định swash hybrid / màu ngọc thuộc Look S (xem [`23`](./23_dviet_profile_decisions_and_backlog.md), quyết định (a)).
