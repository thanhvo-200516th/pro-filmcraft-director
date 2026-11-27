# Chỉ mục 17 video @__dviet (INDEX) — v7.4.0

Chỉ mục duy nhất cho 17 file phân tích từng video trong thư mục này (`<id>.md`, không sửa). Mọi số liệu lấy từ 17 file đó; ngoại lệ được ghi rõ.

Quy ước độ tin cậy (kế thừa các file con): **[ĐO]** = đọc trực tiếp từ ffmpeg/ebur128/transcript; **[ƯỚC]** = ước lượng (*estimate*) bằng mắt hoặc optical-flow LK + RANSAC (sai số ~±10-15 %, chỉ tin cậy ở cảnh talking head). Các mục sau là *estimate* (ước lượng), không phải số đo: hệ số zoom đo bằng LK-flow (cột "zoom"), số cut đếm bằng `select='gt(scene,0.25)'` của ffmpeg (bỏ sót dissolve, ghost và đổi layout cùng tông tối), mọi hex màu đo bằng quantize khung hình, và mọi nhận định về SFX (không nghe trực tiếp, không tách stem).

Phạm vi: 17 video, đăng 2026-07-20 tới 2026-11-13, kênh @__dviet. Tổng hợp tín hiệu lặp lại ở mục 2, bảng khoảng cách "quan sát -> trạng thái PFD" ở mục 3, quyết định và backlog ở [`../23_dviet_profile_decisions_and_backlog.md`](../23_dviet_profile_decisions_and_backlog.md), token style ở [`../../presets/dviet_style_tokens.json`](../../presets/dviet_style_tokens.json).

---

## 1. Bảng 17 video

Cột: id | dài / fps / canvas | dạng | một dòng | hook | palette / accent | caption y | zoom | chuyển cảnh | SFX / loudness (LUFS, true-peak hoặc peak dBFS).

| id | dài / fps / canvas | dạng | một dòng | hook | palette / accent | caption y | zoom (ƯỚC) | chuyển cảnh | SFX / loudness |
|---|---|---|---|---|---|---|---|---|---|
| [7664447064352509204](./7664447064352509204.md) | 27.35 s / 60 / 1080x1920 | tâm sự, footage đời thường | Video đầu tiên của kênh: "mình không ..." anaphora | flicker silhouette 8 frame (plate trống / bóng kem) rồi chữ 2 tầng "của mình" | trắng thuần, chưa có accent | 50-58 % | không có zoom số, chỉ handheld | 9 cut cứng, flicker mở đầu, chữ giữ qua cut | -13.7 / ~0.0 dBFS; hit ~0.04 s (ƯỚC); nhạc liền |
| [7664633717771488532](./7664633717771488532.md) | 27.35 s / 60 / 1080x1920 | breakdown raw vs edited | Cùng audio video đầu: 2 card dọc + timeline CapCut | split card "raw / edited", nhãn vàng đè mép card | nhãn vàng ≈#E8C81A (ƯỚC); card viền trắng ~8 px | n/a (nhãn card) | không có camera move | 0 cut (1 bố cục), flicker bóng kem ở 0.1 s | -13.8 / +0.2 dBFS; audio y hệt video đầu |
| [7664835388476755220](./7664835388476755220.md) | 11.8 s / 30 / 1332x720 | text-first, nhạc + chữ | Motivational: "đừng bận tâm ánh nhìn người ..." | bố cục chòm sao: hero chữ thảo + từ sans quanh | trắng thuần, glow nhẹ | hero y 40-50 % | chân máy, không zoom | 1 cut, silhouette flicker match-cut 6 frame (5.15-5.33 s) | -20.1 / -5.6 dBFS (nhỏ nhất bộ); spike 5.14 s khớp flicker (ƯỚC) |
| [7664969137445276949](./7664969137445276949.md) | 46.47 s / 60 / 1080x1920 | tutorial CapCut: Flicker Effect | Dạy flicker: nền 8 frame + chủ thể tách nền cắt mỗi 2 frame | demo các biến thể flicker ngay trong hook, tiêu đề "FLICKER effect" | trắng thuần | 52 % (A-roll) / 27 % (panel) / 66-72 % (CTA) | zoom CTA ≈1.6-2x trong 0.8-1.2 s; plate nền = A-roll 3x + blur | color-wash 0.6 s, đảo sáng, flicker 2 frame cuối, cut cứng giữa layout | -12.6 / +2.0 dBFS; mỗi flicker có hit (ƯỚC) |
| [7666801391284964628](./7666801391284964628.md) | 50.98 s / 60 / 1080x1920 | listicle 3 hiệu ứng CapCut | "3 hiệu ứng nên lưu lại" (Máy phát nhạc 3, cảnh quay cũ, làm mờ xuyên tâm 2) | số "3" vàng + logo + "Lưu lại" chữ thảo | vàng #E5B70C-#E3B408 + trắng #FFFCF9 | 45-55 % (hero tràn y 70-85 %) | punch ≈2.2x / ≤0.25 s (7.0 s); push 1.3x / 16 s; nhảy +1.15x | cut cứng + ghost 4-5 frame, title card hoa xám, ngả cam #FF4B14 trước cut | -11.2 / +0.9 dBFS; pop khớp entrance chữ hero (ƯỚC) |
| [7667598741888634132](./7667598741888634132.md) | 46.14 s / 60 / 1080x1920 | tutorial: chữ trượt lên "Máy phát nhạc 3" | Hướng dẫn tạo clip ghép + hiệu ứng trượt lên | hook 3 cỡ khung + zoom-out 0.85x + radial blur mạnh | vàng #F1C711 / #F0C311, trắng #FFFEFC | 67 % dưới panel (56-72 %) | đầu 18 % -> 15 % -> 19 % bề rộng (0.85x rồi 1.05x) trong ~0.4 s | film-burn cam 7.65-7.77 s, panel / demo cut cứng, blur xuyên tâm vào A-roll cuối | -10.7 / +1.5 dBFS (to nhất); hit sau mỗi hero word (ƯỚC) |
| [7668334908615560469](./7668334908615560469.md) | 64.67 s / 60 / 1080x1920 | tutorial: Clone effect | Phân thân làm visual hook, 2 chương pre-production / production | handheld quét tới plate sofa trống, chữ CLONE dán tường | trắng + vàng #F3C60F / #F1C511-#FDC601 | 67-69 % (y 1290-1330) | không keyframe scale, chuyển động từ camera thật; nhảy ~1.2x ở 2.72 s | cut cứng match-on-motion, cutaway macro, về plate trống | -11.7 / +1.5 dBFS; whoosh / clone pop suy luận (ƯỚC) |
| [7669054598971133204](./7669054598971133204.md) | 27.75 s / 60 / 1080x1920 | tutorial: Overlapping text | Kỹ thuật chồng chữ, mask mờ chân chữ | punch-in + blur jump cut ở 1.03 s, chữ "cách làm" chồng chéo | vàng/gold #CDA84B-#F3C60F, trắng | 68 % (y ~1310) | punch ~1.15-1.25x kèm blur ở 1.03 s | flash cam/đỏ 3.0-3.6 s, cắt sang nền satin, dissolve tối cuối | -11.4 / +2.2 dBFS; hit 23.25 s tutorial -> A-roll (ƯỚC) |
| [7669758857471741204](./7669758857471741204.md) | 24.94 s / 60 / 1080x1920 | showcase SFX | "Sound effect" + thẻ demo SFX có nhãn | chữ thảo neon xanh "Sound" + lock-up 2 tầng | một màu xanh lá #5DD852 / #3AB031 khớp áo và tường | hook y 50-68 %; lock-up tiêu đề y 12-27 % | không zoom chủ đích | flash trắng 7.6 s (bloom), cross-fade nhãn blur dọc | -12.5 / +2.0 dBTP, LRA 9.6; SFX demo là âm thật |
| [7670574911680777492](./7670574911680777492.md) | 63.25 s / 60 / 1080x1920 | listicle: Glow / Làm mờ / Pixel stretch | Series hiệu ứng nên lưu, nhiều cảnh quay màn hình bằng camera | "3 hiệu ứng" vàng hổ phách + glow, flash prism | #C99613-#F3C60F + trắng #FFF8EE | 50-67 % (y 960-1280) | zoom số chậm 1.057 -> 1.17 (39.7-41.7 s); không punch nhanh | flash prism/lens 3.2 s, motion smear + snap (pixel stretch), fade -> thẻ comment | -11.5 / +3.0 dBFS (peak cao nhất); onset khó quy cho SFX |
| [7672413018575146261](./7672413018575146261.md) | 65.16 s / 60 / 1080x1920 | tutorial 4 bước: biến hình / vanish | Glow + negative + nền trắng để biến mất | vertical roll + motion blur "biến hình" 2.9-3.6 s | vàng gradient #D49E02-#D7B04A + teal #3E8F7A | 68 % (y ~1310) | push chậm ~1.055-1.06x | vertical roll, vanish: white-out -> flash trắng 1-4 f -> plate trống | -12.1 / +0.7 dBFS, LRA 1.6; vacuum -32 dB 0.4 s rồi hit; fade-out cuối 46 dB |
| [7677448217667063061](./7677448217667063061.md) | 71.75 s / 30 / 1080x1920 | talking head ep.1: font + 3 màu | Giới thiệu series, thẻ font specimen, palette chip | zoom-out 0.80x post-cut settle + PiP squircle scale-pop | tím #B360FB / #8C6CFF trên #FAFAFA / #111111 | n/a (thẻ font) | settle 0.80x; push dài 1.1-1.4x (16.9-21.3 s); 0.87-0.95x sau mỗi cut | cut cứng A-roll <-> thẻ, glitch/mosaic, cross-dissolve thẻ font | -10.9 / +0.7 dBFS; không fade cuối |
| [7683763922234641684](./7683763922234641684.md) | 59.33 s / 60 / 1080x1920 | tutorial Blend Mode, CTA comment "blend" | Overlay / Screen / Multiply trong CapCut | per-word pop + deblur "tận dụng blendmode" | teal #3DBFA0 + xanh lá #3EDC57 (ƯỚC) trên trắng | 50-58 % (hero), 60-80 % (UI) | push +4.4 % / 1.7 s rồi reset, +9.7 % / 1.8 s, +8.2 % / 1.3 s | whip blur ngang 13.13 s, flash cam-vàng 16.70-16.93 s, card slide + blur | -10.9 / sample peak -5.7 dBFS; whoosh 16.55 s (ƯỚC) |
| [7688934517783989524](./7688934517783989524.md) | 64.71 s / 60 / 1080x1920 | quảng cáo InVideo AI Agent | Giao việc tẻ nhạt cho agent, CTA comment "invideo" | chuỗi flash-cut 0.1 s ở hook (5 mốc) | trắng + tím; phụ đề EN vàng nghiêng #F8C818 | EN sub y 80-85 % (đo); hero ~50 % | push +5-12 % / 2-3 s; zoom-out dài -36 % / 3.9 s trên B-roll 3D | polarity flip trắng 7.98-10.63 s, wash đỏ-cam, whip xoay 24.8 s, blob logo | -12.1; 23 xung >=10 dB, 4 trùng cut (ƯỚC) |
| [7693026626333871381](./7693026626333871381.md) | 49.27 s / 60 / 1080x1920 | tutorial chọn nhạc nền, ep.2 | BPM >= 140, tách stem, căn beat drop với hook | "talking head VIDEO" bị đầu che, polarity flip tối -> trắng-tím | tím #9878E8-#A898E8, trắng #F8F8F8 | hook y 8-25 %; "edit" y 55 %; UI 58-75 % | +4.6 % / 6.3 s; +7.9 % / 2.0 s ở CTA | polarity flip 3.0 s và 33.0 s, lật dọc (flip stack) 10.7-13.0 s, warp cong 42.2 s | -11.9; nói liền, 0 khoảng nghỉ >= 0.25 s |
| [7706183278461570356](./7706183278461570356.md) | 61.14 s / 24 / 1440x1080 (4:3) | tâm sự, burnout -> MagentX | 1 tháng vắng mặt, rời lối mòn | dolly-out chậm cảnh mở; 2 tầng lead trắng + hero vàng | vàng-hổ phách #E8B818-#F5C518, glow cam 12-20 px | cạnh nhân vật (không che mặt), không đo y % | dolly-out -16 % / 2.3 s; push +10.6-11.9 %; 3 nấc +13 / +8 / +9 % (33.0-35.0 s) | dissolve / dolly-through, bụi khói, rack-focus bokeh, light streak, chữ ghost qua cut | -11.3; xung 60.25 s +21 dB (outro hit, ƯỚC) |
| [7707653827016674580](./7707653827016674580.md) | 57.21 s / 30 / 1440x1080 (4:3) | tutorial 4 cách cut (hard / J / match / on action) | Cắt video không chỉ là bấm split | chữ cong cung quanh đầu, khung ngắm [ đặt máy quay ] + chấm rec | neon mint #38E898, glow 15-25 px | cạnh nhân vật, không đo y % | reveal 1.062 -> 0.536 (0.4-2.8 s); +7.9 % / 2.2 s; +10 % / 2.2 s ở CTA | hard cut chủ đạo, match cut 3 hình tròn, cross-dissolve 0.3-0.5 s | -16.7 (nhỏ thứ hai); cụm 3 xung 25.15-25.7 s khớp J-cut (ƯỚC) |

Ghi chú bảng: số cut "đo" của từng file con dùng ngưỡng scene 0.25 nên là **ước lượng thấp** (ffmpeg bỏ sót dissolve và đổi layout cùng tông). Các số "+x % / y s" ở cột zoom là LK-flow + RANSAC, nhiễu bởi chữ và thẻ.

---

## 2. Tổng hợp tín hiệu lặp lại (có đếm)

Các số đếm dưới đây là số video trong 17, tính theo nội dung các file con. "Trực tiếp" = file con mô tả đúng hiện tượng; "biến thể" = hiện tượng liên quan nhưng khác kỹ thuật.

| Tín hiệu | Số video | Id | Ghi chú |
|---|---|---|---|
| Silhouette flicker (plate trống / bóng kem hoặc trắng, đổi mỗi 1-2 frame) | **4 trực tiếp**, 6 kể cả biến thể | 7664447, 7664633, 7664835, 7664969; biến thể 7668334 (clone), 7672413 (vanish) | 60 fps: 1-3 frame mỗi trạng thái; 30 fps: 2 frame. Công thức do chính tác giả nêu ở 7664969: nền 8 frame + chủ thể tách nền, cắt mỗi 2 frame |
| Layout tutorial: strip màn hình ~1080x600 (y 660-1260) trên nền blur A-roll 3x hoặc nền satin / aurora | **>= 4** | 7664969 (A-roll 3x + blur), 7667598 (nền = frame phóng + blur + tối), 7668334, 7669054 (satin); gần giống: 7672413 (aurora), 7688934 (satin stage) | Phụ đề đặt y ~67-68 % ngay dưới strip |
| Card dọc 9:16 viền trắng bo góc, nhãn vàng đè mép | **1 trực tiếp** | 7664633 (viền ~8 px, bo ~28-30 px) | Biến thể card bo góc UI: 7664969, 7667598, 7683763, 7688934 (ƯỚC) |
| Thẻ profile TikTok giả (avatar, 3 số, bio) | **3** | 7664447 (3.7-4.8 s, ~70 % bề rộng, y ~43 %), 7667598 (43.5-44.3 s), 7664633 (nằm trong card edited) | |
| Lock-up 2 tầng (lead nhỏ trắng + hero lớn; hoặc dòng dưới bất biến + dòng trên đổi từ) | **>= 8** | 7664447, 7667598, 7669758, 7683763, 7688934, 7693026, 7706183, 7707653 | Hero luôn 1-2 từ; tỷ lệ hero / lead 1.8-3.2x |
| Caption y 50-67 % so với mặc định skill 75-83 % | **11** | 7664447, 7664969, 7666801, 7667598, 7668334, 7669054, 7669758, 7670574, 7672413, 7683763, 7693026 | Skill cũ: whisper y=1590 (83 %), minimal captions y=1440 (75 %) |
| Phụ đề tiếng Anh vàng nghiêng ở đáy | 1 | 7688934 (#F8C818, y 80-85 %, đo bằng pixel) | |
| Accent vàng (#F1C711 / #E5B70C / #F8C818 và họ amber) | **9** | 7664633, 7666801, 7667598, 7668334, 7669054, 7670574, 7672413, 7688934 (phụ đề EN), 7706183 | 7664447, 7664835, 7664969 hoàn toàn trắng |
| Punch 220 % / 0.25 s | 1 (ƯỚC) | 7666801 (7.0-7.25 s) | Punch nhỏ hơn 1.15-1.25x: 7669054 (ƯỚC) |
| Push 130 % trong 16 s (ease-in-out) | 1 (ƯỚC) | 7666801 (35 -> 50.9 s) | Push dài khác: 7677448 1.1-1.4x trong 4.4 s |
| Jump-cut reset push +4 .. +10 % (push tuyến tính ~1.3-2.2 s rồi cắt reset) | **5** (ƯỚC) | 7683763, 7688934, 7693026, 7706183, 7707653 | Nhịp "push chậm, cắt nhảy, reset, push tiếp" |
| Zoom-out 0.85x + radial blur mạnh ở mép | 2 (ƯỚC) | 7667598 (3.4-4.5 s, 0.85x), 7666801 (giới thiệu hiệu ứng "Làm mờ xuyên tâm 2") | |
| Mastering to: -10.7 .. -12.6 LUFS | **13** | tất cả trừ 7664447 / 7664633 (-13.7 / -13.8), 7664835 (-20.1), 7707653 (-16.7) | -10.7 là 7667598 |
| Peak dương (true-peak hoặc sample) tới +3.0 dBFS | **10 video > 0 dBFS** | 7664633, 7664969, 7666801, 7667598, 7668334, 7669054, 7669758, 7670574, 7672413, 7677448 | Cao nhất +3.0 (7670574); đích skill cũ -1.5 dBTP |
| Canvas 30 fps | 3 | 7664835 (1332x720), 7677448 (1080x1920), 7707653 (1440x1080) | 24 fps: 7706183; 60 fps: 13 video |
| Canvas 4:3 1440x1080 | 2 | 7706183 (24 fps), 7707653 (30 fps) | 1332x720 (~1.85:1): 7664835 |
| Canvas 1080x1920 | 14 | phần còn lại | |
| Polarity flip (khung trắng / tím 1-2 frame) | 3 | 7688934, 7693026, 7672413 (nền trắng mờ 0.5 s) | Skill đã có `polarity_flip` |
| Flash / film-burn / light leak ấm | 7 | 7667598, 7669054, 7669758, 7670574, 7664969, 7683763, 7666801 (ngả cam trước cut) | Bị cấm trong CRI-100; xem quyết định (e) ở tài liệu 23 |

---

## 3. Bảng khoảng cách: quan sát -> trạng thái PFD

PFD = pro-filmcraft-director. "done v7.4" = có dữ liệu hoặc mã trong bản v7.4.0 này (ghi file). "backlog" = chưa làm, xếp hạng ở tài liệu 23. Không ghi "done" cho thứ chưa có mã.

| Quan sát | Nguồn | Trạng thái PFD |
|---|---|---|
| Caption y 50-58 % (talking), 67 % (panel), 27 % (hero trên panel) | 11 video | done v7.4: `presets/dviet_style_tokens.json` (`caption_y_pct`), `scripts/tools/dviet_text.py` |
| Phụ đề EN vàng nghiêng y 80-85 % | 7688934 | done v7.4: role `bilingual_sub` |
| Lock-up 2 tầng | >= 8 video | done v7.4: roles `lockup_sub` / `lockup_hero` |
| Từ khoá chữ thảo cả từ có dấu | 7664447, 7666801, 7667598 | done v7.4: role `script_accent` (swash hybrid chỉ giữ cho role này) |
| Từ khoá sans nhỏ vàng trong caption | 7667598, 7683763 | done v7.4: role `keyword_sans` + `typography_hierarchy_presets.json` |
| Accent vàng #F1C711 / #E5B70C / #F8C818 | 9 video | done v7.4: tokens palette |
| Tutorial layout strip trên nền blur 3x | >= 4 video | done v7.4: template `screen_strip` (`web_plate_builder.py`), pattern trong `dviet_pattern_catalog.json` |
| Card 9:16 viền trắng + nhãn vàng | 7664633 | done v7.4: template `card_916` |
| Thẻ profile giả | 3 video | done v7.4: template `profile_card` |
| Punch 220 % / 0.25 s, push 130 % / 16 s, step 13-8-9, jump-cut reset push, dolly-out | 7666801, 7706183, 5 video | done v7.4 (giá trị ƯỚC): `dviet_smooth_camera_engine.py` + `atomic_motion_library.json` |
| Radial blur lớn dần theo scale (zoom-out 0.85x) | 7667598, 7666801 | done v7.4 (ƯỚC): `apply_scale_radial_blur` |
| Giới hạn zoom theo đầu (safe-box) và luật C4 (nói liền >= 4 s có zoom) | luật skill | done v7.4: `clamp_scale_to_safe_box`, `c4_zoom_keys` |
| color-wash nhiều màu 0.6 s, film-burn perf 5 f, light leak xoay 90, white flash 0.25 s, vertical roll, orange ghost 5 f, vacuum -32 dB 0.4 s | 7664969, 7667598, 7669054, 7672413, 7683763, 7669758 | done v7.4 (dữ liệu, chỉ `profile_scope: ["dviet"]`); thực thi và cap nằm ở `compile_and_verify.py` qua `presets/profile_overrides.json` của gói P1 |
| Mastering to -10.7 .. -12.6 LUFS, peak tới +3 dBFS | 13 video | done v7.4, opt-in: `--audio-profile tiktok_loud` (P1), trần -1.0 dBTP (v7.9.1, trước đó -0.5); mặc định vẫn -14 LUFS / -1.5 dBTP |
| Canvas 1080x1920 @30, 1440x1080 @24/30, 1332x720 @30 | 6 video | done v7.4 (dữ liệu + ghi chú scale safe-zone): `presets/canvas_presets.json`; renderer plate nhận width/height, chưa kiểm thử end-to-end trên canvas 4:3 |
| Bố cục chòm sao (constellation) | 7664835 | một phần: tham số trong tokens + role `constellation` của `dviet_text.py` (chỉ đặt chữ); renderer plate: backlog |
| Silhouette flicker (6 video) | 4 + 2 biến thể | backlog (cần clean plate + matte + lịch flicker theo frame; xem tài liệu 23) |
| Clean-plate vanish | 4 | backlog |
| Planar tracking chữ dán tường | 4 | backlog |
| Clone / phân thân | 1 | backlog |
| Waveform SFX tile | 1 | backlog |
| Pixel stretch / slit-scan | 1 | backlog |
| Lật dọc (flip stack), warp cong | 1 + 1 | backlog |
| RGB fringe (tách kênh) trên chữ | 1 | backlog |
| Sticker sparkle | 2 | backlog |
| Keycap 3D tile | 1 | backlog |
| Chữ cong bám đầu theo tracker (có `kt11` svg_arc nhưng không có tracker) | 2 | backlog |
| Link hỏng trong tài liệu 12 và 13 (không thuộc phạm vi P3) | - | backlog (liệt kê ở tài liệu 23) |
