# 08 — Thư viện Mẫu & Quy trình 4 Trụ cột (`@haihoang_airaviec` Method trên 13 Video `@__dviet`)

Tài liệu này đóng gói kết quả mổ xẻ **13 video `@__dviet`** theo đúng phương pháp luận 4 trụ cột từ video mẫu `@haihoang_airaviec` (`7707599674923896070`):
1. **Speech-to-Visual Mapping** (Lời thoại → Thiết kế/Cảnh)
2. **Design Anatomy** (Font, Mã màu, Tỷ lệ, Chất liệu)
3. **Motion & Transition Logic** (Chuyển động & Chuyển cảnh)
4. **SFX Selection & Placement** (Chọn đúng loại SFX theo phổ tần số & đặt đúng mili-giây)

---

## 1. Bộ 3 Font & Quy tắc 3 Màu chuẩn (Verified từ `7677448217667063061`)

Chính tác giả `@__dviet` xác nhận hệ thống typography tối giản gồm đúng **3 họ font** + **3 màu**:
- **Font 0 chân (Sans-serif):** `SF Pro Display` / `Inter` / `Be Vietnam Pro` — dùng cho từ nối, caption thoại, và tiêu đề khối đặc (`VIDEO`, `CHO DỰ ÁN`), luôn **giảm letter-spacing âm nhẹ** (`-0.02em..-0.04em`) + drop-shadow mềm.
- **Font có chân (Serif Italic):** `Playfair Display` / `IvyPresto Display` — dùng cho **từ khóa nhấn mạnh cảm xúc/hành động** (`bạn cần biết`, `nhưng`, `phức tạp`, `follow mình`, `workflow`, `nham nhở`).
- **Font sáng tạo (Calligraphy / Script):** `Whisper` / `SVN-Aaron Script` — dùng cho **tên riêng, CTA, từ khóa nghệ thuật** (`Lưu lại`, `Việt`, `videographer`, `editor`, `Mượt`).
- **Quy tắc 3 Màu (`#FAFAFA` + `#111111` + 1 Accent):**
  - **1 Màu Sáng (`#FAFAFA`):** Nền slide đảo cực & chữ chính.
  - **1 Màu Tối (`#111111` / `#0D0D0D` lụa đen):** Nền slide/UI tối & chữ trên nền sáng.
  - **1 Màu Nổi (Accent — khóa 1 màu/video theo màu áo hoặc chủ đề):** Tím Lavender (`#8B5CF6` / `#A78BFA`), Xanh Lá Neon (`#22C55E` / `#4ADE80`), Vàng Gold (`#F5C518`), hoặc Cam Rực (`#F28C18`).

---

## 2. Bảng Speech-to-Visual Mapping (Khi nào giữ mặt vs bung thiết kế?)

| Ngữ cảnh lời thoại | Mẫu thiết kế & Bố cục | Video tham chiếu |
| :--- | :--- | :--- |
| **Mở đầu Hook / Giới thiệu tên** | Talking-head + Text 2 tầng ở **vùng ngực (`y=55–65%`)** hoặc **Text Behind Subject (`y=20–30%`)** | `7677448217667063061`, `7693026626333871381` |
| **Nêu số liệu / Profile / Bằng chứng** | Vẫn giữ Talking-head ở dưới, chèn **UI Card bo góc viền Accent** ở nửa trên hoặc **PiP + Icon vector** | `7664447064352509204`, `7677448217667063061` |
| **Ngắt nhịp / Phản đề (`"Nhưng..."`, `"Lỗi phổ biến"`)** | **Đảo cực Nền Trắng (`#FAFAFA`)** toàn khung hình hoặc **Mirror Flip** đối xứng trên-dưới | `7677448217667063061`, `7688934517783989524`, `7693026626333871381` |
| **Liệt kê 3–4 bước (`Bước 1, 2, 3`)** | **Số cỡ đại (`1`, `2`, `3`)** nền lụa đen `#0D0D0D` + lồng chữ Serif nghiêng + **3-Tier Layout** (Header 25% / UI Card 40% / PiP 25%) | `7688934517783989524`, `7707653827016674580` |
| **Thao tác phần mềm / Demo kết quả** | **Split-Screen 50/50** (UI/Demo nửa trên, A-roll/Bảng thông số nửa dưới), từ khóa thao tác (`ALT+G`, `Screen`, `Multiply`) tô màu Accent | `7667598741888634132`, `7683763922234641684` |
| **Khái niệm trừu tượng / Cảm xúc mạnh** | **Text-on-path uốn tròn quanh đầu**, **Clone đa bản thể**, **Sand/Particle Dissolve**, **Light Match** | `7706183278461570356`, `7664835388476755220` |
| **B-roll minh họa cuối / Kết nối** | **3D Perspective Timeline** (nghiêng góc + motion blur) + **Frosted-Glass Pills** (`nhịp`, `âm thanh`, `màu`) | `7688934517783989524`, `7693026626333871381` |
| **Chốt CTA (`Comment`, `Follow`, `Lưu lại`)** | Talking-head chính diện, chữ **Script/Calligraphy + Accent cỡ đại** ở vùng ngực hoặc sau đầu | Tất cả 13 video |

---

## 3. Ma trận Chọn & Đặt SFX theo Phổ Tần số

Qua phân tích 13 file `sfx/<id>.json` đối chiếu với `transcripts/<id>.json` và `grids/<id>_grid30.jpg`:

1. **`SUB_THUMP / BASS_HIT` (`< 150 Hz`):**
   - **Tần suất:** `3–11` lần/video (chỉ đặt ở **điểm chốt chuyển chương/câu**, không rải dày).
   - **Vị trí đặt:** Ngay tại điểm **đảo cực nền tối → trắng (`#FAFAFA`)**, **bật Title Card / Số bước (`1/2/3`)**, **đổi góc camera/B-roll**, hoặc **từ khóa kết luận (`workflow`, `comment`, `hard cut`, `J-Cut`)**.
2. **`CLICK / FLASH / RISER_HI` (`> 2 kHz`):**
   - **Tần suất:** `1–5` lần/video (tập trung ở video có UI/Tutorial/Before-After).
   - **Vị trí đặt:** Ngay thời điểm **con trỏ chuột click trên UI**, **bật thẻ so sánh `Before / After`**, **xuất hiện Color Swatch**, hoặc **chữ bật sáng/glow**. *(Video thuần kể chuyện điện ảnh như `7706183278461570356` dùng `0` click UI).*
3. **`WHOOSH / VOICE_PUNCH` (`150 Hz – 2 kHz`):**
   - **Tần suất:** `0.9 – 1.8` lần/giây.
   - **Vị trí đặt:** Bám theo từng nhịp **swap Track T2**, **chuyển slide/PiP**, và **đầu câu chuyển ý** (đặc biệt mạnh ở `-4.9` đến `-8.5 dBFS` tại các điểm chuyển động lớn như Whip Pan hoặc White Slide).
