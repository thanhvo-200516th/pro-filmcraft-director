# 24 — Công thức Look S (Studio): bản đồ V21, mốc thời gian V19, màu 4 hồi, cấu trúc âm thanh (v7.6.0)

Tài liệu này gom công thức dựng của ba bản master tham chiếu do skill cũ làm từ cùng một video nguồn (`1080×1920 @ 60fps`, `40.6 s`): **V19** (Dviet VFX SFX BeatDrop), **V20** (Studio Option A Fast), **V21** (Hybrid A×B VoiceSync). Đây là **Look S**, mặc định cho video talking head sản phẩm / thương hiệu / giải thích. **Look D** (kênh `@__dviet`, screen-strip, profile `dviet`) chỉ dùng khi người dùng yêu cầu rõ. Đi cùng [`20`](./20_v73_hybrid_ab_voicesync_and_hairsafe_compositor.md) (compositor, A1/A2/B, VoiceSyncGuard) và [`23`](./23_dviet_profile_decisions_and_backlog.md) (quyết định profile `dviet`). Dữ liệu chạy được: [`presets/studio_scene_recipe.json`](../presets/studio_scene_recipe.json); trình lập cảnh: [`scripts/tools/studio_recipe.py`](../scripts/tools/studio_recipe.py).

Quy ước: **[ĐO]** = lấy từ tài liệu phân tích của chính bản master; **[ƯỚC]** = người viết công thức chọn, chưa đo. Thời điểm lấy từ hai walkthrough khác nhau (V19 và V21) **lệch nhau tới ~1 s** ở vài cảnh (xem cột ghi chú): bản master mới là chuẩn, không phải bảng này.

---

## 1. Bản đồ cảnh V21 (`S01A..S12C`, mỗi cảnh một chế độ A1 / A2 / B)

Nguồn: walkthrough V21, mục 2 điểm 3. `Start V21` chỉ có ở 8 cảnh được nêu giờ; `Khoảng V19` lấy từ bảng VFX của V19.

| Cảnh | Chế độ | Nội dung | Start V21 | Khoảng V19 / ghi chú |
|---|---|---|---|---|
| S01A | **A2** | Hero Serum, PiP vàng, chai dịch trái `-34 px` ở `00:01` | | `0 .. ~3.4` [ƯỚC] |
| S02 | **B** | 3D Polaroids | 04.95 | flash màn trập `3.39 / 3.65 / 3.89` |
| S03 | **A1** | Silver Paper (nền sáng) | 06.42 | `5.83 .. 8.85` (VFX-01) |
| S04 | **B** | Neon Blackout, giữ trọn vai phải | 11.82 | `10.92 .. 12.28` (S04B, VFX-02) |
| S05A | **A2** | Chai Hồng Glitch ("giả trân") | | `12.28 .. 13.00` glitch (VFX-03), radial `13.46` |
| S06 | **A1** | Mint Paper (nền sáng) | 16.25 | `15.07 .. 18.95` (VFX-01) |
| S07 | **A2** | Kính mờ Bento ("3 bước") | | `18.95 ..` (VFX-04) |
| S08 | **B** | Bước 1, Dark Silk | 24.02 | |
| S09 | **B** | Bước 2, đèn `5600K` | 27.15 | cut `27.48` |
| S10 | **A2** | Softbox | | không có giờ trong tài liệu [ƯỚC `~29.0`] |
| S11 | **A2** | Ống kính `85mm`, đã tách chữ khỏi số `3` lớn | | `30.65 .. 34.00` |
| S12A | **A1** | Ivory Paper (nền sáng) | 35.35 | `34.00 .. 35.78` (VFX-01) |
| S12B | **A2** | Khung 3D Prompt (`isometric_3d_prompt_browser`) | | `35.78 .. 37.37` |
| S12C | **B** | CTA kết | 39.20 | |

Ba cảnh sáng (S03, S06, S12A) ≈ `8.7 s` ≈ `21 %` thời lượng [ĐO từ khoảng V19]. Công thức yêu cầu tối thiểu `2` cảnh sáng, khoảng `14 %`.

**Bảng chế độ của trình lập cảnh** (khác bảng V21 ở chỗ tách cảnh theo *vai trò*): `H` = hook B-roll toàn màn hình + PiP (render của A2); `P` = A1 trên giấy `#FAFAFA`; `N` = neon blackout (S04B); `S` = số lớn trên lụa tối (render của B, S08 / S09). Lưới mặc định của `studio_recipe.py` có `15` mục: 14 cảnh trên cộng `S04A` (`8.85 .. 10.92`, khoảng trống của tài liệu V19, [ƯỚC] là thẻ chữ A1). Mốc `S10` cũng là [ƯỚC].

## 2. Mốc thời gian V19 (VFX-01..08)

| VFX | Mốc (`60fps`) | Hiệu ứng |
|---|---|---|
| VFX-01 | `5.83–8.85` (S03), `15.07–18.95` (S06), `34.00–35.78` (S12A) | Đảo cực nền sáng + đầu nhô ra khỏi viền khung (`~160 px`), mực chữ `#14171F` |
| VFX-02 | `10.92–12.28` (S04B) | Neon blackout nền `#050507`, viền `#FF4528` / `#FF6B1A`, bùng `+30 %` ở khe `11.80` |
| VFX-03 | `12.28–13.00` (S05A), `25.14` | RGB glitch `±14 px`, rung `28 Hz`, xé 7 lát |
| VFX-04 | `18.95–27.48`, `30.65–34.00`, `35.78–37.37` | Lụa tối + số lớn `1 • 2 • 3` (`320 px`) |
| VFX-05 | `3.28`, `3.39 / 3.65 / 3.89`, `5.83`, `15.07`, `25.73`, `27.48`, `34.00`, `37.37` | Flash trắng, film-burn hổ phách, light-leak (`Screen`) |
| VFX-06 | whip `8.85, 18.95, 30.65, 35.78`; radial `13.46, 13.95, 14.26, 29.48` | Whip-pan blur, radial zoom-blur 8 lớp |
| VFX-07 | S01, S07, S08, S11, S12B | Lưới tọa độ HUD, nhuộm theo chương, tránh mặt |
| VFX-08 | S01, S02, S07, `26.52`, `38.85` | Quầng sáng backlight (`5600K` ở "ánh sáng", vàng ở "PROMPT") |

**Điểm cắt tham chiếu:** `1.33`, `3.4–3.9`, `5.8`, `8.85`, `12.28`, `13.47`, `15.05`, `18.95`, `27.48`, `30.65`, `34.0`, `35.78` giây.

## 3. Màu 4 hồi (`semantic_4act_jewel`)

Nguồn: bảng "Bảng Màu Ngọc Quý 4 Hồi" trong tài liệu phân tích `dviet_19videos_complete_forensics_and_roundtable.md` (chữ trắng `#FAFAFA` + đúng một màu nhấn của hồi). Lưu ý: tài liệu phân tích này (và hai walkthrough V19 / V21 nêu ở mục cuối) **không** kèm trong repo; bảng dưới đây là bản chép duy nhất trong skill.

| Hồi | Khoảng | Màu nhấn trên nền tối | Mực trên giấy `#FAFAFA` |
|---|---|---|---|
| 1 Hook | `0 – 11.0` | Amber Champagne Gold `#F5C451` | `#D97706` |
| 2 Nỗi đau | `11.0 – 15.2` | Cinema Crimson Coral `#FF4D5E` | `#E11D48` |
| 3A Bước 1 | `15.2 – 25.8` | Luminous Emerald Mint `#34D399` | `#059669` |
| 3B Bước 2 và 3 | `25.8 – 34.2` | Optical Ice-Cyan `#7DD3FC` (qua tungsten ấm) | `#2563EB` |
| 4 CTA | `34.2 – 40.6` | Radiant Gold `#FACC15` (+ thẻ Emerald) | `#D97706` |

Cột "mực trên giấy" là bốn mực ngọc của `SKILL.md` (`#059669 / #2563EB / #E11D48 / #D97706`), ghép theo hồi bởi người viết công thức [ƯỚC]. Preset dùng mốc `15.05` và `34.0` (nhịp thả nhạc và điểm cắt V19) thay cho `15.2` và `34.2` của tài liệu. **Màu của chương thắng luật "một màu nhấn mỗi video"** (luật đó chỉ thuộc Look D). Mỗi cảnh chỉ một màu nhấn, hai cảnh liền nhau không cùng "thế giới màu".

## 4. Cấu trúc âm thanh (profile `studio_14`)

- **Mức:** `-14.0 LUFS` / `-1.2 dBTP` (V19 đo `-14.0 / -1.3`, V21 đo `-14.1 / -1.2`) [ĐO]. Giới hạn `-2.2 dB`. Ducking bật; `meta.bgm_stops` được phép.
- **Chân không `-inf dB`:** `11.80–12.28` (`0.483 s`, trước "giả trân") và `14.95–15.08` (`130 ms`, kèm riser đón điệp khúc).
- **Drop:** `15.08` (chorus nổ đúng chớp trắng mở giải pháp). Nhạc 2 hồi: `0–11.80` dẫn nhập, `12.28–15.08` sub-pulse, `15.08–40.63` chorus.
- **SFX:** `72` cue `48 kHz / 24-bit` trên `6` rãnh không chồng lấn `A3..A8`, khớp `< 30 ms` với `transcript_ms.json` (V21).
- **Chưa kiểm:** độ sâu ducking và khoảng nhạc dưới giọng của `studio_14` **không** được đặt trong preset (theo luật `platform`); chỉ mức to và đỉnh là đo từ master.

## 5. Quy tắc dựng Look S (tóm từ SKILL.md, mục Step 3b)

Tối thiểu `2` cảnh sáng `#FAFAFA` (`~14 %`); A-roll phẳng toàn khung `<= 25 %`; không hai nhịp liền cùng thế giới màu; B-roll toàn màn hình, sạch, presenter ở PiP, không che mặt, nội dung khớp nghĩa nhịp; md5-dedup tài sản Flow tải về. Master dùng chế độ `--master` (`1080×1920 @ 60fps`; nháp `--draft` = `540×960 @ 30`; không có cờ `--fps`). Nguồn `720p`: phóng sẵn trong thẻ, **không** dùng scale FilmCraft `150–168 %`. Khung hình V14: mặt thấp `y ≈ 62 %`, khoảng trống đầu `105–115 px`; góc Left-Third `136 %` bị loại trừ khi nguồn `< 1080p` hoặc đầu phóng `> 1.18x`. Kiểm sọ não: `compile_and_verify.py --context workspace_context.json`.

Quyết định (a) của [`23`](./23_dviet_profile_decisions_and_backlog.md) (sans nén + halation) thuộc **Look D**; **Look S dùng swash hybrid và màu ngọc theo hồi**.

## 6. Tài liệu phân tích nguồn

Thư mục `file phan tich` (9 tệp, cạnh thư mục làm việc của bản dựng mẫu; không nằm trong skill): `dviet_19videos_complete_forensics_and_roundtable.md`, `dviet_45582_frames_and_universal_skill_blueprint.md`, `dviet_7707_channel_vs_skill_roundtable_report.md`, `dviet_v71_kinetic_typography_roundtable_and_v18_walkthrough.md`, `skill_architecture_blueprint.md`, `universal_studio_v70_upgrade_walkthrough.md`, `v19_dviet_redirection_vfx_sfx_beatdrop_walkthrough.md`, `v20_option_a_8fixes_and_v72_speed_walkthrough.md`, `v21_hybrid_ab_voicesync_and_github_skill_package.md`.

## 7. Điều tài liệu này KHÔNG làm

- Không đo lại ba bản master: thời điểm là từ walkthrough, lệch nhau giữa V19 và V21 (S03 `5.83` / `6.42`, S06 `15.07` / `16.25`, S12A `34.00` / `35.35`).
- Không có số đo thật cho S10, S04A và cách ghép màu hồi ↔ mực trên giấy (đều [ƯỚC]).
- `studio_recipe.py` chỉ **lập kế hoạch** (scenes.json); nó không render. Render là chuỗi gọi trong Step 3b của `SKILL.md`.
- Nối `--audio-profile studio_14` vào `compile_and_verify.py` thuộc gói script, không thuộc tài liệu này.
