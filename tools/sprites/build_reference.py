"""Labelled character reference sheet built from the SAME sprite atlas the website uses."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
D = sys.argv[1]
sheet = Image.open(os.path.join(D, 'explorer_sheet.png')).convert('RGBA')
meta = json.load(open(os.path.join(D, 'explorer_sheet.json')))
por = Image.open(os.path.join(D, 'explorer_portraits.png')).convert('RGBA')
pm = json.load(open(os.path.join(D, 'explorer_portraits.json')))
CW, CH = meta['cell']; Z = 4
def cell(var, anim, f, d):
    r = meta['variants'][var][anim]['row'] + f
    return sheet.crop((d * CW, r * CH, (d + 1) * CW, (r + 1) * CH))
rows = [
    ('TURNAROUND (front · 3/4 · side · 3/4 back · back)', [cell('day', 'idle', 0, d) for d in (0, 14, 12, 10, 8, 6, 4, 2)]),
    ('WALK CYCLE - side (8 frames)', [cell('day', 'walk', f, 12) for f in range(8)]),
    ('WALK CYCLE - back / rear-follow (8 frames)', [cell('day', 'walk', f, 8) for f in range(8)]),
    ('IDLE (2) · LOOKING AROUND (4) · SHADING EYES', [cell('day', 'idle', 0, 0), cell('day', 'idle', 1, 0)] + [cell('day', 'look', f, 0) for f in range(4)] + [cell('day', 'shade', 0, 0)]),
    ('STOP & REACT (side, back) · JUMP · PORTAL-LIT VARIANT', [cell('day', 'react', 0, 12), cell('day', 'react', 1, 12), cell('day', 'react', 0, 8), cell('day', 'react', 1, 8), cell('day', 'jump', 0, 12), cell('portal', 'idle', 0, 8), cell('portal', 'react', 0, 9)]),
]
pw = pm['cell'][0]
names = list(pm['frames'].keys())
W = 8 * (CW * Z + 12) + 40
H = 60 + len(rows) * (CH * Z + 46) + pw * 2 + 70
img = Image.new('RGBA', (W, H), (18, 26, 40, 255))
dr = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype('DejaVuSans-Bold.ttf', 18); small = ImageFont.truetype('DejaVuSans.ttf', 14)
except Exception:
    font = small = ImageFont.load_default()
dr.text((20, 16), 'DSI ISLAND - THE EXPLORER - CHARACTER REFERENCE (all views rendered from one model)', fill=(242, 207, 115), font=font)
y = 60
for label, cells in rows:
    dr.text((20, y), label, fill=(160, 200, 220), font=small); y += 22
    for i, c in enumerate(cells):
        x = 20 + i * (CW * Z + 12)
        dr.rectangle((x - 2, y - 2, x + CW * Z + 1, y + CH * Z + 1), fill=(36, 52, 70))
        img.alpha_composite(c.resize((CW * Z, CH * Z), Image.NEAREST), (x, y))
    y += CH * Z + 24
dr.text((20, y), 'CLOSE-UP PORTRAITS: ' + ' · '.join(names), fill=(160, 200, 220), font=small); y += 22
for i, n in enumerate(names):
    c = por.crop((i * pw, 0, (i + 1) * pw, pw)); x = 20 + i * (pw * 2 + 10)
    dr.rectangle((x - 2, y - 2, x + pw * 2 + 1, y + pw * 2 + 1), fill=(36, 52, 70))
    img.alpha_composite(c.resize((pw * 2, pw * 2), Image.NEAREST), (x, y))
img.save(os.path.join(D, 'explorer_reference_sheet.png'))
print('ok', img.size)
