# 30 — Cầu nối điều khiển FilmCraft (control bridge) thay cho `filmcraft-cli`

> Trạng thái: THIẾT KẾ + BẰNG CHỨNG ĐO (2026-11-25, FilmCraft 0.13.0, Linux). Đã triển khai: `scripts/tools/filmcraft_cli.py` (mục 4), nối vào `compile_and_verify.py` và `env_status.py`. Mọi số đo mục 1-3 lấy từ clip `testsrc` 2 s (640x360, 25 fps) và project `.fcproj` 1 clip, dựng bằng `fc_build_fast.py` trong thư mục tạm. Không dựng / render / sửa project thật nào.

## 1. Nguyên nhân gốc: vì sao không có `filmcraft-cli`

| Sự thật | Bằng chứng |
|---|---|
| Máy chỉ có `~/.local/bin/filmcraft` (v0.13.0, ELF GUI, ~100 MB) và `~/.local/bin/effectcraft`. Không có `filmcraft-cli` ở PATH, `~/.local/bin`, `~/.claude/skills`, `~/.hermes`, `opa-software` | `which`, `find`, `grep -rIl filmcraft-cli` |
| `filmcraft --help` chỉ có: `--control <port>`, `--control-input-only`, `--demo`, `--empty`, `--recover`, `--no-recover`, `--data-dir`, `--graphics`, `--version`. KHÔNG có lệnh con `render`, KHÔNG có `--project`, KHÔNG có `--seconds`, `--out` | `filmcraft --help` |
| `filmcraft-cli` chỉ xuất hiện trong chính skill này, được thêm ở một commit duy nhất (`8084094 feat(v7.3.0)`), không có trong repo nào khác (`video-agent-server`, `ffmpeg-skill`, kho skill Hermes) | `git log -S"filmcraft-cli"`, `grep` toàn `opa-software` |
| Cú pháp mà skill giả định `filmcraft-cli --project X render --seconds S --out P.png` là bịa; không công cụ nào của FilmCraft nhận nó | `compile_and_verify.py` ~L6965 và ~L7603 |

Kết luận: `filmcraft-cli` là một binary tưởng tượng (không phải bị gỡ). Hệ quả (TRƯỚC khi có shim): `_filmcraft_bin_or_none(cli=True)` luôn trả `None` → bước "1-frame render smoke" trong `compile_and_verify.py` (~L6941-6958, ~L7597-7600) luôn bị BỎ QUA ("smoke_skipped": "filmcraft-cli not installed") và `env_status.py:119-122` luôn báo thiếu (optional). Tức là hiện giờ không có phép kiểm "0 media offline" thật nào chạy.

Cách đúng để điều khiển FilmCraft trên Linux: chạy bản GUI ở màn hình ảo (Xvfb) với `--control <port>` và nói chuyện bằng JSON-lines qua socket. Skill ĐÃ vendor sẵn client cho việc này (`craftctl.py`, `fc_export.py`, `fc_build_fast.py`), chỉ chưa ai dùng nó cho bước render 1 khung.

## 2. Giao thức điều khiển (đã xác minh bằng thực nghiệm)

Tài liệu gốc `docs/control-protocol.md` (được `--help` nhắc tới) KHÔNG đi kèm bản cài (đã `find /` không thấy; `strings` binary chỉ có thông báo lỗi). Nguồn thật để suy ra giao thức:

1. `~/.local/share/craft-mcp/craft_mcp.py` (docstring: "answer JSON lines on `--control <port>` (engine.commands, engine.execute, ui.elements)").
2. `scripts/vendor/ovs_core/scripts/apps/craft-handoff/tools/craftctl.py` (client chuẩn, bản sao của `video-agent-server/skills/craft-handoff/tools/craftctl.py`).
3. `video-agent-server/skills/craft-handoff/references/filmcraft-commands.json` (của skill `craft-handoff` / `opa-video-studio`, không nằm trong repo này) (710 lệnh, kèm schema tham số).
4. Thực nghiệm trực tiếp (mục 3).

### 2.1 Khởi động và xác thực

```
DISPLAY=:N FILMCRAFT_CONTROL_TOKEN=<64 ký tự hex> \
  ~/.local/bin/filmcraft --control <port> --data-dir <thư mục riêng> --graphics software --no-recover --empty
```

- Token bắt buộc đúng 64 ký tự hex (`secrets.token_hex(32)`); thiếu/sai → `filmcraft: control server disabled: FILMCRAFT_CONTROL_TOKEN must contain 64 random hex characters`.
- Cổng chỉ bind `127.0.0.1`. Ứng dụng in `filmcraft: control server listening on 127.0.0.1:<port>` ra stdout/stderr khi sẵn sàng.
- Biến môi trường thay cờ: `FILMCRAFT_CONTROL_PORT`, `FILMCRAFT_DATA_DIR`.
- `--data-dir` riêng + `--no-recover` + `--empty` để phiên không đụng auto-save / recovery của cửa sổ FilmCraft người dùng.
- `--graphics software` tuỳ chọn (Xvfb không có GPU); không truyền cũng chạy (tự rơi về llvmpipe, `craftctl` hiện không truyền cờ này).
- Cần một X server. KHÔNG dùng `DISPLAY=:0` (màn hình thật của user). `craftctl` mặc định `:93` (tự bật Xephyr/Xvfb nếu chưa có, đổi bằng `CRAFT_DISPLAY`, `CRAFT_X_SERVER`).

### 2.2 Khung thông điệp

Mỗi dòng một JSON UTF-8, kết thúc `\n`. Không có handshake.

```
-> {"id": 7, "token": "<hex64>", "method": "engine.execute", "params": {"command": "file.open", "params": {"path": "/abs/x.fcproj"}}}
<- {"id": 7, "ok": true,  "result": {...}}
<- {"id": 7, "ok": false, "error": "unknown command `nosuch.cmd`"}
```

- Đáp tuần tự theo thứ tự gửi, có thể gửi dồn nhiều dòng rồi đọc dồn (craftctl `pipeline`: ~24 ms/lệnh dồn, ~45 ms/lệnh từng cái theo ghi chú trong code).
- Token sai → `{"error":"control authentication failed; closing the connection","ok":false}` rồi app ĐÓNG kết nối. Dòng không phải JSON object / thiếu `method` / UTF-8 hỏng cũng đóng kết nối. Có giới hạn số kết nối đồng thời (`too many control connections`).
- Chỉ có 3 phương thức thô (method) hợp lệ: `engine.commands` (liệt kê 710 lệnh + schema), `engine.execute` (chạy một lệnh), `ui.elements` (danh sách phần tử UI + rect). MỌI thứ khác trả `unknown method` — đã thử: `ping`, `status`, `project.inspect`, `state.inspect`, `file.open` gọi trực tiếp đều lỗi; phải bọc trong `engine.execute`.
- Không có `ping`/`status` riêng. "Còn sống" = `engine.execute` với `state.inspect` (~40-60 ms).

### 2.3 Lệnh quan trọng (tất cả qua `engine.execute`, đường dẫn phải tuyệt đối)

| Mục đích | `command` | `params` | Kết quả đã quan sát |
|---|---|---|---|
| Mở project | `file.open` | `{"path": "/abs/x.fcproj"}` | `{"migrated":false,"missingMedia":N,"path":...,"schemaVersion":15}`. `missingMedia` = số media offline; KHÔNG ném lỗi khi N>0 |
| Đọc timeline | `sequence.inspect` | `{}` | `name`, `duration` (ticks), `durationFrames`, `video[]`, `audio[]` (mỗi clip: `clip`, `start`, `end`, `effects`...), `settings.frame_rate{num,den}`, `width`, `height` |
| Trạng thái editor | `state.inspect` | `{}` | dict (`active_sequence`, ...). Dùng làm "status" |
| Trạng thái project | `project.inspect` | `{}` | `activeSequence`, `dirty`, `name`, `path`, `revision`, ... |
| Xuất 1 khung | `file.exportFrame` | `{"path":"/abs/f.png","target":"program","time":<ticks>,"format":"png"}` (`depth` 8/16, `sequence`, `item` tuỳ chọn) | `{"depth":8,"width":640,"height":360,"path":...,"time":<ticks đã làm tròn xuống khung>}` |
| Xuất video nhanh | `export.quick` | `{"path":"/abs/o.mp4","format":"h264","wait":true,"crf":23,"bitrateMode":"crf","loudnessLufs":-14}` | `{"job":1,"path":...,"preset":"Match Source – Adaptive High Bitrate"}`; với `wait:true` thì trả về SAU khi file xong |
| Hàng đợi / job | `jobs.list`, `export.queue.*`, `export.presets.*`, `export.formats` | xem `filmcraft-commands.json` | `jobs.list` → `[]` khi rảnh |
| Thoát | `app.quit` | `{}` | `{"ok":true,"result":null}`, tiến trình thoát mã 0 trong <1 s (không có trong JSON lệnh nhưng chạy được) |

Đơn vị thời gian: ticks, `254016000000` ticks = 1 giây (`craftctl.TICKS_PER_SECOND`). `file.exportFrame` làm tròn `time` XUỐNG ranh giới khung (0,45 s @25fps → 0,44 s; 0,5 s → 0,48 s).

Các client có sẵn (đừng viết lại):
- `craftctl.Craft("filmcraft", workdir)`: tự bật X + app + cổng + token, `cmd()`, `rpc()`, `pipeline()`, `close()` (gửi `app.quit`, rồi `terminate`/`kill` chỉ tiến trình CON của nó).
- `fc_export.export(project, out, fmt, lufs, crf)`: `file.open` + `export.quick wait:true`.
- `fc_build_fast.py SPEC OUT.fcproj --report R --frames N`: build + tự xuất N khung PNG qua `file.exportFrame` (đã chạy: khung 640x360, độ lệch chuẩn xám 83,4, tức không rỗng).
- `scripts/open_in_app.py` (của skill `opa-video-studio`, không nằm trong repo này): mở FilmCraft cho người xem, chọn clip; app chạy tiếp sau khi ngắt điều khiển.

## 3. Bằng chứng kết nối (đo thật)

Môi trường: phiên riêng, Xvfb `:187` 1280x720 tự bật rồi tự tắt (chỉ PID đã bật), cổng ngẫu nhiên, token ngẫu nhiên, `--data-dir` riêng trong scratchpad, `--graphics software --no-recover --empty`. `pgrep -x filmcraft` trước và sau: không có tiến trình FilmCraft nào của user; không kill gì ngoài PID đã khởi động.

Dựng project thử (clip `ffmpeg -f lavfi -i testsrc=duration=2:size=640x360:rate=25` + sine, spec 1 clip, `CRAFT_DISPLAY=:187`):

```
python3 .../craft-handoff/tools/fc_build_fast.py spec.craft.json tiny.fcproj --report tiny.report.json --frames 1
-> "fc_build: OK ..." ; mismatches {} ; frame01.png 640x360 ; tổng 3,5 s (gồm khởi động app + dựng + 1 khung + thoát)
```

Phiên thô (client socket tự viết, không dùng craftctl) — độ trễ từng lệnh:

| Bước | Kết quả | Độ trễ |
|---|---|---|
| Spawn → cổng mở | OK | 0,61 s |
| `ping` / `status` / `nosuch.method` | `unknown method` (đúng như mục 2.2) | 17 / 83 / 121 ms (lệnh đầu chậm hơn) |
| `engine.commands` | 710 lệnh | 58 ms |
| `project.inspect` / `state.inspect` / `file.open` gọi thô | `unknown method` | ~42 ms |
| `engine.execute file.open tiny.fcproj` | `missingMedia:0, schemaVersion:15` | 46 ms |
| `sequence.inspect` | đủ track/clip, `durationFrames:50` | 44 ms |
| `ui.elements` | danh sách phần tử | 49 ms |
| `file.exportFrame` (time 0,5 s) | PNG 640x360, 27 914 B, tồn tại | 59 ms |
| `jobs.list` | `[]` | 43 ms |
| `export.quick wait:true` (2 s H.264) | MP4 340 672 B, ffprobe: h264 640x360 50 khung + aac, 2,0 s | 295 ms |
| `engine.execute nosuch.cmd` | `{"ok":false,"error":"unknown command ..."}` | 41 ms |
| Token sai (kết nối thứ 2) | `control authentication failed; closing the connection` | tức thì |
| `app.quit` | `ok:true`; thoát mã 0 | tổng cả phiên 2,0 s |

Shim nguyên mẫu (đặt ở scratchpad, KHÔNG nằm trong skill) bọc `craftctl`; mỗi lần gọi mở một app mới rồi đóng:

| Lệnh | Kết quả | Thời gian cả lần gọi |
|---|---|---|
| `status` | `filmcraft 0.13.0`, kết nối OK | 1,23 s |
| `open tiny.fcproj` | `missingMedia:0`, sequence `v75 tiny` | 1,55 s |
| `--project tiny.fcproj render --seconds 0.45 --out f.png` (đúng hình dạng lệnh `compile_and_verify.py` đang gọi) | PNG 640x360 | 1,17 s |
| `render --frame 10` | PNG | 1,20 s |
| `export tiny.fcproj o.mp4 --crf 23` | 105 571 B | 1,49 s (`fc_export.py` có sẵn của skill: 2,03 s) |
| 4 lệnh `render` chạy song song (4 app, cùng 1 Xvfb) | 4 PNG | 2,86 s tổng |

Các thất bại / bẫy đã gặp (phải xử lý trong shim):

1. **Media offline KHÔNG làm render thất bại.** Project trỏ tới file không tồn tại: `file.open` trả `missingMedia:1` và `file.exportFrame` vẫn xuất PNG, mã thoát 0. Muốn "chứng minh 0 offline" (đúng ý smoke test portable) thì PHẢI đọc `missingMedia` từ `file.open` và trả mã khác 0 khi >0 (nguyên mẫu: mã 3), trừ khi có `--allow-offline`.
2. **Thời điểm vượt độ dài sequence không bị chặn**: `time=99 s` vẫn trả `ok` và xuất PNG gần như đen (5 337 B). Shim phải kẹp `time` vào `[0, duration - 1 khung]` (lấy `duration` từ `sequence.inspect`) hoặc báo lỗi.
3. **Đường dẫn tương đối** (`"relative.png"`) được chấp nhận và ghi theo cwd của tiến trình app → rác. Shim luôn `Path(...).resolve()`.
4. File không tồn tại → `ok:false`, `error: "<path>: No such file or directory (os error 2)"` (craftctl ném `CraftError`).
5. Không có X server dùng được → `CraftError: no X server on :199 and ... is not installed`.
6. Gọi thô `project.inspect` v.v. không bọc `engine.execute` → `unknown method` (đừng tin ví dụ nào trong tài liệu ngụ ý khác).
7. `fps` KHÔNG nằm trực tiếp trong `sequence.inspect`; nằm ở `settings.frame_rate = {"num":25,"den":1}` (nguyên mẫu dùng `.get("fps",25)` là sai, `render --frame` chỉ đúng nhờ mặc định 25 trùng khớp; bản thật phải đọc `settings.frame_rate`).
8. Có nhiều Xvfb khác (`:92`-`:110`) đang chạy trên máy do phiên khác tạo; `craftctl` mặc định `:93` sẽ dùng chung. Nhiều app dùng chung một X được (đã thử 4) vì mỗi app có cổng, token, `--data-dir` riêng.
9. Trên Xvfb phải chịu cảnh báo `libEGL ... DRI3` và `Software rasterizer detected` — vô hại, khung vẫn đúng.

## 4. Cầu nối đã làm: `scripts/tools/filmcraft_cli.py`

Nguyên tắc: một shim mỏng, chỉ dựa vào `craftctl` đã vendor (không viết lại giao thức), giữ nguyên hình dạng lệnh mà `compile_and_verify.py` đã gọi. Một phiên = một app = một lệnh con (không daemon, không trạng thái): đo ~1,2 s/lệnh `render`, ~0,9 s `status`.

### 4.1 Giao diện dòng lệnh

```
filmcraft_cli.py [--project P.fcproj] [--display :N] [--allow-offline] [--timeout S] <lệnh>

  status                              khởi động một app riêng, hỏi state.inspect; in version (filmcraft --version), display
  open   [P.fcproj]                   file.open + sequence.inspect; in missingMedia và tên sequence
  render (--seconds S | --frame N) --out F.png [--min-std X]
                                      file.open + sequence.inspect + file.exportFrame (target program, PNG)
  export [P.fcproj] OUT.mp4 [--crf N] [--lufs L]
                                      uỷ quyền scripts/tools/fc_export.py (chỉ khi user yêu cầu / draft)
```

- `--project` đứng TRƯỚC lệnh con (khớp `[*cli, "--project", P, "render", "--seconds", S, "--out", PNG]` của `compile_and_verify.py`); `open`/`export` còn nhận project làm đối số vị trí.
- stdout đúng MỘT dòng JSON (`ok`, `elapsed_s`, và `error` + `exit` khi lỗi); tham số sai cũng ra JSON (`ok:false`, `error:"usage: ..."`). stderr chỉ có chẩn đoán. `render` in thêm `project`, `missingMedia` (số nguyên thật), `frame_png`, `fps` (dạng `25/1`), `duration_s`, `ticks`, `time_s`, `clamped`, `width`, `height`, `bytes`, `std`.
- Mã thoát: `0` OK; `1` lỗi điều khiển (`CraftError`, `file.open` không trả `missingMedia` số nguyên, thiếu `settings.frame_rate`, sequence rỗng); `2` sai tham số / không có file project / thiếu `craftctl` vendor / display bị từ chối, và hai trường hợp BỎ QUA có `"skipped": true`: không có binary `filmcraft`, không có X (không có socket display và không có Xvfb/Xephyr); `3` media offline (`missingMedia>0` mà không có `--allow-offline`) hoặc khung rỗng/không phải PNG (hoặc `std <= --min-std`); `124` quá `--timeout` (mặc định 120 s, tính từ lúc app đã lên).

### 4.2 Hành vi đã cài

1. Nạp `craftctl` từ `PFD_OVS_DIR` hoặc `scripts/vendor/ovs_core/scripts/apps/craft-handoff/tools` (như `fc_export.py`, bản vendor đứng đầu `sys.path`). Binary `filmcraft` tìm theo `CRAFT_BIN_DIR`, PATH, `~/.local/bin`; thư mục chứa nó được đặt vào `CRAFT_BIN_DIR` cho `craftctl`.
2. Mỗi lệnh: `Craft("filmcraft", tempdir, args=("--graphics","software","--empty"))` làm context manager (`Craft` tự thêm `--control <cổng ngẫu nhiên>`, `--data-dir <tempdir>/fcdata`, `--no-recover`; token 64 hex ngẫu nhiên chỉ nằm trong môi trường tiến trình con). `tempdir` tên `fcli-*`, xoá ở `finally`. `app.quit` rồi chỉ `terminate`/`kill` `Craft.proc`; SIGTERM/SIGALRM (timeout) cũng chỉ dừng đúng tiến trình con đó. Không dùng `pkill`/`killall`.
3. `file.open` bằng đường dẫn tuyệt đối. `missingMedia` phải là số nguyên, nếu không là lỗi mã 1 (không bao giờ coi là 0). `missingMedia>0` và không `--allow-offline` → `ok:false`, mã 3; VẪN xuất khung để người xem xem (`frame_png` có trong JSON).
4. `render`: `sequence.inspect` → fps từ `settings.frame_rate{num,den}` bằng `Fraction` (KHÔNG có mặc định 25; thiếu là lỗi), `duration` (ticks). `--frame N` → `N*den/num*254016000000`; `--seconds S` → `S*254016000000` (đúng cho `30000/1001`). Kẹp vào `[0, duration - 1 khung]`, ghi `clamped:true`. Gọi `file.exportFrame {"path": tuyệt đối, "target":"program", "time": ticks, "format":"png"}`; kiểm file tồn tại, >0 byte, đúng chữ ký PNG; độ lệch chuẩn xám (`std`) luôn được báo nếu có PIL+numpy, chỉ gây mã 3 khi có `--min-std` (một khung tối thật như fade-in không bị coi là hỏng mặc định).
5. Không bao giờ dùng `DISPLAY` của người dùng. Thứ tự: `--display` > `CRAFT_DISPLAY` > mặc định `craftctl` (`:93`). `:0` bị từ chối (mã 2). Thiếu X → mã 2 + `skipped:true`.
6. `status` KHÔNG gọi `ping` (không tồn tại): `state.inspect` + `filmcraft --version`.
7. Shim `render` dùng cho smoke độc lập, không thay `fc_build_fast.py --frames`. PNG chỉ để QA cấu trúc (llvmpipe), không so pixel với GPU.

### 4.3 Nơi gọi đã sửa

| Vị trí | Đã làm |
|---|---|
| `compile_and_verify.py` `_filmcraft_bin_or_none` | chỉ tìm binary `filmcraft` (thêm `CRAFT_BIN_DIR`); cảnh báo to khi thiếu, không còn tìm `filmcraft-cli` |
| `_filmcraft_cli_cmd()` (mới) | trả `[sys.executable, <filmcraft_cli.py cạnh file>]` hoặc `None` khi thiếu binary `filmcraft` |
| `_filmcraft_render_smoke()` (mới) | chạy `--project P render --seconds S --out F` (không `--allow-offline`), đọc dòng JSON cuối của shim |
| `relativize_and_verify_bundle` (portable smoke) | `offline_media` = `missingMedia` thật (số nguyên); mã 3 hoặc `missingMedia>0` hoặc không có `missingMedia` → `RuntimeError` (cổng FAIL, không hạ thành cảnh báo). Thiếu X/binary → in cảnh báo "SMOKE SKIPPED ... check did NOT run" ra stderr, `smoke_skipped: "skipped: no X/filmcraft ..."`, `offline_media: null` |
| `_run_self_tests` mục 3 | gọi shim; bỏ qua to tiếng khi thiếu X/binary; có thì `missingMedia == 0` và `std > 5` |
| `env_status.py` | `filmcraft` (có `--version`) + mục tuỳ chọn `filmcraft_bridge` (version chạy được, Xvfb hoặc Xephyr, file shim); không bao giờ fatal |

`SKILL.md` do gói khác sửa.

### 4.4 Kiểm thử

- `tests/test_filmcraft_cli.py`: đơn vị với `Craft` giả chỉ có `cmd()` (frame↔ticks `25/1`, `24/1`, `30000/1001`, `60/1`; kẹp; đường dẫn tương đối → tuyệt đối; ánh xạ mã thoát; `missingMedia` → mã 3; token không lọt vào JSON); tích hợp (bỏ qua khi thiếu `~/.local/bin/filmcraft` hoặc X): clip `ffmpeg testsrc` 2 s trong tempdir → `fc_build_fast.py` → `render` → PNG 640x360, `std>5`; biến thể offline → mã 3, `missingMedia:1`; hợp đồng `engine.commands` có `file.open`, `file.exportFrame`, `export.quick`, `sequence.inspect`.
- Lưu ý hợp đồng: `app.quit` KHÔNG nằm trong danh sách 710 lệnh của 0.13.0 nhưng chạy được; test kiểm nó bằng mã thoát 0 của app sau `Craft.close()`.
- `tests/test_stability.py` h6 (bộ phân giải trả shim, thiếu binary → mã 2 JSON gọn) và h7 (cổng portable FAIL khi offline, bỏ qua thì to tiếng).
- Đo thật (Xvfb `:93` dùng chung): `render` 1,2 s, `status` 0,9 s.

## 5. Ràng buộc và rủi ro còn lại

- Giao thức chưa có tài liệu chính thức đi kèm (`docs/control-protocol.md` không được cài). Danh sách lệnh lấy từ `filmcraft-commands.json` (sao chép từ phiên bản trước) — nên chạy `engine.commands` thật khi nâng cấp FilmCraft để so khớp (710 lệnh ở 0.13.0), và có test "contract" (`tests/test_filmcraft_cli.py`) kiểm sự tồn tại của `file.open`, `file.exportFrame`, `export.quick`, `sequence.inspect` (`app.quit` chạy được nhưng không được liệt kê).
- `file.exportFrame` làm tròn xuống khung; chênh lệch ≤ 1 khung so với giây yêu cầu.
- Render trên Xvfb dùng CPU (llvmpipe); khung có thể khác nhẹ so với GPU thật (đặc biệt blur/blend) — dùng cho smoke/QA cấu trúc, không dùng để so pixel với bản xuất trên máy có GPU.
- `export.quick` dùng preset "Match Source – Adaptive High Bitrate" mặc định; dùng `--crf` / `--lufs` để cố định. Theo luật của skill, chỉ xuất MP4 khi user yêu cầu hoặc ở chế độ draft; `compile_and_verify.py` không được tự gọi `export`.
- `Craft.close()` dùng `terminate`/`kill` nếu app không thoát sau `app.quit`; tiến trình mồ côi chỉ xảy ra nếu shim bị `SIGKILL` giữa chừng — thư mục tạm tên `fcli-*` (an toàn để xoá tay nếu có).
- `FILMCRAFT_CONTROL_TOKEN` chỉ nằm trong môi trường của tiến trình con (không ghi ra đĩa, không in ra log); đừng in `Craft.token` trong JSON kết quả.
