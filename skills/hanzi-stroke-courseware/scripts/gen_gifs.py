#!/usr/bin/env python3
"""Generate stroke-order animated GIFs from hanzi-writer-data JSON files.

The character being written is drawn in red, completed strokes in ink, the
rest as a light ghost, all on a 米字格 grid. The reveal follows the stroke
median, the same technique Hanzi Writer uses. Requires Pillow.

Usage:
    python gen_gifs.py --words words.json --data-dir data/ --out-dir gifs/
"""
import argparse, json, math, os, re, sys
from PIL import Image, ImageChops, ImageDraw

S = 512                      # canvas px
SCALE = S / 1024.0
INK = (38, 50, 56)           # #263238
RED = (200, 67, 43)          # #C8432B
GHOST = (216, 207, 187)      # #D8CFBB
BG = (255, 253, 248)         # #FFFDF8
GRID = (217, 205, 180)
GRID2 = (228, 218, 194)
BORDER = (185, 169, 143)
MASK_R = 36                  # reveal radius in display px


def load_words(path):
    """Accept an object {"title", "words", "game_chars"} or a plain word list."""
    with open(path, encoding='utf-8') as f:
        spec = json.load(f)
    if isinstance(spec, list):
        spec = {'words': spec}
    return spec


def tf(x, y):
    """hanzi-writer coords -> display px (writer uses translate(0,900) scale(1,-1))."""
    return (x * SCALE, (900 - y) * SCALE)


def parse_path(d):
    """Sample an SVG path (M/L/C/Q/Z) into a polygon point list (display coords)."""
    tokens = re.findall(r'[MLCQZ]|-?\d+(?:\.\d+)?', d)
    pts, cur, start, cmd = [], None, None, None
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in 'MLCQZ':
            cmd = t; i += 1
            if cmd == 'Z':
                if start: pts.append(start)
                cur = start
            continue
        if cmd == 'M':
            x, y = float(t), float(tokens[i + 1]); i += 2
            cur = tf(x, y); start = cur; pts.append(cur); cmd = 'L'
        elif cmd == 'L':
            x, y = float(t), float(tokens[i + 1]); i += 2
            cur = tf(x, y); pts.append(cur)
        elif cmd == 'C':
            x1, y1 = float(t), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x3, y3 = float(tokens[i + 4]), float(tokens[i + 5]); i += 6
            p0 = cur
            p1, p2, p3 = tf(x1, y1), tf(x2, y2), tf(x3, y3)
            steps = 14
            for s in range(1, steps + 1):
                u = s / steps; v = 1 - u
                x = v**3 * p0[0] + 3 * v * v * u * p1[0] + 3 * v * u * u * p2[0] + u**3 * p3[0]
                y = v**3 * p0[1] + 3 * v * v * u * p1[1] + 3 * v * u * u * p2[1] + u**3 * p3[1]
                pts.append((x, y))
            cur = p3
        elif cmd == 'Q':
            x1, y1 = float(t), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3]); i += 4
            p0 = cur
            p1, p2 = tf(x1, y1), tf(x2, y2)
            steps = 10
            for s in range(1, steps + 1):
                u = s / steps; v = 1 - u
                x = v * v * p0[0] + 2 * v * u * p1[0] + u * u * p2[0]
                y = v * v * p0[1] + 2 * v * u * p1[1] + u * u * p2[1]
                pts.append((x, y))
            cur = p2
        else:
            i += 1
    return pts


def grid_base():
    img = Image.new('RGB', (S, S), BG)
    dr = ImageDraw.Draw(img)
    def dashed(p1, p2, color, dash=10, gap=7):
        x1, y1 = p1; x2, y2 = p2
        length = math.hypot(x2 - x1, y2 - y1)
        n = int(length // (dash + gap)) + 1
        for k in range(n):
            a = k * (dash + gap) / length; b = min(1.0, a + dash / length)
            dr.line([x1 + (x2 - x1) * a, y1 + (y2 - y1) * a,
                     x1 + (x2 - x1) * b, y1 + (y2 - y1) * b], fill=color, width=2)
    dashed((S / 2, 4), (S / 2, S - 4), GRID)
    dashed((4, S / 2), (S - 4, S / 2), GRID)
    dashed((4, 4), (S - 4, S - 4), GRID2)
    dashed((S - 4, 4), (4, S - 4), GRID2)
    dr.rectangle([1, 1, S - 2, S - 2], outline=BORDER, width=3)
    return img


def median_travel(med, dist):
    """Traveled polyline at arc-length `dist` along the median (display coords)."""
    pts = [tf(x, y) for x, y in med]
    if dist <= 0:
        return pts[:1]
    out = [pts[0]]; acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + seg >= dist:
            r = 0 if seg == 0 else (dist - acc) / seg
            out.append((a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r))
            return out
        out.append(b); acc += seg
    return out


def median_len(med):
    pts = [tf(x, y) for x, y in med]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def make_gif(ch, data_dir, out_dir):
    with open(os.path.join(data_dir, ch + '.json'), encoding='utf-8') as f:
        data = json.load(f)
    polys = [parse_path(p) for p in data['strokes']]
    meds = data['medians']
    ghost = grid_base()
    gd = ImageDraw.Draw(ghost)
    for poly in polys:
        if len(poly) > 2: gd.polygon(poly, fill=GHOST)

    frames, durations = [], []
    frames.append(ghost.copy()); durations.append(650)

    STEP = 16  # px per frame along the median
    done = []
    for poly, med in zip(polys, meds):
        total = median_len(med)
        dists = []
        d = 0.0
        while d < total:
            dists.append(d); d += STEP
        dists.append(total)
        clip = Image.new('L', (S, S), 0)
        cd = ImageDraw.Draw(clip)
        if len(poly) > 2: cd.polygon(poly, fill=255)
        layer = Image.new('RGB', (S, S), RED)
        for d in dists:
            mask = Image.new('L', (S, S), 0)
            md = ImageDraw.Draw(mask)
            trav = median_travel(med, d)
            if len(trav) == 1:
                x, y = trav[0]
                md.ellipse([x - MASK_R, y - MASK_R, x + MASK_R, y + MASK_R], fill=255)
            else:
                md.line(trav, fill=255, width=MASK_R * 2, joint='curve')
                for x, y in (trav[0], trav[-1]):
                    md.ellipse([x - MASK_R, y - MASK_R, x + MASK_R, y + MASK_R], fill=255)
            both = ImageChops.multiply(mask, clip)  # reveal only inside the stroke outline
            frame = ghost.copy()
            fd = ImageDraw.Draw(frame)
            for dp in done:
                if len(dp) > 2: fd.polygon(dp, fill=INK)
            frame.paste(layer, (0, 0), both)
            frames.append(frame); durations.append(45)
        done.append(poly)
        frames.append(frames[-1].copy()); durations.append(170)  # pause between strokes

    final = ghost.copy()
    fdd = ImageDraw.Draw(final)
    for dp in done:
        if len(dp) > 2: fdd.polygon(dp, fill=INK)
    frames.append(final); durations.append(1900)

    out = os.path.join(out_dir, ch + '.gif')
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=False)
    print(f'{ch}: {len(data["strokes"])} strokes, {len(frames)} frames, '
          f'{os.path.getsize(out) // 1024} KB -> {out}')
    return out


def main():
    ap = argparse.ArgumentParser(description='Generate stroke-order GIFs for a words file.')
    ap.add_argument('--words', required=True, help='words JSON file (see SKILL.md for the format)')
    ap.add_argument('--data-dir', required=True, help='directory with one <char>.json per character')
    ap.add_argument('--out-dir', required=True, help='directory to write one <char>.gif per character')
    args = ap.parse_args()

    spec = load_words(args.words)
    os.makedirs(args.out_dir, exist_ok=True)
    chars = list(dict.fromkeys(w['ch'] for w in spec['words']))
    for ch in chars:
        make_gif(ch, args.data_dir, args.out_dir)


if __name__ == '__main__':
    main()
