#!/usr/bin/env python3
"""Download hanzi-writer-data stroke JSON files for every character in a words file.

Data source: the hanzi-writer-data npm package (stroke data derived from the
Make Me a Hanzi project), fetched per character from the jsDelivr CDN.

Usage:
    python3 fetch_data.py --words words.json --data-dir data/
    python3 fetch_data.py --words words.json --data-dir data/ --force
"""
import argparse, json, os, sys, urllib.parse, urllib.request

CDN = 'https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/{}.json'


def load_words(path):
    """Accept an object {"title", "words", "game_chars"} or a plain word list."""
    with open(path, encoding='utf-8') as f:
        spec = json.load(f)
    if isinstance(spec, list):
        spec = {'words': spec}
    words = spec['words']
    for w in words:
        for key in ('ch', 'py', 'mean'):
            if key not in w:
                raise ValueError(f'word entry missing "{key}": {w!r}')
    return spec


def fetch_char(ch, out_dir, force=False):
    dest = os.path.join(out_dir, ch + '.json')
    if os.path.exists(dest) and not force:
        print(f'{ch}: already present, skip')
        return dest
    url = CDN.format(urllib.parse.quote(ch))
    req = urllib.request.Request(url, headers={'User-Agent': 'hanzi-stroke-courseware/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if len(data.get('strokes', [])) != len(data.get('medians', [])) or not data.get('strokes'):
        raise ValueError(f'{ch}: downloaded data has mismatched strokes and medians')
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f'{ch}: {len(data["strokes"])} strokes -> {dest}')
    return dest


def main():
    ap = argparse.ArgumentParser(description='Download stroke data for a words file.')
    ap.add_argument('--words', required=True, help='words JSON file (see SKILL.md for the format)')
    ap.add_argument('--data-dir', required=True, help='directory to hold one <char>.json per character')
    ap.add_argument('--force', action='store_true', help='re-download files that already exist')
    args = ap.parse_args()

    spec = load_words(args.words)
    os.makedirs(args.data_dir, exist_ok=True)
    chars = list(dict.fromkeys(w['ch'] for w in spec['words']))
    failed = []
    for ch in chars:
        try:
            fetch_char(ch, args.data_dir, args.force)
        except Exception as e:
            failed.append(ch)
            print(f'{ch}: FAILED ({e})', file=sys.stderr)
    print(f'done: {len(chars) - len(failed)}/{len(chars)} characters in {args.data_dir}')
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
