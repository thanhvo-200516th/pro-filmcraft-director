# 21 — `.craft.json` tối thiểu chạy được (v7.4.0)

Spec nhỏ nhất đã **chạy thật** qua `compile_and_verify.py --tier fast` (Gate 1 → Gate 4: `clips=7`, `mismatches={}`) và qua `fc_build.validate`.
Gồm: V1 (A-roll) + VOICE + SFX + BGM + 1 clip chữ. Các quy ước dưới đây **không có trong tài liệu gốc** của `fc_build.py` — thiếu một cái là lỗi khó hiểu.

## 1. Quy ước bắt buộc

| # | Quy ước | Nếu sai |
|---|---|---|
| 1 | Có track VOICE ⇒ clip V1 chứa tiếng nhúng phải đặt `"audio": false` | `fc_build.py:351 KeyError: <clip id>` (`self.info[i]`, clip âm thanh liên kết của V1 không tra được) |
| 2 | Track giọng tên có `giọng` / `voice` / `vo` / `a1` (vd `A1 · Giọng (VOICE)`) | `audio_levels.py` không phân loại được → dừng, báo tên clip |
| 3 | Track SFX tên có `SFX`; track nhạc nền tên có `nhạc` / `music` / `bgm` | bị xếp nhầm vai trò, sai mức độ to |
| 4 | Track âm thanh chỉ nhận file **chỉ có tiếng** (`.wav`/`.mp3`…), không nhận `.mp4` | `SpecError: ... cannot go on track A1` ⇒ tách giọng ra `.wav` stereo 48 kHz trước |
| 5 | Mọi `src` là **đường dẫn tuyệt đối** tới file có thật (trừ `AUTO:<từ khoá>` cho SFX) | `needs an absolute path` / `file not found` |
| 6 | Các clip cùng một track không được chồng thời gian (`at + dur <= at` kế tiếp) | `clip N overlaps clip M` |
| 7 | Không đặt khoá lạ ở clip / top-level (trừ `meta`, compiler tự gỡ) | liệt vào `unsupported`, không mất im lặng nhưng gây nhiễu |

## 2. Ví dụ đầy đủ (thay `{DIR}` bằng thư mục thật)

```json
{
  "name": "demo_minimal",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "duration": 6.0,
  "tracks": [
    {
      "type": "video",
      "name": "V1 · A-roll",
      "clips": [
        {"name": "A-roll", "src": "{DIR}/a-roll-1.mp4", "in": 0.0, "at": 0.0, "dur": 6.0, "audio": false}
      ]
    },
    {
      "type": "text",
      "name": "V2 · Text",
      "clips": [
        {"name": "Hero chữ", "text": "xin chào", "font": "Be Vietnam Pro", "size": 78,
         "color": "#FAFAFA", "position": [540.0, 354.4], "at": 0.4, "dur": 0.8}
      ]
    },
    {
      "type": "audio",
      "name": "A1 · Giọng (VOICE)",
      "clips": [
        {"name": "VO · giọng", "src": "{DIR}/voice.wav", "in": 0.0, "at": 0.0, "dur": 6.0}
      ]
    },
    {
      "type": "audio",
      "name": "A2 · SFX",
      "clips": [
        {"name": "SFX · pop 1", "src": "{DIR}/sfx/pop_hit.wav", "at": 0.4, "dur": 0.4}
      ]
    },
    {
      "type": "audio",
      "name": "A3 · Nhạc nền (BGM)",
      "clips": [
        {"name": "BGM · nhạc nền", "src": "{DIR}/bgm_music.wav", "in": 0.0, "at": 0.0, "dur": 6.0}
      ]
    }
  ]
}
```

Biên dịch (mặc định **không** xuất `.mp4`):

```bash
~/.venvs/video-skills/bin/python3 scripts/tools/compile_and_verify.py \
  --spec demo.craft.json --out out/demo.fcproj --work work --tier fast
```

> Gate 6 (độ to khép kín) chỉ hội tụ trên **giọng nói thật**. Với tín hiệu thử (sine, nhạc thuần, im lặng) nó báo
> `master_lufs` / `bgm_below_voice` FAIL — đó là hành vi đúng, không phải lỗi spec.

## 3. SFX tự chọn: `AUTO:<từ khoá>` + `--auto-sfx-dir`

Thay `src` bằng `AUTO:<từ khoá>`; compiler chọn file trong thư mục `--auto-sfx-dir` (tìm đệ quy, theo tên thư mục + tên file chứa từ khoá):

```json
{"name": "SFX · pop 1", "src": "AUTO:pop", "at": 0.4, "dur": 0.6}
```

```bash
... compile_and_verify.py --spec demo.craft.json --out out/demo.fcproj --work work --auto-sfx-dir /duong/dan/sfx
```

- Mỗi clip `AUTO:` cần **một file khác nhau** (khử trùng MD5, file ≥ 0,10 s, có tín hiệu). Hai clip `AUTO:pop` cần ≥ 2 file `pop*` khác nội dung, nếu không: `Auto-SFX allocator exhausted unique MD5-deduplicated SFX files`.
- Không truyền `--auto-sfx-dir` mà thư mục `assets/sfx/` cạnh spec cũng không có ⇒ lỗi rõ ràng, không đoán.
- Nhiều từ khoá: `AUTO:pop,click` (thử lần lượt). Không file nào khớp từ khoá ⇒ lấy file bất kỳ còn trống (nên đặt tên/thư mục SFX theo từ khoá để khỏi trúng ngẫu nhiên). `AUTO:any` = bỏ qua từ khoá.

## 4. Sinh spec từ plan động học: `spec_from_plan.py`

```bash
~/.venvs/video-skills/bin/python3 scripts/tools/spec_from_plan.py \
  --plan plan.json --words words_tl.json --media-dir DIR --out X.craft.json [--auto-sfx pop] [--no-voice-track]
```

- `plan.json` = kết quả `plan_dviet_kinetic_beat_schedule` (cần `craft_clips`); `words_tl.json` = đầu ra `probe_and_align.py`.
- Tự áp quy ước #1–#4: tách giọng từ A-roll ra `X_voice.wav`, đặt `audio:false` cho V1, đặt tên track đúng, thêm BGM nếu `DIR` có file tên `bgm|music|nhạc`.
- Plate `.mov` không tồn tại trên đĩa ⇒ rơi về clip chữ gốc (`main_text`), có cảnh báo.
- `--auto-sfx pop` thêm một clip `AUTO:pop` cho mỗi beat (nhớ truyền `--auto-sfx-dir` khi biên dịch).

## 5. Xuất MP4 (chỉ khi người dùng yêu cầu hoặc chế độ draft)

```bash
~/.venvs/video-skills/bin/python3 scripts/tools/fc_export.py out/demo.fcproj out/demo.mp4 --crf 20
```

Compile **không bao giờ** tự xuất MP4. Mốc đo: ~49 s cho clip 6 s.
