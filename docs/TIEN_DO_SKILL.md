# TIẾN ĐỘ SKILL `pro-filmcraft-director` (kiểm kê chỉ đọc)

Ngày kiểm kê: 2026-11-26. Nhánh `upgrade/v7.4`, cây làm việc ghi nhãn `v7.9.0` (bản sửa theo kiểm định video v4; trước đó `v7.8.0` gói S2: học thuyết và bộ lập kế hoạch), chưa commit.
Nhãn: **[ĐO]** = đã chạy lệnh và thấy kết quả; **[ƯỚC]** = suy luận từ đọc mã/tài liệu, chưa chạy.
Python dùng để chạy: `/home/vmiz/.venvs/video-skills/bin/python3`.

---

## 1. Tình trạng git (rủi ro lớn nhất)

- **[ĐO]** `git log --oneline` chỉ có **1 commit**: `8084094 feat(v7.3.0) ...`. Không có commit v7.4, v7.5, v7.6, v7.7. Toàn bộ bốn phiên bản nằm trong cây làm việc chưa commit. Tên nhánh `upgrade/v7.4` đã lỗi thời so với nội dung (v7.7.0).
- **[ĐO]** `git status`: 18 file tracked đã sửa (`+3524 / -372` dòng) và **82 file chưa tracked** (47 mục khi git gộp thư mục). `git ls-files` chỉ có 52 file.
- **[ĐO]** Đường cài đặt: `~/.claude/skills/pro-filmcraft-director` là symlink tới thư mục này, nên skill đang chạy từ cây chưa commit.
- Hệ quả: `git stash -u`, `git clean -fd` hoặc clone lại sẽ mất toàn bộ công việc v7.4 đến v7.7 (xem mục 6).

---

## 2. Dòng thời gian phiên bản

| Phiên bản | Trạng thái git | Thêm gì (theo SKILL.md, README.md, mã) |
|---|---|---|
| v7.3.0 | **đã commit** (`8084094`) | Hybrid `Option A x B`: `render_full_head_studio_card` (A1), `render_squircle_pip_window` (A2), `render_bottom_flush_cutout` (B); `clean_aroll_preserve_hair_crown` (giữ vòm tóc); `verify_audio_voice_sync_guard`; 12 khuôn chữ `kt01..kt12`; Gate 3B `CRANIAL_EXCLUSION_AUDIT`; render nhanh draft 30fps / master 60fps; bộ 8 cổng của `compile_and_verify.py`. |
| v7.4.0 | chưa commit | Nguồn sự thật `@__dviet`: `references/dviet_19/INDEX.md` (17 video) + ref 23 (quyết định + BACKLOG); token `dviet_style_tokens.json`, `canvas_presets.json`; `dviet_text.py` (chữ theo vai trò); 5 preset zoom mới trong `dviet_smooth_camera_engine.py` + self-test đo đường cong; chuyển cảnh theo profile `dviet`; 3 layout `screen_strip` / `card_916` / `profile_card`; vendor `scripts/vendor/ovs_core`; `env_status.py`; `compile_and_verify.py --profile` và `--audio-profile`; ingest cứng hơn (`--whisper-threads`, `--timeout`, `--force`, `--music-only`); công cụ mới `fc_export`, `spec_from_plan`, `silence_cut`, `speed_media`, `sfx_auto`, `qa_sync` + `sfx_shift` (Gate 7b), `broll_from_video`. |
| v7.5.0 | chưa commit | Bảng độ to `tiktok_loud` (-12 LUFS, ref 25); `duck_keyframes.py`; `filmcraft_cli.py` (shim `filmcraft --control`, ref 24 control bridge); `flicker_schedule.py` + opener `flicker`; ref 26 (font), ref 27 (công thức Premiere cho effect trong BACKLOG); bảng "đạo diễn được hứa gì" A/B/C trong SKILL.md mục 3. |
| v7.6.0 | chưa commit | **Look S (Studio) là mặc định**, Look D (`@__dviet`) chỉ khi yêu cầu rõ; ref 24 `studio_look_recipe` (bản đồ 12 cảnh V21); `studio_recipe.py` + `studio_scene_recipe.json`; profile âm thanh `studio_14` (-14 LUFS); bàn giao kép MP4 master + `.fcproj`; Step 3b trong SKILL.md; luật màu nhấn chỉ thuộc Look D. |
| v7.7.0 | chưa commit | Ref 28 (hook 5 giây đầu + luật nhịp) và ref 29 (thẻ pop-out); `studio_recipe.hook_template/check_hook/check_pacing/check_source_reuse`; `render_popout_studio_card`; `--audio-profile studio_14` nối vào compile; `person_alpha_u8` cho bộ làm sạch tường; `fc_export.py` thăm dò thay vì chờ mù; prop `echo_opacity` cho `kt12`; vendor `audit_sfx` tính `gain_db`. |
| v7.8.0 | chưa commit | Ba lỗi D1-D3 của video v3 thành luật: chữ hook theo giọng (`hook_text_from_words`, `text_voice_sync`), hero ở vùng an toàn sản phẩm (`hero_safe_zone`), cỡ chữ tối thiểu (`text_min_size`), sàn chuyển động lớp nền (`hook_motion_floor`, `bg_static_hold`, `plan_micro_moves`), mặc định thẻ pop-out nét (ref 29 mục 3.1a), `motion_gate.py` đo trên MP4 (gói S1). Xem mục 2.1. |
| v7.9.0 | chưa commit | Bản sửa theo kiểm định video v4: dọn kho (số phiên bản, số thứ tự tài liệu, liên kết chết, `--help`, `install.sh` chạy bằng glob), cộng các cổng QA và cổng chữ do gói khác thêm (xem mục 2.0). |
| v7.9.1 | chưa commit | Bản sửa theo kiểm định toàn kho (tài liệu + mã, làm song song): `SKILL.md` sắp lại theo luồng 1–5 có đánh số phân cấp, CLI mới `look_s_render.py`, sửa các số liệu sai trong tài liệu, các quyết định về Gate 3, ingest, preflight, flash, vacuum, `tiktok_loud`, lint B-roll (xem mục 2.0a). |

### 2.0a Mục `v7.9.1` (sửa theo kiểm định; tài liệu + mã, chưa commit)

**Nhãn phiên bản:** các hằng trong mã (`COMPILER_VERSION`, `VERSION` của các công cụ, `ENGINE_VERSION`, `studio_scene_recipe.json`) vẫn là `7.9.0`, và test so chúng với frontmatter `SKILL.md`, nên frontmatter / H1 của `SKILL.md` và H1 của README giữ `v7.9.0`. `v7.9.1` chỉ là nhãn của đợt sửa này trong tài liệu (README mục 1, mục này).

**Tài liệu (gói tài liệu: `SKILL.md`, `README.md`, `docs/`, `references/**`, `tests/test_dviet_docs.py`, `tests/test_skill_v73.py`).**
- **`SKILL.md` sắp lại theo quyết định của người dùng:** 1. Tổng quan (1.1 mục đích & vào/ra, 1.2 Look S / Look D – một bảng duy nhất, 1.3 kiến trúc, 1.3.1 bộ não) → 2. Yêu cầu & tài nguyên (2.1 môi trường, 2.2 sáu công cụ lõi, 2.3 CLI phụ trợ, 2.4 bảng lệnh đánh số theo mục 3, 2.5 tier, 2.6 preset, 2.7 tài liệu theo nhóm, 2.8 chỉ mục script) → 3. Quy trình (3.1 preflight … 3.8 bàn giao, 3.8.1 Rule A1 – một bản duy nhất kèm ngoại lệ MP4 của Look S, 3.8.2 Gate 7b, 3.8.3 B-roll) → 4. Luật (4.1 luật sắt, 4.2 cổng kèm **nơi thực thi** từng cổng, 4.3 lớp hứa A/B/C + backlog, 4.4 bằng chứng `@__dviet` 17 video) → 5. QA & lỗi (5.1 danh mục 8 gate, 5.2 `motion_gate`, 5.3 `qa_sync`, 5.4 xử lý lỗi / leo thang). Các đoạn trùng (Look S/D ở 3 chỗ, Rule A1 ở 4 chỗ, hai luật chữ đầu mâu thuẫn) chỉ còn một bản chính.
- **Bảng lịch sử v7.7 / v7.8 / v7.9 rời đầu `SKILL.md`:** bảng cổng v7.9.0 chuyển sang `README.md` mục 1; phần v7.7 / v7.8 đã có ở README và tài liệu 28.
- **Frontmatter `description`:** câu kích hoạt đứng đầu, `<= 1024` ký tự, không có `<`.
- **Sửa sự thật:** "19/19 video" → 17 (`SKILL.md`, tiêu đề tài liệu 13 và 19; thư mục `dviet_19` giữ tên, ghi rõ chứa 17 video); 4 lớp Z-depth (thứ tự track timeline, tài liệu 11 / 16) đối chiếu với 3 mặt phẳng của `LayeredFrameCompositor` trong mã (tài liệu 13); "FilmCraft 0.20.1" → FilmCraft `0.13.0` (`0.20.1` là `wgpu`); luật `45-token` cũ (thật ra `46` token, `8–95` từ) của `visual_blocks.lint_broll_prompt` nay đọc chung `presets/broll_lint_contract.json` (`8–60` từ, không kiểm `anchor_quote`); `1,200` cặp glue → `1199`; tiêu đề "14 micro-bridge" nay liệt kê đủ 14 tên của `format_modes_catalog.json`, 7 tên cũ là bridge của archetype (`visual_archetypes_catalog.json`); `-0.5 dBTP` → `-1.0 dBTP` (`SKILL.md`, tài liệu 23, INDEX); RVM không đi kèm skill, matte người là `u2netp` / `birefnet-portrait` (`SKILL.md` 2.1, tài liệu 29); `--force` của probe là ghi đè file khoá, không phải chạy lại cache; tier `auto` không chọn `studio`, tier `studio` compile `--tier full` nên có chạy `bgm_lra` / `R35`; thời gian / RAM tier lấy từ `execution_tiers.json`; lệnh compile của Look S có `--audio-profile studio_14` (mặc định `platform` = `-16 LUFS`), nêu `--strict-rules` và `--hook-gates`; luật chữ đầu chỉ còn một (`first_text_late`, mặc định chặt: chữ đầu hiện trước từ của nó tối đa `250 ms`); loudness hook `-12 LUFS` trong `studio_scene_recipe.json` ghi là khuyến nghị, không cổng nào thực thi (tài liệu 28 cũng sửa).
- **Tài liệu tham chiếu:** tiêu đề H1 thống nhất dạng `NN — Tiêu đề`; 15–18 gắn nhãn lịch sử (tài liệu 21 là spec hiện hành), 16 / 17 / 18 hết nhảy H1 → H3; Rule A1 ở 15 / 17 / 18 trỏ về `SKILL.md` mục 3.8.1; tài liệu 05 bỏ đường dẫn chết `dviet-filmcraft-director/presets/animation_dna_catalog.json`; tài liệu 24 ghi rõ tài liệu phân tích nguồn không kèm repo; tên script vendor trần ở 21 / 25 / 27 / 30 thành đường dẫn đầy đủ `scripts/vendor/ovs_core/...`; 25 / 26 bỏ đường dẫn tuyệt đối cá nhân; 25 thay số dòng cũ bằng tên hàm; 14 trỏ tới ảnh `visual_primitives_10_showcase.jpg`.
- **README:** liệt kê đủ 19 bộ test (gồm `test_skill_v79.py`, `test_text_legibility_v79.py`, `test_audit_core_v791.py`, `test_look_s_driver_v791.py`, `test_portability_v791.py`), cây thư mục có `docs/` và `scripts/vendor/ovs_core`, bảng biến môi trường (kiểm bằng grep).
- **Test tài liệu (`tests/test_dviet_docs.py`):** test 03 tách theo `### 3.1. Preflight` / `### 3.2.` thay cho `### Step 0` / `### Step 1`, bảng hứa phải là tiêu đề `### 4.3.`; test 12 đòi tiêu đề `### 3.5. Look S recipe` và `#### 3.8.1. Rule A1` thay cho chữ "Step 3b"; test 07 đòi `-1.0 dBTP` ở tài liệu 23 thay cho `-0.5 dBTP`. Mức chặt giữ nguyên.

**Quyết định đang được gói mã thực hiện song song (tài liệu đã ghi như sự thật).**
- Gate 3 báo **SKIPPED** (không phải PASS) khi thiếu `--words` / `--manifest`, **FAIL** khi `edit_rules` lỗi.
- `probe_and_align` từ chối video 0 byte / hỏng; luôn ghi `words_tl.json` (rỗng + cảnh báo khi không có tiếng).
- `env_status` coi FilmCraft (`>= 0.13.0`) và Xvfb là bắt buộc để compile; thư mục cache `PFD_CACHE_DIR`; `requirements.txt` ghim `opencv-python-headless` 4.x.
- CLI mới `scripts/tools/look_s_render.py` (`--scenes --words --aroll --work --out [--draft|--master] [--broll-dir] [--dry-run]`) dựng Look S từ `scenes.json`.
- Chữ whisper / `G2` theo sàn `64 px` (bỏ `26pt`); preset flash bị chặn (độ sáng trung bình `<= 220`, cắt trắng `opacity <= 70`, `<= 3` lần/giây); vacuum cách nhau tối thiểu `20 s`; `tiktok_loud` = `-12 LUFS`, `-1.0 dBTP`, nhạc nền dưới giọng `14 dB`; một bộ lint prompt B-roll duy nhất, nguồn sự thật `presets/broll_lint_contract.json`.

### 2.0 Mục `v7.9.0` (dọn kho theo kiểm định video v4; chưa commit)

**Đã đổi (gói dọn kho, kiểm bằng test và quét liên kết).**
- **Số phiên bản `7.9.0`:** `install.sh` (3 chỗ), `requirements.txt` dòng 1, `scripts/vendor/ovs_core/PROVENANCE.md` dòng 1, `README.md` (tiêu đề, mục 1, sơ đồ cây), `SKILL.md` (frontmatter `description`, tiêu đề H1; nội dung còn lại giữ nguyên, các nhãn `v7.8.0` nói nguồn gốc tính năng được giữ). **Hằng phiên bản trong mã (finding S2, đã đổi ở bước hoàn tất):** `compile_and_verify.COMPILER_VERSION`, `probe_and_align.VERSION`, `env_status.VERSION`, `spec_from_plan.VERSION`, `flicker_schedule.VERSION`, `studio_recipe.VERSION`, `dviet_smooth_camera_engine.ENGINE_VERSION`, `motion_gate.VERSION` và `presets/studio_scene_recipe.json` `version` đều là `7.9.0`; banner đầu file (`fast_studio_compositor.py`, `typography_composer.py`, `fc_export.py`, `filmcraft_cli.py`, `ffskill_bridge.py`, `probe_and_align.py` mô tả CLI) cùng nhãn. Test không còn ghi cứng số: `tests/test_stability.py` (g), `tests/test_studio_recipe.py` và `tests/test_skill_v78.py` (test 14) so với phiên bản trong frontmatter `SKILL.md` (một nguồn duy nhất). Nhãn lịch sử kiểu "thêm ở v7.8.0" giữ nguyên. Trường `version` của `canvas_presets`, `dviet_style_tokens` (`7.4.0`) và `profile_overrides` (`7.6.0`) chưa đổi: đó là phiên bản schema của preset, cần quyết định riêng.
- **`install.sh` chạy mọi `tests/test_*.py` bằng glob** (đã đúng từ v7.8.0; chỉ cập nhật nhãn). README mục 4 bỏ số cứng "cả 14 bộ" (finding S6). `tests/test_skill_v78.py` (test 14) nay đòi `7.9.0` ở `install.sh`, `requirements.txt` và `PROVENANCE.md`.
- **Hết trùng số tài liệu 24 (finding S3):** `references/24_filmcraft_control_bridge.md` đổi thành `references/30_filmcraft_control_bridge.md` (tiêu đề `# 30 —`). Cập nhật liên kết ở `SKILL.md` (dòng 37, 91, danh sách mục), `README.md`, `scripts/tools/filmcraft_cli.py`, `tests/test_skill_v73.py`, `tests/test_dviet_docs.py`. Danh sách đánh số trong `SKILL.md` nay khớp tiền tố file: 24 = Look S, 25, 26, 27, 28 = hook, 29 = pop-out, 30 = control bridge. README ghi `01..30`.
- **Hết liên kết chết (finding S4):** quét 230 liên kết markdown (`SKILL.md`, `README.md`, `docs/`, `references/`), còn 0 liên kết chết. Hai liên kết ở ref 12 và ref 13 (script ngoài repo) đổi thành chữ thường ghi "script ngoài, không đi kèm skill này". Ba đường dẫn chéo skill (`open_in_app.py`, `filmcraft-commands.json` ở ref 30 và ref 27) ghi rõ thuộc skill `opa-video-studio` / `craft-handoff`.
- **`--help` không còn lỗi (finding S5):** `ffskill_bridge.py` có argparse trước bước kiểm phụ thuộc (không đối số vẫn in tóm tắt doctor và thoát 2 khi thiếu `ffmpeg-skill`); `flicker_schedule.py` có `--help` một dòng (thư viện, không có CLI); `dviet_7706_typography_choreography.py` và `vietanh_35_typography_engine.py` chỉ chạy self-test khi có `--self-test`, còn `--help` in cách dùng.

**Luật `7.9.0` (từ kiểm định video v4; mỗi dòng là một cổng, lỗi thì sửa nguyên nhân, không nới ngưỡng).**
- **Thẻ pop-out sạch mép và đỉnh đầu:** `render_popout_studio_card` mặc định tô dải tối hai bên nguồn bằng tường sạch (`clean_source_bands`), lấp đốm tối trên tường (`despeckle_wall`), làm mịn mặt nạ đỉnh đầu (`crown_refine`). Cổng: dải tối mép trong `<= 4 px`, `0` đốm, độ răng cưa đỉnh đầu `<= 1,2 px`, độ dốc 10-90 % `<= 4 px` (ref 29 mục 3.1b).
- **Trần chớp sáng:** chớp không đẩy độ sáng trung bình khung quá `220`; tối đa `3` chớp trong 1 s (WCAG 2.3.1); cắt trắng 3,4 s là `opacity <= 70` trong 3 khung. Kế hoạch: `check_hook`; bản dựng: `motion_gate.py --flash`.
- **Chữ đọc được, kể cả nhãn thẻ:** mọi chữ phủ, nhãn thẻ, chú thích plate `>= 64 px` sau khi nhân tỉ lệ plate, glyph `>= 3,3 %` chiều cao; `decorative: true` chỉ cảnh báo. `render_web_plates_batch` gắn `text_audit` (`audit_plate_text_px`) cho từng plate, chữ nhỏ là lỗi; `enforce_min_text_px(forced=True)` dưới sàn nay báo lỗi (trước chỉ cảnh báo).
- **Khoảng cách giữa hai từ:** `>= 0,25 em` ở mọi khung nhìn thấy của hiệu ứng vào (blur sigma ăn `2 sigma`, scale từng từ ăn `(s - 1) x bề rộng từ`). kt03 mặc định tự hạ blur / scale từng từ (`gap_safe_blur_px`, `gap_safe_word_scale`); preset `per_word_stagger` có thêm `max_word_scale_pct: 100` (kẹp phần vượt `101 %`; giá trị cũ giữ nguyên vì preset chỉ được thêm, không được sửa).
- **Phủ chữ 0-3 s:** từ chữ đầu tiên tới 3,0 s không có quãng trống chữ dài hơn `150 ms` (`text_coverage`).
- **Chữ đầu tiên trước từ nói:** mặc định bật (`check_hook(strict_first_text=True)`, `hook_text_from_words(strict=True)` đặt dòng dẫn trước từ `20 ms`); `strict=False` chỉ để đọc kế hoạch cũ.
- **Hàng SFX `block: true`:** hàng `qa_sync` có tiếng sớm hơn hình quá `0,1 s` không bao giờ là ĐẠT, được ghi `block: true` trong `sfx_shifts.json`, và Gate 7b trượt (exit 1, `gate_pass`) khi còn một hàng như vậy.
- Test: `tests/test_skill_v79.py` 01-10.

**Không thuộc gói này (gói khác lo, xem finding gốc).** Cổng chói sáng (S-NOPHOTO), `qa_sync` đếm hàng chưa đo (S-QAHEAD, S-QABLIND, S-SHIFT), cỡ chữ thật của plate (S-FONTGATE, V1), chữ đầu tiên theo từ nói (S-FIRSTTEXT, V5), blur so với khoảng cách từ (V3), lint của Look S (S-LINTBLIND), PiP đè sản phẩm (V7). Các file đó (`studio_recipe.py`, `motion_gate.py`, `web_plate_builder.py`, `fast_studio_compositor.py`, `studio_scene_recipe.json`, `test_skill_v79.py`) không bị gói dọn kho này chạm vào.

**Bản v5 video:** xem `out/qa_v5`.

### 2.1 Mục `v7.8.0` (gói S2: học thuyết và bộ lập kế hoạch; chưa commit)

**Đã đổi.** `studio_recipe.py` (VERSION `7.8.0`): `hook_text_from_words(words)`, `hook_motion_floor(resets)`, `plan_micro_moves(shots, source_motion)`; `check_hook(hook, words=None)` thêm `text_voice_sync`, `hero_safe_zone`, `text_min_size`, `hook_motion_floor`; `check_pacing` thêm `bg_static_hold` cho shot có cờ `broll` và danh sách `moves`; reset có kiểu `{t, kind, layer: bg|overlay, mag}` (số thực / tuple cũ vẫn là reset nền; không truyền `words` thì chỉ có cảnh báo `no words provided`). Preset `studio_scene_recipe.json` (`version 7.8.0`): `first_text_max_ms 200`, hero là ràng buộc `{anchor_word: auto, lead_ms: [150, 200]}` (hết chữ `3 BƯỚC` và ghi chú thoả hiệp), `hero_box.product_safe` + `stage {s 0.72, text_band_y [0.07, 0.31]}`, thêm các sự kiện nền (glint, snap-punch, thẻ rơi, riser push) và SFX tương ứng, khối `pacing.motion`. Tài liệu: ref 28 (mục 2: hook dựng từ từ của giọng, sân khấu sản phẩm, sàn chuyển động, thước đo dviet chứ không phải V21, SFX dựng lại cùng lượt, bước QA đọc lời 0-3.5 s cạnh danh sách chữ), ref 29 (mục 3.1a: mặc định thẻ nét, thang upscale, quy tắc resample một lần, cổng, vì sao mốc Laplacian toàn khung 430 sai), `SKILL.md`, `README.md`. Hai test `test_skill_v73.py` và `test_dviet_docs.py` đọc phiên bản từ `SKILL.md` (chấp nhận `>= 7.6.0`) thay vì ép `7.6.0`.

**Ba lỗi (nhãn [ĐO] / [ƯỚC]).**
- **D1:** hero `3 BƯỚC` ở `0.17 s`, giọng nói `3` ở `3.48 s` [ĐO]; hero che nửa dưới chai (chai chiếm x 0.25-0.77, y 0.05-0.87 [ĐO]). Quyết định (người dùng duyệt): giữ giọng, chữ theo lời nói. Chữ đầu `TRÊN ĐÂY LÀ` ở 150 ms (không thể có từ khoá thật `video` trước 860 ms nếu không cắt lại giọng, điều đã bị cấm), hero `VIDEO` ở 700 ms (giọng 860 ms), mệnh đề `BỌN MÌNH VỪA LÀM` ở khoảng 1500 ms (giọng 1660 ms) [ƯỚC cho các mốc chữ]. Không dùng chữ `khách hàng` (ASR `hàng` có thể là `hãng`).
- **D2:** thẻ pop-out mềm: mép 19-21 px, Laplacian toàn khung 8-34 [ĐO]. Công thức mới đo trên khung S09 thật: mép 4-5 px, tỉ lệ Laplacian vùng mặt khoảng 2.2x [ĐO]. Không có upscaler nơ-ron trên máy (OpenCV 5.1.0 không có `dnn_superres`, không có realesrgan / waifu2x / torch / ONNX SR); ONNX x2 cần tải về và người dùng duyệt.
- **D3:** nền gần như đứng yên 2.03-3.38 s (frame diff < 1.0, trung bình 1.20 [ĐO]); clip nguồn thực chất là ảnh tĩnh (flow 0.05-0.06 px/khung [ĐO]). Cách sửa: máy quay, ánh sáng và thẻ chồng lên, không sinh media Flow mới. Số chứng minh [ĐO, kỹ sư]: đẩy 4 %/s cho diff 1.23, 14.5 %/s cho 2.09.

**Cổng mới.** Cấp kế hoạch (`studio_recipe.py`): `text_voice_sync`, `hero_safe_zone`, `text_min_size`, `hook_motion_floor`, `bg_static_hold`. Cấp kết xuất (`motion_gate.py`, gói S1): diff nền trung bình `>= 2.0` trong 2.03-3.38 s, không chạy tĩnh `> 0.6 s`, `hero_product_overlap_px = 0`, mép thẻ `<= 6 px`, tỉ lệ Laplacian mặt `>= 1.8x`.

**Giới hạn đã biết.**
- Ngưỡng là [ƯỚC]: 0.8 s / 1.2 s cho đoạn tĩnh, 10 %/s đẩy, 4 % khung/s lia, 64 px / 3.3 % cỡ chữ, dải dẫn 100-250 ms. Chúng rút từ một video của người dùng cộng **17 mẫu `@__dviet` của một kênh**, không phải luật của TikTok.
- Cửa sổ dẫn chữ 0-400 ms và dải thoải mái 100-250 ms là thiết kế, chưa kiểm với người xem. Mốc SFX đều [ƯỚC] (không tách được khỏi giọng và nhạc); phải chạy kiểm trùng clip (Gate 7) với 3 lần dùng `52_UI_Card_Magnetic_Dock`.
- `hero_safe_zone` ở cấp kế hoạch chỉ so hộp chữ với `product_bbox` hoặc đường đỉnh nắp (`0.32 H`); khi chỉ có `stage.s` thì đỉnh nắp lấy `0.32 H` bất kể `s`, và dung sai 2 % tính theo diện tích hộp chữ. Mốc đo thật là `hero_product_overlap_px` trên MP4.
- `text_voice_sync` so từ đầu tiên của mỗi chữ; các từ sau chỉ cảnh báo nếu không có trong lời. Từ ASR sai thì cổng sai theo.
- `studio_recipe.py` vượt 400 dòng (giới hạn kiểm thử nâng lên 480).
- Liên kết chết ở ref 12 và 13 chưa sửa (hai file không thuộc gói S2): `references/12_ffmpeg_skill_42_tools_integration.md` trỏ `../scripts/04_qa_4pass_inspector.py`; `references/13_dviet_19_videos_smooth_zoom_and_pacing_mastery.md` trỏ `../scripts/build_v14_dviet_smooth_master.py`. Việc hai ref cùng số 24 vẫn là backlog.

---

## 3. Bảng tính năng hiện tại

Trạng thái: **works+tested** = chạy được và có test tự động đạt; **works (self-test)** = chạy được qua self-test riêng nhưng không có file test; **works (chưa test)** = `--help` chạy, không có test; **chưa xác minh live** = test offline đạt, chưa dựng/xuất thật trong phiên này; **doc-only** = chỉ có tài liệu.

### 3.1 Công cụ lõi (`scripts/tools/`)

| Tool | Làm gì | Trạng thái |
|---|---|---|
| `probe_and_align.py` (6174 dòng) | Ingest, transcript (faster-whisper), khoảng lặng, `words_tl.json`, contact sheet, tier fast/studio/full/auto | works; chỉ `test_stability.py` chạm tới; **không có test ASR đầu-cuối** |
| `web_plate_builder.py` (7203) | Plate chữ động `kt01..kt12`, thẻ kính 3D, 3 layout `@__dviet`, Chrome headless 60fps | works+tested (`--self-test` rc=0; test_dviet_docs, v76_fixes, v77) |
| `typography_composer.py` (7403) | Lịch kinetic beat, Dual-Rail, Jewel 4 hồi | works+tested (`--self-test`, `--self-test-v71` rc=0) |
| `visual_blocks.py` (2926) | 13 khối thị giác, 4 canvas chuyển động, lint prompt B-roll | works; test chạm qua `test_ports.py` (chỉ lint) |
| `fast_studio_compositor.py` (1453) | A1/A2/B, hair-safe, VoiceSyncGuard, pop-out, compose master | works+tested (v73, v76_fixes, v77, stability); **CLI chỉ re-encode** (`--draft/--master`), plate studio chỉ qua API Python |
| `compile_and_verify.py` (9082) | Biên dịch `.fcproj` + 8 cổng (`--tier`, `--profile`, `--audio-profile`) | works+tested (6 file test) |

### 3.2 CLI phụ trợ

| Tool | Làm gì | Trạng thái |
|---|---|---|
| `scripts/env_status.py` | Preflight node/chrome/ffmpeg/matte/font/ovs_core/filmcraft | works+tested. **[ĐO]** chạy ra `READY`; thiếu (tuỳ chọn): `u2netp`, font DFVN West West Condensed, LigaSFMono, `ffmpeg-skill` |
| `dviet_text.py` | Sự kiện chữ theo vai trò thành track chữ | works+tested (test_dviet_docs) |
| `studio_recipe.py` | Lập cảnh Look S theo V21 + `check_hook/check_pacing/check_source_reuse` | works+tested (`test_studio_recipe.py`) |
| `duck_keyframes.py` | Keyframe ducking nhạc nền 4 điểm | works+tested; **chưa nối vào compile** (README nói rõ profile `tiktok_loud` vẫn `no_ducking: true`) |
| `flicker_schedule.py` | Lịch nhấp nháy silhouette, macro vanish/clone | works+tested (thư viện, `--help` không in gì); hành vi trong FilmCraft **chưa xác minh** (docstring: `behaviour_unverified_in_app`) |
| `filmcraft_cli.py` | Shim `filmcraft --control` | test offline đạt; **chưa xác minh live** (cần Xvfb + app) |
| `fc_export.py` | Xuất `.mp4` từ `.fcproj` qua exporter vendor | test offline đạt; **chưa xác minh live** (README: ~49 s cho clip 6 s) |
| `spec_from_plan.py` | Plan thành `.craft.json` | works+tested (stability, effect_presets) |
| `silence_cut.py`, `speed_media.py` | Cắt lặng / tốc độ trước ingest | works+tested (`test_ports.py`) |
| `sfx_auto.py`, `qa_sync.py`, `sfx_shift.py` | Kế hoạch SFX, đo đồng bộ SFX trên mp4 đã xuất, dịch một lần (Gate 7b) | works+tested (`test_ports.py`, clip tổng hợp) |
| `broll_from_video.py` | Kế hoạch slot B-roll + lint prompt Flow (không sinh media) | works+tested (`test_ports.py`) |

### 3.3 Engine `scripts/`

| Script | Trạng thái |
|---|---|
| `dviet_smooth_camera_engine.py` | works+tested (`--self-test` rc=0, sai số ln < 0.003) |
| `web_cinema_plate_engine.mjs` | works (qua `web_plate_builder`, Node 22 + Chrome có sẵn) |
| `dviet_motion_canvas_engine.py` | works (chưa test tự động nào tham chiếu) |
| `dviet_7706_typography_choreography.py`, `vietanh_35_typography_engine.py` | works (self-test), nhưng **không có argparse: `--help` chạy luôn self-test**; không có test file |
| `ffskill_bridge.py` | **tuỳ chọn, hiện không dùng được**: thiếu `/home/vmiz/opa-software/ffmpeg-skill`, thoát rc=2 |
| `scripts/vendor/ovs_core/` | Bản sao vendor các cổng (spec_lint, edit_rules, audit_sfx, audio_levels, craftctl...), có `PROVENANCE.md` + sha256 |

### 3.4 Preset (16 file `presets/`)

Cũ (tracked): `atomic_motion_library`, `dviet_pattern_catalog`, `execution_tiers`, `format_modes_catalog`, `industry_profiles`, `platform_safe_zones`, `sfx_micro_sync_rules`, `typography_hierarchy_presets`, `visual_archetypes_catalog`.
Mới (**chưa tracked**): `broll_lint_contract`, `canvas_presets`, `dviet_style_tokens`, `pain_keywords`, `profile_overrides` (có `studio_14`, `tiktok_loud`, `platform`), `sfx_catalog`, `studio_scene_recipe`.

### 3.5 Tham chiếu 20 đến 30 (đều chưa tracked trừ ref 20)

| Ref | Nội dung | Ghi chú |
|---|---|---|
| 20 | v7.3 hybrid A x B, voice-sync, hair-safe | tracked, có sửa |
| 21 | Spec `.craft.json` tối thiểu | test_stability kiểm ví dụ |
| 22 | Flow B-roll | |
| 23 | Quyết định profile `dviet` + BACKLOG xếp hạng | |
| 24 | Công thức Look S (`24_studio_look_recipe.md`) | số 24 không còn trùng (control bridge đã đổi thành 30, v7.9.0) |
| 25 | Độ to TikTok vs NLE | |
| 26 | Font `@__dviet` + fallback tiếng Việt | |
| 27 | Công thức Premiere thành FilmCraft (558 dòng) | |
| 28 | Hook 5 giây đầu + luật nhịp | |
| 29 | Thẻ pop-out, khoảng trống H5 (spec chưa có khoá `masks`) | |
| 30 | Cầu nối điều khiển FilmCraft (`30_filmcraft_control_bridge.md`) | trước đây là `24_filmcraft_control_bridge.md` |

### 3.6 Test (chạy bằng venv, **[ĐO]** exit code)

14 file `tests/test_*.py` (gói khác có thể thêm `test_skill_v79.py`), **tất cả phải exit 0**; `install.sh` chạy chúng bằng glob. Danh sách 13 file lúc kiểm kê gốc: `test_ducking`, `test_dviet_docs`, `test_effect_presets`, `test_filmcraft_cli`, `test_flicker_schedule`, `test_fonts_vi`, `test_loudness_v75`, `test_ports`, `test_skill_v73`, `test_skill_v76_fixes`, `test_skill_v77`, `test_stability`, `test_studio_recipe`. Thêm: `web_plate_builder --self-test` rc=0, `dviet_smooth_camera_engine --self-test` rc=0, `typography_composer --self-test` và `--self-test-v71` rc=0. Fixture media (`tests/fixtures_ports`, 17 MB) được tổng hợp lúc chạy và bị `.gitignore` bỏ qua, đúng thiết kế.

---

## 4. Phiên bản lỗi thời (cần sửa)

- `install.sh`: **đã sửa** (nhãn `v7.9.0` ở 3 chỗ; chạy mọi `tests/test_*.py` bằng glob, không còn danh sách cứng 5 test).
- `requirements.txt` dòng 1: **đã sửa** (`v7.9.0`).
- `scripts/dviet_smooth_camera_engine.py:54` `ENGINE_VERSION = "7.4.0"` và chuỗi help "Universal Studio Director v7.4.0".
- `scripts/tools/probe_and_align.py:6017`: description argparse còn "... Engine v7.4.0" (hằng `VERSION` thì đã `7.7.0`).
- `scripts/tools/web_plate_builder.py:7073`: `"version": "7.4.0"` (self-test sinh ra; có thể cố ý vì là bản layout v7.4).
- `presets/dviet_style_tokens.json`, `presets/canvas_presets.json`: `"version": "7.4.0"` (có thể cố ý, đánh dấu phiên bản token; cần quyết định).
- `scripts/vendor/ovs_core/PROVENANCE.md` tiêu đề: **đã sửa** (`v7.9.0`).
- `tests/test_skill_v73.py` và `tests/test_dviet_docs.py`: **đã sửa ở v7.8.0**, đọc phiên bản từ `SKILL.md` (chấp nhận `>= 7.6.0`) và kiểm khớp giữa `SKILL.md`, README và tài liệu này; không còn ép `7.6.0`.
- `SKILL.md`: dòng 15, 23, 68, 93, 159 còn nhãn `v7.6.0` / `v7.5.0`. Phần lớn là chủ ý (nói nguồn gốc tính năng); dòng 68 (bảng tier "Active Physics & v7.6.0") và 93 ("Enforce v7.6.0 ... Laws") nên đọc lại.
- Phiên bản thực tế trong mã: **đã sửa** (mọi hằng phiên bản hiện hành là `7.9.0`; test so với frontmatter `SKILL.md`, xem mục 2.0, finding S2).

---

## 5. Tài liệu so với mã

- **Cờ `--flag`: không có cờ ảo.** **[ĐO]** Trích 91 cờ từ SKILL.md, README.md và ref 20-29, so với `--help` của mọi script: 10 cờ không khớp, tất cả là cờ của binary `filmcraft` (`--control`, `--control-input-only`, `--data-dir`, `--empty`, `--graphics`, `--recover`, `--version`) hoặc `fc_build_fast.py --report` (ref 24), hoặc đoạn URL (`--cms-108166`, `--cms-108578`) bị regex bắt nhầm. Không tool nào của skill bị mô tả sai cờ.
- **Hàm được nhắc trong tài liệu:** kiểm 23 tên hàm dạng `ham(`; không thiếu hàm nào. Kiểm tay thêm: `render_popout_studio_card`, `hook_template`, `check_hook`, `check_pacing`, `check_source_reuse`, `person_alpha_u8`, `echo_opacity`, `check_subject_matte`, `refuse_c_class` đều tồn tại.
- **Liên kết chết (2):** `references/12_ffmpeg_skill_42_tools_integration.md` trỏ `../scripts/04_qa_4pass_inspector.py`; `references/13_dviet_19_videos_smooth_zoom_and_pacing_mastery.md` trỏ `../scripts/build_v14_dviet_smooth_master.py`. Cả hai script không tồn tại.
- **README mục 4 (Kiểm thử)** chỉ liệt kê 5 test + 2 self-test; thực tế có 13 test. Mô tả `test_skill_v73.py` (">= 27 tài liệu tham chiếu") không còn phản ánh số lượng thật (ref 01..29 + `dviet_19/`).
- **README mục 2 (cấu trúc thư mục)** liệt kê 5 test; thiếu 8 file test mới và `docs/`.
- **Tiêu đề "6 Stateless Core Hands"** vẫn đúng, nhưng thực tế có thêm 13 CLI phụ; mô tả SKILL.md đã nêu danh sách, chỉ nên thống nhất cách đếm.
- `ffskill_bridge.py` được mô tả trong README là "cầu nối chuẩn hóa âm thanh & khung hình" nhưng cần repo ngoài chưa clone; README không nói rõ nó đang không chạy được.

---

## 6. File chưa tracked nhưng skill cần (git sẽ làm mất)

**[ĐO]** Các file tracked đã sửa hoặc test đều tham chiếu những file sau, nên clone sạch sẽ hỏng:

- `scripts/vendor/ovs_core/` (764 KB, 15 file): `compile_and_verify`, `fc_export`, `filmcraft_cli`, `env_status`, các test đều import từ đây. Thiếu là gate không chạy.
- `presets/`: `profile_overrides.json` (`--audio-profile` lấy lựa chọn từ file này), `studio_scene_recipe.json`, `dviet_style_tokens.json`, `canvas_presets.json`, `sfx_catalog.json`, `pain_keywords.json`, `broll_lint_contract.json`.
- Toàn bộ 15 CLI mới trong `scripts/tools/` và `scripts/env_status.py` (README và SKILL.md đã ghi tên chúng).
- `references/21..29` (10 file) và `references/dviet_19/` (18 file; `test_dviet_docs.py` đòi `INDEX.md`).
- 12 file test mới + `tests/fixtures_stability/` + 3 JSON trong `tests/fixtures_ports/` (không bị ignore).
- `docs/TIEN_DO_SKILL.md` (file này).

Tất cả đều không nằm trong `.gitignore` (chỉ `*.mp4 *.wav *.mov *.fcproj...` bị ignore, không ảnh hưởng nguồn). Cần `git add` sau khi người dùng cho phép commit.

---

## 7. Khoảng trống và backlog (liên quan 3 lỗi D1-D3 của video v3)

**Cập nhật v7.8.0:** các mục 1-4 dưới đây là hiện trạng trước gói S2; D1 (chữ-giọng, vùng an toàn, `first_text_max_ms 200`, hết `center_y_frac`) và D3 (sàn chuyển động nền, `bg_static_hold`) đã có cổng ở cấp kế hoạch, cổng đo trên MP4 nằm ở `motion_gate.py` (gói S1); mục 2.1 là bản ghi chi tiết.

Đối chiếu với mã hiện tại **[ĐO bằng đọc `studio_recipe.py`, `studio_scene_recipe.json`]**:

1. **D1 (chữ không khớp lời)**: `check_hook` không có kiểm "chữ hero khớp từ khoá đang nói". Không có kiểm hero có đè lên sản phẩm; "must not cover the product" chỉ là ghi chú văn bản trong `hero_box.note`. Preset đặt `hero_box.center_y_frac = [0.55, 0.62]` (nửa dưới khung), đúng vùng thường có chai sản phẩm, nên chính preset có thể gây D1. `first_text_max_ms = 300` trong khi quyết định người dùng là `<= 200 ms`.
2. **D2 (thẻ pop-out mềm)**: `render_popout_studio_card` mặc định `photo_scale=1.36`; ref 29 ghi RVM còn viền xám và đề xuất `downsample_ratio 0.5`. Không có chỉ số độ nét (Laplacian) nào trong compositor, `studio_recipe` hay test; không có QA tự động bắt cảnh nguồn 720p bị upscale mềm.
3. **D3 (tĩnh 2.2-3.4 s)**: `check_pacing` làm việc ở mức kế hoạch (`dead_hold_share` là ước lượng). Không có đo frame-diff trên file đã render, và không có kiểm tra "nền không đổi trong khi PiP pop".
4. **Thiếu cổng đo trên file render** cho hook: SKILL.md dặn "đo file đã render" (độ sâu vacuum, chữ đầu, chiều cao hero) nhưng không có script đo đóng gói; `qa_sync.py` chỉ đo SFX so với hình.
5. **Chưa nối**: `duck_keyframes` vào bộ biên dịch; `studio_14` ducking bật theo preset nhưng thực thi chưa được kiểm trên giọng thật.
6. **Spec thiếu khoá `masks`** (H5): không thể ghi mask native vào `.fcproj`; pop-out chỉ ở lớp B (hai plate RGBA).
7. **BACKLOG hiệu ứng** (ref 23/27): tile waveform SFX, keycap 3D, timeline NLE giả, chữ dán tường trên cảnh cầm tay, planar tracking có che khuất, clone, pixel stretch, constellation. Lớp C (không khả thi): Object Mask chất lượng cao cho vật bất kỳ, Time Displacement native.
8. **Chưa xác minh live** trên FilmCraft: `filmcraft_cli`, `fc_export`, opener `flicker` (MCP `filmcraft` không kết nối được trong phiên này).
9. **Một kênh, 17 mẫu**: mọi số hook/nhịp là [ĐO] trên một kênh, SFX là [ƯỚC] (không tách được khỏi giọng). Script đo (`hook_measure`) không đi kèm skill.
10. **Vệ sinh repo**: hai ref cùng số 24; 2 liên kết chết ở ref 12/13; script `dviet_7706...` và `vietanh_35...` không có argparse nên `--help` chạy luôn render; không có CI chạy cả 13 test; `install.sh` chỉ chạy 5.

## 8. Việc nên làm (thứ tự đề xuất, chưa thực hiện)

1. Người dùng cho phép commit, tạo nhánh mới (`feat/v7.7`), `git add` toàn bộ mục 6 (loại `__pycache__`).
2. Đồng bộ chuỗi phiên bản ở mục 4 (đặc biệt `install.sh`, `requirements.txt`, camera engine, `probe_and_align` argparse) và để `install.sh` chạy cả 13 test.
3. Thêm vào `studio_recipe`: kiểm "chữ hero khớp từ đang nói" (so với `words_tl.json`, hero đến sớm 150-200 ms), vùng an toàn sản phẩm (không đè bbox sản phẩm), `first_text_max_ms` = 200, dời `center_y_frac` khỏi vùng sản phẩm.
4. Thêm cổng đo trên render: Laplacian theo cảnh (cảnh pop-out), frame-diff theo cửa sổ 1 s (bắt cảnh tĩnh).
5. Sửa README mục 2 và 4; sửa 2 liên kết chết; đổi tên một trong hai ref 24.
