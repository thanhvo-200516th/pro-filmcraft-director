# 03 — Thông số Vi mô Từng Frame (`30fps` / `60fps`) & Quy luật Micro-Sync

*(Quy đổi: `1 frame @ 30fps = 33.33ms`; khi dựng trên timeline `60fps`, nhân đôi số frame `× 2` để giữ nguyên mili-giây).*

## 1. Quy luật Đồng bộ Âm–Hình (Micro-Sync Law)
1. **Transition SFX (`Whoosh`, `Whip`, `Film Burn`):**
   - Đặt **pre-roll `-2` đến `-4 frames` (`-67ms` đến `-133ms`)** trước điểm cắt, đỉnh năng lượng chạm đúng **Frame 0** cảnh mới hoặc **Frame khóa khung** sau blur.
2. **Text / UI Pop / Badge (`Pop`, `Click`, `Impact`):**
   - **Không đặt ở frame bắt đầu fade mờ.** Đặt tại **frame giữa cú tăng tốc (`50%–60%` scale)** hoặc **frame khóa nét 100% (`0 frame` offset)**.
3. **Đảo cực & Xé giấy (`Polarity Flip`, `Paper Tear`):**
   - `Polarity Flip` (1f snap): Khớp **`0 frame`** hoặc hình đi trước **`-3..-4f`** so với đỉnh thoại.
   - `Paper Tear`: Đỉnh SFX rơi vào frame **nội dung bên trong bắt đầu lộ ra**.

## 2. Bảng Công thức Frame Chuẩn (`@ 30fps` | `@ 60fps`)

| Kỹ thuật | Thời lượng (`30fps` \| `60fps`) | Chi tiết Keyframe / Diễn biến |
| :--- | :--- | :--- |
| **Clean Text Fade-in** | `4–5f` \| `8–10f` (`133–167ms`) | Opacity `15% → 100%` (`Ease Out`). |
| **Editorial Blur-in** | `10f` \| `20f` (`333ms`) | `Gaussian Blur 18px → 0px`, Opacity `10% → 100%`, SFX peak ở frame cuối. |
| **Flicker / Strobe Pop** | `6f` \| `12f` (`200ms`) | 3 nhịp `On-Off-On-Off-On-Off-Lock` + Flash Glow `3f` ở đỉnh. |
| **Pill Badge Unroll-Y** | `8–9f` \| `16–18f` (`267–300ms`) | Anchor ở đáy/tâm; `Scale Height: 10% → 60% → 105% → 100%`. |
| **Ghost Trail** | `4f` \| `8f` (`133ms`) | `2f` chữ mới vào nét + `2f` bóng mờ chữ cũ tan dần. |
| **Grid / Card Stagger** | `3–5f/tầng` \| `6–10f/tầng` | Grid hàng `3f`; 3D Card 3 tầng `5f/tầng`; `Sans → Script` `4–10f`; Icon `8f`. |
| **Zoom / Whip Blur** | `3–7f` \| `6–14f` (`100–233ms`) | `3f` Ramp-in Blur + `2f` Peak Blur + `2f` Ramp-out (`Shutter 300–360°`). |
| **Ink Blot Transition** | `12f` \| `24f` (`400ms`) | `5f` mực loang che `100%` + `7f` cảnh mới fade-in. |
| **Light Leak / Film Burn** | `13f` \| `26f` (`433ms`) | Lõi bùng sáng che điểm cắt `3f` (`100ms`), `Blend = Screen`. |
| **Diagonal Paper Tear** | `16f` \| `32f` (`533ms`) | `5f` mở khe xé + `11f` lộ chữ nghiêng theo vết rách. |
| **Polarity Flip** | `1f` \| `1f` (`0ms` lag) | Hard-cut đảo nền Đen ↔ Kem sáng / Đỏ (`#FDFBE0` / `#B91C1C`). |
| **Micro-Pause CTA** | `1–12f` \| `2–24f` (`33–400ms`) | Khoảng trống chữ `1f` + khoảng nghỉ thoại `0.25–0.40s` tạo sức nặng. |

## 3. Nhịp Camera `V1` (Zoom In / Slow Drift / Zoom Out)
- **Punch-In Trọng Âm (`10–14f @30fps`):** `Scale 100% -> 118%` (hoặc `150% -> 175%` khi up-scale), `Bezier` (`out_inf: 0.20, in_inf: 0.88`), dời `Anchor` về vùng mắt/ngực trên và nhích `Position Y` `-12..-20px` để không cắt đầu.
- **Slow Drift (Câu dài `2.0–3.5s`):** Kéo mượt `+2%` đến `+4%` (`150% -> 154%`) để khung hình không bị "chết".
- **Zoom-Out Release (`12–16f @30fps`):** Lùi `175% -> 150%` (hoặc `122% -> 100%`) tại điểm chuyển sang B-Roll hoặc kết luận/CTA.

## 4. Chuẩn Gain dB SFX (Không bị chìm dưới Voice `-14 LUFS`)
*(Áp dụng trên file SFX đã chuẩn hóa `48 kHz 16-bit PCM WAV`, so với Voice Master `-14..-12 LUFS` và BGM ducked `-26..-24 dBFS`)*:
- **Text Chính (Hero / Số / Keyword) & Chuyển cảnh (`Impact`, `Hit`, `Hard Whoosh`, `Whip`, `Film Burn`):** `gain_db: -3.5` đến `-5.5 dB` (đặt tại `60%` scale hoặc `-2..-4f` pre-roll).
- **Zoom In / Zoom Out (`V1` Camera):** `gain_db: -4.5` đến `-6.0 dB` (`Fabric Whoosh` / `Clean Whoosh` pre-roll `-2f`).
- **Text Phụ nói dài (UI / Anchor):** `gain_db: -7.5` đến `-9.0 dB` (`Click` / `Shutter` chỉ chấm ở đầu cụm ý, không gắn từng từ).
