#!/usr/bin/env python3
"""Generate Eastward SVG touch icons and bake them into dm/gfx/nvn/overlay/ovl_font.h.

Uses a 16-cell horizontal R8 atlas (2048x128, 128x128 per cell) compatible with ovl.frag's
smoothstep(0.35, 0.65, s) edge sharpening.
"""
import math
import os
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, 'eastward_icons')
OUT_H = os.path.join(HERE, 'ovl_font.h')

CELL = 128
SS = 4  # 512x512 supersampling per cell
W_SS = CELL * SS
COLS = 16


def q_bezier(p0, p1, p2, steps=20):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def svg_arc_points(cx, cy, rx, ry, deg0, deg1, steps=28):
    pts = []
    for i in range(steps + 1):
        a = math.radians(deg0 + (deg1 - deg0) * (i / steps))
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def render_svg_file(svg_path):
    """Render clean SVG icon primitives (128x128 viewBox) into a 128x128 L-mode image."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    im = Image.new('L', (W_SS, W_SS), 0)
    dr = ImageDraw.Draw(im)

    def sc(v):
        return float(v) * SS

    def color_val(s):
        if not s or s == 'none':
            return None
        if s == '#000' or s == '#000000' or s == 'black':
            return 0
        return 255

    def draw_elem(el):
        tag = el.tag.split('}')[-1]
        fill = color_val(el.attrib.get('fill', '#fff'))
        stroke = color_val(el.attrib.get('stroke', 'none'))
        sw = max(1, int(round(sc(el.attrib.get('stroke-width', '0')))))

        if tag == 'circle':
            cx, cy, r = sc(el.attrib['cx']), sc(el.attrib['cy']), sc(el.attrib['r'])
            box = [cx - r, cy - r, cx + r, cy + r]
            if fill is not None:
                dr.ellipse(box, fill=fill)
            if stroke is not None and sw > 0:
                dr.ellipse(box, outline=stroke, width=sw)
        elif tag == 'ellipse':
            cx, cy = sc(el.attrib['cx']), sc(el.attrib['cy'])
            rx, ry = sc(el.attrib['rx']), sc(el.attrib['ry'])
            box = [cx - rx, cy - ry, cx + rx, cy + ry]
            if fill is not None:
                dr.ellipse(box, fill=fill)
            if stroke is not None and sw > 0:
                dr.ellipse(box, outline=stroke, width=sw)
        elif tag == 'rect':
            x, y = sc(el.attrib.get('x', 0)), sc(el.attrib.get('y', 0))
            w, h = sc(el.attrib['width']), sc(el.attrib['height'])
            rx = sc(el.attrib.get('rx', 0))
            box = [x, y, x + w, y + h]
            if rx > 0:
                if fill is not None:
                    dr.rounded_rectangle(box, radius=rx, fill=fill)
                if stroke is not None and sw > 0:
                    dr.rounded_rectangle(box, radius=rx, outline=stroke, width=sw)
            else:
                if fill is not None:
                    dr.rectangle(box, fill=fill)
                if stroke is not None and sw > 0:
                    dr.rectangle(box, outline=stroke, width=sw)
        elif tag == 'line':
            x1, y1 = sc(el.attrib['x1']), sc(el.attrib['y1'])
            x2, y2 = sc(el.attrib['x2']), sc(el.attrib['y2'])
            c = stroke if stroke is not None else 255
            dr.line([(x1, y1), (x2, y2)], fill=c, width=sw)
            r = sw * 0.5
            if el.attrib.get('stroke-linecap') == 'round':
                dr.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=c)
                dr.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=c)
        elif tag in ('polygon', 'polyline'):
            raw = el.attrib['points'].replace(',', ' ').split()
            pts = [(sc(raw[i]), sc(raw[i + 1])) for i in range(0, len(raw), 2)]
            if tag == 'polygon':
                if fill is not None:
                    dr.polygon(pts, fill=fill)
                if stroke is not None and sw > 0:
                    dr.line(pts + [pts[0]], fill=stroke, width=sw, joint='curve')
            else:
                c = stroke if stroke is not None else 255
                dr.line(pts, fill=c, width=sw, joint='curve')
                if el.attrib.get('stroke-linecap') == 'round':
                    r = sw * 0.5
                    for px, py in (pts[0], pts[-1]):
                        dr.ellipse([px - r, py - r, px + r, py + r], fill=c)

    for child in root:
        draw_elem(child)

    small = im.resize((CELL, CELL), Image.Resampling.LANCZOS)
    # Soft 0.7px edge ramp centered cleanly around 0.5 for ovl.frag smoothstep(0.35, 0.65, s)
    return small.filter(ImageFilter.GaussianBlur(radius=0.65))


def render_label_text(txt):
    im = Image.new('L', (W_SS, W_SS), 0)
    dr = ImageDraw.Draw(im)
    font = None
    for cand in ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.isfile(cand):
            font = ImageFont.truetype(cand, int(CELL * 0.44 * SS))
            break
    if font is None:
        font = ImageFont.load_default()
    bbox = dr.textbbox((0, 0), txt, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    dr.text(((W_SS - tw) / 2 - bbox[0], (W_SS - th) / 2 - bbox[1]), txt, fill=255, font=font)
    small = im.resize((CELL, CELL), Image.Resampling.LANCZOS)
    return small.filter(ImageFilter.GaussianBlur(radius=0.6))


def arc_poly(cx, cy, r, deg0, deg1, steps=24):
    return ' '.join(f'{cx + r * math.cos(math.radians(deg0 + (deg1 - deg0) * i / steps)):.1f},{cy + r * math.sin(math.radians(deg0 + (deg1 - deg0) * i / steps)):.1f}'
                    for i in range(steps + 1))


def build_svg_sources():
    os.makedirs(ICON_DIR, exist_ok=True)
    # 0: A - Interact / Hand
    svgs = {}
    svgs[0] = ('0_hand_interact.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect x="40" y="54" width="46" height="44" rx="18" fill="#fff"/>
  <rect x="57" y="18" width="12" height="44" rx="6" fill="#fff"/>
  <rect x="42" y="25" width="12" height="38" rx="6" fill="#fff"/>
  <rect x="72" y="24" width="12" height="40" rx="6" fill="#fff"/>
  <rect x="86" y="37" width="11" height="34" rx="5.5" fill="#fff"/>
  <line x1="25" y1="62" x2="46" y2="76" stroke="#fff" stroke-width="12" stroke-linecap="round"/>
  <circle cx="63" cy="76" r="7" fill="#000"/>
</svg>''')

    # 1: B - Group / Ungroup (two side-by-side characters: John & Sam)
    svgs[1] = ('1_group_chars.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <circle cx="44" cy="36" r="14" fill="#fff"/>
  <rect x="22" y="54" width="44" height="42" rx="16" fill="#fff"/>
  <circle cx="84" cy="44" r="12" fill="#fff"/>
  <rect x="64" y="60" width="40" height="36" rx="14" fill="#fff"/>
  <rect x="56" y="58" width="12" height="38" rx="4" fill="#000"/>
  <circle cx="84" cy="44" r="14" fill="none" stroke="#000" stroke-width="4"/>
  <circle cx="84" cy="44" r="11" fill="#fff"/>
</svg>''')

    # 2: X - Sam's Energy Ability (bright 4-point sparkle + inner ring)
    pts_star = []
    for i in range(8):
        ang = math.radians(i * 45 - 90)
        rad = 46 if i % 2 == 0 else 17
        pts_star.append(f'{64 + rad * math.cos(ang):.1f},{64 + rad * math.sin(ang):.1f}')
    svgs[2] = ('2_ability_star.svg', f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <polygon points="{' '.join(pts_star)}" fill="#fff"/>
  <circle cx="96" cy="32" r="7" fill="#fff"/>
  <circle cx="32" cy="96" r="5.5" fill="#fff"/>
  <circle cx="64" cy="64" r="10" fill="#000"/>
  <circle cx="64" cy="64" r="5" fill="#fff"/>
</svg>''')

    # 3: Y - Attack (John's Frying Pan!)
    svgs[3] = ('3_attack_pan.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <line x1="65" y1="62" x2="96" y2="93" stroke="#fff" stroke-width="14" stroke-linecap="round"/>
  <circle cx="51" cy="49" r="28" fill="#fff"/>
  <circle cx="51" cy="49" r="18" fill="#000"/>
  <circle cx="51" cy="49" r="13" fill="#fff"/>
  <circle cx="91" cy="88" r="4" fill="#000"/>
  <polygon points="82,22 89,34 99,27 91,39 101,46 87,46 80,35" fill="#fff"/>
</svg>''')

    # 4: L - Backpack / Inventory
    svgs[4] = ('4_bag_inventory.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect x="48" y="22" width="32" height="18" rx="9" fill="none" stroke="#fff" stroke-width="7"/>
  <rect x="31" y="36" width="66" height="66" rx="18" fill="#fff"/>
  <rect x="37" y="64" width="54" height="7" rx="3.5" fill="#000"/>
  <rect x="57" y="58" width="14" height="17" rx="4" fill="#000"/>
  <rect x="60" y="61" width="8" height="11" rx="2" fill="#fff"/>
  <rect x="43" y="80" width="42" height="12" rx="4" fill="#000"/>
</svg>''')

    # 5: R - Switch Weapon (dual circular swap arrows + sword/wrench emblem)
    a_top = arc_poly(64, 64, 34, 200, 345)
    a_bot = arc_poly(64, 64, 34, 20, 165)
    svgs[5] = ('5_swap_weapon.svg', f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <polyline points="{a_top}" fill="none" stroke="#fff" stroke-width="9.5" stroke-linecap="round"/>
  <polygon points="103,56 83,52 96,35" fill="#fff"/>
  <polyline points="{a_bot}" fill="none" stroke="#fff" stroke-width="9.5" stroke-linecap="round"/>
  <polygon points="25,72 45,76 32,93" fill="#fff"/>
  <line x1="51" y1="77" x2="77" y2="51" stroke="#fff" stroke-width="10" stroke-linecap="round"/>
  <line x1="50" y1="66" x2="62" y2="78" stroke="#fff" stroke-width="7" stroke-linecap="round"/>
</svg>''')

    # 7: ZR - Swap Character (John <-> Sam opposing arrows + two heads)
    svgs[7] = ('7_swap_char.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <circle cx="38" cy="34" r="10.5" fill="#fff"/>
  <rect x="24" y="48" width="28" height="16" rx="7.5" fill="#fff"/>
  <circle cx="90" cy="82" r="10.5" fill="#fff"/>
  <rect x="76" y="96" width="28" height="16" rx="7.5" fill="#fff"/>
  <line x1="60" y1="34" x2="92" y2="34" stroke="#fff" stroke-width="8.5" stroke-linecap="round"/>
  <polygon points="104,34 85,22 85,46" fill="#fff"/>
  <line x1="68" y1="84" x2="36" y2="84" stroke="#fff" stroke-width="8.5" stroke-linecap="round"/>
  <polygon points="24,84 43,72 43,96" fill="#fff"/>
</svg>''')

    # 8: + - Pause / Main Menu
    svgs[8] = ('8_menu_pause.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect x="38" y="30" width="18" height="68" rx="9" fill="#fff"/>
  <rect x="72" y="30" width="18" height="68" rx="9" fill="#fff"/>
</svg>''')

    # 9: - - Map (folded trifold map + location marker)
    svgs[9] = ('9_map_pin.svg', '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <polygon points="24,40 50,29 78,40 104,29 104,90 78,99 50,88 24,97" fill="#fff"/>
  <line x1="50" y1="32" x2="50" y2="86" stroke="#000" stroke-width="5.5"/>
  <line x1="78" y1="42" x2="78" y2="95" stroke="#000" stroke-width="5.5"/>
  <circle cx="64" cy="54" r="11" fill="#000"/>
  <circle cx="64" cy="54" r="4.5" fill="#fff"/>
</svg>''')

    rendered = {}
    for idx, (fname, xml) in svgs.items():
        p = os.path.join(ICON_DIR, fname)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(xml + '\n')
        rendered[idx] = render_svg_file(p)

    # Keep crisp text labels for fallback/optional slots (ZL, L3, R3)
    rendered[6] = render_label_text('ZL')
    rendered[10] = render_label_text('L3')
    rendered[11] = render_label_text('R3')
    return rendered


def main():
    cells = build_svg_sources()
    atlas = Image.new('L', (CELL * COLS, CELL), 0)
    for idx, cell in cells.items():
        atlas.paste(cell, (idx * CELL, 0))

    raw = atlas.tobytes()
    with open(OUT_H, 'w', encoding='utf-8') as f:
        f.write('// Generated by gen_ovl_font.py from eastward_icons/*.svg: 16 cells of 128x128, R8, top row first\n')
        f.write(f'static const unsigned ovl_font_w = {CELL * COLS}, ovl_font_h = {CELL};\n')
        f.write('static const unsigned char ovl_font[] = {\n')
        stride = 512
        for off in range(0, len(raw), stride):
            chunk = raw[off:off + stride]
            f.write(','.join(str(b) for b in chunk))
            f.write(',\n' if off + stride < len(raw) else '\n')
        f.write('};\n')

    # Save visual preview grid for inspection
    prev = Image.new('RGB', (CELL * 6, CELL * 2), (24, 24, 28))
    for i in range(12):
        r, c = divmod(i, 6)
        tile = Image.new('RGB', (CELL, CELL), (42, 36, 20) if i == 3 else (32, 34, 42))
        dr = ImageDraw.Draw(tile)
        dr.ellipse([6, 6, CELL - 6, CELL - 6], outline=(245, 196, 40), width=3)
        white = Image.new('RGB', (CELL, CELL), (255, 255, 255))
        tile.paste(white, (0, 0), cells[i])
        prev.paste(tile, (c * CELL, r * CELL))
    prev_path = r'C:\Users\HYPE AMD\.gemini\antigravity\brain\fadce4ab-c23b-4f23-a365-db6cf0b7448e\scratch\eastward_ovl_preview.png'
    os.makedirs(os.path.dirname(prev_path), exist_ok=True)
    prev.save(prev_path)
    print(f'Wrote {OUT_H} ({len(raw)} bytes) and preview {prev_path}')


if __name__ == '__main__':
    main()
