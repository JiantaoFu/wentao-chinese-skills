#!/usr/bin/env python3
"""Assemble the single-file interactive HTML courseware.

Inlines the Hanzi Writer library, the stroke data, the word list and the game
characters into assets/template.html. The output needs no network access.

Usage:
    python3 build_html.py --words words.json --data-dir data/ --out lesson.html
    python3 build_html.py --words words.json --data-dir data/ --out lesson.html --title 笔顺小课堂
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, '..', 'assets', 'template.html')
DEFAULT_LIB = os.path.join(HERE, '..', 'assets', 'hanzi-writer.min.js')


def load_words(path):
    """Accept an object {"title", "words", "game_chars"} or a plain word list."""
    with open(path, encoding='utf-8') as f:
        spec = json.load(f)
    if isinstance(spec, list):
        spec = {'words': spec}
    spec['words'] = [{'ch': w['ch'], 'py': w['py'], 'mean': w['mean']} for w in spec['words']]
    if not spec.get('game_chars'):
        spec['game_chars'] = [w['ch'] for w in spec['words'][:6]]
    return spec


def main():
    ap = argparse.ArgumentParser(description='Build the single-file HTML courseware.')
    ap.add_argument('--words', required=True, help='words JSON file (see SKILL.md for the format)')
    ap.add_argument('--data-dir', required=True, help='directory with one <char>.json per character')
    ap.add_argument('--out', required=True, help='output HTML file')
    ap.add_argument('--title', default=None, help='lesson title, defaults to the title in the words file')
    ap.add_argument('--template', default=DEFAULT_TEMPLATE, help='HTML template path')
    ap.add_argument('--lib', default=DEFAULT_LIB, help='hanzi-writer.min.js path')
    args = ap.parse_args()

    spec = load_words(args.words)
    title = args.title or spec.get('title') or '笔顺小课堂'
    words = spec['words']
    game = [c for c in spec['game_chars']][:6]

    chars = list(dict.fromkeys([w['ch'] for w in words] + game))
    char_data = {}
    for ch in chars:
        path = os.path.join(args.data_dir, ch + '.json')
        if not os.path.exists(path):
            print(f'missing stroke data for {ch}: {path} (run fetch_data.py first)', file=sys.stderr)
            sys.exit(1)
        with open(path, encoding='utf-8') as f:
            char_data[ch] = json.load(f)

    with open(args.template, encoding='utf-8') as f:
        html = f.read()
    with open(args.lib, encoding='utf-8') as f:
        lib = f.read().replace('</script', '<\\/script')

    html = html.replace('/*__LIB__*/', lib)
    html = html.replace('/*__DATA__*/', json.dumps(char_data, ensure_ascii=False))
    html = html.replace('/*__WORDS__*/', json.dumps(words, ensure_ascii=False))
    html = html.replace('/*__GAME__*/', json.dumps(game, ensure_ascii=False))
    html = html.replace('/*__TITLE__*/', '文韬中文 · ' + title)

    # Preset the stage header to the first word so the page is right even before JS runs.
    first = words[0]
    n = len(char_data[first['ch']]['strokes'])
    html = re.sub(r'(<span class="big" id="hChar">).*?(</span>)', r'\g<1>' + first['ch'] + r'\g<2>', html, count=1)
    html = re.sub(r'(<span class="py" id="hPinyin">).*?(</span>)', r'\g<1>' + first['py'] + r'\g<2>', html, count=1)
    html = re.sub(r'(<span class="mean" id="hMean">).*?(</span>)', r'\g<1>' + first['mean'] + r'\g<2>', html, count=1)
    html = re.sub(r'(<span class="strokes" id="hStrokes">).*?(</span>)', r'\g<1>共 ' + str(n) + r' 笔\g<2>', html, count=1)

    leftovers = re.findall(r'/\*__[A-Z]+__\*/', html)
    if leftovers:
        print(f'unreplaced placeholders: {leftovers}', file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'saved {args.out} ({os.path.getsize(args.out) // 1024} KB, '
          f'{len(words)} words, {len(char_data)} data sets, game: {" ".join(game)})')


if __name__ == '__main__':
    main()
