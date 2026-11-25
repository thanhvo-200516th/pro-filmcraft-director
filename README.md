# Pro FilmCraft Director (`pro-filmcraft-director` · v7.3.0)

Bộ Skill Đạo diễn & Biên dịch Hậu kỳ Video Dọc `9:16` (`1080×1920 @ 60fps`) chuẩn Studio theo ngôn ngữ thị giác kênh TikTok **`@__dviet` ("Việt Mỏi Lưng")** — kết xuất đồng thời **Video Master MP4 (`-14.0 LUFS / -1.2 dBTP`)** và **Project FilmCraft gốc (`.fcproj`) chỉnh sửa trực tiếp trên timeline**, tích hợp **8 Cổng Kiểm Định Tự Động (`Gates 1–8`)**.

---

## 1. Điểm Nổi Bật Phiên Bản `v7.3.0`

- **Đạo diễn Kết Hợp Hài Hòa `Option A × Option B` (`fast_studio_compositor.py`):**
  - **Option A1 (`render_full_head_studio_card`):** Thẻ bo góc Studio trên nền giấy sáng (`Silver / Mint / Warm Ivory`) với khoảng thở đỉnh tóc rộng rãi (`~115px`), bóng đổ đa tầng.
  - **Option A2 (`render_squircle_pip_window`):** Cửa sổ Squircle viền đôi phát sáng (`Dual-Rim`) cho cảnh sản phẩm Hero / bảng kính 3D Bento, bảo toàn `+80px` khoảng thở trên đỉnh đầu.
  - **Option B (`render_bottom_flush_cutout`):** Tách nền nhân vật full hai vai (`x = 0..1080`), khử sạch viền ám tường be, khóa đáy chạm sát `y = 1920` với hào quang viền `1.5px` cho các đại cảnh chiều sâu `Dark Silk`, `Neon Blackout` và `5600K Key-Light`.
- **Bảo Toàn Vòm Tóc Cong Tự Nhiên 100% (`clean_aroll_preserve_hair_crown`):**
  - Thuật toán **Scale-Space Morphological Opening** (`MORPH_ELLIPSE(15, 13)` trên không gian `1/2`-res) xóa sạch `100%` giá treo đồ, công tắc và ổ điện trên tường nhưng giữ nguyên `100%` vòm tóc cong tự nhiên (`y` lên tới `742px`) và tóc mai hai bên.
- **Khóa Cứng Giọng Đọc Khớp Miệng (`verify_audio_voice_sync_guard`):**
  - Kiểm định tự động thời lượng, mật độ thoại (`speech_density`), khoảng lặng nội bộ và tương quan sóng âm, ngăn chặn triệt để lỗi lệch khẩu hình hoặc mất tiếng.
- **12 Khuôn Chữ Động Kinetic Typography (`kt01..kt12`) & Nhạc Nền Beat-Drop + SFX 48kHz:**
  - Động cơ Web-Cinema (`web_cinema_plate_engine.mjs`) kết xuất chữ tiếng Việt chuẩn NFC (`134/134` ký tự dấu) từng từ/cụm theo đúng nhịp đọc (`transcript_ms.json`), đi kèm cổng kiểm tra khóa vùng sọ mặt (`Gate 3B CRANIAL_EXCLUSION_AUDIT`).
- **Tăng Tốc Render `~6x` (`Draft 30fps` & `Master 60fps`):**
  - Streaming tuần tự siêu nhẹ (`< 350 MB` RAM), bộ nhớ đệm băm theo phân cảnh (`Incremental Segment Hash Cache` — sửa 1 cảnh chỉ render lại đúng cảnh đó, các cảnh còn lại `0.00s`) và ghép lớp một lượt qua đồ thị lọc `FFmpeg C/AVX2`.

---

## 2. Cấu Trúc Thư Mục

```text
pro-filmcraft-director/
├── SKILL.md                                   # Chỉ dẫn điều phối trung tâm cho AI Agent (v7.3.0)
├── README.md                                  # Tài liệu tổng quan & hướng dẫn cài đặt
├── install.sh                                 # Script liên kết nhanh vào ~/.gemini & ~/.claude + chạy test
├── requirements.txt                           # Các gói Python cần thiết
├── data/                                      # Dữ liệu kiểm thử tiếng Việt NFC & Haar Cascade nhận diện mặt
├── presets/                                   # 9 bộ catalog JSON (Archetypes, Motion, Safe Zones, SFX, Tiers...)
├── references/                                # 20 tài liệu chuyên khảo từ phân tích 45.582 frames @__dviet -> v7.3
├── scripts/
│   ├── web_cinema_plate_engine.mjs            # Động cơ HTML/CSS/SVG/Canvas kết xuất 12 mẫu chữ động 60fps
│   ├── dviet_smooth_camera_engine.py          # Đường cong Bezier camera mượt, Parallax 2.5D & SubPixelSprite
│   ├── dviet_7706_typography_choreography.py  # Vũ đạo chữ @__dviet & Z-depth
│   ├── dviet_motion_canvas_engine.py          # Kết xuất đồ họa chuyển động bổ trợ
│   ├── vietanh_35_typography_engine.py        # 35 hiệu ứng xuất hiện chữ mở rộng
│   ├── ffskill_bridge.py                      # Cầu nối xử lý FFmpeg chuẩn hóa âm thanh & khung hình
│   └── tools/                                 # 6 công cụ lõi gọi trực tiếp:
│       ├── probe_and_align.py                 # Dò thông số media, đồng bộ transcript & khoảng lặng
│       ├── web_plate_builder.py               # Điều phối kết xuất hàng loạt plate chữ & thẻ kính 3D (.mov)
│       ├── typography_composer.py             # Tính toán vùng an toàn chữ Dual-Rail & đường cong nhịp điệu
│       ├── visual_blocks.py                   # Dựng khối thị giác, HUD tọa độ & hiệu ứng chuyển cảnh
│       ├── fast_studio_compositor.py          # Compositor v7.3 (Hybrid A×B, Hair-Safe, VoiceSyncGuard, Cache)
│       └── compile_and_verify.py              # Trình biên dịch .fcproj + 8 cổng kiểm định tự động (Gates 1-8)
├── templates/
│   └── edit_plan_viewer.html                  # Giao diện HTML xem & duyệt Edit Plan trực quan
└── tests/
    └── test_skill_v73.py                      # Bộ kiểm thử tự động toàn diện cho Skill v7.3.0
```

---

## 3. Hướng Dẫn Cài Đặt Nhanh

```bash
# 1. Clone kho mã nguồn về thư mục skills của Antigravity / Claude
git clone https://github.com/thanhvo-200516th/pro-filmcraft-director.git \
  ~/.gemini/config/skills/pro-filmcraft-director

# 2. Cài đặt môi trường Python (khuyến nghị Python 3.10+ & FFmpeg 6.1+)
python3 -m venv ~/.venvs/video-skills
~/.venvs/video-skills/bin/pip install -r ~/.gemini/config/skills/pro-filmcraft-director/requirements.txt

# 3. Chạy script liên kết & kiểm tra tự động
bash ~/.gemini/config/skills/pro-filmcraft-director/install.sh
```

---

## 4. Kiểm Thử Tự Động

```bash
~/.venvs/video-skills/bin/python3 tests/test_skill_v73.py
```
Khi đạt chuẩn, bộ kiểm thử sẽ xác nhận toàn bộ cú pháp mã nguồn, tính di động đường dẫn đa máy (`0` đường dẫn cứng cá nhân), `9/9` bộ preset JSON, `20/20` tài liệu tham chiếu và các hàm lõi `v7.3` (`clean_aroll_preserve_hair_crown`, `render_full_head_studio_card`, `render_squircle_pip_window`, `render_bottom_flush_cutout`, `verify_audio_voice_sync_guard`).
