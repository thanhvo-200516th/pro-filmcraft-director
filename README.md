# Pro FilmCraft Director (`pro-filmcraft-director` · v7.9.0)

Bộ Skill Đạo diễn & Biên dịch Hậu kỳ Video Dọc `9:16` (`1080×1920 @ 60fps`) chuẩn Studio theo ngôn ngữ thị giác kênh TikTok **`@__dviet` ("Việt Mỏi Lưng")** — tạo ra **Project FilmCraft gốc (`.fcproj`) chỉnh sửa trực tiếp trên timeline** (Rule A1: chỉ xuất **Video Master MP4 (`-14.0 LUFS / -1.5 dBTP`)** khi người dùng yêu cầu hoặc ở chế độ draft, qua `scripts/tools/fc_export.py`; **ngoại lệ Look S**: giao **MP4 master từ compositor + bản `.fcproj` song song**, xem mục 1), tích hợp **8 Cổng Kiểm Định Tự Động (`Gates 1–8`)**.

---

## 1. Điểm Nổi Bật Phiên Bản `v7.9.0`

Bản này là bản sửa theo kiểm định bản dựng v4: các cổng mới ở lớp `studio_recipe.py`, `motion_gate.py`, `web_plate_builder.py`, `fast_studio_compositor.py` và `qa_sync.py`, cộng phần dọn kho (số phiên bản, số thứ tự tài liệu, liên kết chết, `--help`). Chi tiết từng thay đổi nằm trong `docs/TIEN_DO_SKILL.md` (mục `v7.9.0`).

### `v7.8.0` (giữ nguyên)

Bản này biến ba lỗi của bản dựng v3 thành luật (nhãn **[ĐO]** = đã đo, **[ƯỚC]** = ước lượng; cơ sở là một video của người dùng và 17 mẫu `@__dviet` của một kênh, nên ngưỡng là [ƯỚC]).

- **D1, chữ hook phải khớp giọng:** hero `3 BƯỚC` hiện ở `0.17 s` trong khi giọng nói "Vì trên đây là video sản phẩm..." và chỉ nói `3` ở `3.48 s`, lại che nửa dưới chai serum. Giờ chữ hook lấy từ chính các từ của giọng (`studio_recipe.hook_text_from_words`), giọng giữ nguyên, chữ đầu là dòng dẫn trích mệnh đề đầu (`<= 200 ms`), hero là từ khoá đầu tiên và hiện sớm hơn từ đó `150-200 ms`, con số chỉ xuất hiện khi giọng nói nó, và hero nằm ở "sân khấu" phía trên sản phẩm (`s = 0.72`, đỉnh nắp y khoảng `613`), không bao giờ đè lên sản phẩm. Cổng mới: `text_voice_sync`, `hero_safe_zone`, `text_min_size` (font `>= 64 px`, hộp chữ `>= 3.3 %`).
- **D3, hết đoạn nền đứng yên:** mỗi `1.0 s` của `0-3.4 s` cần ít nhất một reset của lớp NỀN (cắt, flash, glint, thẻ rơi, nấc zoom `>= 4 %`); PiP pop và chữ thì không tính (`hook_motion_floor`). Một đoạn B-roll toàn màn hình giữ `> 0.8 s` trong hook (`> 1.2 s` ở nơi khác, cảnh báo) cần một cử động nhỏ: đẩy `>= 10 %/s`, lia `>= 4 %` khung/giây hoặc vệt sáng (`bg_static_hold` trong `check_pacing`; `plan_micro_moves` đề xuất cách sửa, kèm số chứng minh [ĐO] 4 %/s cho diff 1.23, 14.5 %/s cho 2.09). Thước đo là 17 hook B-roll-first của `@__dviet` (trung bình vùng nền 1.9-2.4), không phải V21 (V21 có đoạn giữ 2.0 s ở 1.35-3.35 s).
- **D2, thẻ pop-out sắc nét:** mặc định mới (`card_rect (70,1065,1010,1705)`, `rx 64`, `edge_feather 1.6`, `edge_blur 0`, `bulge 0.03`, `sag 0.015`, Lanczos4, một lần unsharp) và các cổng: mép 10-90 % `<= 6 px`, Laplacian vùng mặt `>= 1.8x` ảnh Lanczos thường, pop `7-11 %` chiều cao. Mốc Laplacian toàn khung 430 **không** dùng được (xem tài liệu 29, mục 3.1a). Không có bộ upscale nơ-ron trên máy này.
- **`studio_recipe.py` (v7.8.0):** thêm `hook_text_from_words`, `hook_motion_floor`, `plan_micro_moves`; `check_hook(hook, words=None)` và `check_pacing` nhận reset có kiểu `{t, kind, layer, mag}` (số thực và tuple cũ vẫn là reset nền). Preset: `first_text_max_ms 200`, hero là một ràng buộc (`binding`) thay cho chữ cố định, `pacing.motion`. `scripts/tools/motion_gate.py` (gói S1) đo các cổng trên MP4 đã kết xuất.

### `v7.7.0` (giữ nguyên)

Bản này mã hoá một đợt đo (17 hook `@__dviet`, so với V19-V21 và bản dựng v2) thành luật. Mọi con số trong hai tài liệu mới mang nhãn **[ĐO]** (đã đo) hoặc **[ƯỚC]** (ước lượng). Giới hạn của bằng chứng: **một kênh, 17 mẫu**, và SFX không tách được khỏi giọng nên mọi mốc SFX là [ƯỚC]. Các script đo (hook_measure và phân tích nhịp) là công cụ nghiên cứu, **không** kèm trong skill.

- **Hook-first 5 giây ([`references/28_hook_first_5s_and_pacing.md`](references/28_hook_first_5s_and_pacing.md)):** công thức hook v3 trên cấu trúc V21 (B-roll sản phẩm toàn màn hình + PiP người dẫn): khung 0 đã chuyển động, giọng vào `<= 40 ms`, chữ đầu `<= 300 ms`, hero `12-18 %` chiều cao khung và không che sản phẩm, `3-5` sự kiện chữ trong `0-3 s`, cắt punch ở `1330 ms` với whoosh sai số `±12 ms`, chân không `>= 12 dB` (mục tiêu `17 dB`) ở `3.2-3.4 s`, flash trắng ở `3.4 s`. Danh sách SFX theo tên file nằm trong tài liệu; dữ liệu chạy được là khoá `hook_0_5s` của `presets/studio_scene_recipe.json`.
- **Luật nhịp (cùng tài liệu 28):** không giữ cảnh `> 2.0 s` mà không có reset (cắt, nấc zoom, flash, chữ mới), trần của công thức `2.4 s`; `>= 3` reset trong cửa sổ `0-5 s` và `>= 2` ở mỗi cửa sổ `5 s` sau đó; `>= 2` shot dưới `1 s` mỗi `10 s` (khuyến nghị); dead hold mục tiêu `<= 45 %`; không dùng lại cùng giây B-roll; trần punch-in theo lớp (cutout B `+6 %`, thẻ A1 `+12 %`, PiP `+8 %`, B-roll toàn màn hình `+25 %`). Mọi sửa đổi là tách cảnh, chỉ thay đổi hình, tốc độ `1.0x`. **Không** đổi mật độ lời, mật độ chữ, độ to.
- **`studio_recipe.py` (v7.7.0):** thêm `hook_template()`, `check_hook()`, `check_pacing()` (báo `hold_s` và `dead_hold_share` theo cửa sổ; `dead_hold_share` là chỉ số ước ở mức kế hoạch) và `check_source_reuse()`, trả về danh sách phát hiện có cấu trúc. Hàm và khoá cũ không đổi.
- **Thẻ pop-out ([`references/29_popout_card_premiere_to_filmcraft.md`](references/29_popout_card_premiere_to_filmcraft.md)):** đầu nhô lên khỏi thẻ sáng. Công thức Premiere / CapCut ánh xạ sang FilmCraft A / B / C; ship ở loại **B** (hai plate RGBA và bản ghép master) qua `render_popout_studio_card` (cờ **Look S pop-out**, thẻ bo góc mặc định không đổi). Spec **chưa có khoá `masks`** (khoảng trống H5); alpha RVM còn viền xám phải xử lý trước khi ship.
- **Gói compositor / compile / export:** profile `studio_14` chọn được bằng `--audio-profile`, bộ làm sạch tường nhận alpha RVM (`person_alpha_u8`), `fc_export.py` thăm dò (polling) thay vì chờ mù.

## 1-prev. Phiên Bản `v7.6.0` (giữ nguyên)

- **Hai look, chọn ở Bước 3 của `SKILL.md`:** **Look S (Studio)** là mặc định cho video talking head sản phẩm / thương hiệu / giải thích, theo ba master tham chiếu V19-V21; **Look D** (kênh `@__dviet`, screen-strip, profile `dviet`, `tiktok_loud`) chỉ khi người dùng yêu cầu rõ. Công thức: [`references/24_studio_look_recipe.md`](references/24_studio_look_recipe.md) (bản đồ 12 cảnh V21, mốc VFX-01..08, màu 4 hồi, cấu trúc âm thanh).
- **Hybrid `Option A × B` là trung tâm của Look S (từ v7.3, giữ nguyên):** **Option A1** `render_full_head_studio_card` (thẻ studio bo góc, đầu không bị cắt), **Option A2** `render_squircle_pip_window` (cửa sổ PiP squircle, nhường chỗ cho B-roll / sản phẩm / UI), **Option B** `render_bottom_flush_cutout` (cutout dính đáy, giữ trọn hai vai), kèm `clean_aroll_preserve_hair_crown` (giữ vòm tóc) và `verify_audio_voice_sync_guard` (khoá giọng khớp miệng). Thêm cảnh giấy sáng `#FAFAFA` (tối thiểu `2`, `~14 %`), neon blackout, số lớn trên lụa tối và hook B-roll toàn màn hình với presenter trong PiP: bảng chọn theo cảnh ở `SKILL.md` Step 3b.
- **Bàn giao kép cho Look S:** **MP4 master** dựng bằng compositor (`1080×1920 @ 60fps`, `-14 LUFS`) **và** bản **`.fcproj` song song** để sửa trên timeline. Đây là ngoại lệ được khai báo của Rule A1; Look D và mọi lần chạy khác vẫn giao `.fcproj` trước. CLI `fast_studio_compositor.py --draft/--master` chỉ **re-encode**, không dựng plate studio.
- **`scripts/tools/studio_recipe.py` + `presets/studio_scene_recipe.json`:** trình lập cảnh không trạng thái (`--words words_tl.json --duration D --out scenes.json`): gán chế độ cho từng nhịp theo mẫu V21, giữ tối thiểu `2` cảnh sáng, trần A-roll phẳng `25 %`, không hai nhịp liền cùng thế giới màu, phát màu ngọc theo hồi. Nhận cả dict của probe lẫn mảng trần. Chỉ lập kế hoạch, bộ não (agent) quyết định.
- **Profile âm thanh `studio_14`** trong `presets/profile_overrides.json`: `-14.0 LUFS`, `-1.2 dBTP`, bộ giới hạn `-2.2`, ducking bật, `bgm_stops` được phép, tới `72` cue SFX. `platform` và `tiktok_loud` giữ nguyên số; `tiktok_loud` nay được ghi là **Look D** và các con số của nó **chưa kiểm** trên giọng thật. Nối `--audio-profile studio_14` vào `compile_and_verify.py` thuộc gói script.
- **Token `dviet`:** luật "một màu nhấn mỗi video" chỉ thuộc Look D (`palette.accent_policy: tokens`); Look S dùng `color_world`. Xung đột Iron Law 6 giải quyết rõ: swash hybrid = Look S, sans nén = Look D.

## 1a. Phiên Bản `v7.5.0` (giữ nguyên)

- **Bảng độ to cho TikTok (`compile_and_verify.py --audio-profile tiktok_loud`)**, lấy từ [`references/25_loudness_tiktok_vs_nle.md`](references/25_loudness_tiktok_vs_nle.md): `-12 LUFS` (cửa sổ `±0.5` trên `mix.wav`), trần true-peak `-1.0 dBTP` (bộ giới hạn `-1.2`), đỉnh giọng `-3.5..-1.5 dBFS`, nhạc nền dưới giọng `12..17 LU` (đích `14`), sàn "lời trên nhạc" `8 LU`, đỉnh SFX theo tầng `-4 / -7 / -10 dBFS`. Ngoài ra có nhạc nền khi không lời (`4..8 LU`), LRA `> 6` và short-term tối đa `> -7 LUFS`, **chỉ cảnh báo, không bao giờ FAIL**. Hồ sơ `platform` giữ nguyên (có test hồi quy). **Đã đo:** `-12 LUFS` của kênh, chênh `~14 LU` giọng/nhạc, và chiều của độ vượt đỉnh sau AAC (một tín hiệu tổng hợp, bộ mã AAC của ffmpeg, chỉ mang tính định hướng). **Suy ra, chưa kiểm trên giọng thật:** sàn `8 LU`, các tầng SFX, đoạn ép `0.25 s`, nhạc nền không lời `6 LU`. TikTok không công bố mức độ to đích, skill không khẳng định con số chuẩn hoá chính thức nào.
- **`scripts/tools/duck_keyframes.py`:** hàm thuần sinh keyframe ducking 4 điểm từ khoảng thời gian của từng từ (`0.35 s` trước từ đầu, hạ trong `0.25 s`, sâu `8 dB`, giữ qua khoảng nghỉ `< 1.5 s`, nhả `0.7 s`, tuỳ chọn vacuum `-32 dB` trong `0.4 s`, tối đa 1 lần / 20 s). Hằng số đọc từ `presets/sfx_micro_sync_rules.json`. Profile `tiktok_loud` vẫn để `no_ducking: true` cho tới khi nối vào bộ biên dịch.
- **`scripts/tools/filmcraft_cli.py`:** shim điều khiển FilmCraft qua `filmcraft --control` (cần binary `filmcraft` và màn hình X, nếu không có thì báo rõ rồi bỏ qua). `filmcraft-cli` chưa từng tồn tại, xem [`references/30_filmcraft_control_bridge.md`](references/30_filmcraft_control_bridge.md). Chuỗi font dự phòng theo vai trò ở preset font trong `presets/`, xem [`references/26_dviet_fonts.md`](references/26_dviet_fonts.md).
- **`scripts/tools/flicker_schedule.py` và opener `flicker`:** lịch nhấp nháy silhouette (loại A+B: plate matte đặt lên timeline). Công thức Premiere cho các hiệu ứng còn trong BACKLOG nằm ở [`references/27_premiere_recipes_to_filmcraft.md`](references/27_premiere_recipes_to_filmcraft.md).
- **Bảng "đạo diễn được hứa gì" (xem `SKILL.md` mục 3):** **A** = làm native trên timeline FilmCraft; **B** = làm bằng plate render sẵn; **C** = không khả thi (chất lượng Object Mask cho vật bất kỳ, planar tracking có xử lý che khuất, keycap 3D thật, Time Displacement native). Tile waveform, keycap, timeline NLE và chữ dán tường trên cảnh cầm tay vẫn nằm trong BACKLOG ([`references/23_dviet_profile_decisions_and_backlog.md`](references/23_dviet_profile_decisions_and_backlog.md)).

## 1b. Phiên Bản `v7.4.0` (độ trung thực `@__dviet`, giữ nguyên)

- **Một nguồn sự thật cho `@__dviet`:**
  - [`references/dviet_19/INDEX.md`](references/dviet_19/INDEX.md): bảng 17 video (độ dài / fps / canvas, hook, palette, caption `y`, zoom, chuyển cảnh, loudness), các tín hiệu lặp lại có đếm (flicker silhouette, layout tutorial, thẻ 9:16, thẻ profile, lock-up 2 tầng, caption `y` 50–67 %, accent vàng, mastering to) và bảng khoảng cách *quan sát → done v7.4 / backlog*.
  - [`references/23_dviet_profile_decisions_and_backlog.md`](references/23_dviet_profile_decisions_and_backlog.md): các quyết định có nguồn gốc và **BACKLOG xếp hạng những hiệu ứng chưa cài đặt** (silhouette flicker, clean-plate vanish, planar tracking, clone, waveform SFX tile, constellation, pixel stretch, ...). README này không hứa tính năng nào nằm trong backlog.
  - [`presets/dviet_style_tokens.json`](presets/dviet_style_tokens.json): token duy nhất (palette, vai trò font, cỡ chữ, `caption_y_pct` theo layout, lock-up, constellation, canvas, âm thanh) với cờ `measured` / `estimate`; [`presets/canvas_presets.json`](presets/canvas_presets.json): `1080×1920@60|30`, `1440×1080@24|30`, `1332×720@30`.
- **Chữ theo vai trò (`scripts/tools/dviet_text.py`):** `caption`, `keyword_sans`, `script_accent`, `number`, `header`, `cta`, `bilingual_sub`, `lockup_sub`, `lockup_hero`, `constellation` (+ `font_specimen`); `y%`, cỡ chữ và kiểu vào lấy từ token; kiểm NFC; thiếu font chỉ cảnh báo.
- **Zoom (`scripts/dviet_smooth_camera_engine.py`):** `punch_220_q25`, `push_130_long` (16 s), `step_zoom_13_8_9`, `jc_reset_push_4_10`, `dolly_out_12_16` (giá trị là *ước lượng* đã làm tròn; preset mặc định không đổi), radial blur lớn dần theo scale, kẹp scale theo đỉnh đầu (nguồn `>= 1080p`), luật C4 (đoạn nói liền `>= 4 s` có khoá zoom) và self-test đo đường cong scale bằng `cv2.estimateAffinePartial2D` trên clip tổng hợp 5 s.
- **Chuyển cảnh theo profile `dviet` (`presets/atomic_motion_library.json`):** `color_wash_multi_0p6s`, `film_burn_perf_5f`, `light_leak_overlay`, `white_flash_0p25s`, `vertical_roll_slide`, `orange_ghost_pre_cut_5f`, `vacuum_32db_0p4s` (`profile_scope: ["dviet"]`, có `max_duration` và `caps`; thực thi nằm ở `compile_and_verify.py --profile dviet`).
- **3 template layout (`web_plate_builder.py`):** `screen_strip`, `card_916`, `profile_card` với slot đặt tên theo vai trò, mỗi template có PNG self-test.
- **Công cụ mới của v7.4.0:** `scripts/env_status.py` (bước 0), `compile_and_verify.py --profile default|dviet --audio-profile platform|tiktok_loud`, `probe_and_align.py --whisper-threads --timeout --force --music-only`, `fc_export.py`, `spec_from_plan.py`, `silence_cut.py`, `speed_media.py`, `sfx_auto.py`, `qa_sync.py` + `sfx_shift.py` (Gate 7b, dịch một lần), `broll_from_video.py`.
- **Đã có từ v7.3 và giữ nguyên:**
  - **Đạo diễn Kết Hợp Hài Hòa `Option A × Option B` (`fast_studio_compositor.py`):** Option A1 (`render_full_head_studio_card`), Option A2 (`render_squircle_pip_window`), Option B (`render_bottom_flush_cutout`).
  - **Bảo toàn vòm tóc cong 100% (`clean_aroll_preserve_hair_crown`):** Scale-Space Morphological Opening xóa giá treo/ổ điện nhưng giữ vòm tóc (`y` lên tới `742px`).
  - **Khóa cứng giọng đọc khớp miệng (`verify_audio_voice_sync_guard`):** kiểm định thời lượng, mật độ thoại, khoảng lặng và tương quan sóng âm.
  - **12 khuôn chữ động `kt01..kt12`** (Web-Cinema `web_cinema_plate_engine.mjs`, NFC `134/134`) và **Gate 3B `CRANIAL_EXCLUSION_AUDIT`**.
  - **Render nhanh:** `Draft 30fps` / `Master 60fps`, bộ nhớ đệm theo phân cảnh, ghép một lượt qua đồ thị lọc `FFmpeg C/AVX2`.

---

## 2. Cấu Trúc Thư Mục

```text
pro-filmcraft-director/
├── SKILL.md                                   # Chỉ dẫn điều phối trung tâm cho AI Agent (v7.9.0)
├── README.md                                  # Tài liệu tổng quan & hướng dẫn cài đặt
├── install.sh                                 # Liên kết vào ~/.gemini & ~/.claude, chạy env_status + test
├── requirements.txt                           # Các gói Python cần thiết (+ ghi chú node/chrome/ffmpeg/matte)
├── data/                                      # Dữ liệu kiểm thử tiếng Việt NFC & Haar Cascade nhận diện mặt
├── presets/                                   # Catalog JSON (Archetypes, Motion, Safe Zones, SFX, Tiers, Tokens @__dviet, Canvas...)
├── references/                                # Tài liệu 01..30 (24 là công thức Look S `24_studio_look_recipe`, 30 là cầu nối điều khiển FilmCraft `30_filmcraft_control_bridge`; 28 hook-first 5 s và luật nhịp, 29 thẻ pop-out, v7.7.0; chữ hook theo giọng, sân khấu sản phẩm, mặc định thẻ nét, v7.8.0) + dviet_19/ (INDEX.md và 17 file phân tích từng video)
├── scripts/
│   ├── env_status.py                          # Preflight: node >=22, Chrome, ffmpeg, matte model, font (bước 0)
│   ├── web_cinema_plate_engine.mjs            # Động cơ HTML/CSS/SVG/Canvas (Node >=22) kết xuất plate 60fps
│   ├── dviet_smooth_camera_engine.py          # Camera Bezier mượt, zoom preset v7.4.0, safe-box, luật C4, radial blur
│   ├── dviet_7706_typography_choreography.py  # Vũ đạo chữ @__dviet & Z-depth
│   ├── dviet_motion_canvas_engine.py          # Kết xuất đồ họa chuyển động bổ trợ
│   ├── vietanh_35_typography_engine.py        # 35 hiệu ứng xuất hiện chữ mở rộng
│   ├── ffskill_bridge.py                      # Cầu nối xử lý FFmpeg chuẩn hóa âm thanh & khung hình
│   └── tools/                                 # 6 công cụ lõi + CLI hỗ trợ:
│       ├── probe_and_align.py                 # Ingest, transcript, khoảng lặng (--tier fast|studio|full|auto)
│       ├── web_plate_builder.py               # Plate chữ động kt01..kt12, thẻ kính 3D và layout screen_strip / card_916 / profile_card
│       ├── typography_composer.py             # Vùng an toàn chữ Dual-Rail, lịch kinetic beat
│       ├── visual_blocks.py                   # Khối thị giác, HUD tọa độ & hiệu ứng chuyển cảnh
│       ├── fast_studio_compositor.py          # Compositor (Hybrid A×B, Hair-Safe, VoiceSyncGuard, Cache)
│       ├── compile_and_verify.py              # Biên dịch .fcproj + 8 cổng kiểm định (--profile, --audio-profile)
│       ├── dviet_text.py                      # Sự kiện chữ theo vai trò -> track chữ (token @__dviet)
│       ├── silence_cut.py / speed_media.py    # Cắt lặng và tốc độ trước khi ingest
│       ├── sfx_auto.py / qa_sync.py / sfx_shift.py  # Kế hoạch SFX, đo đồng bộ, Gate 7b dịch một lần
│       ├── spec_from_plan.py / broll_from_video.py  # Plan -> .craft.json, kế hoạch B-roll & kiểm lint prompt
│       ├── filmcraft_cli.py                   # Shim điều khiển FilmCraft qua `filmcraft --control` (v7.5.0)
│       ├── flicker_schedule.py                # Lịch nhấp nháy silhouette cho opener `flicker` (v7.5.0)
│       ├── duck_keyframes.py                  # Keyframe ducking nhạc nền 4 điểm, hàm thuần (v7.5.0)
│       ├── studio_recipe.py                   # Trình lập cảnh Look S theo mẫu V21 + kiểm hook / nhịp / nguồn B-roll, hàm thuần (v7.8.0: chữ-giọng, vùng an toàn, sàn chuyển động)
│       ├── motion_gate.py                     # Cổng đo trên MP4 đã kết xuất: diff nền, mép thẻ, Laplacian mặt, hero đè sản phẩm (v7.8.0)
│       └── fc_export.py                       # Xuất .mp4 từ .fcproj (chỉ khi người dùng yêu cầu hoặc draft)
├── templates/
│   └── edit_plan_viewer.html                  # Giao diện HTML xem & duyệt Edit Plan trực quan
└── tests/                                     # 14 bộ kiểm thử, mỗi bộ chạy độc lập và thoát 0 khi đạt
    ├── test_studio_recipe.py                  # studio_recipe (+ hook 0-5 s, max hold, reset mỗi 5 s, nguồn B-roll; v7.8.0: chữ-giọng, vùng an toàn, cỡ chữ, sàn chuyển động nền), preset, profile studio_14
    ├── test_skill_v73.py                      # Kiểm thử nền: cú pháp, preset, tài liệu, compositor, VoiceSyncGuard (không gắn phiên bản, >= 7.6.0)
    ├── test_skill_v76_fixes.py                # Hồi quy mã v7.6: rò chữ demo kt05/kt06, tràn kt05, `--words` dạng probe doc
    ├── test_skill_v77.py                      # Gói S1: thẻ pop-out, bộ làm sạch tường có alpha, export, polling (+ cổng v7.8.0 của S1)
    ├── test_skill_v78.py                      # Gói S1 v7.8.0: thẻ pop-out nét, sân khấu sản phẩm, glint, motion_gate, cổng chữ tối thiểu
    ├── test_dviet_docs.py                     # Chỉ mục 17 video, nhãn phiên bản (đọc từ SKILL.md), token, preset, dviet_text, layout, zoom
    ├── test_loudness_v75.py                   # Bảng độ to tiktok_loud, hồi quy platform, verdict trên clip tổng hợp <= 3 s (v7.5.0)
    ├── test_ducking.py                        # duck_keyframes: đơn điệu, độ sâu, gộp khoảng nghỉ < 1.5 s, tất định (v7.5.0)
    ├── test_flicker_schedule.py               # flicker_schedule và khoá `opener` của spec_from_plan
    ├── test_filmcraft_cli.py                  # Shim filmcraft_cli: ticks, render flow, mã thoát
    ├── test_effect_presets.py                 # Preset hiệu ứng gốc thử nghiệm và macro vanish / clone-appear
    ├── test_fonts_vi.py                       # Phủ glyph tiếng Việt của chuỗi font trong dviet_style_tokens.json
    ├── test_ports.py                          # silence_cut, speed_media, sfx_auto, qa_sync, sfx_shift
    └── test_stability.py                      # Lõi ổn định: banner và hằng phiên bản khớp mô-đun
```

---

## 3. Yêu Cầu Môi Trường & Cài Đặt Nhanh

Yêu cầu (kiểm bằng `python3 scripts/env_status.py [--json] [--strict]`):

| Thành phần | Tối thiểu | Dùng cho |
|---|---|---|
| Python | 3.10+ (venv `~/.venvs/video-skills`) | tất cả công cụ `.py` |
| Node.js | `>= 22` | `web_cinema_plate_engine.mjs` (plate 60fps) |
| Chrome / Chromium | bản headless bất kỳ trên `PATH` | kết xuất HTML5/CSS3/SVG của plate |
| FFmpeg + ffprobe | 6.1+ | ingest, render, đo âm thanh |
| Matte model | `u2netp` hoặc `birefnet-portrait` (`~/.rembg/models`, hoặc `PFD_MATTE_MODEL`) | tách nền người (RVM sandwich, Cranial Lock) |
| Font | Be Vietnam Pro, Playfair Display (tùy chọn có fallback: SVN-Aaron, DFVN West West Condensed) | chữ tiếng Việt chuẩn NFC |

```bash
# 1. Clone kho mã nguồn về thư mục skills của Antigravity / Claude
git clone https://github.com/thanhvo-200516th/pro-filmcraft-director.git \
  ~/.gemini/config/skills/pro-filmcraft-director

# 2. Cài đặt môi trường Python
python3 -m venv ~/.venvs/video-skills
~/.venvs/video-skills/bin/pip install -r ~/.gemini/config/skills/pro-filmcraft-director/requirements.txt

# 3. Chạy script liên kết, preflight (env_status) & kiểm tra tự động
bash ~/.gemini/config/skills/pro-filmcraft-director/install.sh
```

---

## 4. Kiểm Thử Tự Động

```bash
for t in tests/test_*.py; do ~/.venvs/video-skills/bin/python3 "$t" || break; done   # mọi bộ tests/test_*.py (install.sh cũng chạy bằng glob)
~/.venvs/video-skills/bin/python3 tests/test_studio_recipe.py
~/.venvs/video-skills/bin/python3 tests/test_skill_v73.py
~/.venvs/video-skills/bin/python3 tests/test_skill_v76_fixes.py
~/.venvs/video-skills/bin/python3 tests/test_skill_v77.py
~/.venvs/video-skills/bin/python3 tests/test_skill_v78.py
~/.venvs/video-skills/bin/python3 tests/test_dviet_docs.py
~/.venvs/video-skills/bin/python3 tests/test_loudness_v75.py
~/.venvs/video-skills/bin/python3 tests/test_ducking.py
~/.venvs/video-skills/bin/python3 tests/test_flicker_schedule.py
~/.venvs/video-skills/bin/python3 tests/test_filmcraft_cli.py
~/.venvs/video-skills/bin/python3 tests/test_effect_presets.py
~/.venvs/video-skills/bin/python3 tests/test_fonts_vi.py
~/.venvs/video-skills/bin/python3 tests/test_ports.py
~/.venvs/video-skills/bin/python3 tests/test_stability.py
~/.venvs/video-skills/bin/python3 scripts/tools/web_plate_builder.py --self-test
~/.venvs/video-skills/bin/python3 scripts/dviet_smooth_camera_engine.py --self-test
```
`test_skill_v73.py` xác nhận cú pháp mã nguồn, tính di động đường dẫn (`0` đường dẫn cứng cá nhân), `>= 11` bộ preset JSON, `>= 27` tài liệu tham chiếu và các hàm lõi của compositor (`clean_aroll_preserve_hair_crown`, `render_full_head_studio_card`, `render_squircle_pip_window`, `render_bottom_flush_cutout`, `verify_audio_voice_sync_guard`). `test_dviet_docs.py` xác nhận chỉ mục đủ 17 id, nhãn phiên bản (đọc từ `SKILL.md`, chấp nhận `>= 7.6.0`, khớp giữa `SKILL.md`, README và tài liệu tiến độ), link tương đối của `SKILL.md`, token / preset (NFC, khóa mới, khóa cũ giữ nguyên), `dviet_text`, 3 template layout và đường cong zoom.
