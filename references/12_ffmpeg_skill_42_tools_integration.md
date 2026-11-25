# Tích Hợp `kajisho5/ffmpeg-skill` (`v4.5.3` — 42 FFmpeg Tools & MCP Server) Vào `pro-filmcraft-director`

Tài liệu này quy định kiến trúc kết hợp 2 tầng giữa:
1. **`pro-filmcraft-director` (`THE CREATIVE BRAIN`):** Đạo diễn nhịp dựng 25 Micro-Beats (`Fast-Fast-Slow`), 35 Preset Typography `@vietanh.videoeditor`, 7 Choreography `@__dviet`, tách nền 2.5D Parallax (`rembg` + `cv2.inpaint`), 4-Plane Z-Depth Speaker Cutout Sandwich, và biên dịch project `.fcproj v17`.
2. **`kajisho5/ffmpeg-skill` (`THE DETERMINISTIC HANDS` — cài đặt tại `../ffmpeg-skill/`):** Bộ 42 công cụ FFmpeg Python stdlib-only + MCP Server (`mcp/server.py`) + 70+ chốt chặn lỗi (`docs/defect-guards.json`), đóng vai trò tầng tiền xử lý tín hiệu, cắt GOP thông minh, chuẩn hóa màu/âm thanh, xuất đa NLE (`.fcpxml`/`.otio`/`.edl`) và kiểm định 20 tiêu chí phát sóng.

---

## 1. Danh Mục 42 Công Cụ Đã Cài Đặt & Kiểm Định (`42/42 Usable = YES`)

| Nhóm (Role) | 12 Core Tools (`MCP Default`) | 30 Specialized Tools (`FFMPEG_SKILL_MCP_FULL=1`) | Ứng Dụng Trong 6 Pha Của `pro-filmcraft-director` |
| :--- | :--- | :--- | :--- |
| **1. Analysis (Đo đạc)** | `probe` (`--analyze` VFR, HDR/HLG/DV, SAR, Log) | `scenes` (`--beats`, `--shots` optical flow, `--audio-peaks`, `--speech`), `cropdetect` (`--motion-centre`) | **Pha 1 & Pha 2:** Quét cấu trúc file thô, dò nhịp nhạc (`--beats`), dò chuyển cảnh & tâm chuyển động chủ thể (`--motion-centre`). |
| **2. Analysis & Execution** | `silence` (`--speech-aware`, `--filler`, `cut_points` RMS 50ms, `--timemap`), `loudness` (2-pass EBU R128 + khử AAC True-Peak overshoot) | `sync` (1ms FFT cross-correlation + `--fix-drift` ppm cho mic thu rời) | **Pha 1 & Pha 5:** Đồng bộ mic rời với máy quay; cắt khoảng lặng giữ hơi thở tự nhiên trong câu; chuẩn hóa âm lượng `-14.0 LUFS / -1.0 dBTP` không vọt đỉnh sau nén AAC. |
| **3. Cutting, Timing & Framing** | `cut` (`-c copy`, `--accurate`, `--smart` partial-GOP H.264, `--snap beats`), `fit` (`9:16` crop/pad/blur, Lanczos, CFR conform) | `join` (`xfade`/`acrossfade` frame-exact), `broll`, `speedramp`, `freeze`, `pad`, `loop`, `reverse`, `crop`, `straighten`, `sphere` | **Pha 1 & Pha 3:** Cắt thô A-Roll siêu tốc bằng `--smart` (chỉ re-encode biên GOP, copy 90% giữa); chuẩn hóa B-Roll về `9:16 CFR 60fps`. |
| **4. Picture, Color & Audio** | `caption` (`.ass` HarfBuzz, `--wrap phrase`, `--karaoke`, `--emoji-assets`), `graphics`, `audio` (`--voice light\|medium\|strong`, `--duck` exact-dB sidechaingate) | `overlay` (`on_grid`, `windowed_overlay_x`), `color` (`--to-sdr` Hable tonemap, `--lut`, `--legalize bt709`), `denoise`, `deinterlace`, `stabilize`, `redact`, `insert`, `background`, `sequence`, `waveform`, `grid`, `metadata`, `proxy` | **Pha 3, Pha 4 & Pha 5:** Tone-map video iPhone HDR sang SDR BT.709; làm sạch giọng nói 3 cấp độ; tự động hạ nhạc nền chính xác theo dB bằng `sidechaingate`; chạy phụ đề `.ass` tốc độ C cho thoại thường; kẹp dải màu `--legalize bt709`. |
| **5. Delivery, Orchestration & QA** | `export` (platform presets, ProRes 4444 alpha, `--max-mb`), `render` (`project.json`, `--export-timeline` `.fcpxml`/`.otio`/`.edl`), `check` (`--platform`, `--content`, `--levels bt709`), `look` (`--safe tiktok/reels/shorts`, `--compare`) | `batch` (content-hash cache + `--jobs`), `multicam` (`--switch energy`), `report` (HTML client report), `verify` (10-step real-footage self-test), `_review.py` (`_review.html` 3-column offline NLE review UI) | **Pha 4 & Pha 6:** Xuất timeline sang Final Cut Pro (`.fcpxml`) & DaVinci Resolve / Premiere (`.otio`) song song `.fcproj v17`; chạy 20 bài kiểm tra TikTok/Reels (`0` flash frame, `0` audio dropout, BT.709 legal levels); xuất báo cáo HTML & giao diện duyệt `_review.html`. |

---

## 2. Cầu Nối Gọi Trực Tiếp Từ Python (`scripts/ffskill_bridge.py`)

Mọi script trong `pro-filmcraft-director` có thể gọi trực tiếp 42 công cụ của `ffmpeg-skill` qua [`ffskill_bridge.py`](../scripts/ffskill_bridge.py):
- `ffskill_doctor()`: Kiểm tra toàn bộ 231 encoders, 561 decoders, 568 filters, 57 bitstream filters, font đa ngôn ngữ và trạng thái 42 tools.
- `ffskill_probe(video_path, analyze=True)`: Phân tích sâu VFR, HDR/SDR, SAR/DAR, kênh âm thanh.
- `ffskill_speech_aware_silence(video_path, out_path, timemap_path)`: Cắt khoảng lặng giữ hơi thở trong câu + đo RMS `±50ms` quanh điểm cắt.
- `ffskill_smart_cut(video_path, start, end, out_path)`: Cắt H.264 theo biên GOP không giảm chất lượng.
- `ffskill_check_comprehensive(video_path, platform="tiktok", content=True, levels="bt709")`: Chạy 20 bài kiểm định nền tảng, quét 1-frame flash (`6 bytes/frame`), black/frozen frame, audio dropouts và dải màu BT.709.
- **Quy tắc Bất Di Bất Dịch Khi Xuất `.mp4` Có Kinetic Typography (`Strict -sn Guard`):** Tuyệt đối **KHÔNG** dùng `caption.py --mode mux` hay `-c:s mov_text` để nhúng luồng phụ đề chìm vào file `.mp4` đã có Kinetic Typography (`@__dviet` / `@vietanh.videoeditor`). Phải luôn dùng cờ **`-sn`** khi mux MP4 và kiểm định bằng `check_no_soft_subtitle_streams()` trong [`04_qa_4pass_inspector.py`](../scripts/04_qa_4pass_inspector.py) để trình phát video (QuickTime / macOS / VLC / iOS) không bao giờ hiển thị phụ đề hệ thống đè lên hình!
