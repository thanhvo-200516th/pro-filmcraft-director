# 26 - Font của @__dviet và chuỗi fallback

Cập nhật 2026-11-25. Chi tiết nguồn / giấy phép / hash: `/home/vmiz/Thanh/Media/TNEDIT/01_Font/DViet_Fonts_Research/README.md`.
Font đã cài qua symlink `~/.local/share/fonts/TNEDIT_DViet` (fc-cache đã chạy).

## 1. Điều thật sự biết về font của kênh

Chỉ một video nêu tên font: ep.1 `7677448217667063061` (giây 37-56, tác giả tự đọc và hiện tên):
- Sans: Helvetica, Inter, SF Pro Display
- Serif: Playfair Display, Instrument Serif, IvyPresto Display
- Sáng tạo: Whisper, De Fonte
- Combo chốt: SF Pro Display Regular + Playfair Display Italic + Whisper Regular
- Nơi tìm font: DFVN (dafontvn.com), fonttiengviet.com

Không tìm thấy danh sách font nào do tác giả đăng. Hai video 11/2026 là sans hình học nén ngang, chưa gọi được tên (suy đoán: SF Pro Display / Be Vietnam Pro scaleX 78-85 %).
`SVN-Aaron Script`, `DFVN West West Condensed`, `LigaSFMono` là lựa chọn của preset skill, không phải bằng chứng từ video.

## 2. Vai trò -> font -> fallback (mọi phần tử đều đủ dấu Việt, trừ ghi chú)

| Vai trò | Font ưu tiên | Fallback 1 | Fallback 2 | Cuối |
|---|---|---|---|---|
| Lead sans / phụ đề (hạng chính) | SF Pro Display Regular/Semibold (đã có) | Inter | Be Vietnam Pro | Arimo |
| Hero sans đậm tracking khít | SF Pro Display Bold/Heavy | Be Vietnam Pro ExtraBold | Inter ExtraBold | Arimo Bold |
| Hero sans condensed (CLONE, FLICKER, 11/2026 nén ngang) | SF Pro Display Heavy + scaleX 78-85 % | Barlow Condensed ExtraBold/Black | Barlow Condensed Bold | Be Vietnam Pro + scaleX |
| Serif nghiêng nhấn từ khoá | Playfair Display Italic (Bold Italic tĩnh ở `~/.local/share/fonts/PlayfairDisplay-BoldItalic.ttf`) | Cormorant Garamond Italic | Fraunces Italic | Be Vietnam Pro Italic |
| Hero script thư pháp | Whisper Regular | SVN-Aaron Script | Dancing Script | Playfair Display Italic |
| Nhãn thẻ specimen (De Fonte) | Arimo Bold | Inter | - | - |
| Mono (nếu cần) | LigaSFMono (không có bản tự do) | JetBrains Mono | Be Vietnam Pro Regular | - |

Ghi chú:
- Instrument Serif không dùng cho chữ Việt (thiếu ạ ầ ữ ơ ư ẫ ẳ ỡ). Chỉ hợp để hiện tên font tiếng Anh.
- IvyPresto Display, Helvetica, De Fonte, LigaSFMono, DFVN West West Condensed: không có bản tự do, không tải. Dùng cột fallback.
- SF Pro Display: giấy phép Apple, dùng nội bộ máy này, không chép / phân phối.
- Great Vibes bị bỏ khỏi chuỗi script: `references/04` cấm nó. Fira Code và DejaVu Sans Mono bị bỏ khỏi chuỗi mono có dấu Việt: đo thật: Fira Code thiếu ơ ư ạ ầ ẫ ẳ ỡ ữ, DejaVu Sans Mono thiếu ầ ẫ ẳ; chỉ còn dùng cho chữ ASCII.
- `scripts/env_status.py` (`FONT_FALLBACKS`): DFVN West West Condensed -> Barlow Condensed ExtraBold/Black (không còn Anton / Bebas Neue: `references/04` cấm, không có dấu Việt); thêm mục tuỳ chọn Whisper, Arimo; Instrument Serif báo "English labels only".
- Nguồn máy đọc được: `presets/dviet_style_tokens.json` -> `fonts` (thêm, không đổi `font_roles`): vai trò -> `primary` -> `fallbacks` có thứ tự, mỗi mục có `provenance`. `creator-stated` chỉ cho SF Pro Display Regular, Playfair Display Italic, Whisper Regular; `skill-preset, no evidence` cho SVN-Aaron Script, DFVN West West Condensed, LigaSFMono (và mọi suy đoán về độ đậm / độ nén); `free stand-in` cho Inter (thay SF Pro), Barlow Condensed (thay chữ nén), JetBrains Mono (thay LigaSFMono), Arimo (thay Helvetica). `font_roles` vẫn là thứ `dviet_text.py` đọc hôm nay.
- Không chép font vào repo, không phân phối SF Pro.

## 3. Font mới thêm lần này (đều SIL OFL 1.1, đã kiểm tra đủ 90/90 ký tự Việt mở rộng)

- Whisper Regular
- Arimo (Regular + Italic, variable wght)
- Barlow Condensed Regular, Medium, SemiBold, ExtraBold, Black (Bold đã có sẵn)

## 4. Kiểm tra nhanh

`python3 tests/test_fonts_vi.py`: với mọi vai trò `vietnamese: true`, mỗi font đã cài trong chuỗi (qua `fc-match`) phải có đủ ạ ầ ữ ơ ư ẫ ẳ ỡ đ; font mà `fc-match` không khớp được tên họ thì SKIP (máy này: DFVN West West Condensed, SVN-Aaron Script, LigaSFMono), font đã cài mà thiếu glyph thì FAIL. Vai trò `vietnamese: false` (nhãn specimen, Instrument Serif) được phép thiếu.

```bash
fc-list | grep TNEDIT_DViet | sed 's/:style.*//' | sort -u
fc-match "Whisper"; fc-match "Barlow Condensed:weight=extrabold"
```
