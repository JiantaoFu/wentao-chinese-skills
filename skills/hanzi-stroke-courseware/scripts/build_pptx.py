#!/usr/bin/env python3
"""Build the PPTX courseware: title, how-to, one slide per character with its
stroke-order GIF, a matching game slide and an end slide. Requires python-pptx.

Run gen_gifs.py first so every character has a GIF in the gif directory.

Usage:
    python build_pptx.py --words words.json --data-dir data/ --gif-dir gifs/ --out lesson.pptx
"""
import argparse, json, os, sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

INK = RGBColor(0x26, 0x32, 0x38)
PAPER = RGBColor(0xFA, 0xF6, 0xEF)
RED = RGBColor(0xC8, 0x43, 0x2B)
TEAL = RGBColor(0x1F, 0x7A, 0x6D)
GOLD = RGBColor(0xE3, 0xA7, 0x2F)
SUB = RGBColor(0x6B, 0x7A, 0x80)
LINE = RGBColor(0xE7, 0xDF, 0xD2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GHOSTC = RGBColor(0xD8, 0xCF, 0xBB)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
GRID_C = RGBColor(0xD9, 0xCD, 0xB4)
GRID2_C = RGBColor(0xE4, 0xDA, 0xC2)
FRAME_C = RGBColor(0xB9, 0xA9, 0x8F)


def load_words(path):
    """Accept an object {"title", "words", "game_chars"} or a plain word list."""
    with open(path, encoding='utf-8') as f:
        spec = json.load(f)
    if isinstance(spec, list):
        spec = {'words': spec}
    spec['words'] = [(w['ch'], w['py'], w['mean']) for w in spec['words']]
    if not spec.get('game_chars'):
        spec['game_chars'] = [w[0] for w in spec['words'][:6]]
    return spec


def bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def tb(slide, x, y, w, h, text, size, color=INK, bold=False, font='Microsoft YaHei',
       align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, ln in enumerate(text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run(); r.text = ln
        r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color
        r.font.name = font
        rPr = r._r.get_or_add_rPr()
        ea = rPr.find(qn('a:ea'))
        if ea is None:
            ea = rPr.makeelement(qn('a:ea'), {}); rPr.append(ea)
        ea.set('typeface', font)
    return box


def rect(slide, x, y, w, h, fill=None, line_color=None, line_w=0.75):
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.shadow.inherit = False
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line_color is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line_color; sp.line.width = Pt(line_w)
    return sp


def line_shape(slide, x1, y1, x2, y2, color=LINE, w=0.75, dash=None):
    cn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    cn.line.color.rgb = color; cn.line.width = Pt(w)
    cn.shadow.inherit = False
    if dash:
        ln = cn.line._get_or_add_ln()
        ln.append(ln.makeelement(qn('a:prstDash'), {'val': dash}))
    return cn


def practice_grid(slide, x, y, size, ch):
    rect(slide, x, y, size, size, fill=CARD, line_color=FRAME_C, line_w=1.2)
    line_shape(slide, x + size / 2, y + 0.03, x + size / 2, y + size - 0.03, GRID_C, 0.75, 'dash')
    line_shape(slide, x + 0.03, y + size / 2, x + size - 0.03, y + size / 2, GRID_C, 0.75, 'dash')
    line_shape(slide, x + 0.03, y + 0.03, x + size - 0.03, y + size - 0.03, GRID2_C, 0.5, 'dash')
    line_shape(slide, x + size - 0.03, y + 0.03, x + 0.03, y + size - 0.03, GRID2_C, 0.5, 'dash')
    tb(slide, x, y + size * 0.08, size, size * 0.84, ch, size * 52, color=GHOSTC,
       font='KaiTi', align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def shuffled_pinyin(pairs):
    """Rotate the pinyin list so no character sits next to its own pinyin."""
    pys = [py for _ch, py in pairs]
    if len(pys) < 2:
        return pys
    for shift in range(1, len(pys)):
        cand = [pys[(i + shift) % len(pys)] for i in range(len(pys))]
        if all(cand[i] != pys[i] for i in range(len(pys))):
            return cand
    return pys[::-1]


def main():
    ap = argparse.ArgumentParser(description='Build the PPTX courseware.')
    ap.add_argument('--words', required=True, help='words JSON file (see SKILL.md for the format)')
    ap.add_argument('--data-dir', required=True, help='directory with one <char>.json per character')
    ap.add_argument('--gif-dir', required=True, help='directory with one <char>.gif per character')
    ap.add_argument('--out', required=True, help='output PPTX file')
    ap.add_argument('--title', default=None, help='deck title, defaults to the title in the words file')
    args = ap.parse_args()

    spec = load_words(args.words)
    title = args.title or spec.get('title') or '笔顺小课堂'
    words = spec['words']
    total = len(words)
    by_char = {ch: py for ch, py, _m in words}
    game = [(ch, by_char[ch]) for ch in spec['game_chars'][:6] if ch in by_char]
    game_py = shuffled_pinyin(game)

    for ch, _py, _m in words:
        for path in (os.path.join(args.data_dir, ch + '.json'), os.path.join(args.gif_dir, ch + '.gif')):
            if not os.path.exists(path):
                print(f'missing input for {ch}: {path} (run fetch_data.py and gen_gifs.py first)',
                      file=sys.stderr)
                sys.exit(1)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    BLANK = prs.slide_layouts[6]

    # ---------- 1. Title ----------
    s = prs.slides.add_slide(BLANK); bg(s, INK)
    rect(s, 0.9, 1.55, 0.85, 0.07, fill=GOLD)
    tb(s, 0.9, 1.8, 8.5, 0.6, '文韬中文 · Wentao Chinese', 20, color=GOLD, bold=True)
    tb(s, 0.9, 2.5, 11.5, 1.6, title, 66, color=WHITE, bold=True, font='KaiTi')
    tb(s, 0.9, 4.15, 11.5, 0.7, '汉字笔顺动画 · PPT 课件', 26, color=RGBColor(0xB9, 0xC6, 0xCA))
    tb(s, 0.9, 5.6, 11.5, 0.6, f'共 {total} 个字：' + ' '.join(ch for ch, _p, _m in words),
       17, color=RGBColor(0xE8, 0xD9, 0xB0), font='KaiTi')
    tb(s, 0.9, 6.75, 11.5, 0.4, '提示：进入放映模式，笔顺动画会自动循环播放。', 13.5,
       color=RGBColor(0x8E, 0x9E, 0xA3))

    # ---------- 2. How to use ----------
    s = prs.slides.add_slide(BLANK); bg(s, PAPER)
    tb(s, 0.9, 0.55, 11.5, 0.7, '上课这样用', 32, bold=True)
    rect(s, 0.9, 1.32, 0.85, 0.06, fill=RED)
    steps = [
        ('看', '放映这一页，笔顺一笔一画自动播放，先看一遍。'),
        ('读', '跟着动画读出每一笔，慢的地方指着笔画说。'),
        ('写', '在右侧描红格里照着写，或在本子上写。'),
        ('玩', '最后一页有连线游戏，复习拼音。'),
    ]
    for i, (verb, desc) in enumerate(steps):
        x = 0.9 + i * 3.0
        rect(s, x, 1.75, 2.75, 2.5, fill=CARD, line_color=LINE, line_w=1.0)
        tb(s, x + 0.25, 1.95, 2.25, 0.6, verb, 30, color=RED, bold=True, font='KaiTi')
        tb(s, x + 0.25, 2.75, 2.28, 1.4, desc, 14.5, color=INK, spacing=1.25)
    tb(s, 0.9, 4.7, 11.5, 0.5, '本课生字', 19, bold=True)
    for i, (ch, py, _m) in enumerate(words):
        x = 0.9 + (i % 6) * 1.97; y = 5.3 + (i // 6) * 0.92
        rect(s, x, y, 1.72, 0.78, fill=CARD, line_color=LINE, line_w=1.0)
        tb(s, x + 0.08, y + 0.07, 0.7, 0.62, ch, 25, font='KaiTi', align=PP_ALIGN.CENTER)
        tb(s, x + 0.72, y + 0.22, 0.95, 0.4, py, 14, color=SUB)

    # ---------- Character slides ----------
    for idx, (ch, py, mean) in enumerate(words):
        with open(os.path.join(args.data_dir, ch + '.json'), encoding='utf-8') as f:
            n = len(json.load(f)['strokes'])
        s = prs.slides.add_slide(BLANK); bg(s, PAPER)
        tb(s, 0.9, 0.5, 3.4, 0.45, f'第 {idx + 1} 个字 / 共 {total} 个', 14, color=SUB)
        pic = s.shapes.add_picture(os.path.join(args.gif_dir, ch + '.gif'),
                                   Inches(0.9), Inches(1.55), Inches(4.7), Inches(4.7))
        pic.line.color.rgb = FRAME_C; pic.line.width = Pt(1.2)
        tb(s, 0.9, 6.38, 4.7, 0.4, '放映时动画自动循环', 12.5, color=SUB, align=PP_ALIGN.CENTER)
        tb(s, 6.15, 1.5, 2.2, 1.7, ch, 92, font='KaiTi')
        tb(s, 8.15, 1.78, 4.2, 0.75, py, 37, color=RED, bold=True)
        tb(s, 8.15, 2.62, 4.2, 0.55, mean, 19, color=INK)
        tb(s, 8.15, 3.22, 4.2, 0.5, f'共 {n} 笔', 17, color=SUB)
        line_shape(s, 6.15, 4.15, 12.4, 4.15, LINE, 1.2)
        tb(s, 6.15, 4.35, 6.2, 0.45, '描一描：在格子里照着写', 16, bold=True, color=TEAL)
        for k in range(3):
            practice_grid(s, 6.15 + k * 2.12, 4.9, 1.85, ch)
        tb(s, 10.6, 7.02, 1.85, 0.35, '文韬中文 · ' + title, 11, color=SUB, align=PP_ALIGN.RIGHT)
        s.notes_slide.notes_text_frame.text = (
            f'「{ch}」{py}，{mean}，共 {n} 笔。放映时笔顺 GIF 自动循环播放；'
            '先让学生看一遍，再跟着读笔画，最后在描红格里写。')

    # ---------- Game ----------
    s = prs.slides.add_slide(BLANK); bg(s, PAPER)
    tb(s, 0.9, 0.55, 11.5, 0.7, '小游戏 · 连一连', 32, bold=True)
    rect(s, 0.9, 1.32, 0.85, 0.06, fill=RED)
    tb(s, 0.9, 1.55, 11.5, 0.5, '把左边的汉字和右边的拼音连起来。', 17, color=SUB)
    for i, (ch, _py) in enumerate(game):
        y = 2.35 + i * 0.78
        rect(s, 2.2, y, 1.35, 0.64, fill=CARD, line_color=LINE, line_w=1.0)
        tb(s, 2.2, y + 0.05, 1.35, 0.55, ch, 24, font='KaiTi', align=PP_ALIGN.CENTER)
        tb(s, 3.75, y + 0.14, 0.4, 0.4, '·', 22, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
        rect(s, 9.75, y, 1.6, 0.64, fill=CARD, line_color=LINE, line_w=1.0)
        tb(s, 9.75, y + 0.13, 1.6, 0.45, game_py[i], 19, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
        tb(s, 11.55, y + 0.14, 0.4, 0.4, '·', 22, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    s.notes_slide.notes_text_frame.text = (
        '答案：' + '、'.join(f'{ch} {py}' for ch, py in game) + '。右边拼音已打乱顺序。')

    # ---------- End ----------
    s = prs.slides.add_slide(BLANK); bg(s, INK)
    tb(s, 0.9, 2.2, 11.5, 1.1, '写完了，真棒！', 48, color=WHITE, bold=True, font='KaiTi',
       align=PP_ALIGN.CENTER)
    tb(s, 0.9, 3.6, 11.5, 0.6, f'今天的 {total} 个字都学会啦。', 20,
       color=RGBColor(0xB9, 0xC6, 0xCA), align=PP_ALIGN.CENTER)
    tb(s, 0.9, 5.9, 11.5, 0.9,
       '制作说明：笔顺动画由开源数据批量生成（Hanzi Writer / Make Me a Hanzi）。\n'
       '换一张生字表，就能生成新一课的 PPT，不用再手工做动画。',
       13.5, color=RGBColor(0x8E, 0x9E, 0xA3), align=PP_ALIGN.CENTER, spacing=1.4)

    prs.core_properties.title = '文韬中文 · ' + title
    prs.core_properties.author = 'Wentao Chinese'
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    prs.save(args.out)
    print(f'saved {args.out} ({os.path.getsize(args.out) // 1024} KB, '
          f'slides: {total + 4} = 1 title + 1 how-to + {total} characters + 1 game + 1 end)')


if __name__ == '__main__':
    main()
