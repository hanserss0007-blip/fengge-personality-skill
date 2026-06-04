#!/usr/bin/env python3
"""Batch subtitle download with rate limiting."""
import json, subprocess, time, glob, os, sys

COOKIE_FILE = 'bilibili_cookies.txt'
SUBTITLE_DIR = 'data_raw/subtitles'
DELAY = 5  # seconds between requests

# Load pending
# Default to full batch if no arg
batch_file = sys.argv[1] if len(sys.argv) > 1 else 'data_raw/metadata/batch_all.json'
with open(batch_file, 'r', encoding='utf-8') as f:
    targets = json.load(f)

print(f'Downloading subtitles for {len(targets)} videos...')
print(f'Delay: {DELAY}s between requests\n')

success = 0
for i, v in enumerate(targets):
    bvid = v['bvid']
    title = v.get('title', '')[:50]
    print(f'[{i+1}/{len(targets)}] {bvid} {title}')

    try:
        r = subprocess.run([
            'yt-dlp', '--cookies', COOKIE_FILE,
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '--write-subs', '--write-auto-subs',
            '--sub-langs', 'zh-Hans,zh,ai-zh',
            '--skip-download',
            '-o', f'{SUBTITLE_DIR}/{bvid}_%(section_number)03d',
            f'https://www.bilibili.com/video/{bvid}'
        ], capture_output=True, text=True, timeout=60)

        files = glob.glob(f'{SUBTITLE_DIR}/{bvid}*.srt')
        if files:
            total_size = sum(os.path.getsize(f) for f in files)
            print(f'  OK: {len(files)} files, {total_size//1024}KB')
            success += 1
        else:
            # Check if it's a playlist with no subs
            if 'no subtitles' in r.stderr.lower() or 'there are no subtitles' in r.stderr.lower():
                print(f'  No subs available')
            else:
                print(f'  No subs (may need login or not available)')
    except subprocess.TimeoutExpired:
        print(f'  Timeout')
    except Exception as e:
        print(f'  Error: {e}')

    time.sleep(DELAY)

# Summary
existing = set()
for f in glob.glob(f'{SUBTITLE_DIR}/*.srt'):
    existing.add(os.path.basename(f).split('_')[0])

print(f'\nDone: {success}/{len(targets)} new with subtitles')
print(f'Total videos with subs: {len(existing)}')
