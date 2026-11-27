# 25. Độ to âm thanh cho TikTok và cách từng phần mềm dựng xử lý — bảng số khuyến nghị

Ngày nghiên cứu: 2026-11-25. Phạm vi: chỉ nghiên cứu và đề xuất số. Không dựng, không render, không sửa file nào khác của skill. Việc cần sửa ở file khác nằm ở mục 9.

Cập nhật v7.5.0: bảng mục 7 đã được cài vào `presets/profile_overrides.json` và `audio_levels.py`; giá trị nào đo và giá trị nào suy ra xem mục 7.2, phần còn lại xem mục 9.

Quy ước độ tin cậy: **[CHÍNH THỨC]** = tài liệu của chính tổ chức ban hành (EBU, AES qua bản tóm tắt, Meta Engineering). **[ĐO]** = đo trực tiếp (số liệu 17 video @__dviet trong `dviet_19/INDEX.md`, hoặc thí nghiệm tổng hợp ở mục 4). **[BÊN THỨ BA]** = blog, hãng công cụ, diễn đàn; không có tài liệu gốc đi kèm. **[SUY LUẬN]** = tôi suy ra từ các mục trên, chưa kiểm bằng đo thật.

---

## 1. Kết luận ngắn (đọc phần này trước)

1. **TikTok không công bố mức độ to đích.** Không tìm thấy trang chính thức nào (trang TikTok Ads Help trả về chỉ nói định dạng/chính sách, không có LUFS). Mọi con số "-14 LUFS" đều là [BÊN THỨ BA], không dẫn nguồn đo; có nguồn nói -16, có nguồn nói -9..-12, có nguồn nói TikTok không chuẩn hoá khi phát trong feed. **Không có phép đo có kiểm soát nào** (upload nhiều mức, đo lại) được tìm thấy. Con số nào của skill về "TikTok normalize về X" đều chưa kiểm chứng được.
2. **Nếu có chuẩn hoá thì nó nằm ở phía phát (playback), không nằm trong file.** Meta mô tả đúng cách này cho Reels/Stories: giữ nguyên âm thanh, gửi metadata độ to, máy khách chỉnh theo ngữ cảnh nghe [CHÍNH THỨC]. Hệ quả cho dữ liệu của kênh: file @__dviet tải về có -10.7..-12.6 LUFS cho biết **người làm kênh xuất ra mức nào**, không cho biết **người xem nghe mức nào**. Đừng dùng nó để "chứng minh" TikTok không hạ mức.
3. **Chọn -12 LUFS vẫn là lựa chọn an toàn** vì tổn thất bất đối xứng: nếu nền tảng hạ về -14 thì bản -12 chỉ bị giảm 2 dB (nghe y như bản -14, ít động lực hơn một chút); nếu nền tảng không chuẩn hoá thì bản -12 to hơn video -14 xung quanh 2 LU, đúng vị thế của kênh. Rủi ro thật nằm ở phía **quá nhỏ**: YouTube không nâng video nhỏ lên, và video -20.1 LUFS của kênh bị lệch 8 LU so với các video còn lại.
4. **Trần true-peak phải đổi từ -0.5 sang -1.0 dBTP** (mục 4: mã hoá lại AAC làm đỉnh nhảy lên 0.1 đến 3 dB tuỳ bitrate; ở -0.5 hầu như luôn vượt 0 dBFS sau mã hoá). Đây là phần số liệu mạnh nhất, nhưng chỉ là thí nghiệm tổng hợp bằng bộ mã AAC của ffmpeg.
5. **`bgm_below_voice = 6.6 dB` là số đoán và nên bỏ** cho đoạn có lời. Số liệu kênh (5 video, nền nhạc đo ở khoảng nghỉ) cho nhạc nền thấp hơn giọng khoảng **13 đến 17 dB**, trung vị 14.3. Con số 6.6 gần với mức nhạc ở đoạn **không có lời** (5 đến 6 dB, 2 video, lẫn SFX), nên tôi tách thành hai trạng thái (mục 7).
6. Skill hiện có **ba bộ số độ to mâu thuẫn nhau** (ovs -16/-14, `sfx_micro_sync_rules` -14 ±1 / -1.5 dBTP / nhạc "ducked" -28..-24 dBFS, `tiktok_loud` -12). Bảng ở mục 7 nhằm thay thế cho profile `tiktok_loud`; hai bộ kia giữ cho profile `platform`.

---

## 2. TikTok, YouTube, Instagram Reels, Facebook

| Nền tảng | Điều đã biết | Nguồn / độ tin cậy |
|---|---|---|
| **TikTok** | Không có spec độ to công bố. Tuyên bố "-14 LUFS, -1 dBTP" từ hãng công cụ, không có phép đo. Một nguồn nói không chuẩn hoá khi phát trong feed (khuyên -7..-8 LUFS, rất khó tin); một nguồn nói mục tiêu nội bộ ~-16; một nguồn nói -9..-12. Việc "nén nặng khi mã hoá lại" cũng chỉ là tuyên bố, không nêu codec hay bitrate. | [BÊN THỨ BA], mâu thuẫn nhau. Mục 8 có quy trình tự đo. |
| **YouTube** | Quan sát (không có spec công bố): chuẩn hoá quanh -14 LUFS, **chỉ hạ, không nâng**. "Stats for nerds" có dòng *content loudness*, giá trị dương nghĩa là video đang bị hạ. | [BÊN THỨ BA], nhiều nguồn khớp nhau; bài Fora Soft ghi rõ "YouTube publishes no number". |
| **Instagram Reels / Stories** | Dùng **xHE-AAC**. Chuẩn hoá làm ở **phía phát** bằng metadata, đưa độ to trung bình của mọi phiên về cùng một mức đích, kèm điều khiển dải động (MPEG-D DRC) theo ngữ cảnh (tai nghe, loa máy, ồn). Bài không nêu số LUFS hay bitrate. | [CHÍNH THỨC] Meta Engineering. Con số "-14" cho Reels là [BÊN THỨ BA]; tuyên bố "HE-AACv2 48 kbps" từ Reddit mâu thuẫn với bài của Meta nên bỏ qua. |
| **Facebook** | Có xHE-AAC trên iOS và Android; không nêu số mức đích. | [CHÍNH THỨC] cùng bài Meta. |

Ghi chú cho việc đọc các bài "-14 LUFS cho mọi nền tảng": phần lớn là bài của hãng công cụ loudness, có lợi ích bán công cụ. Bài của Fora Soft (2026) tóm gọn đúng tinh thần: không nền tảng nào trong nhóm TikTok/Meta công bố mục tiêu, mọi số cố định là ước lượng; khuyên -1 dBTP là lời khuyên của tác giả, không phải của nền tảng.

---

## 3. Chuẩn phát sóng và khuyến nghị streaming (để biết "đích chuẩn" nằm ở đâu)

| Chuẩn | Mức tích hợp | Trần true-peak | Ghi chú |
|---|---|---|---|
| **EBU R128 (2023)** | -23.0 LUFS; dung sai ±0.5 LU (±1.0 cho chương trình phát trực tiếp); ±0.2 LU cho sai số đo trong QC | **-1 dBTP** khi sản xuất tuyến tính; mức tối đa cho phép có thể thấp hơn tuỳ hệ thống phân phối và bitrate nén | [CHÍNH THỨC]. Đo trên toàn bộ chương trình, không nhấn vào lời hay nhạc. |
| **EBU R128 s1 (2020), nội dung ngắn** | -23.0 LUFS; short-term tối đa -18 LUFS (+5 LU); **LRA "không áp dụng"** vì với clip ngắn (quảng cáo, promo, tới ~2 phút) quá ít điểm dữ liệu | -1 dBTP | [CHÍNH THỨC]. Quan trọng với ta: video TikTok 25 đến 65 s thuộc loại này, nên **không dùng LRA làm cổng cứng**. |
| **EBU R128 s2 (2023), streaming** | Khuyến nghị phát nguyên mức -23; nếu đơn vị phát muốn tự xử lý động trước khi stream thì mức "Distribution Loudness" tạm thời -20..-16 LUFS | Dùng bộ giới hạn true-peak ở thiết bị khi cần | [CHÍNH THỨC]. Cho thấy lý do chuẩn streaming cao hơn phát sóng: thiết bị di động thiếu headroom/gain. |
| **ATSC A/85** | -24 LKFS (LKFS = LUFS) | -2 dBTP | [BÊN THỨ BA] (bài Fora Soft, DaVinci Resolve 21 guide, ITU-R BS.2434). Dung sai ±2 chỉ thấy trong bảng ITU, chưa đối chiếu với văn bản A/85. Chỉ để tham khảo: kênh này không giao truyền hình Mỹ. |
| **AES TD1004 (2015)** | Streaming/phát file: -16 LKFS khuyến nghị, cho phép -16..-20 | -1 dBTP tại đầu vào bộ mã hoá lossy, có thể cần lùi thêm tuỳ codec và bitrate | Bản tóm tắt qua Radio World, Scribd; **không đọc được bản gốc** (aes.org trả 403). Có nguồn thứ ba nói -18, nên coi là [BÊN THỨ BA]. |
| **AES TD1008 (2021)** | Âm nhạc -16 LUFS; **lời nói, quảng cáo xen, trợ lý ảo -18 LUFS**; mức này là "Distribution Loudness", do dịch vụ chuẩn hoá chứ nhà sản xuất không cần master về đúng số đó | -1 dBTP tại đầu vào codec; bộ mã tốc độ cao (khoảng 256 kbps) có thể chịu -0.5 dBTP; **overshoot tăng khi bitrate giảm** | Tóm tắt từ Production Advice và ghi chú công cụ trích TD1008; **bản gốc không truy cập được**. Đáng chú ý: AES khuyên lời nói thấp hơn nhạc 2 đến 3 dB. |

Điều cần rút ra cho TikTok: các chuẩn trên mô tả mức **phát lại sau chuẩn hoá** (-16/-18/-23), không phải mức nên master. Một video thuyết trình ngắn master ở -12 là chọn lựa thẩm mỹ/cạnh tranh mức to, không phải chuẩn. Cái chuẩn nào cũng đồng ý là **-1 dBTP** ở đầu vào bộ mã.

---

## 4. Thí nghiệm: đỉnh true-peak sau khi mã hoá lại AAC [ĐO, tổng hợp]

Mục đích: kiểm tra trần -0.5 dBTP của `tiktok_loud` có ý nghĩa gì sau khi nền tảng mã hoá lại.

Cách làm (thư mục tạm của phiên, không nằm trong skill, không có video): tín hiệu tổng hợp 3 s gồm "giọng" (hài âm 120 Hz có rung, bao biên độ 4 Hz, xì xào) trộn "nhạc" (nhiễu hồng + hợp âm), trộn nhạc -6.6 dB, giới hạn, rồi chỉnh gain để true-peak trước mã hoá lần lượt là -3.0, -2.0, -1.5, -1.0, -0.5 dBTP. Mã hoá `aac` của ffmpeg (bộ mã gốc của ffmpeg, **không phải** bộ mã của TikTok), giải mã lại, đo bằng ebur128 `peak=true`. Cột là mức thay đổi true-peak (dB) sau mã hoá, bản mix:

| True-peak trước mã hoá | 256 kbps | 128 kbps | 96 kbps | 64 kbps |
|---|---|---|---|---|
| -3.0 dBTP | +1.1 | +0.9 | +2.5 | +3.0 |
| -2.0 | -0.1 | +0.1 | +1.4 | +2.3 |
| -1.5 | -0.2 | -0.1 | +0.8 | +1.6 |
| -1.0 | -0.1 | +0.1 | +0.7 | +1.1 |
| -0.5 | -0.2 | +0.6 | +0.9 | +0.7 |

Độ to tích hợp gần như không đổi sau mã hoá (chênh dưới 0.3 LU trong mọi ô).

Đọc kết quả, kèm các giới hạn:
- Ở **≥128 kbps** đỉnh gần như giữ nguyên (đa số ô trong ±0.2 dB, ngoại lệ ở hàng -3.0 là +0.9..+1.1). Ở **≤96 kbps** đỉnh tăng 0.7 đến 3 dB. Phù hợp với ghi chú TD1008 "bitrate càng thấp, overshoot càng lớn".
- Ở trần -0.5 dBTP, mix **luôn** vượt 0 dBFS ở 128 kbps trở xuống (+0.1..+0.4 dBTP). Với trần -1.0, true-peak sau mã hoá là -0.9 (128 kbps), -0.3 (96 kbps), +0.1 (64 kbps).
- Các ô không đơn điệu (hàng -3.0 có +1.1 ở 256 kbps), tức là kết quả nhạy với tín hiệu. Chỉ có **một** tín hiệu tổng hợp, một bộ mã. Đây là bằng chứng định hướng, **không phải** mô hình của TikTok. Tôi không biết bitrate âm thanh TikTok dùng khi phát.
- Khớp với dữ liệu thật: 10/17 video kênh có đỉnh > 0 dBFS, cao nhất +3.0 (đó là file đã qua AAC; xem 7670574911680777492). Master bị limiter ép sát + AAC cho đúng kiểu vượt đỉnh này.

Hệ quả: -1.0 dBTP là mức tối thiểu hợp lý; không có trần nào đảm bảo ≤ 0 dBFS sau khi nền tảng mã hoá lại, nên cổng kiểm cần đo **cả mix.wav** (trước mã) **và** file xuất (sau mã), file xuất chỉ cảnh báo.

---

## 5. Từng phần mềm dựng xử lý độ to như thế nào

Giới hạn tìm kiếm: trang trợ giúp Adobe và Blackmagic không mở được bằng công cụ lấy trang (HTTP 403); thông tin Premiere, CapCut, Resolve dưới đây lấy từ bài hướng dẫn bên thứ ba và trang marketing, **cần đối chiếu trên bản cài thực tế** trước khi ghi vào quy trình.

| Phần mềm | Cơ chế | Điều cần cẩn thận |
|---|---|---|
| **Premiere Pro, Essential Sound > Auto-Match** | Quét clip từ điểm vào đến điểm ra, đo LUFS, chỉnh **gain** về mức cố định theo loại. Cộng đồng báo Dialogue ≈ -23 LUFS (có bài khác nói -14, mâu thuẫn); Music -25, SFX -21, Ambience -30 chỉ có một nguồn mỗi loại [BÊN THỨ BA]. Chỉ là gain, không nén. Clip quá ngắn không đo được. Preset kiểu Podcast (-16) không xác nhận được. | Là công cụ cân clip theo chuẩn phát sóng, **không phải** công cụ master -12. Dùng để cân giọng giữa các clip rồi tự nâng cả bus. `essentialSound.generateDucking` xoá keyframe cũ (đã ghi ở `02_nle_premiere_filmcraft.md`). |
| **Premiere Pro, Loudness Radar** | Theo trợ giúp Adobe (qua kết quả tìm kiếm): hiệu ứng **chỉ đo**, không đổi mức; có Target Loudness, Radar Speed, Radar Resolution và preset theo chuẩn; nay đã được **Loudness Meter** thay thế, cùng quy trình ở Premiere và Audition. | Đặt Target Loudness của meter bằng -12 thì vạch "xanh" mới có nghĩa. Thang EBU +9 (hẹp) hay +18 (rộng) chỉ là cỡ hiển thị. |
| **Premiere Pro, Audio Track Mixer** | Fader theo track và tự động hoá (write/touch/latch) cho ducking thủ công. | Không có thông tin chính thức về giá trị mặc định ducking của Essential Sound; không dựa vào mặc định, dùng bộ số mục 7. |
| **Adobe Media Encoder, Loudness Normalization khi xuất** | Có tuỳ chọn chuẩn hoá khi xuất (một bài hướng dẫn nói chọn ITU BS.1770-3 và nhập mức). | **Tắt** hoặc đặt trùng -12, nếu không bản xuất bị đổi mức sau khi đã kiểm. |
| **CapCut, Loudness Normalization** | Tính năng "pro", áp cho **clip đang chọn**, theo trang của CapCut đưa về **-23 LUFS** và "giữ khuyến nghị EBU" [BÊN THỨ BA: trang resource của chính CapCut, không phải tài liệu trợ giúp; trang công cụ không nêu số]. | Đưa clip về -23 nghĩa là sau đó phải tự nâng ~11 dB để tới -12, dễ gây clip. **Không dùng làm bước master**. Dùng tối đa để cân các clip giọng với nhau, rồi đo bản xuất bằng công cụ ngoài (lệnh ở mục 8). |
| **DaVinci Resolve, Fairlight** | Loudness Meter đo Momentary (400 ms), Short-term (30 s trong mô tả bài viết), **Integrated**, LRA và True Peak. "Target Loudness Level" ở Project Settings, mặc định -23, **chỉ dời điểm 0 của đồng hồ, không đổi âm thanh**. "Normalize Audio Levels" (chuột phải clip) mặc định là **Sample Peak**, có chế độ True Peak và chế độ theo thuật toán loudness, **chỉ thấy clip đang chọn, không thấy mix cuối**. Cách chỉnh mix: phát toàn timeline, đọc Integrated, trừ khỏi đích, dời fader bus Main, đo lại. Báo cáo diễn đàn: Normalize và đồng hồ Fairlight từng lệch nhau. | Đặt target = -12 để meter đọc đúng; đo trên bus **Main**, đặt limiter ở bus Main. Fairlight meter hiển thị Sample Peak, Control Room mới hiển thị True Peak (theo diễn đàn Blackmagic), nên đừng đọc đỉnh từ sai đồng hồ. |
| **FilmCraft (skill này)** | `scripts/vendor/ovs_core/scripts/audio_levels.py` đọc các số từ `rules.json` (`params.audio`) và **dừng nếu thiếu khoá**. `plan` đặt `gain_db` từng clip: giọng theo **đỉnh mẫu** về `voice_peak_dbfs.target`; nhạc theo **LUFS** (LUFS giọng − `bgm_below_voice_lu.target`); SFX theo **đỉnh** theo tầng A/B/C, rồi hạ cả cụm SFX chồng nhau nếu đỉnh cụm vượt đích. `stems` dựng 3 stem xấp xỉ; `check` đo mix (LUFS tích hợp, true-peak) và so với luật, `speech_floor` dùng short-term trên cửa sổ có lời (cửa ≥ LUFS giọng − 10 LU). `compile_and_verify.py` chạy vòng đo-chỉnh nhanh, chỉnh lại nếu lệch > 0.45 LU và coi đạt khi lệch ≤ 0.55 LU. **FilmCraft không có sidechain**, ducking làm bằng keyframe âm lượng 4 điểm (`02_nle_premiere_filmcraft.md` §4). | `mix.wav` FilmCraft xuất ra mới là chuẩn đo LUFS/true-peak (tài liệu trong `audio_levels.py`); stem từ spec chỉ là xấp xỉ. Profile `tiktok_loud` hiện đặt `no_ducking: true`. |

---

## 6. Bằng chứng từ kênh @__dviet (17 video, ground truth)

Nguồn: `references/dviet_19/INDEX.md` và các file con. Tất cả [ĐO] bằng ebur128/RMS 50 ms trừ khi ghi [ƯỚC]. File phân tích là bản AAC tải về (HEVC + AAC), không rõ bitrate âm thanh.

| Chỉ số | Giá trị đo | Số video |
|---|---|---|
| Độ to tích hợp | -10.7 đến -12.6 LUFS (trung vị 13 video = **-11.5**) | 13/17 |
| Ngoại lệ nhỏ | -13.7, -13.8 (cùng một audio), -16.7, **-20.1** | 4/17 |
| Đỉnh mẫu hoặc true-peak > 0 dBFS | +0.2 đến **+3.0** (7670574911680777492) | 10/17 |
| LRA | 1.6 đến 3.5 LU (một video showcase SFX 9.6) | hầu hết |
| Đỉnh của riêng giọng (khoảng) | -2.0, -2.6, -2.9 dB, giọng median RMS -12.2 đến -13.1 dB | 3 video có ghi [ƯỚC: lấy từ mix] |
| Nền nhạc ở khoảng nghỉ so với giọng median (RMS 50 ms) | thấp hơn **13.3, 13.7, 14.3, 14.8, 16.6 dB** (trung vị 14.3) | 5 video [ƯỚC]; sàn p2 -25.8..-29.8 dBFS |
| Mức khoảng nghỉ gần giọng hơn | 6.1 dB (7688934517783989524) và ~5 dB (7683763922234641684, lẫn SFX) | 2 video [ƯỚC] |
| Đoạn nào xuống dưới -48 dB | không có | cả 17 (trừ vacuum cố ý: 7672413018575146261, -32 dB trong 0.4 s trước hit) |
| Hit/pop theo từng chữ hero | transient +14..+20 dB so với nền, trễ 0.1 đến 0.3 s sau khi chữ vào | 7667598741888634132 [ƯỚC, không nghe trực tiếp] |

Hai điểm ghi chú:
- Đỉnh +3.0 dBFS của file tải về cho thấy master bị giới hạn rất sát (hoặc clip), sau đó qua AAC. Skill đã quyết không noi theo (`23_dviet_profile_decisions_and_backlog.md` mục d); tôi giữ nguyên quyết định đó và chỉ đổi trần -0.5 thành -1.0.
- Số liệu nền nhạc là **ước lượng gián tiếp** (đo ở khoảng nghỉ, không tách stem), và nếu kênh có ducking thì mức nhạc **trong lúc nói** thấp hơn mức đo ở khoảng nghỉ, tức khoảng cách thật còn lớn hơn 14 dB. Vì vậy 14 là cận dưới thận trọng cho đoạn có lời.

---

## 7. Bảng số khuyến nghị cuối cùng (profile `tiktok_loud`, thay cho bản hiện tại)

Đơn vị: LUFS cho độ to tích hợp; dBTP cho true-peak; dBFS cho đỉnh mẫu của stem tương ứng (đo riêng từng stem sau gain); LU cho chênh độ to tích hợp giữa hai stem.

| # | Thông số | Giá trị đích | Cửa sổ đạt | Căn cứ và độ tin cậy |
|---|---|---|---|---|
| 1 | **Độ to tích hợp, file giao (mp4 xuất)** | **-12.0 LUFS** | -13.0 đến -11.0 (±1.0); ngoài -14..-10 là FAIL | Trung vị kênh -11.5, giữ 0.5 LU thận trọng hơn; tổn thất bất đối xứng (mục 1.3). Trần trên -10.5: kênh không có video nào to hơn -10.7 [ĐO + SUY LUẬN]. |
| 1b | Độ to tích hợp trên `mix.wav` (trước AAC) | -12.0 | ±0.5 (giữ cổng hiện tại; vòng re-trim 0.45) | Tại đây thuật toán đo là tất định; AAC đổi độ to dưới 0.3 LU (mục 4) [ĐO]. |
| 2 | **Trần true-peak** | **-1.0 dBTP** (đặt bộ giới hạn ở **-1.2 dBTP**, chừa sai số đồng hồ ±0.3 dB) | `mix.wav`: ≤ -1.0 đạt; -1.0..-0.5 cảnh báo; > -0.5 FAIL. File xuất sau AAC: chỉ cảnh báo nếu > 0 dBTP | R128 và TD1008 đều -1 dBTP ở đầu vào codec [CHÍNH THỨC/BÊN THỨ BA]; mục 4 cho thấy -0.5 luôn vượt 0 dBFS sau mã hoá. Nếu chỉ có limiter đỉnh mẫu (không oversample), đặt ở -1.5 dBFS. |
| 3 | **LRA** | Không có cổng cứng; ghi nhận 1.5 đến 5 LU | Cảnh báo nếu > 6 | R128 s1: LRA không có nghĩa với clip ngắn [CHÍNH THỨC]. Kênh 1.6 đến 3.5 LU [ĐO]. |
| 3b | Short-term tối đa | ≤ **-7 LUFS** (đích + 5 LU) | Cảnh báo nếu vượt | Tương tự R128 s1 (−23 → −18, tức +5 LU) [CHÍNH THỨC, áp lại bằng suy luận]. |
| 4 | **Giọng thoại: đỉnh mẫu** | **-2.0 dBFS** | **-3.5 đến -1.5** (hiện -3.5..-0.5; hạ cận trên vì trần -1.0 dBTP và còn nhạc/SFX cộng vào) | Đỉnh giọng kênh -2.0..-2.9 [ƯỚC]; cận trên là suy luận [SUY LUẬN]. |
| 4b | Giọng thoại: độ to tích hợp của stem | **-12.5 LUFS** | -13.5 đến -11.5 (chỉ theo dõi) | Giọng ≈ mix − 0.3..0.5 dB vì nhạc/SFX nhỏ cộng thêm; PLR giọng ≈ 10.5 dB; nếu tới đỉnh -2.0 mà LUFS còn thấp, tăng **nén giọng**, không nâng đỉnh [SUY LUẬN]. |
| 5 | **Nhạc nền khi có lời** (giọng đang nói) | **14 LU** dưới giọng | 12 đến 17 | Kênh: 13.3..16.6, trung vị 14.3 [ƯỚC]; nghiên cứu Salford/Fraunhofer: người nghe khó tính ưa chênh 16 đến 23 LU với lời bình, voice-over-voice tối thiểu 20 LU [BÊN THỨ BA, tóm tắt]; thực hành phát sóng 10 đến 20 dB. Chọn 14 để bám kênh. Thay 6.6. |
| 5b | Sàn "lời luôn trên nhạc" (short-term, mọi cửa sổ có lời) | **≥ 8 LU** | WARN 6..8, FAIL < 6 | Con số dẫn xuất (đích 14 − 6, cùng biên độ như bộ ovs 17 → 10 là 7); **chưa đo trên giọng thật** [SUY LUẬN]. Thay `bgm_speech_floor_lu: 3.0`, vốn là số đoán. |
| 6 | **Nhạc nền khi không có lời** (khoảng trống giọng ≥ 1.5 s, hoặc cảnh B-roll không voice-over) | **6 LU** dưới giọng chuẩn | 4 đến 8 | 2 video kênh: 5 đến 6 dB [ƯỚC, lẫn SFX]. Nhạc "bung" lên +8 dB so với mức có lời, nhưng **không bao giờ vượt mức giọng chuẩn** [SUY LUẬN]. |
| 7 | **Ducking** (không sidechain, keyframe 4 điểm) | Sâu **8 dB** (từ mức 6 LU xuống 14 LU) | 6 đến 10 | Ép xuống bắt đầu **0.35 s trước** chữ đầu, hạ xong trong 0.25 s (kịp về mức thấp 0.1 s trước khi giọng vào); khoảng nghỉ < 1.5 s giữ nguyên mức thấp (chống bơm); tăng lại **0.7 s** theo đường mũ, bắt đầu 0.2 s sau chữ cuối. Hai con số 0.35 và 0.7 là sẵn có (`sfx_micro_sync_rules.json`: `pre_roll_sec` 0.35, `release_sec` 0.7, `hold_through_gap_under_sec` 1.5); 0.25 s và 8 dB là [SUY LUẬN]. Bỏ khoảng "-24..-28 dB" trong `02_nle_premiere_filmcraft.md` §4 cho profile này. |
| 8 | **SFX, nhóm hit/impact/boom/stinger (tầng A)** | **-4.0 dBFS** đỉnh | -5.0 đến -3.0 | Hit của kênh đi theo chữ hero, là phần nổi nhất của mix [ƯỚC]; dưới đỉnh giọng 2 dB, đoạn ngắn (< 0.3 s) đóng góp dưới 0.1 LU [SUY LUẬN]. |
| 9 | **SFX, whoosh mạnh / whip / film-burn / riser cao trào (tầng B)** | **-7.0 dBFS** | -9.0 đến -5.0 | Dài hơn hit nên góp độ to nhiều hơn; tách riêng khỏi tầng A [SUY LUẬN]. Kênh: SFX chuyển cảnh nhỏ và chồng dưới giọng (7670574911680777492 [ƯỚC]). |
| 10 | **SFX, whoosh nhẹ (zoom, vải), click, shutter, pop UI, text phụ (tầng C)** | **-10.0 dBFS** | -12.0 đến -8.0 | Giữ nguyên dải -12..-8 của luật ovs hiện có (không có dữ liệu mới) và ánh xạ tầng C. |
| 11 | **Cụm SFX chồng nhau** | Đỉnh cụm ≤ mức đích lớn nhất của cụm + 0.05 dB | như `audio_levels.py` | Không đổi. |
| 12 | **Vacuum trước hit** | Nhạc hạ -32 dB trong 0.4 s rồi hit | Tối đa 0.5 s; cho phép -inf (`meta.bgm_stops`) | Đo ở 7672413018575146261 [ĐO]. Chỉ dùng cố ý, ≤ 1 lần / 20 s [SUY LUẬN]. |
| 13 | **Sàn im lặng** | Nền nhạc/ambience ở khoảng nghỉ **-26 đến -30 dBFS** (RMS 50 ms) | Không đoạn nào < -48 dBFS ngoài vacuum đã khai báo | Kênh: p2 -25.8..-29.8 và không có đoạn < -48 dB ở cả 17 video [ĐO]. |
| 14 | **Bộ giới hạn cuối** | True-peak limiter ở -1.2 dBTP, lookahead ≥ 5 ms | Độ ép đỉnh tối đa ≤ 3 dB tại hit | [SUY LUẬN]: nếu ép > 3 dB, hạ tầng A của SFX thay vì ép thêm. |

Kiểm tra số học nhanh (tránh bảng tự mâu thuẫn): giọng -12.5 LUFS, nhạc thấp hơn 14 LU (-26.5 LUFS) góp ~0.2 dB, SFX ngắn góp ~0.1 đến 0.3 dB, tổng mix ≈ -12.1 đến -12.0 LUFS. Giọng có đỉnh -2.0 dBFS cộng nhạc cách 14 dB tạo đỉnh mix ≈ -1.6 dBFS, nằm dưới trần -1.0 dBTP có chừa chỗ cho giới hạn.

Quy tắc ưu tiên khi có xung đột giữa các hàng: (1) trần true-peak, (2) giọng nghe rõ (hàng 5b), (3) độ to tích hợp. Muốn to hơn thì tăng nén giọng, không tăng đỉnh và không tăng nhạc.

### 7.1. Cài đặt cho phần mềm dựng khi xuất

Áp dụng cho Premiere Pro, CapCut, DaVinci Resolve và FilmCraft. Tên menu cần đối chiếu trên bản cài, vì tài liệu chính thức của Adobe và Blackmagic không mở được khi nghiên cứu.

| Mục | Cài đặt | Lý do |
|---|---|---|
| Codec âm thanh | AAC-LC, 48 kHz, stereo | Khớp tần số lấy mẫu khung stem của `audio_levels.py` (48 kHz) và đầu vào mã hoá của nền tảng. |
| Bitrate âm thanh xuất | **≥ 256 kbps** (tối thiểu 192) | Nền tảng sẽ mã hoá lại; bitrate cao ở đầu vào giảm tổn thất thế hệ. Bitrate TikTok dùng khi phát không được công bố. Mục 4: ≥128 kbps overshoot nhỏ, ≤96 kbps lớn. |
| Chuẩn hoá lúc xuất (Premiere/Media Encoder, CapCut, bước Deliver của Resolve) | **TẮT** | Mọi bước chuẩn hoá tự động sẽ làm đổi mức sau khi đã kiểm, hoặc kéo về -23 (CapCut). |
| Bộ đo trong phần mềm | Đặt Target Loudness của meter = **-12 LUFS** (Premiere: Loudness Meter, thay cho Loudness Radar; Resolve: Project Settings > Fairlight) | Meter chỉ đúng khi mốc 0 đúng. |
| Bộ giới hạn trên master/bus Main | True-peak limiter **-1.2 dBTP**; nếu chỉ có limiter đỉnh mẫu thì **-1.5 dBFS** | Hàng 2 của bảng mục 7. |
| Cân giọng giữa các clip | Auto-Match (Premiere), Loudness Normalization (CapCut), Normalize Audio Levels (Resolve) chỉ để **cân clip giọng với nhau**; sau đó đo toàn mix và chỉnh fader bus | Các công cụ này làm việc trên clip đã chọn, không thấy mix cuối. |
| Ducking | FilmCraft: keyframe 4 điểm như hàng 7. Premiere: Audio Track Mixer + keyframe tay, hoặc Essential Sound Ducking với *Duck Amount* khoảng -8 dB và fade tương ứng (đã ghi: `generateDucking` xoá keyframe cũ) | Không có sidechain trong FilmCraft. |
| Kiểm cuối bắt buộc, ngoài phần mềm | `ffmpeg -nostats -i FILE -vn -af ebur128=peak=true -f null -` rồi đọc `I:`, `LRA:` và `Peak:` ở phần Summary | Một công cụ đo duy nhất cho mọi phần mềm, là cách `audio_levels.py` đo. |

### 7.2. Đã đưa vào mã (v7.5.0): giá trị nào đo, giá trị nào suy ra

Bảng ở trên đã được cài vào `presets/profile_overrides.json` (profile `tiktok_loud`) và `scripts/vendor/ovs_core/scripts/audio_levels.py`. Hồ sơ `platform` không đổi (có test hồi quy trong `tests/test_loudness_v75.py`). **TikTok không công bố mức độ to đích; không có mã hay tài liệu nào của skill được phép nêu một con số chuẩn hoá "chính thức" của TikTok.**

| Nhóm | Giá trị | Ghi trong preset |
|---|---|---|
| **ĐO** | -12 LUFS tích hợp (17 video của kênh, -10.7..-12.6); chênh giọng/nhạc nền ~14 LU (13.3..16.6); chiều của độ vượt đỉnh sau AAC: bản -0.5 dBTP vượt 0 dBFS sau mã hoá, nên trần -1.0 dBTP (một tín hiệu tổng hợp, bộ mã AAC của ffmpeg, chỉ mang tính định hướng) | `target_lufs`, `master_lufs.final`, `bgm_below_voice_lu.target`, `true_peak_dbtp`, `master_true_peak_dbtp` |
| **SUY RA, chưa kiểm trên giọng thật** | sàn lời-trên-nhạc 8 LU; ba tầng SFX -4 / -7 / -10 dBFS; đoạn ép 0.25 s và độ sâu 8 dB; cận trên đỉnh giọng -1.5; nhạc nền không lời 6 LU (4..8); cảnh báo LRA > 6 và short-term tối đa > -7 LUFS | `bgm_speech_floor_lu`, `sfx_peak_dbfs`, `voice_peak_dbfs.max`, `bgm_no_voice_lu`, `lra_warn_lu`, `short_term_max_lufs` |

Mức đạt trong mã: LUFS `mix.wav` ±0.5, true peak ≤ -1.0, đỉnh giọng, chênh nhạc/giọng và sàn lời-trên-nhạc là **FAIL** khi lệch. Nhạc nền không lời, LRA và short-term tối đa chỉ **WARN** (không đổi exit code của `audio_levels.py check`), và chỉ chạy khi `rules.json` có khoá tương ứng. Hai chỗ khác với cột "Cửa sổ đạt" ở bảng mục 7: (1) true peak dùng một ngưỡng cứng -1.0 dBTP chứ chưa có dải cảnh báo -1.0..-0.5; (2) LRA của clip ngắn (dưới ~10 s) do ebur128 báo thường vọt lên vì cửa sổ 3 s chưa đầy (đo trên clip tổng hợp 3 s: 20 LU), nên chỉ để tham khảo. Nhạc nền không lời chỉ tính các cửa sổ short-term mà cả 3 s đều không có lời, nên khoảng nghỉ phải dài hơn 3 s mới có số đo.

---

## 8. Điều chưa biết và phép thử đề xuất (chưa chạy)

Chưa chạy vì cần tài khoản và đăng bài (ngoài phạm vi nghiên cứu này):

1. Tạo 3 phiên bản **cùng một nội dung** ở -9, -12, -16 LUFS (cùng trần -1.0 dBTP), đăng ở chế độ riêng tư.
2. Phát trên một điện thoại, âm lượng máy cố định, ghi lại âm thanh phát (ghi nội bộ hoặc cáp loopback; ghi qua micro thì sai), rồi đo từng bản bằng lệnh ebur128 ở mục 7.1.
3. Đọc kết quả: nếu ba bản ra gần cùng mức, TikTok chuẩn hoá hai chiều. Nếu chỉ bản -9 bị hạ, chuẩn hoá chỉ giảm. Nếu chênh đúng 3 LU và 4 LU, không chuẩn hoá. Lặp trên cả iOS và Android, và cả phiên bản nhỏ để biết có nâng lên hay không.
4. Thêm: tải file về và đo để biết **bitrate và codec âm thanh** của bản lưu trữ (`ffprobe`), đối chiếu với mục 4.

Ngoài ra: thí nghiệm mục 4 chỉ dùng một tín hiệu tổng hợp và bộ mã AAC của ffmpeg; cần lặp trên giọng thật + nhạc thật trước khi đổi `compile_and_verify.py`. Con số `bgm_speech_floor = 8 LU` cũng cần kiểm trên giọng thật (docstring hiện tại của `tiktok_loud` đã thừa nhận "voice-peak window and speech floor are conservative derived values, NOT measured").

---

## 9. Việc cần làm tiếp ở file khác (trạng thái sau v7.5.0)

Đã làm trong v7.5.0: `presets/profile_overrides.json` (mọi giá trị của hàng 2, 4, 5, 5b, 8, 9, 10, 14; `tol_lu` 0.5 giữ nguyên), khoá `sfx_peak_dbfs` và nhạc nền không lời / LRA / short-term tối đa trong `audio_levels.py`, hàm `scripts/tools/duck_keyframes.py` (hàng 7, 12), `tests/test_loudness_v75.py` và `tests/test_ducking.py`.

Còn lại (CHƯA làm):

- `no_ducking` vẫn `true`: cần nối `duck_keyframes.py` vào bộ biên dịch (`compile_and_verify.py`, gói khác) trước khi đổi.
- Cổng LRA / đo sau AAC nằm trong `compile_and_verify.py` (không thuộc gói này): hạ LRA xuống thông tin (cảnh báo > 6) và thêm cổng đo thứ hai trên file mp4 xuất (chỉ cảnh báo nếu > 0 dBTP, mục 7 hàng 2) ở đó.
- Dải cảnh báo true peak -1.0..-0.5 của `mix.wav` (hàng 2) chưa cài; hiện là một ngưỡng cứng -1.0 dBTP.
- `presets/sfx_micro_sync_rules.json` (-14 LUFS ±1 / -1.5 dBTP, `bgm_ducked` -28..-24 dBFS) và `02_nle_premiere_filmcraft.md` §4 (-24..-28 dB) áp cho profile `platform`; cần ghi chú rõ để tránh nhầm với `tiktok_loud`.
- `23_dviet_profile_decisions_and_backlog.md` mục (d) nên trỏ sang file này và đổi "trần -0.5 dBTP" thành "-1.0 dBTP".
- Mọi test mới nên dùng clip tổng hợp ≤ 3 s (`ffmpeg` `sine`, `anoisesrc`), không dùng media thật.

---

## 10. Nguồn

Tài liệu chính thức hoặc gần chính thức (đã đọc nội dung):
- EBU R 128 (2023), Loudness normalisation and permitted maximum level of audio signals: https://tech.ebu.ch/docs/r/r128.pdf
- EBU R 128 s1 (2020), Loudness parameters for short-form content: https://tech.ebu.ch/docs/r/r128s1.pdf
- EBU R 128 s2 (2023), Loudness in streaming: https://tech.ebu.ch/docs/r/r128s2.pdf
- EBU Tech 3344, hướng dẫn phân phối và tái tạo theo R128 (chỉ lướt mục lục và bảng mức): https://tech.ebu.ch/docs/tech/tech3344.pdf
- Meta Engineering, high-quality audio với xHE-AAC (Reels, Stories, Facebook; chuẩn hoá ở phía phát): https://engineering.fb.com/2023/04/11/video-engineering/high-quality-audio-xhe-aac-codec-meta/
- Pre-print về độ to ưa thích giữa lời thoại và nền (Resti, Strauss, Torcoli, Habets, Edler, 2023): https://arxiv.org/abs/2305.19100v2

AES (chỉ qua bản tóm tắt, không mở được bản gốc):
- Production Advice, bài về AES TD1008: https://productionadvice.co.uk/td1008/
- Tóm tắt TD1004 qua kết quả tìm kiếm (Radio World): https://www.radioworld.com/?p=95793 (trang trả 403 khi lấy, thông tin lấy từ đoạn trích kết quả tìm kiếm)
- Bản sao TD1004 trên Scribd (không mở): https://www.scribd.com/document/440898812/AESTD1004-1-15-10-pdf
- Ghi chú công cụ trích TD1008 về -1 dBTP, 256 kbps, bitrate thấp tăng overshoot: https://docs.rs/crate/headroom/2.0.0/source/docs/true-peak-ceiling.md

ATSC A/85 và ITU:
- ATSC A/85 (bản 2026-07), không đọc nội dung: https://www.atsc.org/wp-content/uploads/2026/07/A85-2026-07.pdf
- ITU-R BS.2434 (so sánh các chuẩn), không đọc nội dung: https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-BS.2434-2018-PDF-E.pdf
- Bài so sánh R128 / BS.1770 / A85 của Fora Soft: https://www.forasoft.com/learn/audio-for-video/articles-audio/loudness-normalization-ebu-r128-bs1770-atsc-a85

Nền tảng (BÊN THỨ BA, cần dè dặt):
- Fora Soft, "LUFS targets per platform 2026": https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026
- Critical Listening Lab, loudness mạng xã hội: https://www.criticallisteninglab.com/en/learn/loudness/social-media
- Mr. Vocal, Loudness for Shorts: https://mrvocal.com/posts/loudness-for-shorts
- OpusClip blog (hãng công cụ, nói TikTok/Reels -10..-12, Facebook -13): https://opus.pro/blog/best-loudness-normalizers
- DEV Community, "-14 LUFS standard" (không dẫn nguồn): https://dev.to/arthurvalle1_a2586dd2b4bc/mastering-for-reels-tiktok-and-youtube-shorts-the-lufs-14-standard-2ck5
- LoudFix, normalize audio TikTok: https://loudfix.pages.dev/normalize-audio-tiktok
- Trang TikTok Ads Help (chính sách định dạng, không có spec độ to): https://ads.tiktok.com/help/article/tiktok-ads-policy-ad-format-and-functionality
- Production Advice, YouTube loudness và Stats for nerds: https://productionadvice.co.uk/youtube-loudness/ và https://productionadvice.co.uk/stats-for-nerds/ (trang thứ hai trả 401, thông tin lấy từ tóm tắt kết quả tìm kiếm)
- Meterplugs, YouTube đổi mốc về -14 LUFS: https://www.meterplugs.com/blog/2019/09/18/youtube-changes-loudness-reference-to-14-lufs.html

Phần mềm dựng:
- Adobe, Loudness Radar (cũ) và Loudness Meter: https://helpx.adobe.com/premiere-pro/using/old-loudness-radar.html và https://helpx.adobe.com/premiere-pro/using/loudness-meter.html (nội dung lấy qua tóm tắt kết quả tìm kiếm; trang trả 403)
- Adobe Community, Auto-Match không khớp: https://community.adobe.com/t5/premiere-pro-discussions/premiere-pro-does-not-automatch-loudness-correctly/m-p/14748427
- Frame.io Insider, tự động hoá mix Essential Sound: https://blog.frame.io/2024/08/07/insider-tips-premiere-pro-essential-sound-automation/
- Adobe Media Encoder, Automatic loudness correction (không mở được, 403): https://helpx.adobe.com/media-encoder/desktop/encoding-and-exporting/automatic-loudness-correction.html
- CapCut, bài chuẩn hoá âm thanh trong Premiere (nêu -23 LUFS cho CapCut): https://www.capcut.com/resource/normalize-audio-premiere
- CapCut, trang công cụ loudness normalization (không nêu số): https://www.capcut.com/tools/loudness-normalization
- DaVinci Resolve 21 guide về loudness: https://davinciresolve21.com/blog/davinci-resolve-loudness-normalization-lufs
- Diễn đàn Blackmagic, Normalize và Fairlight meter lệch: https://forum.blackmagicdesign.com/viewtopic.php?p=767883 và https://forum.blackmagicdesign.com/viewtopic.php?p=768171

Tỉ lệ giọng/nền:
- Salford, Loudness differences for voice-over-voice (không mở được, tóm tắt qua tìm kiếm): https://salford-repository.worktribe.com/output/1341554/loudness-differences-for-voice-over-voice-audio-in-tv-and-streaming
- Torcoli và cộng sự về loudness difference lời bình/nền khi ducking (AES 2019; chỉ qua tóm tắt tìm kiếm): https://aes2.org/publications/elibrary-page/?id=20995

Nguồn nội bộ:
- `/home/vmiz/opa-software/pro-filmcraft-director/scripts/vendor/ovs_core/scripts/audio_levels.py` và `scripts/vendor/ovs_core/rules.json` (`params.audio`)
- `/home/vmiz/opa-software/pro-filmcraft-director/presets/profile_overrides.json`, `presets/sfx_micro_sync_rules.json`
- `/home/vmiz/opa-software/pro-filmcraft-director/scripts/tools/compile_and_verify.py` (vòng đo-chỉnh: dòng 8596, 8718)
- `/home/vmiz/opa-software/pro-filmcraft-director/references/dviet_19/INDEX.md` và 17 file con
- `/home/vmiz/opa-software/pro-filmcraft-director/references/02_nle_premiere_filmcraft.md`, `03_micro_timing_recipes.md`, `23_dviet_profile_decisions_and_backlog.md`
