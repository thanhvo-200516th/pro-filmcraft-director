# Tạo 3D Assets minh hoạ câu thoại bằng Google Flow (`flow_3d_assets.py`)

Tài liệu hướng dẫn quy trình tạo **asset / đạo cụ 3D minh hoạ trực quan** cho các câu thoại đắt giá trong kịch bản và video (số liệu, từ khoá nỗi đau, khái niệm AI/hệ thống, ẩn dụ lõi) thông qua MCP `google-flow`, sau đó tách nền alpha RGBA và gắn trực tiếp lên track overlay trong `pro-filmcraft-director` / FilmCraft.

> **Tài liệu liên quan:** [`references/22_flow_broll.md`](22_flow_broll.md) · [`references/24_studio_look_recipe.md`](24_studio_look_recipe.md)

---

## 1. Khái niệm & Chọn chế độ (`image_alpha` vs `video_3d`)

| Chế độ | Tool Google Flow MCP | Model (ID chuẩn / Nhãn UI) | Đầu ra & Cách ghép | Khi nào nên dùng |
| :--- | :--- | :--- | :--- | :--- |
| **`image_alpha`** (mặc định) | `flow_generate_image` | `nano-banana-pro` / `nano-banana-2` (`nano-banana-2-1`) | Ảnh vật thể 3D isometric trên nền đồng nhất `#00FF00` → tách qua `extract-alpha` thành **PNG RGBA trong suốt** | Minh hoạ **trên A-roll** (`upper_right` / `upper_left`, không che mặt người nói) hoặc **trên B-roll** (`center_card`); nhanh, ít tốn tín dụng, tách nền sạch 100%, ghép trực tiếp lên compositor hoặc FilmCraft overlay track. |
| **`video_3d`** | `flow_generate_video` | `omni-flash` (`omni-1-2-flash`) | Clip 3D macro diorama chuyển động (`Slow 3D turntable orbit`, `9:16`) | Minh hoạ **cảnh cắt toàn/trung tâm (`full_cutaway` / `center_card`)** cho ẩn dụ phức tạp (dòng chảy dữ liệu, bánh răng đồng bộ, cát chảy trong đồng hồ cát). |
| **`mixed`** | Kết hợp cả hai | Cả hai model trên | Tự phân bổ `video_3d` cho cảnh B-roll trọng tâm và `image_alpha` cho các điểm nhấn còn lại | Video cần 1–2 cảnh 3D động làm điểm nhấn kết hợp 3–5 prop 3D nổi quanh người nói. |

---

## 2. Quy trình 6 bước từ Kịch bản → Timeline

### Bước 1: Lập kế hoạch (`flow_3d_assets.py plan`)
Trích xuất các câu/mệnh đề có trọng số cao nhất (số liệu, tiền, `%`, từ khoá nỗi đau trong `PAIN_LEXICON`, khái niệm AI/quy trình, ẩn dụ lõi), gắn `seq`, mốc `at`/`dur` theo tốc độ video, `placement` an toàn trên khung `1080×1920`, và prompt chuẩn `SPEC-MASTER-VIDEO-PROMPT-ARCH-V1`:

```bash
PY=~/.venvs/video-skills/bin/python3

# Từ 00_storyboard_manifest.json (khuyên dùng kèm --speed-plan để lấy mốc at/dur khớp khít timeline)
$PY scripts/tools/flow_3d_assets.py plan \
  --manifest /path/to/00_storyboard_manifest.json \
  --speed-plan /path/to/media/speed_plan.json \
  --max-assets 6 \
  --mode image_alpha \
  --out-dir /path/to/work/3d_assets

# Hoặc từ broll_plan.json (khi làm việc với video talking head thô)
$PY scripts/tools/flow_3d_assets.py plan \
  --plan /path/to/broll_plan.json \
  --speed 1.10 \
  --mode mixed \
  --out-dir /path/to/work/3d_assets
```

Đầu ra gồm `3d_assets_plan.json` (máy đọc) và `3d_assets_plan.md` (bảng duyệt cho người & agent).

### Bước 2: Kiểm định Prompt & Anchor Quote (`lint-plan`)
Bắt buộc chạy trước khi gọi Google Flow MCP để đảm bảo 0 Anti-Slop, 0 cú pháp trọng số CLIP `(x:1.3)`, có chuyển động máy cho `video_3d`, không đuôi phủ định, và `anchor_quote` nằm nguyên văn trong kịch bản:

```bash
$PY scripts/tools/flow_3d_assets.py lint-plan /path/to/work/3d_assets/3d_assets_plan.json
```

### Bước 3: Tạo bằng Google Flow MCP
1. Kiểm tra tài khoản & số dư tín dụng: `flow_list_accounts` → `flow_inspect_account` (xác nhận model `nano-banana-pro` / `nano-banana-2` / `omni-flash` và số dư; thiếu tín dụng → báo người dùng và dừng).
2. Với từng mục `image_alpha`: gọi `flow_generate_image` với:
   - `prompt`: copy nguyên văn `asset["prompt"]`
   - `model`: `"nano-banana-pro"` (hoặc `"nano-banana-2"`)
   - `aspectRatio`: `"1:1"`
   - `outputs`: `1` (hoặc `2` để chọn bản sạch nhất)
   - `outputDirectory`: `"/path/to/work/3d_assets/_raw"`
   - `fileName`: `"3d_01_raw"`
   - `confirmCreditSpend`: `true`
3. Với từng mục `video_3d`: gọi `flow_generate_video` với `model` và `aspectRatio` đúng mã `flow_inspect_account` trả về (vd `omni-1-2-flash`, `9:16`), `upscale: "1080p"` (không có thì `highest_available`), `outputDirectory`, `confirmCreditSpend: true`. Nếu `status="processing"` → poll `flow_job_status` → tải qua `flow_download_job`.

### Bước 4: Tách nền RGBA PNG sạch metadata (`extract-alpha`)
Với các ảnh `image_alpha` sinh trên nền `#00FF00` (hoặc trắng `#FFFFFF` / đen `#0A0E17`):

```bash
$PY scripts/tools/flow_3d_assets.py extract-alpha \
  /path/to/work/3d_assets/_raw/3d_01_raw.png \
  /path/to/work/3d_assets/3d_01_alpha.png \
  --bg auto --pad 16 --max-size 720
```

Script thực hiện:
- Tự nhận diện màu nền từ viền ảnh (`--bg auto|green|white|black`).
- **Edge-connected flood-fill** từ 4 cạnh ảnh: chỉ xoá nền nối thông ra biên, bảo vệ tuyệt đối vùng sáng trắng hoặc bóng tối nằm bên trong vật thể.
- **Green despill** trên vùng viền bán trong suốt để không lem viền xanh lá lên vật thể sáng màu.
- Làm mịn biên anti-aliased (`GaussianBlur`), crop gọn theo alpha bounding box kèm lề `--pad`, resize theo `--max-size`, và ghi PNG **không có metadata** (`pnginfo=None`, sạch EXIF/XMP/C2PA/tEXt).

### Bước 5: Tạo bảng kiểm QA nền caro (`sheet`)
Kiểm tra bằng mắt trước khi đưa vào timeline (đảm bảo viền sạch, không cắt mất chi tiết, đúng nghĩa `anchor_quote`, không lẫn chữ rác):

```bash
$PY scripts/tools/flow_3d_assets.py sheet /path/to/work/3d_assets/3d_assets_plan.json \
  --assets-dir /path/to/work/3d_assets \
  --out /path/to/work/3d_assets/3d_assets_sheet.jpg
```

### Bước 6: Gắn lên Timeline / Compositor
Nạp `3d_assets_plan.json` và gắn các file `alpha_file` vào overlay track của compositor hoặc `.fcproj` tại mốc `(at, dur)` với toạ độ `pos`, `scale`, `anim` (`float` | `spin3d` | `slide` | `pop`) và SFX `pop`.

---

## 3. Quy tắc viết Prompt 3D Asset (chuẩn `SPEC-MASTER-VIDEO-PROMPT-ARCH-V1`)

1. **Vật liệu xúc giác rõ ràng (Tactile 3D Materiality):**
   Luôn mô tả vật liệu vật lý cụ thể thay cho tính từ sáo rỗng: `matte clay`, `brushed anodized aluminum`, `frosted glass`, `brushed brass`, `matte ceramic`.
2. **Bố cục & Quang học Studio (Primacy Zone + Optics):**
   - `image_alpha`: `Studio macro product photograph of a stylized tactile 3D isometric <object>` + `studio three-point rim light, soft diffused top key light, 50mm macro f/4, crisp edge separation`.
   - `video_3d`: bắt buộc đặt 1 chuyển động máy duy nhất ở đầu câu (`Slow 3D turntable orbit around a tactile 3D macro diorama of <object>`) + `SUBJECT ACTION` + `LIGHTING & OPTICS` + `Smooth 24fps motion, consistent geometry`.
3. **Quy tắc Phông nền `#00FF00` cho `image_alpha`:**
   Ghi rõ `centered with generous margin on a uniform solid flat chroma green #00FF00 seamless cyclorama backdrop` (hoặc `#FFFFFF` / `#0A0E17` khi vật thể bản thân mang sắc xanh lá). Đảm bảo vật thể không chạm mép khung để `extract-alpha` giữ trọn vẹn biên trong suốt.
4. **Tuân thủ Anti-Slop & Affirmative Clean-Frame:**
   - **CẤM** từ sáo rỗng: `stunning`, `breathtaking`, `hyper-detailed`, `8k masterpiece`, `magical`, `very realistic`.
   - **CẤM** cú pháp trọng số CLIP: `(keyword:1.3)`, `keyword::2`.
   - **CẤM** đuôi phủ định (`no text`, `no logos`, `no watermarks`, `no subtitles`). Thay bằng ràng buộc khẳng định: `Clean isolated object, unbranded, blank surfaces, centered with full margin`.
   - Tránh gọi tên đồ vật chứa chữ/UI (`chart`, `dashboard`, `number`, `label`, `screen`); thay bằng hình khối vật lý thuần (`ascending prism bars`, `metallic tokens`, `frosted-glass blocks`).

---

## 4. Vùng đặt an toàn trên khung `1080×1920`

| `placement` | `pos` mặc định | `scale` (%) | `anim` mặc định | Ngữ cảnh dùng |
|---|---|---|---|---|
| `upper_right` | `(760, 560)` | `38.0` | `float` | A-roll người nói ở giữa; tránh góc TikTok bên phải (`x > 920`) và phụ đề dưới (`y ≥ 1290`). |
| `upper_left` | `(320, 560)` | `38.0` | `float` | A-roll xen kẽ trái/phải để cân khung hình. |
| `center_card` | `(540, 820)` | `46.0` | `spin3d` | B-roll hoặc khoảng trống giữa vùng tiêu đề trên và phụ đề dưới. |
| `full_cutaway` | `(540, 880)` | `68.0` | `slide` | `video_3d` hoặc điểm nhấn lớn trên B-roll. |
