# 27 — Công thức Premiere Pro cho các hiệu ứng @__dviet còn trong BACKLOG, và cách dịch sang FilmCraft

Tài liệu nghiên cứu (không cài mã, không dựng/ render dự án video). Mục đích: với mỗi hiệu ứng ở [`23_dviet_profile_decisions_and_backlog.md`](./23_dviet_profile_decisions_and_backlog.md) mục 2 (tác giả dựng bằng CapCut), tìm cách làm trong Adobe Premiere Pro (kèm After Effects khi Premiere không có), rồi quy về những gì FilmCraft và các renderer của skill làm được.

**Trạng thái triển khai (v7.4, gói PKG-C): xem mục 8.** Các mục 3.x phía trên là nghiên cứu; chỉ mục 8 nói hiệu ứng nào đã có công cụ/ preset, hiệu ứng nào còn backlog.

Mô tả từng khung của video gốc nằm ở [`dviet_19/INDEX.md`](./dviet_19/INDEX.md) và 17 file con (`dviet_19/<id>.md`). Id video viết tắt 7 chữ số đầu (ví dụ 7664969 = 7664969137445276949).

---

## 0. Cách đọc tài liệu này

**Phân loại**

| Nhãn | Nghĩa |
|---|---|
| **A** | Công thức dựng ngay trên timeline FilmCraft: clip, `effects`, `motion`, `opacity`, `blend`, transition, text clip trong spec `*.craft.json` (hoặc ghi thẳng `.fcproj`). Có thể cần một asset đầu vào làm sẵn (matte, PNG) nhưng phần dựng là timeline. |
| **B** | Phải render một plate/ asset có alpha bằng công cụ của skill (ffmpeg, OpenCV/numpy, HTML qua `web_plate_builder.py`/ `web_cinema_plate_engine.mjs`, matte `u2netp`/RVM) rồi thả lên timeline như một clip. |
| **C** | Chưa khả thi với phần hiện có: thiếu model/ công cụ lớn. |

Một số mục là **A+B**: phần dựng là A, phần tiền xử lý (matte, clean plate, tracker) là B. Nhãn chính ghi theo phần quyết định.

**Mức xác minh nguồn (đánh dấu cạnh mỗi URL)**

| Dấu | Nghĩa |
|---|---|
| `[ĐÃ MỞ]` | Tôi đã mở trang và đọc công thức; các giá trị nêu trong tài liệu lấy từ trang đó. |
| `[TÌM KIẾM]` | Chỉ thấy tiêu đề và đoạn trích trong kết quả WebSearch; chưa đọc nội dung đầy đủ. Coi là gợi ý, cần mở lại trước khi làm theo. |
| `[LỖI]` | Mở trang bị 403/404 lúc kiểm; URL có trong kết quả tìm kiếm nên chỉ ghi để tra sau. |

**Chi phí** tính bằng **ngày công** của một dev đã quen codebase, gồm test; mọi con số là **[ƯỚC]**, chưa đo.

**Giới hạn của lần nghiên cứu này (nói thẳng)**

- WebSearch chỉ trả kết quả Mỹ. Tôi **không tìm được hướng dẫn Premiere của người Việt** cho các hiệu ứng này (các truy vấn tiếng Việt chỉ trả về trang Adobe/CapCut bản tiếng Việt). Không bịa tên kênh. Việc tìm tiếp trên YouTube cần người có tài khoản/ vùng phù hợp.
- Không có hướng dẫn Premiere nào khớp **nguyên** hiệu ứng ở một số mục (flicker silhouette, vanish có glow+negative, pixel stretch, keycap, constellation). Ở các mục đó phần "Công thức Premiere" là **ghép từ các thao tác nguyên tử đã có nguồn**, và tôi ghi rõ chỗ nào là suy luận.
- Nhiều trang `helpx.adobe.com` và `motionarray.com` trả 403 khi mở; nội dung các trang đó chỉ lấy từ đoạn trích tìm kiếm.
- FilmCraft **không chạy** trong phiên này (MCP `filmcraft` mất kết nối). Danh sách hiệu ứng lấy từ bản dump `effects.list` ngày 2026-10-29 (FilmCraft 0.13) trong `opa-video-studio/references/kb-master-video-edit.md` dòng 1345-1640. Tên tham số có trong dump, **hành vi** của từng effect chưa kiểm trong app; các chỗ cần kiểm được gom ở mục 7.
- Các lệnh ffmpeg trong tài liệu đã chạy thử trên clip tổng hợp (`testsrc2` 360x640, <= 2 s, trong thư mục scratch) để chắc là chạy được; xem mục 6.

---

## 1. Khả năng FilmCraft đã kiểm (từ mã, không chạy app)

### 1.1 Ba đường vào FilmCraft và giới hạn của từng đường

| Đường | Nguồn mã | Làm được | **Không** làm được |
|---|---|---|---|
| **Spec `*.craft.json` -> `fc_build.py` / `fc_build_fast.py`** | `scripts/vendor/ovs_core/scripts/apps/craft-handoff/tools/fc_build*.py` | Track `video`/`text`/`audio`; clip có `src,at,in,dur,speed` (hằng), `motion` {scale, position, rotation, anchor, scale_width} có keyframe; `opacity` có keyframe; `blend` thuộc `normal|screen|multiply|add|overlay`; `effects: [{effect, params}]` mọi id trong `effects.list`, mọi tham số keyframe được (`linear|bezier|easeIn|easeOut|hold`); `transition_in/out` {effect, frames}; `preset`; text clip (font, stroke, shadow, tracking); captions SRT; markers. Keyframe snap theo frame (60 fps = mốc 1/60 s). | **mask**, **nest**, **adjustment layer**, **freeze/ frame hold**, **reverse**, **speed keyframe** (`speed` chỉ là hằng), tracking. Khoá lạ trong spec vào danh sách `unsupported`, không mất im lặng. Clip trên cùng một track **không được chồng nhau** (`_check_overlaps`). |
| **Lệnh app qua `craftctl`** | `references/filmcraft-commands.json` của skill `opa-video-studio` (710 lệnh, không nằm trong repo này) | `masks.add/set/track` (ellipse, polygon, rectangle, bezier; `mode`, `feather`, `expansion`, `trackMethod`; **mask tracking** `position|positionRotation|positionScaleRotation`), `clip.frameHold`, `clip.insertFrameHoldSegment`, `clip.speedDuration` (có `reverse`, `opticalFlow`), `clip.nest`, `file.newAdjustmentLayer`, `effects.setParam` có tham số `mask: n`, `graphics.newShape/newEllipse/newRectangle` | `fc_build` hiện **không gọi** các lệnh này. Muốn dùng phải mở rộng builder (mục 1.3). |
| **Ghi thẳng JSON `.fcproj`** | `compile_and_verify.py`: `inject_micro_bridge_adjustment_layers_fcproj` (dòng ~6396), `fc_build_fast.py` (vá giá trị tham số) | Chèn `AdjustmentLayer` làm clip synthetic, thêm effect `time_remap`, vá tham số/ keyframe hàng loạt | Phải tự giữ đúng schema nội bộ; chỉ dùng cho thứ app/ spec không có. |

Ghi chú về blend: dump `effects.list` chỉ liệt kê 6 lựa chọn đầu của `opacity.blend` (Normal, Dissolve, Darken, Multiply, Color Burn, Linear Burn) nhưng `fc_build.BLEND` ánh xạ thêm `Screen`, `Overlay`, `Linear Dodge (Add)` và skill đã dùng Screen/Add/Overlay cho overlay (`references/02_nle_premiere_filmcraft.md` mục V6). Tôi coi đó là danh sách bị cắt trong dump, **chưa kiểm trong app**.

### 1.2 Hiệu ứng FilmCraft 0.13 liên quan (id trong `effects.list`)

| Nhóm | Id (tham số chính) |
|---|---|
| Keying/ matte | `ultra_key`, `track_matte` (`matte` chỉ **Video 1-5**, `composite` Matte Alpha/Luma, `reverse`), `color_key`, `luma_key`, `alpha_adjust`, `edge_feather`, `crop` (có `feather`), `rounded_crop` |
| Méo hình | `corner_pin` (4 điểm xy), `lens_distortion` (curvature, v/h_decentering), `spherize`, `wave_warp`, `turbulent_displace` (Bulge/Twist), `mirror` (center, angle), `offset`, `horizontal_flip`, `vertical_flip`, `rotate_3d` (rot_x/y/z, perspective), `basic_3d` (swivel, tilt, distance), `warp_stabilizer` |
| Màu/ kênh | `invert` (channel, blend), `channel_blur`, `channel_mix`, `tint`, `rgb_split` (Linear/Radial, amount, angle, blend), `lumetri`, `posterize`, `find_edges`, `black_white` |
| Sáng/ glow | `wonder_glow`, `echo_glow`, `edge_glow`, `glint` (`rays` 2/4/6/8), `light_leaks`, `lens_flare`, `volumetric_rays` |
| Mờ | `gaussian_blur`, `directional_blur`, `focus_blur` (shape **Radial**/Linear, size, feather, amount), `camera_blur`, `bokeh_blur`, `compound_blur` |
| Thời gian/ nhấp nháy | `time_remap` (speed), `posterize_time` (rate), `strobe` (duration, period), `camera_shake`, `wiggle` |
| Sinh/ tiện ích | `gradient`, `ramp`, `four_color_gradient`, `graphic_shape`, `graphic_text`, `stroke`, `clone` (**lát gạch** columns/rows/gap, không phải nhân bản chủ thể), `replicate` |
| Chuyển cảnh | `cross_dissolve`, `dip_to_white`, `flash`, `flicker` (flickers, seed), `zoom_blur` (center, strength), `radial_blur` (center, angle), `cross_zoom`, `glitch`, `burn_chroma`, `chroma_leak`, `light_leak`, `whip`, `stretch`, `mirror_transition` |

**Không có** trong 0.13: Time Displacement (slit-scan), tracker phẳng/ 3D, Roto/ Object Mask AI, Audio Waveform/ Spectrum, extrude 3D.

### 1.3 Renderer có sẵn của skill (đã đọc đầu file/ chữ ký hàm)

| Công cụ | Dùng được cho |
|---|---|
| `scripts/tools/fast_studio_compositor.py`: `predict_u2netp_alpha_u8`, `get_or_build_fullwidth_person_alpha_seq`, `render_bottom_flush_cutout`; `_render_polarity_flip_matte` nằm ở `dviet_motion_canvas_engine.py` (ma trận lật phân cực, không phải alpha người) | Alpha người/ vật nổi bật bằng ONNX `u2netp` (salient object, **không phải** tách theo từ khoá) |
| `opa-video-studio/scripts/matte.py` (RVM -> ProRes 4444 alpha). **Không** nằm trong `scripts/vendor/ovs_core` của skill này | Alpha người chất lượng cao hơn; cần đường dẫn ngoài skill |
| `scripts/dviet_motion_canvas_engine.py`: `compute_3d_perspective_homography` (dòng 507), `render_timeline_playhead_stage` (dòng 1052: timeline 3D kính, 46 thanh waveform **giả**, playhead), `render_motion_canvas` | Warp phối cảnh bằng homography; timeline giả |
| `scripts/tools/web_plate_builder.py` + `scripts/web_cinema_plate_engine.mjs` | Plate HTML -> ProRes 4444 / `qtrle` có alpha 60 fps; có `screen_strip`, `card_916`, `profile_card`, `kt01..kt12` (kt11 có `svg_arc`) |
| `scripts/dviet_smooth_camera_engine.py`: `apply_scale_radial_blur`, `apply_radial_lens_edge_softness`, `clamp_scale_to_safe_box` | Làm mờ xuyên tâm bằng OpenCV (đã có từ v7.4) |
| `scripts/tools/dviet_text.py` (role `constellation`, `lockup_*`, `script_accent`, `bilingual_sub`) | Đặt chữ theo role/ vị trí |
| `~/.venvs/video-skills`: `cv2 5.0.0`, `numpy 2.5.4`, `onnxruntime 1.31.1`; `cv2.findHomography`, `calcOpticalFlowPyrLK`, `inpaint`, `createBackgroundSubtractorMOG2` có sẵn | Nền cho tracker, clean plate |

### 1.4 Bảng đối chiếu công cụ Premiere/ After Effects -> FilmCraft

| Premiere/ AE | FilmCraft tương đương | Ghi chú |
|---|---|---|
| Object Mask (Premiere 2025+), Roto Brush 3 (AE) | **Không có** AI mask. Thay: alpha .mov từ `u2netp`/RVM rồi đặt lên track; hoặc `ultra_key` nếu có phông xanh | Mục 2, hạ tầng H1 |
| Track Matte Key | `track_matte` (matte phải ở Video 1-5) | Skill đã dùng trong `motion_fx.behind_person` |
| Mask Path + Mask Feather/Expansion | `masks.*` (chỉ qua lệnh app) / `crop`+`feather` / `rounded_crop` (spec) | Spec chưa có khoá `masks` |
| Time Remapping + Frame Hold | `clip.frameHold` (lệnh app); trong spec thay bằng PNG tĩnh trích từ ffmpeg (clip ảnh dài 5 s mặc định, chỉnh `dur`) | |
| Corner Pin | `corner_pin` (4 điểm có keyframe) | Không tự track |
| Lens Distortion, Spherize, Wave Warp | `lens_distortion`, `spherize`, `wave_warp` | 1:1 |
| Mirror, Flip | `mirror`, `vertical_flip` | 1:1 |
| Invert | `invert` (có `blend` để hoà) | 1:1 |
| Strobe Light, Posterize Time | `strobe`, `posterize_time` | 1:1 |
| Channel Blur + Levels (RGB split tự chế) | `rgb_split` dựng sẵn | Gọn hơn Premiere |
| Radial Blur (AE) | `focus_blur` (Radial) làm mờ mép; transition `radial_blur`, `zoom_blur`; `transform` có `shutter_angle` 360 | Không có effect radial blur gắn clip |
| Basic 3D | `basic_3d`, `rotate_3d` | |
| Adjustment layer | lệnh `file.newAdjustmentLayer`, hoặc chèn `.fcproj` | Không có trong spec |
| Audio Waveform/ Spectrum (AE) | **Không có** | Làm bằng plate (B) |

---

## 2. Hạ tầng dùng chung (nhiều hiệu ứng cần)

| Mã | Việc | Hiện có | Còn thiếu | Chi phí [ƯỚC] |
|---|---|---|---|---|
| **H1** | Alpha cutout cho 1 shot -> `.mov` ProRes 4444 cùng khung nguồn | `u2netp` (`predict_u2netp_alpha_u8`), RVM `matte.py` (ngoài skill) | Bọc thành lệnh một dòng: nhận video + khoảng giây, ghi alpha .mov + cache; mặt nạ "silhouette kem" (đổ màu #FFFBF0 theo alpha) | 1 ngày |
| **H2** | Clean plate (khung không người) | `cv2.inpaint`, MOG2, ffmpeg trích khung | Chọn đoạn chủ thể rời khung; hoặc trung vị theo thời gian các khung mà alpha = 0; kiểm lệch sáng | 0.5 ngày |
| **H3** | Lịch frame-chính-xác | `to_frames`/ snap của `fc_build` | Hàm sinh danh sách clip 2 frame ở 60 fps (xem mục 3.1) | 0.5 ngày |
| **H4** | Tracker phẳng 4 điểm -> keyframe 4 góc | `calcOpticalFlowPyrLK`, `findHomography` có trong cv2; `compute_3d_perspective_homography` | Module theo dõi vùng tường, RANSAC, làm mượt, giảm keyframe (RDP), cờ mất track | 3 ngày |
| **H5** | Khoá `masks` trong spec `fc_build` (ellipse/rect/bezier, feather, mode, path có keyframe) | Lệnh app `masks.add/set` | Validate, gọi `masks.*`, xác minh sau mở lại, `fc_build_fast` | 1.5 ngày |
| **H6** | Khoá `adjustment`/`nest` trong spec | Lệnh app; injector `.fcproj` | Như H5 | 1 ngày |

---

## 3. Từng hiệu ứng

Thứ tự theo backlog tài liệu 23 mục 2.

### 3.1 Silhouette / plate flicker (mở đầu) — hạng 1, 6 video

**Quan sát (ĐO, 7664447, 0.0-0.133 s, 60 fps, 8 frame):** f0 plate không người; f1-f3 bóng kem `#FFFBF0` đúng tư thế; f4-f5 plate trống; f6 bóng kem; f7 người thật. Tác giả tự giải thích công thức ở 7664969 (0-46 s): clip nền 8 frame + chủ thể tách nền, cắt chủ thể mỗi 2 frame, áp đường cong đảo sáng để "chớp".

**Công thức Premiere (ghép từ thao tác có nguồn; không có hướng dẫn khớp nguyên):**

1. V1 = clean plate (quay thêm một clip không người, hoặc trích khung sau khi chủ thể đi ra). V2 = clip có chủ thể.
2. Tách chủ thể bằng **Object Mask**: chọn khung chủ thể rõ nhất, công cụ Object Mask, nhấp chủ thể, **Track forward and backward**, rồi kéo mask từ *Unassigned Masks* vào **Opacity** (bước 4, 7, 10 của Adobe). Dọn mép: **Expansion khoảng -3.0** rồi thêm Feather (Adobe, bài thay nền). Hai chế độ Sharp/ Smooth; Smooth không có Expansion (Adobe, kết quả tìm kiếm).
3. Cắt V2 mỗi 2 frame (Razor `C`, đặt playhead bằng phím mũi tên 2 frame) rồi xoá xen kẽ, hoặc dựng nhiều layer lệch 1 frame (Filmora mô tả cách này).
4. "Bóng kem": đổ màu đặc lên chủ thể (Lumetri/ Brightness & Contrast đẩy tới trắng ngà). Đảo sáng bằng **Invert** hoặc **Levels** keyframe `hold` (suy luận, chưa có nguồn trực tiếp).
5. Nếu chỉ cần chớp ngẫu nhiên toàn khung: **Strobe Light** trên adjustment layer, `Strobe Duration 0.05-0.2 s`, `Strobe Period 0.1-0.4 s`, `Random Strobe Probability 25-75 %`.

**Nguồn:**
- Adobe Learn — Text behind subject (Object Mask, track, kéo mask vào Opacity): https://www.adobe.com/learn/premiere-pro/web/text-behind-subject-object-mask `[ĐÃ MỞ]`
- Adobe Learn — Thay nền bằng Object Mask (Expansion -3.0 + feather): https://www.adobe.com/learn/premiere-pro/web/remove-background-object-mask `[ĐÃ MỞ]`
- Filmora — Flicker trong Premiere (Strobe Light, giá trị ở trên): https://filmora.wondershare.com/customize-video/add-flicker-effect-in-premiere-pro.html `[ĐÃ MỞ]`
- Motion Array — Flicker effects (nhấp nháy nhanh 1-2 frame, chậm 5-10 frame): https://motionarray.com/learn/premiere-pro/flicker-effects-in-premiere-pro/ `[LỖI 403, chỉ đoạn trích]`
- Tuts+ — Flicker effects trong Premiere: https://photography.tutsplus.com/tutorials/how-to-quickly-create-cool-flicker-effects-in-premiere-pro--cms-108578 `[TÌM KIẾM]`

**Dịch sang FilmCraft — phân loại A (+ B cho matte):**

| Bước | Cách |
|---|---|
| Plate | Clip ảnh/ video `plate.mp4` trên V1 (ffmpeg trích khung, H2) |
| Chủ thể | `matte.mov` từ H1; thêm bản "bóng kem" `silhouette.mov` sinh sẵn bằng ffmpeg (alpha giữ nguyên, RGB cố định `#FFFBF0`) để khỏi phụ thuộc hành vi `tint` |
| Lịch | H3 sinh các clip dài đúng 2 frame, xen kẽ `silhouette`/ trống/ `matte`, mỗi clip một dòng spec trên V2 (không chồng nhau nên hợp lệ với `_check_overlaps`); đặt `at` bằng số nguyên frame/ fps |
| Đảo sáng | `invert` (`blend` 0->100, interp `hold`) trên clip silhouette, hoặc `lumetri.exposure` |
| Cách dự phòng | Transition `flicker` (`flickers = N`) của FilmCraft giữa clip plate và clip chủ thể có thể cho cùng kết quả **nếu** nó luân phiên hai nguồn; chưa kiểm trong app (mục 7) |

Đã kiểm bằng ffmpeg trên clip tổng hợp: `overlay=enable='lt(mod(n,4),2)'` cho độ sáng tâm khung theo frame là `252, 252, 23, 23, 252, 252, 23, 23, ...` (2 frame bóng kem, 2 frame plate) ở 60 fps; tức lịch 2-frame đúng như quan sát.

**Chi phí [ƯỚC]:** 1.5-2 ngày (H1 + H2 + H3 + preset + test lịch). **Rủi ro:** `u2netp` viền tóc kém; mở đầu 8 frame nên lỗi viền ít lộ. Không tính chất lượng thị giác (chưa so với video gốc).

---

### 3.2 Clone / phân thân — hạng 6, 1 video (7668334 hook 0-4.9 s; 7707653 hook 4 tay)

**Quan sát:** camera quét tới plate sofa trống, người xuất hiện, bản sao thứ hai hiện sau ~1.3 s kèm flicker khi xuất hiện.

**Công thức Premiere:**

- Quay **tripod cố định**, đánh dấu sàn, quay mỗi nhân vật một lượt (McKinnon).
- Xếp mỗi lượt một track, clip trên cùng vẽ **mask** (ellipse/ rectangle/ Pen), **Mask Feather/ Expansion** để hoà mép, thêm adjustment layer phía trên để cân màu/ LUT.
- Khi hai bản sao chồng nhau hoặc đi qua nhau: phải **rotoscope** (Object Mask/ Roto Brush) hoặc quay lại.
- Biến thể "clean plate": đặt plate sạch, mask phần tử cần nhân bản, keyframe **Mask Path**, xếp chồng và lệch thời gian, feather (Josh Enobakhare).

**Nguồn:**
- No Film School — Peter McKinnon, Clone yourself (YouTube https://youtu.be/B3AqxXYBm28, đoạn Premiere từ 2:00): https://nofilmschool.com/2017/06/watch-easily-clone-yourself-adobe-premiere-pro-cc `[ĐÃ MỞ]`
- No Film School — Josh Enobakhare, clone bằng clean plate + Mask Path keyframe: https://nofilmschool.com/2018/04/watch-learn-how-duplicate-objects-simple-cloning-trick-premiere-pro `[ĐÃ MỞ]`
- Justin Odisho — How to Clone Yourself in Premiere (qua trang premierebro): https://premierebro.squarespace.com/premiere-in-post/justin-odisho-how-to-clone-yourself-in-adobe-premiere-pro `[LỖI 404, chỉ tiêu đề trong kết quả tìm kiếm]`
- Premiere Gal — Roundtrip rotoscope Premiere -> After Effects (Roto Brush, Refine Edge, Freeze, Render and Replace ProRes 4444): https://premieregal.squarespace.com/blog/2024/8/30/easy-roundtrip-workflow-rotoscope-masking-from-premiere-pro-to-after-effects `[ĐÃ MỞ]`

**Dịch sang FilmCraft — A + B:**

- **Hai lượt quay cố định (không chồng nhau):** V1 = lượt A; V2 = lượt B với `crop` (`left/right`, `feather`) hoặc `rounded_crop`; hoặc `track_matte` với một clip mặt nạ nửa-khung sinh bằng ffmpeg. Hoàn toàn A, spec hiện đủ. Chi phí 0.5 ngày.
- **Có chồng/ đi qua nhau, hoặc chỉ có một lượt quay:** dùng alpha `matte.mov` (H1) của chủ thể đặt lên V2, **lệch `in` vài giây** để thành bản sao cùng người ở thời điểm khác. Lúc bản sao xuất hiện áp lịch flicker mục 3.1. Hiệu quả: không cần quay hai lượt. Chi phí thêm 1 ngày trên nền H1.
- Mask vẽ tay có path keyframe: cần H5 (1.5 ngày). Effect `clone` của FilmCraft **không** liên quan (nó lát gạch).

**Chi phí [ƯỚC]:** 1-1.5 ngày (sau H1, H3). **Rủi ro:** bóng đổ và lệch sáng giữa hai bản sao; camera cầm tay phá cách "lệch thời gian" (hook gốc có camera quét, nên đoạn quét phải nằm ngoài vùng clone).

---

### 3.3 Vanish / biến mất (glow + negative + trắng) — hạng 3, 4 video

**Quan sát (ĐO, 7672413 63.3-63.7 s):** người trắng loá, flash trắng ~1-4 f, rồi plate không người; tutorial của tác giả: glow 4-5 f + negative 4 f + nền trắng mờ 0.5 s; cần 01 shot có chủ thể và 01 clean plate.

**Công thức Premiere (ghép):**

1. Clip chủ thể trên V2, clean plate trên V1 (cùng khung, tripod).
2. Chủ thể rời: cắt V2 tại frame biến mất; trước đó 4-5 frame **glow**: nhân đôi, Gaussian Blur (nguồn tham khảo dao động 70-200), blend **Screen**, hoặc Lumetri + Luma Key để chỉ phát sáng vùng sáng.
3. **Negative 4 frame:** áp **Invert** trên 4 frame (Justin Odisho dạy "flashing invert"), hoặc keyframe **Levels** gamma/ white input.
4. **Nền trắng mờ 0.5 s:** solid trắng blend **Screen/ Add** hoặc opacity adjustment layer keyframe (Adobe Community).
5. Nếu cần "tan dần": Color Key với tolerance keyframe (Adobe Color Dissolve).

**Nguồn:**
- Adobe Community — flash âm bản kiểu phim kinh dị (Levels gamma/ white input, solid trắng Screen/ Add): https://community.adobe.com/t5/premiere-pro/video-effects-for-a-horror-thriller-trailer/m-p/5798185 `[TÌM KIẾM]`
- Justin Odisho — Flashing Invert Color Effect: https://premierebro.squarespace.com/premiere-in-post/justin-odisho-flashing-invert-color-effect-adobe-premiere-pro `[TÌM KIẾM]`
- Adobe — Color Dissolve (Color Key tolerance): https://helpx.adobe.com/ro/premiere-pro/how-to/color-dissolve-transition.html `[TÌM KIẾM]`
- Motion Array — Mask tracking, mục "Make Objects Disappear" (xoá mask ở clip dưới rồi dời clip sang thời điểm không còn chủ thể): https://motionarray.com/learn/premiere-pro/premiere-pro-mask-tracking/ `[LỖI 403, chỉ đoạn trích]`
- Glow (duplicate + blur + Screen): https://miracamp.com/learn/premiere-pro/film-halation-effect `[TÌM KIẾM]`

**Dịch sang FilmCraft — A (trên nền H1 + H2):**

| Pha | Cách trong spec |
|---|---|
| Plate trống | V1 clip plate (H2) |
| Chủ thể | V2 `matte.mov` đến frame biến mất |
| Glow 4-5 f | `wonder_glow` trên chủ thể, `intensity` 0 -> ~120 (cùng cách skill đã dùng cho chữ: threshold 40, radius 22) |
| Negative 4 f | `invert` `blend` 0 -> 100, interp `hold`, 4 frame |
| Trắng 0.5 s | `transition_out`: `flash`/ `dip_to_white` (frames 4 -> 30 @60) hoặc clip trắng với `opacity` keyframe + `blend: screen` |

Chi phí [ƯỚC]: 1 ngày (preset + test), sau H1/H2. **Ràng buộc quy tắc skill:** flash trắng/ film-burn chỉ cho profile `dviet`, có cap, và Dental/ Skincare vẫn bị veto (tài liệu 23 mục 1e).

---

### 3.4 Chữ 3D dán tường theo phối cảnh (planar tracking) — hạng 2, 4 video

**Quan sát:** 7668334 ("CLONE" dán tường, camera cầm tay quét), 7669054, 7672413 ("CHỦ THỂ/ TRONG KHUNG HÌNH" dán tường, vị trí giữ nguyên khi người bước ra), 7677448.

**Công thức Premiere:** Premiere **không có planar tracker**; Corner Pin gốc không tự track.

1. **Mocha AE (kèm After Effects):** nhân bản clip (`Alt/Opt` kéo), *Replace with After Effects Composition*; tạo text bằng Type Tool; áp **Animation > Track in Boris FX Mocha**; vẽ mặt phẳng tường bằng **X-plane**; track forward/ backward; bật **Surface Area** đặt 4 góc đúng phối cảnh, bật Grid để xem; đóng Mocha; **Create Track Data**, **Layer Export to** = layer chữ. (Premiere Gal, bản dán chữ lên mặt đất; áp cho tường là **suy luận** của tôi, trang không nói riêng về tường).
2. **Boris FX Continuum Corner Pin Studio** chạy ngay trong Premiere (cần giấy phép Continuum).
3. Không tracker: **Corner Pin** thủ công, đặt keyframe 4 góc cho cảnh chân máy/ chuyển động đơn giản.
4. Chữ 3D thật: AE 3D Camera Tracker + text 3D (HelpX).
5. Chữ bị vật đi qua che: Track Matte/ Track Mask trong AE.

**Nguồn:**
- Premiere Gal — Track text to ground (Mocha AE, Create Track Data): https://premieregal.squarespace.com/blog/track-text-to-ground-after-effects `[ĐÃ MỞ]`
- Boris FX — Corner Pin Studio: Tracking text inside Premiere Pro (video, trang chỉ có mô tả): https://borisfx.com/videos/corner-pin-studio-tracking-text-inside-premiere-pro/ `[ĐÃ MỞ]`
- Adobe HelpX (tiếng Việt) — Thêm chữ 3D lên cảnh quay trong After Effects: https://helpx.adobe.com/vn_vi/after-effects/how-to/add-3d-text-video-footage.html `[TÌM KIẾM]`
- Adobe HelpX (tiếng Việt) — Track matte và traveling matte: https://helpx.adobe.com/vn_vi/after-effects/using/track-mattes-and-traveling-mattes.html `[TÌM KIẾM]`
- Adobe Community — corner pin tường: https://community.adobe.com/questions-729/how-to-wall-text-mockup-moving-scene-1387101 `[TÌM KIẾM]`

**Dịch sang FilmCraft — A (cảnh tĩnh) / B (cảnh cầm tay):**

| Ca | Cách |
|---|---|
| Camera cố định (tripod) | Plate chữ phẳng (từ `web_plate_builder`, ví dụ `kt05_wall_spatial_counterpoint`) đặt lên V3 + `corner_pin` 4 điểm đặt tay (một lần) hoặc `rotate_3d` (`rot_y`, `perspective`). **A, 0.5-1 ngày.** |
| Camera cầm tay | H4: tracker OpenCV (ORB + LK + `findHomography` RANSAC) cho 4 góc vùng tường -> keyframe `corner_pin` (giảm bằng RDP). Chữ vẫn là một clip sửa được trên timeline. **A + B, tổng 3-4 ngày**, kể cả H4 |
| Phương án tránh phụ thuộc FilmCraft | Render chữ đã warp từng frame bằng `compute_3d_perspective_homography` + `cv2.warpPerspective` thành alpha .mov. B, 2 ngày, nhưng mất khả năng sửa trên timeline |
| Vật đi qua trước chữ | alpha vật đó + `track_matte` (xem 3.15f) |

**Rủi ro:** tường ít texture làm LK trôi; cần cờ "mất track" và cách sửa tay.

---

### 3.5 Pixel stretch / slit-scan — hạng 9, 1 video (7670574 52.6-56.4 s)

**Quan sát:** chủ thể cắt ra phát sáng kiểu thermal (vàng-trắng, viền cam) trên mặt trời đỏ; **smear ngang** kéo dài rồi snap về A-roll.

**Công thức Premiere/ AE:**

- Premiere **không có** native. Plugin: aescripts **Pixel Stretch** (chỉnh Stretch amount, pixel size, distribution curve; đề xuất offset bắt đầu khoảng 60-80 %, Linear Ramp Up) và Motion Array **Stretch**.
- Cách tự làm kiểu Photoshop: nhân đôi lớp, lấy một **dải 1 pixel**, kéo giãn (PHLearn/ Tuts+).
- **Slit-scan thật = After Effects Time Displacement:** bản đồ gradient 16-bit; pixel sáng hơn 50 % xám lấy khung muộn hơn, tối hơn lấy khung sớm hơn; `Max Displacement Time` ví dụ 2 s; nên quay tốc độ khung cao (nhóm tác giả quay 120 fps); camera tĩnh, nền trung tính.

**Nguồn:**
- aescripts — Pixel Stretch: https://aescripts.com/pixel-stretch `[LỖI 403, chỉ đoạn trích]`
- PHLearn — Pixel stretch (Photoshop): https://phlearn.com/tutorial/how-to-create-a-stretch-effect-in-photoshop/ `[TÌM KIẾM]`
- No Film School — Slit-scan 2001 bằng Time Displacement (AE): https://nofilmschool.com/2016/11/03/how-to-create-2001-slit-scanning-effect `[ĐÃ MỞ]`
- Motion Array — Stretch plugin cho Premiere: https://motionarray.com/learn/motion-array/premiere-pro-stretch-plugins/ `[TÌM KIẾM]`

**Dịch sang FilmCraft:**

- **A (xấp xỉ):** V2 = bản sao chủ thể, `crop` lấy một dải mỏng (`left`=X %, `right`=100-X-0.2 %), `motion.scale_width` keyframe 100 -> ~2000 với `uniform_scale` tắt (spec cho phép `scale_width` trong `motion`), `directional_blur` ngang, `tint`/`gradient` cho màu thermal, snap về A-roll bằng `hold`. 1 ngày. Chưa kiểm hình trong app.
- **B (chính xác):** ffmpeg `crop=2:ih:X:0,scale=...:flags=neighbor` rồi `overlay` — đã chạy thử OK trên clip tổng hợp; hoặc numpy: slit-scan thật (mỗi cột lấy khung lệch theo `x`) — đã chạy thử OK (60 khung 180x320 trong 8 ms). 0.5-1 ngày.
- **C với Time Displacement native:** không có effect tương đương trong FilmCraft; chỉ làm bằng B.

---

### 3.6 Lật dọc (vertical flip stack) — hạng 10, 1 video (7693026 10.7-13.0 s)

**Quan sát:** talker lật dọc (bản trên ngược, đen trắng, motion blur dọc; bản dưới thuận) trên nền trắng.

**Công thức Premiere:** Nhân đôi clip lên track trên; **Vertical Flip** (Transform) hoặc **Mirror** (`Reflection Angle` 90 cho trên-dưới, `Reflection Center`); chỉ áp đoạn cần bằng Razor; chồng nhiều Mirror được; B/W + **Directional Blur** góc 90°.

**Nguồn:**
- Motion Array — Mirror effect trong Premiere: https://motionarray.com/tutorials/premiere-pro-tutorials/how-to/how-to-use-the-mirror-effect-in-premiere-pro `[TÌM KIẾM]`
- Adobe — Flip video: https://www.adobe.com/creativecloud/video/discover/flip-video `[TÌM KIẾM]`

**Dịch sang FilmCraft — A:** V1 bản thuận (`crop` nửa dưới, `motion.position`); V2 bản `vertical_flip` + `black_white` + `directional_blur` (`direction` 90) + `crop` nửa trên; nền trắng bằng clip màu/PNG. Có thể dùng `mirror` (`angle` 90) thay `vertical_flip`. Phép ffmpeg tương đương `split,vflip,vstack` đã chạy thử OK. **Chi phí 0.5 ngày.** Không rủi ro đáng kể.

---

### 3.7 Warp cong kiểu panorama — hạng 11, 1 video (7693026 42.2-42.4 s, 3 frame)

**Công thức Premiere:** **Lens Distortion** (`Curvature` âm/ dương, `Vertical/ Horizontal Decentering`), có thể chồng hai Lens Distortion (cái thứ hai Curvature âm) rồi mask/ feather mép (Motion Array fisheye); **Spherize** (AE, cũng có ở Premiere), **Wave Warp**; Boris `S_WarpFishEye`. Adobe Community: Premiere không lý tưởng để cuộn phẳng thành cung hoàn chỉnh.

**Nguồn:**
- Motion Array — Fisheye lens effect: https://motionarray.com/learn/premiere-pro/fisheye-lens-effect-premiere-pro/ `[LỖI 403, chỉ đoạn trích]`
- Boris FX — Fisheye lens effect: https://borisfx.com/blog/create-a-fisheye-lens-effect-in-premiere-pro/ `[TÌM KIẾM]`
- Adobe — Distort effects (danh mục): https://helpx.adobe.com/premiere/desktop/add-video-effects/effects-and-transitions-library/distort-effects.html `[LỖI 403]`
- Adobe Community — cuộn video cong hoàn toàn: https://community.adobe.com/t5/premiere-pro-discussions/curve-a-video-fully-around/m-p/14775039/highlight/true `[TÌM KIẾM]`

**Dịch sang FilmCraft — A:** `lens_distortion` `curvature` keyframe 0 -> ~-60 -> 0 trong 3 frame (con số -60 là cùng kiểu của Pixflow, **không** đo từ video gốc), cộng `wave_warp`/ `turbulent_displace` (Bulge) cho độ gợn; `spherize` thay thế. Dự phòng B: ffmpeg `lenscorrection` hoặc `v360=input=flat:output=cylindrical` (cả hai chạy thử OK). **Chi phí 0.5 ngày** (chủ yếu chỉnh mắt). Hiệu ứng ngắn 3 frame nên sai số hình ít lộ.

---

### 3.8 RGB fringe (tách kênh) trên chữ — hạng 12, 1 video (7688934 12.85 s, 2-3 frame)

**Công thức Premiere:** (a) **Levels + Channel Blur** trên sequence lồng: Channel Blur `Red 300`, `Green 30`, bật **Repeat Edge Pixels**, keyframe Levels; (b) VR **Chromatic Aberration** trên adjustment layer; (c) ba bản sao, mỗi bản giữ một kênh, lệch vị trí, blend Screen/Add (Justin Odisho).

**Nguồn:**
- Noble Desktop — RGB transition (Levels + Channel Blur, giá trị ở trên): https://www.nobledesktop.com/learn/premiere-pro/rgb-transition-effect `[ĐÃ MỞ]`
- Motion Array — RGB split trong Premiere: https://motionarray.com/learn/premiere-pro/rgb-split-effect-premiere-pro/ `[LỖI 403, chỉ đoạn trích]`
- Premiere Bro — Ignace Aleya, RGB glitch transition: https://premierebro.squarespace.com/premiere-in-post/ignace-aleya-how-to-create-a-rgb-glitch-transition-in-premiere-pro `[TÌM KIẾM]`

**Dịch sang FilmCraft — A (rất rẻ):** FilmCraft có sẵn `rgb_split` (`mode` Linear, `amount`, `angle` 0 = ngang, `blend`). Gắn lên text clip: `amount` keyframe `hold` theo `[14, -10, 5, 0]` px của preset `glitch_rgb_split` (`presets/typography_hierarchy_presets.json:352`, tối đa 14 px, chỉ ngang). **Chi phí 0.25 ngày.** Lưu ý INDEX (7688934, mục 4) đã ghi dạng RGB split cho chữ là "đã hỗ trợ" về dữ liệu; mục backlog 12 nên đóng khi có test spec.

---

### 3.9 Radial-blur zoom-out — 2 video (7667598 3.4-4.5 s, zoom-out 0.85x; 7666801)

**Quan sát:** đầu 18 % -> 15 % -> 19 % bề rộng (0.85x rồi 1.05x) trong ~0.4 s, mép mờ xuyên tâm mạnh, tâm giữ nét.

**Công thức Premiere:** Premiere **không có** Radial Blur kiểu AE (Adobe Community: không tái tạo được bằng effect chuẩn; cần Impact/ Red Giant). Có **Radial Blur Impacts** trong Modern transitions. Cách tự làm:

1. **Lens Distortion + Transform** trên clip ra/ vào, 10 frame mỗi bên: Curvature 0 -> -60, Scale 100 -> ~200 (ra) và ngược lại (vào), **Shutter Angle 360**. (Pixflow)
2. **Adjustment layer + Transform:** Scale 100 -> 200 (đúng điểm cắt) -> 100, `Shutter Angle 360`, Bezier. (Pixflow, Motion Array)
3. **Replicate (Count 3) + Mirror x4** để bỏ viền khi phóng 300 %, hai adjustment layer, 12 frame. (Pixflow)
4. **Directional Blur** với Blur Length để làm mượt zoom (Filmora).

**Nguồn:**
- Pixflow — Zoom blur transition (3 phương pháp, giá trị ở trên): https://pixflow.net/blog/?p=2667 `[ĐÃ MỞ]`
- Premiere Gal — Fast zoom blur (Lens Distortion keyframe, adjustment layer; trang không nêu giá trị): https://premieregal.squarespace.com/blog/zoom-blur-premiere-pro `[ĐÃ MỞ]`
- Motion Array — Zoom transitions: https://motionarray.com/learn/premiere-pro/zoom-transitions-in-premiere-pro/ `[TÌM KIẾM]`
- Adobe — Modern transitions (Radial Blur Impacts): https://helpx.adobe.com/cz/premiere/desktop/add-video-effects/types-of-effects/transitions.html `[TÌM KIẾM]`
- Adobe Community — zoom blur không dùng transition: https://community.adobe.com/t5/premiere-pro-discussions/zoom-blur-effect-w-o-the-transition/m-p/9959776 `[TÌM KIẾM]`
- CapCut (tiếng Việt) — Zoom transition trong Premiere: https://www.capcut.com/vi-vn/resource/zoom-transition-in-premiere-pro `[TÌM KIẾM]`

**Dịch sang FilmCraft — A (đã có B từ v7.4):**

| Cách | Chi tiết |
|---|---|
| A, native | `motion.scale` 100 -> 85 (`bezier`/`easeIn`) trong ~0.4 s; `focus_blur` (shape **Radial**, `size` ~64 % bán kính, `feather`, `amount` keyframe ~13 -> 120 theo `|ln(scale)|`) cho mép mờ trong khi tâm nét; `transform` `shutter_angle` 360; nếu cần luồng tia: `transition_in` `radial_blur`/ `zoom_blur` 4-5 khung |
| B, đã có | `apply_scale_radial_blur` (OpenCV) và luật trong `atomic_motion_library.json:238` (`inner_r = clamp(0.64 - 0.9d, 0.30, 0.64)`, kernel tối đa 13 + gain·d, `d=|ln(scale)|`) -- dùng khi cần render sẵn |

`focus_blur` Radial là tương đương gần nhất của "tâm nét, mép mờ" nhưng **chưa kiểm hành vi trong app** (mục 7). **Chi phí 0.5 ngày**, thêm nếu phải chỉnh để khớp luật `inner_r`.

---

### 3.10 Thẻ SFX có waveform — hạng 7, 1 video (7669758: 5 thẻ nổi quanh đầu 0-2.4 s; thẻ ~580x300 giữa khung, playhead trắng quét đúng độ dài âm)

**Công thức Premiere:** Premiere gốc **không có** hiển thị waveform lên hình (Tuts+ ghi rõ: "can't be done with Premiere Pro by itself"; một bài Hollyland nói có Audio Spectrum/ Waveform ở Premiere, mâu thuẫn với Adobe Community và Filmora, **coi là sai cho tới khi kiểm**). Cách làm:

1. Chọn track audio + video, *Replace With After Effects Composition*; solid, **Effect > Generate > Audio Waveform**; chọn **Audio Layer**; chỉnh màu/ độ dày.
2. Hoặc **Audio Spectrum** trong AE; hoặc BCC Audio Visualizer (Boris Continuum); hoặc MOGRT.
3. Thẻ bo góc + nhãn: Essential Graphics (hình chữ nhật bo góc, text), playhead là đường kẻ keyframe vị trí.

**Nguồn:**
- Tuts+ — Audio Waveform trong Premiere/ AE: https://photography.tutsplus.com/tutorials/how-to-work-with-audio-waveform-effect-in-premiere-pro--cms-108166 `[ĐÃ MỞ]`
- Motion Array — Audio spectrum trong AE: https://motionarray.com/learn/after-effects/how-to-create-an-audio-spectrum-in-adobe-after-effects/ `[TÌM KIẾM]`
- Filmora — Audio visualizer trong Premiere (nói Premiere không có sẵn): https://filmora.wondershare.com/video-editor-review/audio-visualizer-premiere-pro.html `[TÌM KIẾM]`
- Hollyland — 3 cách (khẳng định có Audio Spectrum/ Waveform, **mâu thuẫn**): https://store.hollyland.com/blogs/creator-hub/create-an-audio-visualizer-in-premiere-pro `[TÌM KIẾM]`

**Dịch sang FilmCraft — B:**

- FilmCraft **không có** effect waveform; lệnh `clip.generateAudioWaveform` là waveform trên timeline, không phải đồ hoạ.
- Làm một template HTML `sfx_waveform_tile` trong `web_plate_builder.py`: đỉnh âm lấy **từ chính file SFX** (ffmpeg/ numpy peaks, không phải 46 thanh giả như `render_timeline_playhead_stage`), thẻ bo góc 55-60 px nền `#144E2C`, sóng `#EAEAEA`, glow, nhãn, playhead quét đúng `dur`; xuất ProRes 4444 alpha 60 fps; đặt lên timeline bằng `at` = onset SFX (từ `sfx_auto.py`/ `sfx_shift.py`).
- Bản nhanh bằng ffmpeg: `showwaves=mode=cline` + `drawbox` playhead chạy thử OK (119 frame cho 2 s). Làm đồ hoạ thẻ vẫn cần HTML.

**Chi phí [ƯỚC]:** 2 ngày (template + peaks + đồng bộ + test); bản ffmpeg thô 0.5 ngày. Đàn 5 thẻ nổi quanh đầu cần kiểm Cranial Lock.

---

### 3.11 Sticker sparkle (sao 4 cánh + vòng teal) — hạng 4, 2 video (7670574 glow text 27.3 s, 7669054)

**Công thức Premiere:** overlay hạt lấp lánh (MOV có alpha, hoặc nền đen blend **Screen/ Lighten/ Add**), keyframe **Scale/ Opacity/ Rotation** cho nhấp nháy, **Directional Blur** keyframe cho chuyển động, **Glow**, **Brightness & Contrast**; snap keyframe theo đỉnh nhạc.

**Nguồn:**
- Pixflow — Sparkle 90s trong Premiere: https://pixflow.net/blog/create-stunning-90s-sparkle-effects-in-premiere-pro/ `[ĐÃ MỞ]` (không có giá trị keyframe Scale/ Opacity/ Rotation)
- Motion Array — Video star overlays: https://motionarray.com/learn/video-effects/video-star-overlays/ `[TÌM KIẾM]`
- PremiumBeat — Light leaks, text reveals: https://www.premiumbeat.com/blog/tutorial-light-leaks-text-reveals/ `[TÌM KIẾM]`

**Dịch sang FilmCraft — A (sprite PNG) hoặc B:**

- **A:** một PNG sao 4 cánh + vòng teal (SVG -> PNG 1 lần) làm clip; `motion.scale` 0 -> 110 -> 100 (`bezier`), `rotation` 0 -> 45, `opacity` nhấp nháy `hold`, `blend: add`/ `screen`. Lịch xuất hiện: sinh từ danh sách từ khoá. 0.5 ngày.
- **A, thay thế:** effect `glint` (`rays` **4**, `threshold`, `rotation` 45, `length`) vẽ tia 4 cánh trên vùng sáng của chữ; chưa kiểm hình (vòng teal vẫn cần sprite).
- **B:** template HTML/ SVG với twinkle animation, alpha .mov.

**Chi phí [ƯỚC]:** 0.5-1 ngày. Rủi ro thấp; chỉ cần bám giới hạn "sparkle '+' accent" hiện có trong `dviet_7706_typography_choreography.py:514`.

---

### 3.12 Keycap tile 3D — hạng 13, 1 video (7707653 20.5-21.8 s)

**Quan sát:** từ "xuất", "hiện", "phim", "nhiều", "điện", "trong" in trong ô phím 3D trắng/ xanh, lưới nghiêng.

**Công thức Premiere/ AE:** Không có tutorial khớp. Premiere không extrude 3D. Hướng đi: AE (shape bo góc + 3D layers, `Extrusion` của renderer Cinema 4D/ Element 3D keyboard template), Premiere chỉ **Basic 3D** (Swivel/ Tilt/ Distance) cho tấm phẳng nghiêng + **Drop Shadow** xếp tầng giả độ dày.

**Nguồn:**
- MotionElements — Keyboard animation template (Element 3D, chỉnh `Entertaste`): https://www.motionelements.com/sv/after-effects-template-13045331-keyboard-animation-with-customizable-enter-key `[TÌM KIẾM]`
- Video Copilot — Animating typewriter keys: https://www.videocopilot.net/blog/2013/08/new-tutorial-animating-typewriter-keys `[TÌM KIẾM]`
- Greyscalegorilla — AE built-in 3D: https://greyscalegorilla.com/?p=475 `[TÌM KIẾM]`
- CG Cookie — Keycaps (Blender): https://cgcookie.com/lessons/keycaps-introduction `[TÌM KIẾM]`

**Dịch sang FilmCraft — B (chính), A-lite:**

- **B:** template CSS 3D trong `web_plate_builder.py` (chồng `box-shadow` làm "độ dày", gradient bevel, `perspective`, chữ NFC có dấu); mẫu gần nhất đã có: `course_3d_matte_asset_box`, `isometric_3d_prompt_browser`. Mỗi từ vào ô theo nhịp nói (các template v7.1 đã có cách kích theo giây thật của âm tiết, xem đầu `web_plate_builder.py`).
- **A-lite:** `graphic_shape` (Rectangle, `corner_radius`, `fill_kind` gradient) + `long_shadow`/ `drop_shadow` + `basic_3d` (`tilt`, `swivel`) + text clip. Trông phẳng hơn, sửa được trên timeline.
- **C:** ánh sáng 3D thật (phản chiếu, bevel vật lý) chưa khả thi.

**Chi phí [ƯỚC]:** B 1.5 ngày; A-lite 0.5 ngày.

---

### 3.13 Constellation text (chòm sao) — hạng 8, 1 video (7664835)

**Quan sát:** hero chữ thảo giữa, quanh nó 3-6 từ sans nhỏ ở toạ độ lệch; từ **tích luỹ** đến hết cụm rồi **xoá cả cụm** (3.5 -> 4.0 s); vào bằng fade + trượt nhẹ.

**Công thức Premiere:** không có hướng dẫn riêng. Cách làm chuẩn: **mỗi từ một text layer**, đặt vị trí tay, so le thời điểm vào vài frame, keyframe Opacity/ Position; hero trên layer riêng.

**Nguồn:**
- Pixflow — Text animation trong Premiere (layer mỗi từ, lệch vài frame): https://pixflow.net/blog/?p=88409 `[TÌM KIẾM]`
- Filmbro — Kinetic typography trong Premiere (đánh dấu điểm vào theo audio): https://filmbro.com/blogs/tutorials/how-to-create-a-kinetic-typography-animation-in-premiere-pro `[TÌM KIẾM]`
- Adobe — How to make a lyric video: https://www.adobe.com/creativecloud/video/discover/how-to-make-a-lyric-video `[TÌM KIẾM]`
- School of Motion — Kinetic Typography in After Effects: https://www.schoolofmotion.com/tutorials/kinetic-typography-after-effects-part-1 `[TÌM KIẾM]`

**Dịch sang FilmCraft — A:** chỉ cần một **planner** (Python) sinh danh sách text clip: hero `script_accent` ở giữa, 3-6 từ `keyword_sans` ở toạ độ lệch (tránh va chạm bbox, giữ ngoài vùng đầu theo Cranial Lock), `opacity` 0 -> 100 + `position` trượt ngắn, `stagger` 3 frame, tất cả hết hạn cùng lúc ở cuối cụm. Đã có `dviet_text.py` role `constellation` (chỉ đặt chữ) và `per_word_stagger` (`stagger_frames 3`, `word_dur_frames 8`). **Chi phí 1-1.5 ngày** (planner + kiểm va chạm + test). Không cần plate.

---

### 3.14 Breakdown "raw | edited" với timeline NLE giả — hạng 14 (timeline-playhead split), 1 video (7664633)

**Quan sát (ĐO):** hai card dọc viền trắng ~8 px, bo ~28-30 px, nhãn vàng ≈ `#E8C81A` đè mép; timeline CapCut chiếm ~28 % chiều cao dưới, **cuộn ngang** theo playhead ~65 px/s (thang ~16.6 s/1080 px); clip nhãn thật ("Clip ghép1 00:00:04:47", ...); mỗi từ phụ đề một clip chữ đỏ; audio "Lồng tiếng1".

**Công thức Premiere:** hai clip trên hai track, **Crop** mỗi clip về nửa khung (Noble Desktop), hoặc Position/ Scale; **Comparison View** của Program Monitor chỉ để kiểm tra, **không** xuất hình. Timeline giả: ảnh chụp màn hình hoặc Essential Graphics (chữ nhật + text), cuộn bằng keyframe **Position**.

**Nguồn:**
- Noble Desktop — Split screen trong Premiere (hai track + Crop): https://nobledesktop.com/learn/premiere-pro/split-screen-effect-premiere-pro `[TÌM KIẾM]`
- Adobe Learn — Frame comparison view: https://www.adobe.com/id_en/learn/premiere-pro/web/frame-comparison-view `[LỖI 404, chỉ đoạn trích]`
- Motion Array — Split screen tutorial: https://motionarray.com/premiere-pro/split-screen-adobe-premiere-pro-tutorial/ `[TÌM KIẾM]`

**Dịch sang FilmCraft — A + B:**

- **A (hai card):** hai clip (raw, edited) với `rounded_crop` (`radius` ~30, `border` ~8, `border_color` trắng), `motion.position/scale`, nhãn là text clip vàng. Template `card_916` đã có phần khung/nhãn.
- **B (timeline giả):** `render_timeline_playhead_stage` có sẵn khung timeline 3D kính + playhead nhưng dùng **waveform giả** và không phải UI NLE. Cần template mới `nle_timeline_breakdown` (HTML): các hàng track, clip có nhãn/ độ dài lấy **thẳng từ spec** (đọc clip `at`/`dur`), playhead đồng bộ, cuộn ngang 65 px/s; xuất alpha .mov. Điểm hay: timeline có thể vẽ **từ chính timeline vừa dựng**, nên luôn khớp.

**Chi phí [ƯỚC]:** 3 ngày (A 0.5, B 2.5). Rủi ro: tránh giả UI của sản phẩm khác (CapCut) -- dùng UI trung tính.

---

### 3.15 Các layout còn lại (tài liệu 23 mục 2, đoạn "Layout chưa dựng")

| # | Layout | Video | Công thức Premiere (nguồn) | FilmCraft | Loại | Chi phí [ƯỚC] |
|---|---|---|---|---|---|---|
| a | Khung ngắm `[ đặt máy quay ]` + chấm REC nhấp nháy | 7664447, 7707653 | Essential Graphics: góc khung bằng Rectangle/ Pen, Ellipse đỏ + chữ "REC", Opacity keyframe nhấp nháy, blend để hoà vào hình. Adobe Community: https://community.adobe.com/t5/premiere-pro-discussions/add-record-quot-light-quot-effect-in-post/m-p/12856061 `[TÌM KIẾM]`. Không có tutorial đủ bộ | `graphic_shape` (Rectangle viền, Ellipse đỏ `fill_color`) + text clip; `opacity` keyframe `hold` cho nhấp nháy. 4 góc có thể là 4 shape hoặc một PNG | A | 0.5 ngày |
| b | Thẻ palette chip + mã hex | 7677448 | Shapes + text; không cần hướng dẫn riêng | `graphic_shape` (`fill_color` = màu mẫu) + text clip hex; `rounded_crop` | A | 0.5 ngày |
| c | Thẻ font specimen (Instrument Serif, De Fonte) | 7677448 | Text layer với font cài sẵn | text clip với `font`; builder cảnh báo khi font thiếu (`fonts.list`). Ngoại lệ cấm font chỉ ở role `font_specimen` (tài liệu 23 mục 1b) | A, B nếu font không cài (HTML `@font-face`) | 0.5 ngày |
| d | Quay màn hình bằng camera nghiêng, DoF | 7664447, 7670574 | Basic 3D (Swivel/ Tilt) hoặc Corner Pin cho mặt phẳng nghiêng; **Camera Blur** + gradient mask cho DoF. Không có hướng dẫn riêng | `basic_3d` hoặc `rotate_3d` + `focus_blur` (shape **Linear**, góc theo mặt nghiêng) + `camera_shake` | A | 0.5-1 ngày (chỉnh mắt) |
| e | Mockup điện thoại, chữ hoà bằng Overlay | 7683763, 7667598 | Corner Pin lên màn hình điện thoại (track bằng Mocha hoặc Perspective Corner Pin của AE Tracker), blend Overlay/ Screen cho phản chiếu/ chữ. Adobe Stock, CXL, Toolfarm: https://helpx.adobe.com/stock/how-to/mobile-mockup-branding-green-screen.html `[TÌM KIẾM]`; https://www.toolfarm.com/?p=23256 `[TÌM KIẾM]`; https://community.cxl.com/t/create-mockup-video-in-premiere-pro/910 `[TÌM KIẾM]` | `corner_pin` + `blend: overlay` (spec có `overlay`) + text clip; điện thoại cố định: A; điện thoại di chuyển: cần H4. Nhớ quy tắc 02: khi `blend != 0` tắt `drop_shadow` | A (cố định) / A+B | 1 ngày / +H4 |
| f | Chữ bị vật tiền cảnh che (chữ sau vai/ chân người) | 7706183 | Adobe: nhân đôi clip, Object Mask vật/ người, theo dõi, mask kéo vào **Opacity** của bản trên, chữ kẹp giữa. Premiumbeat: mask thủ công + Mask Path tracking + feather: https://www.premiumbeat.com/blog/layer-text-behind-objects-premiere-pro `[TÌM KIẾM]` | Cùng cơ chế `behind_person`: alpha .mov (H1) + `track_matte` (`composite` Matte Alpha, `reverse` True, matte ở Video 1-5). Skill đã có cho người; **vật không phải người** cần `u2netp`/ mask tay (H5) | A + B | 1 ngày với người/ vật nổi bật; **C** cho vật bất kỳ (chưa có model phân vùng theo vật) |
| g | Chữ cong bám đầu (backlog hạng 5: 7706183, 7707653) | 2 | Premiere Pro **không** có text-on-path; AE có Path Options. Mask Tracking của Premiere (Adobe masking & tracking) dùng được để bám đầu: https://helpx.adobe.com/ro/premiere-pro/using/masking-tracking.html `[TÌM KIẾM]` | `kt11_cranial_svg_arc_or_tilt` đã vẽ cung (B); thêm **theo dõi đầu** (Haar có sẵn trong skill cho Cranial Lock, hoặc `masks.track` của app) -> keyframe `motion.position` cho plate cung. Giảm keyframe bằng RDP, smoothing | A + B | 1.5-2 ngày |

---

## 4. Bảng tổng hợp

(Cột "Làm được ngay" bên dưới là ước lượng lúc nghiên cứu. Trạng thái thực tế sau PKG-C: mục 8.)

| Hạng backlog | Hiệu ứng | Loại | Phụ thuộc | Chi phí [ƯỚC] | Làm được ngay (không code mới)? |
|---|---|---|---|---|---|
| 1 | Silhouette/ plate flicker | A (+B matte) | H1, H2, H3 | 1.5-2 ngày | Một phần: dựng tay clip 2 frame trong spec |
| 2 | Chữ dán tường planar track | A (tĩnh) / A+B (cầm tay) | H4 cho cầm tay | 0.5-1 / 3-4 ngày | Tĩnh: có (`corner_pin`) |
| 3 | Vanish | A | H1, H2 | 1 ngày | Một phần (glow/ invert/ flash có sẵn) |
| 4 | Sticker sparkle | A | sprite PNG | 0.5-1 ngày | Có, nếu có PNG |
| 5 | Chữ cong bám đầu | A+B | theo dõi đầu | 1.5-2 ngày | Cung `kt11` có, bám đầu chưa |
| 6 | Clone/ phân thân | A+B | H1, H3 (+H5 tuỳ chọn) | 1-1.5 ngày | Hai lượt quay tĩnh: có (`crop`/ `track_matte`) |
| 7 | Waveform SFX tile | B | peaks thật, template | 2 ngày | Không |
| 8 | Constellation text | A | planner | 1-1.5 ngày | Một phần (`dviet_text.py`) |
| 9 | Pixel stretch/ slit-scan | A (xấp xỉ) / B | numpy/ ffmpeg | 1 ngày | Một phần |
| 10 | Lật dọc | A | -- | 0.5 ngày | Có |
| 11 | Warp cong | A | -- | 0.5 ngày | Có |
| 12 | RGB fringe | A | -- | 0.25 ngày | Có |
| 13 | Keycap 3D | B (A-lite) | template CSS 3D | 1.5 ngày (0.5) | Không |
| 14 | Layout: raw\|edited + timeline NLE | A+B | template NLE | 3 ngày | Hai card: có |
| -- | Radial-blur zoom-out | A (B đã có) | -- | 0.5 ngày | Có (B hiện hữu) |
| -- | Layout a-f (mục 3.15) | A / A+B | tuỳ | 0.5-1 ngày mỗi cái | Phần lớn có |

**Chưa khả thi (C) hiện tại**

1. Tách theo vật bất kỳ chất lượng Object Mask/ Roto Brush 3 (thiếu model; `u2netp` chỉ là salient object, RVM chỉ cho người). Ảnh hưởng 3.15f cho vật không phải người, và clone khi hai người chồng sát nhau.
2. Planar tracking tự động có xử lý che khuất, đáng tin cậy như Mocha: bản OpenCV chỉ làm được trên tường đủ texture.
3. Ánh sáng 3D thật cho keycap.
4. Time Displacement native trong FilmCraft: không có effect; chỉ làm bằng B.

**Tổng ước tính nếu làm hết:** hạ tầng H1-H6 ~7.5 ngày + phần riêng của từng hiệu ứng (đã trừ hạ tầng) ~20 ngày = **khoảng 25-28 ngày công** [ƯỚC thô, các dòng trong bảng trên có chồng lấn với H nên không cộng thẳng; chưa tính vòng chỉnh hình với video gốc].

---

## 5. Thứ tự đề xuất

1. **Rẻ, độc lập (A, ~3 ngày):** RGB fringe, lật dọc, warp cong, radial focus-blur, sticker sparkle (PNG), layout a/ b/ c. Không đụng hạ tầng mới.
2. **Gói matte (H1 + H2 + H3, ~3 ngày) rồi:** flicker, vanish, clone (hạng 1, 3, 6: tổng 6 video chứa). Một hạ tầng dùng cho cả ba.
3. **Constellation planner** (A, 1-1.5 ngày) và **pixel stretch** (A xấp xỉ + B).
4. **Plate B:** waveform tile, keycap, timeline NLE (~6.5 ngày), dùng chung `web_plate_builder.py`.
5. **Tracker H4 (~3 ngày):** chữ dán tường cầm tay, mockup điện thoại di chuyển, chữ cong bám đầu.
6. **H5/ H6 (khoá `masks`, `adjustment`/ `nest` trong spec)** khi cần mask vẽ tay hoặc adjustment layer từ spec.

---

## 6. Bằng chứng đã đo (clip tổng hợp, thư mục scratch, <= 2 s; không dựng dự án)

Chạy bằng `ffmpeg n8.1.3` trên `testsrc2` 360x640:

| Kiểm | Kết quả |
|---|---|
| Lịch flicker `overlay=enable='lt(mod(n,4),2)'` ở 60 fps | Độ sáng tâm khung theo frame: `252, 252, 23, 23, 252, 252, 23, 23, 252, 252, 23, 23` (đúng 2 frame mỗi trạng thái) |
| `negate`, `rgbashift=rh=-8:bh=8:enable=between(n,10,15)`, `split,vflip,vstack`, `lenscorrection=k1=-0.35:k2=0.1`, `v360=flat:cylindrical`, `crop=2:ih:X:0,scale,overlay` (pixel stretch), `perspective` 4 góc, `showwaves=cline` + `drawbox` playhead | Tất cả thoát mã 0, ra đủ số frame (ví dụ `showwaves` 119 frame / 2 s). **Chưa đánh giá thị giác.** |
| Slit-scan numpy (mỗi cột lấy khung lệch theo x) trên 60 khung 180x320 | Chạy được, 8 ms |
| Môi trường: `cv2 5.0.0`, `numpy 2.5.4`, `onnxruntime 1.31.1`; `findHomography`, `calcOpticalFlowPyrLK`, `inpaint`, MOG2 có | Xác nhận có sẵn |

Không chạy FilmCraft, không dựng/ render dự án; không sửa file nào khác ngoài tài liệu này.

---

## 7. Việc còn lại / chưa kiểm (cần người có FilmCraft chạy được)

1. Chạy `effects.list` để xác nhận id, tham số và kiểu của: `tint`, `invert` (`blend`), `rgb_split`, `focus_blur` (Radial/ Linear), `lens_distortion`, `glint`, `corner_pin`, và **hành vi** transition `flicker` (có luân phiên hai nguồn không). Dump 2026-10-29 có thể đã cũ.
2. Xác nhận `opacity.blend` có đủ Screen/ Overlay/ Add trong app (dump chỉ liệt kê 6 lựa chọn đầu).
3. Kiểm `track_matte` chỉ nhận **Video 1-5**: bố trí track khi có hơn 5 track video (kb-master-video-edit dòng 1759 ghi "phải sắp lại track, chưa làm").
4. Xác nhận spec cho phép 2-frame clip liên tiếp ở 60 fps mà `verify` của `fc_build` đếm đúng (`clips` khớp `dur`).
5. Các trang đánh dấu `[LỖI]`/ `[TÌM KIẾM]` cần mở lại bằng trình duyệt trước khi dùng làm công thức.
6. Chưa tìm được hướng dẫn Premiere của người Việt; nên tìm trực tiếp trên YouTube với các từ khoá: "Object Mask Premiere", "clean plate Premiere", "Corner Pin Mocha Premiere", "RGB split Premiere".
7. Tất cả chi phí và con số keyframe (curvature -60, `amount` 14 px...) là **[ƯỚC]** hoặc lấy từ hướng dẫn bên ngoài, chưa đối chiếu với video gốc.

---

## 8. Trạng thái triển khai v7.4 (gói PKG-C)

Nhãn: **implemented** = có mã không trạng thái và test tổng hợp (ffmpeg `testsrc2` <= 2 s, numpy), chạy được không cần FilmCraft; **experimental** = preset/ macro tạo ra dòng spec hợp lệ (qua `fc_build.validate`, `sanitize_spec`, `spec_lint`) nhưng **hành vi trong app chưa kiểm** (`behaviour_unverified_in_app`: MCP `filmcraft` mất kết nối khi làm, bản dump `effects.list` 2026-10-29 có thể cũ); **backlog** = chưa làm. Mọi preset experimental đều mang `"status": "experimental"` và `"behaviour_unverified_in_app": true` trong JSON.

| Hiệu ứng (hạng backlog) | Trạng thái | Nằm ở đâu | Ghi chú |
|---|---|---|---|
| Silhouette flicker (1), mở đầu 8 frame | **implemented** (công cụ) + **experimental** (trong app) | `scripts/tools/flicker_schedule.py`: `flicker_schedule`, `schedule_to_clips`, `overlay_enable_expr`, `silhouette_mov_cmd`, `matte_from_frames`, `check_subject_matte`, `clean_plate_median`; khoá plan `opener` của `scripts/tools/spec_from_plan.py`; preset `flicker_silhouette_opener_8f` trong `atomic_motion_library.json` | Lịch đúng frame ở 60, 24, 25, 30, 30000/1001, một track, không chồng nhau. Mẫu mặc định = 8 frame đo ở mục 3.1. Số frame giữ nguyên ở mọi fps (24 fps chạy 8 frame chậm hơn 60 fps, không đổi theo giây). State `subject` mặc định không sinh clip: A-roll V1 hiện qua. Màu bóng đúng `#FFFBF0` (lossless `qtrle`/`png`; ProRes 4444 đi qua YUV nên lệch tối đa 3 mức). Matte lấy từ `predict_u2netp_alpha_u8`, không vendor RVM |
| Clean plate (H2) | **implemented** | `clean_plate_median` | Trung vị theo thời gian trên các frame alpha == 0, `cv2.inpaint` cho điểm không bao giờ trống; nếu hơn 25 % khung không bao giờ trống thì **báo lỗi** thay vì làm giả |
| Bảo vệ matte | **implemented** | `check_subject_matte` | Raise `MatteError` khi matte rỗng, phủ gần cả khung, có nhiều/ chồng chủ thể, hoặc blob rộng hơn cao (không phải người). Là heuristic, không phải bộ nhận diện người |
| RGB fringe trên chữ (12) | **experimental** | `rgb_fringe_text_native` trong `typography_hierarchy_presets.json` (`native_effect_presets_v74`) | `rgb_split` Linear, `amount` 14, 10, 5, 0 `hold` trong 3 frame. Mở rộng `glitch_rgb_split` (lấy offset từ đó, không thay thế); dấu của offset bị bỏ, hướng của `amount` chưa kiểm |
| Lật dọc (10) | **experimental** | `vertical_flip_stack_native` | Hai clip: `upright` (crop top 50) và `flipped` (`vertical_flip` + `black_white` + `directional_blur` 90 + crop bottom 50). Nền trắng không nằm trong preset. Đơn vị `crop` giả định là % |
| Warp cong (11) | **experimental** | `curved_warp_lens_wave_3f` | `lens_distortion` curvature 0 -> -60 -> 0 và `wave_warp` trong 3 frame; -60 là số từ hướng dẫn ngoài, không đo từ video gốc |
| Radial-blur zoom-out | **experimental** (bản gốc FilmCraft) / **implemented** (bản B có từ trước) | `radial_focus_blur_zoom_out` (tham chiếu `radial_blur_scale_grow`) | `motion.scale` 100 -> 85 trong 0.4 s + `focus_blur` Radial. Bản OpenCV `apply_scale_radial_blur` vẫn là đường render sẵn. Đơn vị `size`/`feather` và đường cong `amount` chưa kiểm |
| Sticker sparkle (4) | **experimental** | `sparkle_sprite_pop_6f` | Vai `sprite` (scale/rotation/opacity `hold`/blend add) và vai `glint_alt` (`glint` rays 4). PNG sao 4 cánh và vòng teal **chưa kèm theo** |
| Vanish (3) | **experimental** | `vanish_rows` + preset `vanish_glow_negative_white` | `wonder_glow` 5 frame cuối, `invert` blend 0 -> 100 `hold` 4 frame cuối, rồi `transition_out` `dip_to_white` 0.5 s. Cần clean plate và matte của chủ thể. `profile_scope: ["dviet"]`, có `caps` (kế thừa `white_flash_0p25s`; đuôi trắng 0.5 s dài hơn trần 0.3 s của nó nên là [ƯỚC]) |
| Clone / phân thân (6) | **experimental** | `clone_appear_rows` + preset `clone_appear_flicker` | Một lượt quay: cùng matte, trễ `offset_s`, vào bằng chớp 2 frame (`off 2, on 2, off 2`, dựng từ `flicker_schedule`) rồi giữ. Ba track không chồng. Hai bản đi qua/ chồng nhau cần matte có xử lý che khuất: không làm |
| Planar tracking (2), chữ cong bám đầu (5), waveform tile (7), constellation (8), pixel stretch (9), keycap (13), layout (14) | **backlog** | -- | Không đụng tới ở PKG-C (không có masks `fc_build`, tracker phẳng, tile waveform/ keycap/ timeline NLE) |

**Loại C: từ chối bằng lỗi, không giả lập.** `refuse_c_class(name)` raise `UnsupportedEffectError` cho Time Displacement (và slit-scan native), chất lượng AI Object Mask / Roto Brush, planar tracking có xử lý che khuất, extrude 3D. Khoá plan `opener` của `spec_from_plan.py` đi qua hàm này nên các yêu cầu đó thoát mã 2 với thông báo rõ, preset lạ cũng vậy.

**Test (tĩnh, không dựng/ render dự án):** `tests/test_flicker_schedule.py` (lịch đúng frame ở năm tốc độ khung, `overlay enable='lt(mod(n,4),2)'` trên `testsrc2` 360x640@60 cho độ sáng tâm `252, 252, P, P` lặp lại, màu bóng đúng `#FFFBF0`, clean plate trung vị gỡ ô vuông chuyển động, lỗi rõ ràng khi matte rỗng/ không phải người/ chồng, khoá `opener`), `tests/test_effect_presets.py` (id hiệu ứng có trong `effects.list` của mục 1.2, tên tham số và lựa chọn khớp bản dump khi tìm thấy, giá trị nằm trong `param_ranges` khai báo, khoá bằng số frame nguyên ở mọi fps, dòng spec qua `fc_build.validate` + `sanitize_spec` + `spec_lint`, vị trí frame của macro vanish và clone). `filmcraft-commands.json` chỉ liệt kê **lệnh** (không có danh sách id hiệu ứng), nên test kiểm các lệnh builder cần (`effects.apply`, `effects.setParam`, `effects.setKeyframe`, `effects.setInterpolation`) và dùng mục 1.2 + bản dump cho id; file nào vắng thì test in `[SKIP]`.

**Chênh lệch đo so với mục 6:** độ sáng silhouette `252` lặp lại đúng. Độ sáng "plate" ở tâm khung phụ thuộc điểm lấy mẫu: x = W/2 nằm đúng mép hai dải màu của `testsrc2` nên test lấy điểm phẳng bên cạnh (kết quả `29`, không phải `23` ghi ở mục 3.1/ 6, vị trí lấy mẫu lúc đó không được ghi lại). Mẫu `252, 252, P, P` (2 frame mỗi trạng thái) không đổi.

**Còn chưa kiểm trong app (thêm vào mục 7):** hành vi `rgb_split` (đơn vị và dấu của `amount`), `focus_blur` Radial (`size`/ `feather`), `crop` (đơn vị %), `glint` (`rays` nhận chuỗi "4" hay chỉ số), `invert` blend hold, `wonder_glow` intensity, transition `dip_to_white`/ `flash` có vượt trần của `white_flash_0p25s` không, và việc 2-frame clip liên tiếp ở 60 fps được `fc_build` đếm đúng khi dựng thật.

## 9. Con trỏ v7.7.0 (không viết lại các mục trên)

- Hook 5 giây đầu và luật nhịp (max hold, reset mỗi 5 giây, ngưỡng dead hold, trần zoom theo lớp, số liệu 17 video có nhãn [ĐO] / [ƯỚC]): [`28_hook_first_5s_and_pacing.md`](./28_hook_first_5s_and_pacing.md).
- Thẻ pop-out (đầu nhô lên khỏi thẻ sáng): công thức Premiere / CapCut và bảng A / B / C, `render_popout_studio_card`, cảnh báo thiếu khoá `masks` (H5) và viền xám của RVM: [`29_popout_card_premiere_to_filmcraft.md`](./29_popout_card_premiere_to_filmcraft.md).
