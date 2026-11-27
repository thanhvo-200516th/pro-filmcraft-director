# Pro FilmCraft Director (`pro-filmcraft-director` · v7.9.0)

Bộ Skill Đạo diễn & Biên dịch Hậu kỳ Video Dọc `9:16` (`1080×1920 @ 60fps`) chuẩn Studio: tạo ra **Project FilmCraft gốc (`.fcproj`) chỉnh sửa trực tiếp trên timeline** và, với **Look S (Studio, mặc định)**, thêm **MP4 master** dựng bằng compositor. Quy tắc bàn giao (Rule A1 và ngoại lệ Look S) chỉ được viết một lần, ở `SKILL.md` mục 3.8.1: `.fcproj` luôn được giao; `.mp4` chỉ xuất khi người dùng yêu cầu hoặc ở chế độ draft (qua `scripts/tools/fc_export.py`), trừ Look S giao **MP4 master + `.fcproj` song song**. Bộ biên dịch có **8 Cổng Kiểm Định (`Gates 1–8`)**; các cổng hook / nhịp / chữ ở mức kế hoạch là hàm thư viện mà agent phải tự gọi (`SKILL.md` mục 4.2).

`SKILL.md` (đợt sửa v7.9.1; nhãn phiên bản trong mã và frontmatter vẫn `v7.9.0`) đã được sắp lại theo luồng **1. Tổng quan → 2. Yêu cầu & tài nguyên → 3. Quy trình từng bước → 4. Luật / rào chắn → 5. QA & xử lý lỗi**, đánh số `1.` / `1.1.` / `1.1.1.`; mỗi luật chỉ còn một bản chính, nơi khác trỏ tới đó.

---

## 1. Điểm Nổi Bật Phiên Bản `v7.9.0` và bản sửa kiểm định `v7.9.1`

### `v7.9.1` (sửa tài liệu và mã theo kiểm định)

- **`SKILL.md` sắp lại** (xem trên); các bảng lịch sử phát hành v7.7 / v7.8 / v7.9 rời khỏi đầu `SKILL.md`, về README này (bảng cổng v7.9.0 ngay dưới) và tài liệu 28.
- **CLI mới `scripts/tools/look_s_render.py`:** dựng Look S từ `scenes.json` của `studio_recipe.py` (`--scenes --words --aroll --work --out [--draft|--master] [--broll-dir] [--dry-run]`), thay cho "tự viết driver".
- **Sự thật đã chỉnh trong tài liệu:** Gate 3 báo **SKIPPED** (không phải PASS) khi thiếu `--words` / `--manifest` và **FAIL** khi `edit_rules` lỗi; `probe_and_align` từ chối video 0 byte / hỏng và luôn ghi `words_tl.json` (rỗng + cảnh báo khi không có tiếng); `env_status` coi FilmCraft (`>= 0.13.0`) và Xvfb là bắt buộc để compile; thư mục cache `PFD_CACHE_DIR`; `requirements.txt` ghim `opencv-python-headless` 4.x; tier `auto` không bao giờ chọn `studio`; tier `studio` compile bằng `--tier full` nên **có** chạy `bgm_lra` và `R35`.
- **Ngưỡng mới:** chữ whisper / `G2` của FilmCraft theo sàn `64 px` (bỏ `26pt`); preset flash bị chặn (độ sáng trung bình `<= 220`, cắt trắng `opacity <= 70`, `<= 3` lần/giây); vacuum cách nhau tối thiểu `20 s`; `tiktok_loud` = `-12 LUFS`, `-1.0 dBTP`, nhạc nền dưới giọng `14 dB`; một bộ lint prompt B-roll duy nhất, nguồn sự thật `presets/broll_lint_contract.json`.
- **Sửa số liệu sai:** "19/19 video" → 17 (thư mục `dviet_19` giữ tên nhưng chứa 17 video); 4 lớp Z-depth (timeline) so với 3 mặt phẳng trong mã (`LayeredFrameCompositor`); "FilmCraft 0.20.1" → FilmCraft `0.13.0` (0.20.1 là `wgpu`); `1,200` cặp glue → `1199`; luật `45-token` cũ (thật ra `46` token, `8–95` từ) của `visual_blocks.lint_broll_prompt` nay đọc chung hợp đồng `presets/broll_lint_contract.json` (`8–60` từ); 14 micro-bridge liệt kê đủ 14 tên (cộng 7 bridge của archetype); `-0.5 dBTP` → `-1.0 dBTP`; RVM **không** đi kèm skill (matte người là `u2netp` / `birefnet-portrait`).
- Chi tiết: `docs/TIEN_DO_SKILL.md` mục 2.0a.

### `v7.9.0` — các cổng từ kiểm định bản dựng v4

Bản này là bản sửa theo kiểm định bản dựng v4: các cổng mới ở lớp `studio_recipe.py`, `motion_gate.py`, `web_plate_builder.py`, `fast_studio_compositor.py` và `qa_sync.py`, cộng phần dọn kho (số phiên bản, số thứ tự tài liệu, liên kết chết, `--help`). Bảng dưới là bản lịch sử (chuyển từ đầu `SKILL.md`); giới hạn hiện hành và nơi thực thi từng cổng ở `SKILL.md` mục 4.2.

| Cổng (v7.9.0) | Giới hạn | Nơi |
|---|---|---|
| Mép thẻ pop-out sạch | dải tối mép trong `<= 4 px`, `0` đốm tường, răng cưa đỉnh tóc `<= 1.2 px`, độ dốc đỉnh tóc `<= 4 px` | `render_popout_studio_card(clean_source_bands, despeckle_wall, crown_refine)`; `motion_gate.popout_inner_edge_dark_strip_px`, `card_dark_speck_count`, `crown_edge_metrics` |
| Trần flash (`flash_luma_cap`, `flash_rate`) | độ sáng trung bình khung `<= 220`; `<= 3` flash mỗi giây (WCAG 2.3.1); cắt trắng `opacity <= 70`, ramp 3 khung | kế hoạch: `check_hook` qua `motion_gate.check_flash_plan`; bản dựng: `motion_gate.py --flash` |
| Chữ đọc được (`text_min_size`) | mọi chữ phủ, nhãn thẻ, chú thích plate `>= 64 px` trên khung, glyph `>= 3.3 %` H; chữ phụ `70 px` | `check_hook`, `check_text_legibility`; `render_web_plates_batch` CHẶN CỨNG (`UndersizedTextError`) |
| Khoảng cách từ (`word_gap_collision`) | `>= 0.25 em` trên mọi khung của blur-in / scale-in | `motion_gate.check_word_gaps`, `check_hook`; plate kt02/04/05/07/08/09/11 |
| Phủ chữ (`text_coverage`) | từ chữ đầu tới `3.0 s` không quãng trống chữ `> 150 ms` | `check_hook` |
| Chữ đầu trước từ của nó (`first_text_late`) | chữ đầu hiện trước hoặc đúng lúc từ đầu tiên được nói; mặc định BẬT | `check_hook(plan, words=words)` |
| Hàng SFX chặn (Gate 7b) | hàng `block: true` (tiếng sớm hơn hình `> 0.1 s`) không bao giờ ĐẠT, gate thoát `1` | `qa_sync.py` (`gate_pass`) |

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
- **Gói compositor / compile / export:** profile `studio_14` chọn được bằng `--audio-profile`, bộ làm sạch tường nhận alpha người (`person_alpha_u8`; skill không kèm RVM, matte tự tạo là `u2netp`), `fc_export.py` thăm dò (polling) thay vì chờ mù.

## 1-prev. Phiên Bản `v7.6.0` (giữ nguyên)

- **Hai look, chọn ở `SKILL.md` mục 3.4.1 (bảng so sánh ở mục 1.2):** **Look S (Studio)** là mặc định cho video talking head sản phẩm / thương hiệu / giải thích, theo ba master tham chiếu V19-V21; **Look D** (kênh `@__dviet`, screen-strip, profile `dviet`, `tiktok_loud`) chỉ khi người dùng yêu cầu rõ. Công thức: [`references/24_studio_look_recipe.md`](references/24_studio_look_recipe.md) (bản đồ 12 cảnh V21, mốc VFX-01..08, màu 4 hồi, cấu trúc âm thanh).
- **Hybrid `Option A × B` là trung tâm của Look S (từ v7.3, giữ nguyên):** **Option A1** `render_full_head_studio_card` (thẻ studio bo góc, đầu không bị cắt), **Option A2** `render_squircle_pip_window` (cửa sổ PiP squircle, nhường chỗ cho B-roll / sản phẩm / UI), **Option B** `render_bottom_flush_cutout` (cutout dính đáy, giữ trọn hai vai), kèm `clean_aroll_preserve_hair_crown` (giữ vòm tóc) và `verify_audio_voice_sync_guard` (khoá giọng khớp miệng). Thêm cảnh giấy sáng `#FAFAFA` (tối thiểu `2`, `~14 %`), neon blackout, số lớn trên lụa tối và hook B-roll toàn màn hình với presenter trong PiP: bảng chọn theo cảnh ở `SKILL.md` mục 3.5.1.
- **Bàn giao kép cho Look S:** **MP4 master** dựng bằng compositor (`1080×1920 @ 60fps`, `-14 LUFS`) **và** bản **`.fcproj` song song** để sửa trên timeline. Đây là ngoại lệ được khai báo của Rule A1; Look D và mọi lần chạy khác vẫn giao `.fcproj` trước. CLI `fast_studio_compositor.py --draft/--master` chỉ **re-encode**, không dựng plate studio.
- **`scripts/tools/studio_recipe.py` + `presets/studio_scene_recipe.json`:** trình lập cảnh không trạng thái (`--words words_tl.json --duration D --out scenes.json`): gán chế độ cho từng nhịp theo mẫu V21, giữ tối thiểu `2` cảnh sáng, trần A-roll phẳng `25 %`, không hai nhịp liền cùng thế giới màu, phát màu ngọc theo hồi. Nhận cả dict của probe lẫn mảng trần. Chỉ lập kế hoạch, bộ não (agent) quyết định.
- **Profile âm thanh `studio_14`** trong `presets/profile_overrides.json`: `-14.0 LUFS`, `-1.2 dBTP`, bộ giới hạn `-2.2`, ducking bật, `bgm_stops` được phép, tới `72` cue SFX. `platform` và `tiktok_loud` giữ nguyên số; `tiktok_loud` nay được ghi là **Look D** và các con số của nó **chưa kiểm** trên giọng thật. Nối `--audio-profile studio_14` vào `compile_and_verify.py` thuộc gói script.
- **Token `dviet`:** luật "một màu nhấn mỗi video" chỉ thuộc Look D (`palette.accent_policy: tokens`); Look S dùng `color_world`. Xung đột Iron Law 6 giải quyết rõ: swash hybrid = Look S, sans nén = Look D.

## 1a. Phiên Bản `v7.5.0` (giữ nguyên)

- **Bảng độ to cho TikTok (`compile_and_verify.py --audio-profile tiktok_loud`)**, lấy từ [`references/25_loudness_tiktok_vs_nle.md`](references/25_loudness_tiktok_vs_nle.md): `-12 LUFS` (cửa sổ `±0.5` trên `mix.wav`), trần true-peak `-1.0 dBTP` (bộ giới hạn `-1.2`), đỉnh giọng `-3.5..-1.5 dBFS`, nhạc nền dưới giọng `12..17 LU` (đích `14`), sàn "lời trên nhạc" `8 LU`, đỉnh SFX theo tầng `-4 / -7 / -10 dBFS`. Ngoài ra có nhạc nền khi không lời (`4..8 LU`), LRA `> 6` và short-term tối đa `> -7 LUFS`, **chỉ cảnh báo, không bao giờ FAIL**. Hồ sơ `platform` giữ nguyên (có test hồi quy). **Đã đo:** `-12 LUFS` của kênh, chênh `~14 LU` giọng/nhạc, và chiều của độ vượt đỉnh sau AAC (một tín hiệu tổng hợp, bộ mã AAC của ffmpeg, chỉ mang tính định hướng). **Suy ra, chưa kiểm trên giọng thật:** sàn `8 LU`, các tầng SFX, đoạn ép `0.25 s`, nhạc nền không lời `6 LU`. TikTok không công bố mức độ to đích, skill không khẳng định con số chuẩn hoá chính thức nào.
- **`scripts/tools/duck_keyframes.py`:** hàm thuần sinh keyframe ducking 4 điểm từ khoảng thời gian của từng từ (`0.35 s` trước từ đầu, hạ trong `0.25 s`, sâu `8 dB`, giữ qua khoảng nghỉ `< 1.5 s`, nhả `0.7 s`, tuỳ chọn vacuum `-32 dB` trong `0.4 s`, tối đa 1 lần / 20 s). Hằng số đọc từ `presets/sfx_micro_sync_rules.json`. Profile `tiktok_loud` vẫn để `no_ducking: true` cho tới khi nối vào bộ biên dịch.
- **`scripts/tools/filmcraft_cli.py`:** shim điều khiển FilmCraft qua `filmcraft --control` (cần binary `filmcraft` và màn hình X, nếu không có thì báo rõ rồi bỏ qua). `filmcraft-cli` chưa từng tồn tại, xem [`references/30_filmcraft_control_bridge.md`](references/30_filmcraft_control_bridge.md). Chuỗi font dự phòng theo vai trò ở preset font trong `presets/`, xem [`references/26_dviet_fonts.md`](references/26_dviet_fonts.md).
- **`scripts/tools/flicker_schedule.py` và opener `flicker`:** lịch nhấp nháy silhouette (loại A+B: plate matte đặt lên timeline). Công thức Premiere cho các hiệu ứng còn trong BACKLOG nằm ở [`references/27_premiere_recipes_to_filmcraft.md`](references/27_premiere_recipes_to_filmcraft.md).
- **Bảng "đạo diễn được hứa gì" (xem `SKILL.md` mục 4.3):** **A** = làm native trên timeline FilmCraft; **B** = làm bằng plate render sẵn; **C** = không khả thi (chất lượng Object Mask cho vật bất kỳ, planar tracking có xử lý che khuất, keycap 3D thật, Time Displacement native). Tile waveform, keycap, timeline NLE và chữ dán tường trên cảnh cầm tay vẫn nằm trong BACKLOG ([`references/23_dviet_profile_decisions_and_backlog.md`](references/23_dviet_profile_decisions_and_backlog.md)).

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
├── SKILL.md                                   # Chỉ dẫn trung tâm cho AI Agent: 1 Tổng quan → 2 Yêu cầu → 3 Quy trình → 4 Luật → 5 QA
├── README.md                                  # Tài liệu tổng quan, lịch sử phiên bản, cài đặt, biến môi trường, kiểm thử
├── install.sh                                 # Liên kết vào ~/.gemini & ~/.claude, chạy env_status + mọi tests/test_*.py
├── requirements.txt                           # Gói Python (ghim opencv-python-headless 4.x) + ghi chú node/chrome/ffmpeg/matte
├── docs/
│   └── TIEN_DO_SKILL.md                       # Nhật ký tiến độ & kiểm kê (tiếng Việt), mục v7.9.1
├── data/                                      # text_vi.json (1199 cặp glue NFC) & Haar Cascade nhận diện mặt
├── presets/                                   # 16 catalog JSON (Archetypes, Motion, Safe Zones, SFX, Tiers, Tokens @__dviet, Canvas, Look S, broll_lint_contract...)
├── references/                                # Tài liệu 01..30 (nhóm theo SKILL.md mục 2.7; 15–18 là lịch sử, 21 là spec hiện hành)
│   └── dviet_19/                              # INDEX.md + 17 file phân tích từng video (tên thư mục cũ, chứa 17 video)
├── scripts/
│   ├── env_status.py                          # Preflight: node >=22, Chrome, ffmpeg, FilmCraft >=0.13.0 + Xvfb, matte, font (bước 3.1)
│   ├── web_cinema_plate_engine.mjs            # Động cơ HTML/CSS/SVG/Canvas (Node >=22) kết xuất plate 60fps
│   ├── dviet_smooth_camera_engine.py          # Camera Bezier mượt, zoom preset, safe-box, luật C4, radial blur, LayeredFrameCompositor 3 mặt phẳng
│   ├── dviet_7706_typography_choreography.py  # Vũ đạo chữ @__dviet & Z-depth
│   ├── dviet_motion_canvas_engine.py          # Lane C: canvas chuyển động toàn màn hình
│   ├── vietanh_35_typography_engine.py        # 35 hiệu ứng xuất hiện chữ mở rộng
│   ├── ffskill_bridge.py                      # Cầu nối ffmpeg-skill (tuỳ chọn)
│   ├── vendor/
│   │   └── ovs_core/                          # Bản vendor của opa-video-studio (PROVENANCE.md, rules.json): edit_rules, spec_lint,
│   │                                          #   audio_levels, audit_sfx, apps/craft-handoff/tools/{fc_build, fc_build_fast, fc_export, craftctl}.py
│   └── tools/                                 # 6 công cụ lõi + CLI hỗ trợ:
│       ├── probe_and_align.py                 # Ingest, transcript, khoảng lặng (--tier fast|studio|full|auto)
│       ├── web_plate_builder.py               # Plate chữ động kt01..kt12, thẻ kính 3D và layout screen_strip / card_916 / profile_card
│       ├── typography_composer.py             # Vùng an toàn chữ Dual-Rail, lịch kinetic beat
│       ├── visual_blocks.py                   # 10 khối thị giác RGBA, HUD & hiệu ứng chuyển cảnh
│       ├── fast_studio_compositor.py          # Compositor Look S (Hybrid A×B, Hair-Safe, VoiceSyncGuard, pop-out, Cache)
│       ├── compile_and_verify.py              # Biên dịch .fcproj + 8 cổng kiểm định (--profile, --audio-profile, --strict-rules, --hook-gates)
│       ├── look_s_render.py                   # Dựng Look S từ scenes.json của studio_recipe (v7.9.1)
│       ├── studio_recipe.py                   # Trình lập cảnh Look S + hàm kiểm hook / nhịp / chữ / nguồn B-roll
│       ├── motion_gate.py                     # Cổng đo trên MP4 đã kết xuất: chuyển động nền, flash + hàm đo thẻ pop-out / chữ
│       ├── dviet_text.py                      # Sự kiện chữ theo vai trò -> track chữ (token @__dviet)
│       ├── silence_cut.py / speed_media.py    # Cắt lặng và tốc độ trước khi ingest (--fps 60 cho Look S)
│       ├── sfx_auto.py / qa_sync.py / sfx_shift.py  # Kế hoạch SFX, đo đồng bộ, Gate 7b dịch một lần
│       ├── spec_from_plan.py / broll_from_video.py  # Plan -> .craft.json, kế hoạch B-roll & lint prompt (broll_lint_contract.json)
│       ├── filmcraft_cli.py                   # Shim điều khiển FilmCraft qua `filmcraft --control` (v7.5.0)
│       ├── flicker_schedule.py                # Lịch nhấp nháy silhouette cho opener `flicker` (v7.5.0)
│       ├── duck_keyframes.py                  # Keyframe ducking nhạc nền 4 điểm, hàm thuần (v7.5.0)
│       └── fc_export.py                       # Xuất .mp4 từ .fcproj (chỉ các trường hợp của Rule A1)
├── templates/
│   └── edit_plan_viewer.html                  # Giao diện HTML xem & duyệt Edit Plan trực quan
└── tests/                                     # 19 bộ kiểm thử, mỗi bộ chạy độc lập và thoát 0 khi đạt (danh sách ở mục 4)
```

---

## 3. Yêu Cầu Môi Trường & Cài Đặt Nhanh

Yêu cầu (kiểm bằng `python3 scripts/env_status.py [--json] [--strict]`; `--strict` thoát `1` khi thiếu mục bắt buộc):

| Thành phần | Tối thiểu | Dùng cho |
|---|---|---|
| Python | 3.10+ (venv `~/.venvs/video-skills`) | tất cả công cụ `.py` |
| Node.js | `>= 22` | `web_cinema_plate_engine.mjs` (plate 60fps) |
| Chrome / Chromium | bản headless bất kỳ trên `PATH` | kết xuất HTML5/CSS3/SVG của plate |
| FFmpeg + ffprobe | 6.1+ | ingest, render, đo âm thanh |
| FilmCraft | `>= 0.13.0` (bên trong dùng `wgpu 0.20.1`) | biên dịch `.fcproj` (Gate 4), xuất MP4 |
| Xvfb (hoặc Xephyr) | bất kỳ | màn hình ảo cho FilmCraft; không bao giờ dùng `:0` |
| Matte người | `u2netp` (`~/.rembg/models/u2netp/u2netp.onnx`), dự phòng `birefnet-portrait` (chậm) | cutout, thẻ pop-out, kẹp chữ sau người (Cranial Lock). Skill **không** kèm RVM |
| Font | Be Vietnam Pro, Playfair Display (tùy chọn có fallback: SVN-Aaron, DFVN West West Condensed) | chữ tiếng Việt chuẩn NFC |

### 3.1 Biến môi trường

| Biến | Tác dụng | Đọc ở |
|---|---|---|
| `PFD_FONT_DIR` | thư mục font ưu tiên | `web_plate_builder.py`, `fast_studio_compositor.py` |
| `PFD_CACHE_DIR` | gốc cache của skill (cache âm học SFX, bản sao lưu `.fcproj`), mặc định `~/.cache/pro-filmcraft-director` | `probe_and_align.py`, `compile_and_verify.py` |
| `CHROME_BIN` | đường dẫn Chrome / Chromium | `web_cinema_plate_engine.mjs`, `install.sh` |
| `NODE_BIN` | đường dẫn Node `>= 22` | `web_plate_builder.py` |
| `FFMPEG_BIN` | đường dẫn ffmpeg cho động cơ plate | `web_cinema_plate_engine.mjs` |
| `PFD_MATTE_MODEL` | file `.onnx` của matte người | `env_status.py`, `fast_studio_compositor.py`, `install.sh` |
| `U2NETP_ONNX_PATH` | đường dẫn `u2netp.onnx` | `fast_studio_compositor.py` |
| `PFD_LOOK_S_POPOUT` | `1` bật thẻ pop-out thay thẻ bo góc mặc định | `fast_studio_compositor.py` |
| `PFD_GLOW_SCALE` | hệ số quầng sáng chữ của plate | `web_plate_builder.py` |
| `PFD_WHISPER_THREADS` | số luồng faster-whisper | `probe_and_align.py` |
| `TRANSCRIPT_MS_JSON` | transcript theo ms cho lịch chữ | `typography_composer.py` |
| `OPA_VIDEO_STUDIO_DIR` | thư mục skill `opa-video-studio` (khi không dùng bản vendor) | `compile_and_verify.py` |
| `PFD_OVS_DIR` | thư mục `ovs_core` thay bản vendor | `compile_and_verify.py`, `fc_export.py`, `filmcraft_cli.py`, `env_status.py` |
| `CRAFT_DISPLAY` | màn hình X cho FilmCraft (mặc định `:93`) | `filmcraft_cli.py`, `compile_and_verify.py`, `craftctl.py` (vendor) |
| `FILMCRAFT_VENV_PYTHON` | Python của venv FilmCraft | `compile_and_verify.py`, `install.sh` |
| `HF_HOME` | cache model Hugging Face (model whisper mặc định `small`; `HF_HUB_CACHE` được ưu tiên) | `env_status.py` (faster-whisper cũng đọc) |

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
~/.venvs/video-skills/bin/python3 scripts/tools/web_plate_builder.py --self-test
~/.venvs/video-skills/bin/python3 scripts/dviet_smooth_camera_engine.py --self-test
```

| Bộ test | Kiểm |
|---|---|
| `test_skill_v73.py` | nền: cú pháp, đường dẫn di động, `>= 11` preset, `>= 28` tài liệu, hàm lõi compositor, VoiceSyncGuard (không gắn phiên bản, `>= 7.6.0`) |
| `test_dviet_docs.py` | chỉ mục 17 video, nhãn phiên bản (đọc từ `SKILL.md`), link của `SKILL.md`, cấu trúc mục 3.1 / 3.5 / 3.8.1 / 4.3, token, preset, `dviet_text`, layout, zoom |
| `test_studio_recipe.py` | `studio_recipe` (+ hook 0-5 s, max hold, reset mỗi 5 s, nguồn B-roll, chữ-giọng, vùng an toàn, cỡ chữ, sàn chuyển động), preset, `studio_14` |
| `test_skill_v76_fixes.py` | hồi quy v7.6: rò chữ demo kt05/kt06, tràn kt05, `--words` dạng probe doc |
| `test_skill_v77.py` | gói S1: thẻ pop-out, bộ làm sạch tường có alpha, export, polling |
| `test_skill_v78.py` | gói S1 v7.8.0: thẻ pop-out nét, sân khấu sản phẩm, glint, `motion_gate`, cổng chữ tối thiểu |
| `test_skill_v79.py` | lỗi bản dựng v4 thành cổng: mép thẻ pop-out, đỉnh tóc, flash (kế hoạch + bản dựng), chữ đọc được |
| `test_text_legibility_v79.py` | khoảng cách từ khi blur-in / scale-in trên plate Chrome và FilmCraft (**chạy lâu, > 5 phút; chạy cuối**) |
| `test_audit_core_v791.py` | v7.9.1: Gate 3 FAIL / SKIPPED, video 0 byte / hỏng, không có tiếng, timeout giải mã, CLI `studio_recipe`, help `tiktok_loud`, `--display` |
| `test_look_s_driver_v791.py` | v7.9.1: đường compositor Look S (dọn ffmpeg con, ghép plate, kiểm hình học, cache matte, font fallback, NFD) |
| `test_portability_v791.py` | v7.9.1: chữ `G2` theo sàn `64 px`, trần flash và khoảng cách vacuum `20 s`, `tiktok_loud` `-1.0 dBTP` / `14 dB`, một hợp đồng lint B-roll, tìm Chrome, runner plate, xoá metadata, font, `rules.json` vendor |
| `test_loudness_v75.py` | bảng độ to `tiktok_loud`, hồi quy `platform`, verdict trên clip tổng hợp `<= 3 s` |
| `test_ducking.py` | `duck_keyframes`: đơn điệu, độ sâu, gộp khoảng nghỉ `< 1.5 s`, tất định |
| `test_flicker_schedule.py` | `flicker_schedule` và khoá `opener` của `spec_from_plan` |
| `test_filmcraft_cli.py` | shim `filmcraft_cli`: ticks, render flow, mã thoát |
| `test_effect_presets.py` | preset hiệu ứng gốc thử nghiệm và macro vanish / clone-appear; tài liệu 23 / 27 |
| `test_fonts_vi.py` | phủ glyph tiếng Việt của chuỗi font trong `dviet_style_tokens.json` |
| `test_ports.py` | `silence_cut`, `speed_media`, `sfx_auto`, `qa_sync`, `sfx_shift` |
| `test_stability.py` | lõi ổn định: banner và hằng phiên bản khớp `SKILL.md`, vendor, ví dụ tài liệu 21 |
