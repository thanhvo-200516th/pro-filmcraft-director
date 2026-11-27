"""Read-only SFX manifest audit; requires ffmpeg and ffprobe for --measure."""
import argparse
import array
from collections import defaultdict
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


def measure(path, source_in=0.0, duration=None):
    """Peak / RMS of the used window [source_in, source_in + duration] (v7.9.3: was the whole file, so a loud head or tail the
    clip never plays read as clipping). duration=None measures to the end of the file."""
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                            '-show_entries', 'stream=channels', '-of', 'json', str(path)],
                           capture_output=True, check=False, timeout=120)
    if probe.returncode:
        raise ValueError(probe.stderr.decode('utf-8', errors='replace'))
    streams = json.loads(probe.stdout).get('streams', [])
    if not streams:
        raise ValueError('No audio stream')
    channels = int(streams[0]['channels'])
    proc = subprocess.Popen(
        ['ffmpeg', '-v', 'error', '-ss', f'{max(0.0, float(source_in)):.6f}',
         *(['-t', f'{float(duration):.6f}'] if duration is not None else []), '-i', str(path), '-map', '0:a:0', '-vn', '-f', 'f32le',
         '-acodec', 'pcm_f32le', '-ar', '48000', 'pipe:1'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peak = power = count = 0
    while True:
        raw = proc.stdout.read(65536)
        if not raw:
            break
        values = array.array('f')
        values.frombytes(raw)
        if sys.byteorder != 'little':
            values.byteswap()
        if values:
            peak = max(peak, max(abs(x) for x in values))
            power += sum(x*x for x in values)
            count += len(values)
    error = proc.stderr.read().decode('utf-8', errors='replace')
    if proc.wait():
        raise ValueError(error.strip())
    db = lambda x: round(20*math.log10(x), 2) if x > 0 else None
    return {'peak_dbfs': db(peak), 'rms_dbfs': db(math.sqrt(power/count) if count else 0),
            'decoded_duration': round(count/(48000*channels), 6), 'clipping': peak >= 1.0,
            'peak_linear': float(peak)}


def audit(events, base, duration=None, do_measure=False):
    takes = defaultdict(list)
    rows = []
    for i, event in enumerate(events):
        start, length = float(event['start']), float(event['duration'])
        if not all(math.isfinite(x) and x >= 0 for x in [start, length]):
            raise ValueError(f'Event {i+1}: start/duration must be finite and nonnegative')
        path = Path(event['path'])
        if not path.is_absolute():
            path = base/path
        source = str(event.get('source') or path).replace('\\', '/').casefold()
        key = (source, round(float(event.get('sourceIn', 0)), 5))
        takes[key].append(i+1)
        row = {'event': i+1, 'start': start, 'path': str(path), 'missing': not path.is_file()}
        if duration is not None and start+length > duration+0.001:
            row['tail_past_video_seconds'] = round(start+length-duration, 6)
        if do_measure and not row['missing']:
            try:
                source_in = float(event.get('sourceIn', 0) or 0)
                row.update(measure(path, source_in, length))
                row['measured_window'] = [round(source_in, 6), round(source_in + length, 6)]
                # v7.7.0: clipping is judged on the post-gain peak (clip gain_db from the manifest, default 0 dB)
                gain_db = float(event.get('gain_db') or 0.0)
                row['gain_db'] = gain_db
                peak_after = row['peak_linear'] * 10 ** (gain_db / 20)
                row['peak_dbfs_after_gain'] = round(20*math.log10(peak_after), 2) if peak_after > 0 else None
                row['clipping'] = peak_after >= 1.0
                if start+row['decoded_duration'] > (duration if duration is not None else math.inf)+0.001:
                    row['decoded_tail_past_video'] = True
            except ValueError as exc:
                row['decode_error'] = str(exc)
        rows.append(row)
    repeats = [{'source': src, 'sourceIn': point, 'events': ids}
               for (src, point), ids in takes.items() if len(ids) > 1]
    return {'events': len(events), 'unique_takes': len(takes), 'repeated_takes': repeats,
            'missing_files': sum(r['missing'] for r in rows), 'files': rows,
            'note': 'Read-only measurements; not a listening review. Low RMS can include silence/tails.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--video-duration', type=float)
    parser.add_argument('--measure', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.measure and not all(shutil.which(x) for x in ['ffmpeg', 'ffprobe']):
        parser.error('ffmpeg and ffprobe are required for --measure')
    if args.video_duration is not None and (not math.isfinite(args.video_duration) or args.video_duration < 0):
        parser.error('--video-duration must be finite and nonnegative')
    try:
        events = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        if not isinstance(events, list):
            raise ValueError('Manifest must be a JSON list')
        result = audit(events, args.manifest.resolve().parent, args.video_duration, args.measure)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output, encoding='utf-8')
        print(json.dumps({k: result[k] for k in ['events', 'unique_takes', 'missing_files', 'repeated_takes']}, ensure_ascii=False))
    else:
        print(output)
    return 2 if any(r['missing'] or r.get('decode_error') for r in result['files']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
