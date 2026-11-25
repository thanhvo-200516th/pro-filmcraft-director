# Trụ cột 2, 3 & 5: Kỹ năng NLE Premiere Pro ↔ FilmCraft (`.fcproj v17`)

## 1. Kiến trúc Track Chuẩn Studio (`8V + 8A`)
- **Video Tracks (Bottom-Up):**
  - `V1`: A-Roll chính (khóa sync `A1`).
  - `V2`: B-Roll / Split-Card nền blur / Text Behind-Subject.
  - `V3`: Cutout / RVM Subject Isolation (đồng bộ transform `V1 === V3`).
  - `V4`: Adjustment Layer — Color (`Lumetri`: Basic + Creative + Vignette trên GPU; HSL/Curves khi cần).
  - `V5`: Adjustment Layer — Camera/VFX (`Transform` + `Gaussian/Directional Blur` đặt trên `V4`).
  - `V6`: Overlays (`Screen`/`Add` cho Light Leak/Dust; `Multiply` cho Paper; `Overlay`/`Soft Light` cho Grain/Vignette). **Khi `blend != 0`, tắt `drop_shadow`.**
  - `V7`: `graphic_text` / `.fcgt` / Hero Text.
  - `V8`: Phụ đề đáy (`bottom_anchor_rail`) / HUD / CTA Pill.
- **Audio Tracks (`S_VO`, `S_SFX`, `S_BGM`):**
  - `A1`: Dialogue (`S_VO`, `-14..-12 LUFS`, chuỗi `parametric_eq → deesser → multiband_compressor`).
  - `A2–A3`: Transition SFX (`S_SFX`, `Whoosh/Whip/Riser`).
  - `A4–A5`: Impact / UI / Semantic SFX (`S_SFX`, tách track để không cắt cụt đuôi `A2–A3`).
  - `A6–A7`: BGM (`S_BGM`, Bar-Cut `4/4`, ducking `-24..-28 dB` khi có thoại).
  - `A8`: Ambience / Room Tone (`-36 dBFS`).
  - **Master:** `hard_limiter` tại **`-1.0` đến `-1.6 dBTP`**.

## 2. Adjustment Layer vs Nest (Sub-composition)
- **Adjustment Layer:** Áp Color/Camera/Blur lên toàn bộ track dưới cùng lúc.
- **Nest:** Bắt buộc dùng khi cần đồng bộ `Transform` đa lớp (PiP Phone + Screen + Label) hoặc cô lập Blur/Shake khỏi nền `V1`.

## 3. Toán học `Anchor Point`, `Transform` & `Bezier`
- **Anchor Point:** Dời về **điểm giữa 2 mắt** trước khi Zoom-in; dời về **cạnh đáy** trước khi Unroll-Y; dời về **tâm hình học** trước khi xoay.
- **Effect `Transform` thay cho `Motion`:** Bắt buộc bật `shutter_override: true`, đặt `shutter_angle: 180°` (chuyển động thường) hoặc `270°–360°` (Whip-Pan/Zoom). Không keyframe trùng `position`/`scale` trên cả `motion` và `transform`.
- **FilmCraft `Bezier` Limits:** `in_influence` / `out_influence` nằm trong `[0.0 .. 1.0]`. Để tạo **Overshoot (`100% → 105% → 100%`)**, dùng **3–4 keyframes `Bezier`**.
- **Hệ tọa độ thời gian FilmCraft:** `254,016,000,000 ticks/giây`. Trong `.fcproj` & `effects.setKeyframe`, `time`/`mediaTime` tính theo **Media Time** (`source_in + offset * speed`).

## 4. Audio Ducking 4 Điểm (Không dùng Sidechain)
FilmCraft không có cross-track Sidechain và `essentialSound.generateDucking` xóa keyframe cũ. Dùng **Volume Keyframes 4 điểm** trên `A6/A7`:
1. Giảm trước thoại `0.3s–0.5s`.
2. Giữ `-24..-28 dB` suốt đoạn nói.
3. **Khoảng nghỉ `< 1.5s`: giữ nguyên mức thấp** (chống pumping).
4. Tăng lại từ từ trong `0.5s–1.0s` khi dứt hẳn câu.
- Dùng `Constant Power` nối 2 clip liên tiếp; dùng `Exponential Fade` khi fade-in/out từ khoảng lặng.
