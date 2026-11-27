# 23 — Quyết định profile `dviet` và BACKLOG (v7.4.0)

Tài liệu này ghi các quyết định có nguồn gốc (provenance) cho profile `dviet`, và danh sách xếp hạng những hiệu ứng quan sát được nhưng **chưa cài đặt**. Nguồn dữ liệu: [`dviet_19/INDEX.md`](./dviet_19/INDEX.md) và 17 file con. Token chạy được: [`../presets/dviet_style_tokens.json`](../presets/dviet_style_tokens.json).

Xem thêm [`24_studio_look_recipe.md`](./24_studio_look_recipe.md) (công thức Look S, v7.6.0).

Quy ước: **[ĐO]** = đo trực tiếp; **[ƯỚC]** = ước lượng. Mọi mục "ƯỚC" không phải giá trị chuẩn.

---

## 1. Quyết định

### (a) Sans nén Nov-2026 + halation thay cho drop shadow; swash hybrid chỉ giữ cho `script_accent`

- Quyết định: profile `dviet` dùng một họ sans nén ngang làm chữ chính, và **halation (glow cùng màu chữ, bán kính 14-22 px)** thay cho đổ bóng đen. Luật `swash_initial_hybrid` (chữ cái đầu ASCII dạng swash + phần còn lại Be Vietnam Pro / Playfair Italic) **chỉ còn áp dụng cho role `script_accent`**; mọi role khác không dùng swash.
- Provenance: 7706183278461570356 (2026-11-09) và 7707653827016674580 (2026-11-13) dùng sans đồng nhất, glow cam 12-20 px (7706183) và neon mint glow 15-25 px (7707653), không còn serif Playfair hay script ở hai video tháng 11 [ĐO bằng quantize + quan sát khung]. Bảng "typography_shift" của bản phân tích ovs (`dviet-style.json`, mục `nov_2026_updates`) cho scale_x 78-85 %, tracking -45..-70 [ƯỚC, đo trên 2 video]. Các video 07-10/2026 vẫn dùng bóng đen mềm (7664447, 7666801) và chữ thảo (7664447, 7666801, 7667598).
- Hệ quả trong token: `fonts.condensed_sans` (family `Barlow Condensed`, fallback `Be Vietnam Pro`), `shadow_policy: halation`, `script_accent.swash_hybrid: true` và `swash_hybrid` bị `false` ở các role khác. Nếu máy không có font nén, `dviet_text.py` in cảnh báo và dùng `Be Vietnam Pro`; không lỗi.
- Độ tin cậy: kích thước font quy từ chiều cao x trung vị, sai số ±10-15 % [ƯỚC].
- Phạm vi theo look (v7.6.0): quyết định (a) áp cho **Look D** (kênh `@__dviet`, profile `dviet`). **Look S** (Studio, mặc định cho talking head sản phẩm / thương hiệu / giải thích) dùng **swash hybrid** và **màu ngọc theo hồi** (`semantic_4act_jewel`) như các master V19-V21: xem [`24_studio_look_recipe.md`](./24_studio_look_recipe.md). Luật 6 trong `SKILL.md` (Iron Law) giải quyết xung đột này: swash hybrid = Look S, sans nén = Look D.

### (b) Xung đột Instrument Serif / De Fonte

- Mâu thuẫn: `presets/visual_archetypes_catalog.json:190` cấm `Instrument Serif` trong `forbidden_fonts_vi` (thiếu glyph tiếng Việt, theo kiểm tra 41 ký tự thiếu của ovs); nhưng tác giả @__dviet **dạy** Instrument Serif và De Fonte trong thẻ font của 7677448217667063061 ("Playfair Display, Instrument Serif, IvyPresto / Whisper, De Fonte").
- Quyết định: **lệnh cấm giữ nguyên cho mặc định** (mọi profile, mọi role). Chỉ **cho phép** dưới profile `dviet`, role `font_specimen` (thẻ minh hoạ chính tên font đang được nói tới), và chỉ cho đúng chữ tên font (ASCII, không dấu tiếng Việt), không bao giờ cho caption hay hero.
- Provenance: 7677448217667063061 (thẻ font 37-52 s; hệ font do chính tác giả nêu). Token: `font_roles.font_specimen.allow_banned_fonts: ["Instrument Serif", "De Fonte"]`, `scope: profile dviet`.
- Việc còn lại: tệp `visual_archetypes_catalog.json` không thuộc gói P3, nên lệnh cấm ở đó không đổi; cơ chế ngoại lệ do bộ kiểm profile của P1 đọc từ token này (chưa có test end-to-end ở P3).

### (c) Cranial Lock và chữ sau đầu (text-behind-head)

- Quy tắc: một clip chữ nằm **dưới** lớp người đã tách nền (RVM) tính là **kẹp (sandwiched)**, không tính là chồng lên mặt/tóc. Lớp chữ trên lớp người vẫn bị kiểm Cranial Lock `0 %` như cũ.
- Provenance: 7693026626333871381 ("talking head VIDEO" bị đầu che), 7706183278461570356 (chữ sau chân người, sau vai), `presets/dviet_pattern_catalog.json` mục `dviet_text_behind_subject`, và `atomic_motion_library.json` mục `text_behind_subject` (đã tồn tại, `occlusion_target_pct [30, 50]`).
- Phạm vi: đây là **quy tắc ghi nhận**; việc đếm chồng lấn theo thứ tự lớp do `compile_and_verify.py` đảm nhiệm (không thuộc P3, không sửa ở đây).

### (d) Mastering to là profile opt-in, trần -0.5 dBTP

- Quyết định: loudness `tiktok_loud` (khoảng -10.7 .. -12.6 LUFS, peak tới +3 dBFS ở nguồn) là **tuỳ chọn**, bật bằng `compile_and_verify.py --audio-profile tiktok_loud` (gói P1). Trần true-peak khi bật: **-0.5 dBTP** (không noi theo +3 dBFS của nguồn: đó là clip). Mặc định giữ `platform` (-14 LUFS, -1.5 dBTP).
- Provenance: 13 trong 17 video nằm trong -10.7 .. -12.6 LUFS, 10 video có peak > 0 dBFS, cao nhất +3.0 dBFS (7670574911680777492); ngoại lệ nhỏ: 7664835388476755220 (-20.1) và 7707653827016674580 (-16.7) [ĐO ebur128].
- Phạm vi look (v7.6.0): `tiktok_loud` là mastering của **Look D** và các con số của nó **chưa kiểm** trên giọng thật; Look S dùng profile `studio_14` (`-14.0 LUFS / -1.2 dBTP`), xem [`24_studio_look_recipe.md`](./24_studio_look_recipe.md).
- Token: `audio.tiktok_loud` chỉ là **tham chiếu** (`lufs_range`, `tp_cap_dbtp`, `enforced_by: P1`).

### (e) Film-burn / white-flash chỉ mở cho profile `dviet`, có cap

- Mâu thuẫn: `compile_and_verify.py` có gate `CRI100_FORBIDDEN_WARM_FILM_BURN` và `industry_profiles.json` có `warm_film_burn_veto` cho Dental / Skincare / Nail. Kênh @__dviet dùng flash cam, light leak, flash trắng ở 7 video.
- Quyết định: các preset `color_wash_multi_0p6s`, `film_burn_perf_5f`, `light_leak_overlay`, `white_flash_0p25s`, `vertical_roll_slide`, `orange_ghost_pre_cut_5f`, `vacuum_32db_0p4s` (trong `atomic_motion_library.json`) mang `profile_scope: ["dviet"]`, `max_duration` và `caps` (tối đa số lần mỗi phút). Chúng **không hiệu lực** ngoài profile `dviet`. Skin có veto cứng (`warm_film_burn_veto` trong `industry_profiles.json`: `luxury_skincare`, `dental_clinic`, `beauty_spa`) **vẫn thắng** profile: dviet không mở film-burn trên Dental CRI-100. `presets/format_modes_catalog.json` có khối `profile_vetoes` mô tả việc này.
- Phạm vi P3: chỉ **dữ liệu và tài liệu**. Thực thi nằm ở gói P1: bật bằng `compile_and_verify.py --profile dviet` (mặc định `--profile default`), đọc `presets/profile_overrides.json`. P3 không sửa `compile_and_verify.py`.
- Provenance: 7667598741888634132 (film-burn cam 7.65-7.77 s), 7664969137445276949 (color-wash 7.07-7.67 s), 7669054598971133204 (flash cam/đỏ 3.0-3.6 s), 7669758857471741204 (flash trắng 7.6 s), 7672413018575146261 (vertical roll + flash trắng), 7683763922234641684 (flash cam-vàng 16.70-16.93 s), 7666801391284964628 (ghost ngả cam trước cut). Các thông số chi tiết là [ƯỚC].

### (f) Các quyết định nhỏ khác

- `4-Cut Grammar` giữ nguyên là luật cứng. Không cổng (port) quy tắc C1 của ovs.
- Zoom: giá trị trong preset là [ƯỚC] đã làm tròn theo bậc (1 % scale, 0.05 s). Quy tắc C4: một đoạn nói liền >= 4 s phải có khoá zoom (hàm `c4_zoom_keys`).
- Các preset zoom mới không đổi mặc định cũ; chỉ dùng khi chọn trực tiếp.

---

## 2. BACKLOG xếp hạng (chưa cài đặt)

Xếp theo số video chứa hiệu ứng (nhiều trước), rồi theo giá trị dựng/ chi phí. "n" = số video trong 17. Cột cuối "Trạng thái v7.4" ghi đúng cái đã có: **implemented** = công cụ chạy và có test tổng hợp, **experimental** = công thức/ preset gốc FilmCraft đã sinh được dòng spec hợp lệ nhưng hành vi trong app chưa kiểm (`behaviour_unverified_in_app`), **backlog** = chưa làm. Chi tiết và danh sách việc chưa kiểm: [`27_premiere_recipes_to_filmcraft.md`](./27_premiere_recipes_to_filmcraft.md) mục 8.

| Hạng | Hiệu ứng | n | Video | Cần gì để làm | Trạng thái v7.4 |
|---|---|---|---|---|---|
| 1 | Silhouette flicker | 4 trực tiếp, 6 kể cả biến thể | 7664447, 7664633, 7664835, 7664969; biến thể 7668334, 7672413 | Trích clean plate khi chủ thể rời khung; hàm fill matte kem/ trắng + lịch flicker theo frame @60 (2 frame mỗi trạng thái); đường cong đảo sáng. Hạ tầng matte có sẵn (`predict_u2netp_alpha_u8` trong `fast_studio_compositor.py`) | implemented (lịch + lệnh matte + clean plate + khoá `opener` của `spec_from_plan.py`: `flicker_schedule.py`) / experimental (hành vi trong app); chưa có lệnh một dòng matte -> `.mov` cho cả shot |
| 2 | Planar tracking (chữ dán tường theo phối cảnh) | 4 | 7668334, 7669054, 7672413, 7677448 | Tracker mặt phẳng hoặc đặt tay 4 điểm; render chữ perspective trong plate | backlog |
| 3 | Clean-plate vanish (người biến mất) | 4 | 7672413, 7668334, 7669054, 7664447 | Glow 4-5 f + negative 4 f + nền trắng mờ 0.5 s; cần clean plate | experimental (`vanish_rows`, preset `vanish_glow_negative_white`; cần clean plate + matte; `profile_scope` dviet) |
| 4 | Sticker sparkle (sao 4 cánh, vòng teal) | 2 | 7670574, 7669054 | Thư viện sprite + lịch xuất hiện | experimental (`sparkle_sprite_pop_6f`; PNG sao chưa kèm theo) |
| 5 | Chữ cong bám đầu theo tracker | 2 | 7706183, 7707653 | `kt11` có `svg_arc` nhưng không có tracker đầu | backlog |
| 6 | Clone / phân thân | 1 | 7668334 | Nhiều lượt quay trên plate, mask mềm 5-10 px, flicker khi xuất hiện | experimental (`clone_appear_rows`, preset `clone_appear_flicker`; hai bản chồng/ đi qua nhau bị từ chối vì cần matte che khuất) |
| 7 | Waveform SFX tile | 1 | 7669758 | Thẻ nhãn SFX có sóng âm | backlog |
| 8 | Constellation text (renderer plate) | 1 | 7664835 | Tham số bố cục đã có trong token; chưa có renderer plate (chỉ `dviet_text.py` đặt vị trí chữ) | backlog |
| 9 | Pixel stretch / slit-scan | 1 | 7670574 | Filter smear ngang theo cột pixel | backlog (Time Displacement/ slit-scan native bị từ chối; chỉ làm được bằng B) |
| 10 | Lật dọc (vertical flip stack) | 1 | 7693026 | Mirror/ flip xếp chồng 10.7-13.0 s | experimental (`vertical_flip_stack_native`) |
| 11 | Warp cong (curved panorama warp) | 1 | 7693026 | Warp 3 frame ở 42.2 s | experimental (`curved_warp_lens_wave_3f`) |
| 12 | RGB fringe (tách kênh) trên chữ | 1 | 7688934 | Tách kênh 2-3 frame tại 12.85 s | experimental (`rgb_fringe_text_native`, mở rộng `glitch_rgb_split`, không thay nó) |
| 13 | Keycap 3D tile | 1 | 7707653 | Ô phím 3D chứa chữ (20.5-21.8 s) | backlog |
| 14 | Layout chưa dựng | 1-2 mỗi loại | xem dưới | | backlog |

Layout chưa dựng (số video): timeline-playhead split "raw | edited" cuộn ngang (1: 7664633), khung ngắm `[ đặt máy quay ]` + chấm rec (2: 7664447, 7707653), thẻ palette chip + hex (1: 7677448), thẻ font specimen (1: 7677448), quay màn hình bằng camera nghiêng có DoF (2 rõ: 7664447, 7670574), mockup điện thoại có chữ hoà bằng Overlay (2: 7683763, 7667598), chữ bị vật tiền cảnh che (1: 7706183). Các layout `screen_strip`, `card_916`, `profile_card` đã làm ở v7.4.0 (xem INDEX mục 3).

Ghi chú: các số đếm là từ nội dung file con; số cut và hệ số zoom là [ƯỚC] (xem INDEX).

### 2.1 Link hỏng cần chủ sở hữu sửa (không thuộc phạm vi P3)

Hai tài liệu tham chiếu có đường dẫn không tồn tại. P3 không sở hữu chúng nên **không sửa**, và SKILL.md **không** chứa các link này:

- `references/12_ffmpeg_skill_42_tools_integration.md` -> `../scripts/04_qa_4pass_inspector.py` (không có file).
- `references/13_dviet_19_videos_smooth_zoom_and_pacing_mastery.md` -> `../scripts/build_v14_dviet_smooth_master.py` (không có file).

---

## 3. Điều v7.4.0 KHÔNG làm

- Không cài renderer plate cho hiệu ứng ở bảng backlog (waveform, keycap, timeline NLE, constellation...). Phần đã làm ở gói PKG-C (silhouette flicker dạng công cụ không trạng thái, và các preset/ macro gốc FilmCraft ở cột "Trạng thái v7.4") không render hay dựng video nào; mọi hành vi trong app còn `behaviour_unverified_in_app`.
- Không giả lập hiệu ứng loại C: Time Displacement, chất lượng AI Object Mask, planar tracking có xử lý che khuất, extrude 3D bị từ chối bằng lỗi rõ ràng (`flicker_schedule.refuse_c_class`).
- Không đổi `compile_and_verify.py`, `probe_and_align.py`, `fast_studio_compositor.py`, `typography_composer.py`.
- Không xác nhận bằng nghe: mọi nhận định SFX là [ƯỚC].
- Không xuất `.mp4` mặc định (Rule A1): chỉ khi người dùng yêu cầu hoặc ở chế độ draft, qua `scripts/tools/fc_export.py`.
