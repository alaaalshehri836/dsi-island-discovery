"""Render the explorer sprite atlas + portraits from the single model."""
import json, os, sys, numpy as np
from PIL import Image
from sdf import render
import character as C

OUT = sys.argv[1]
CW, CH = 40, 54          # cell size
ANCHOR = (20, 50)        # feet point inside a cell
DIRS = 16
ANIMS = [('idle', C.POSES['idle']), ('walk', C.POSES['walk']), ('look', C.POSES['look']),
         ('shade', C.POSES['shade']), ('react', C.POSES['react']), ('jump', C.POSES['jump'])]
LIGHTS = {
    'day': {'key': (-0.55, 0.72, 0.5)},
    # portal glow: blue light coming from in front of the character (+Z in model space)
    'portal': {'key': (-0.4, 0.75, 0.45), 'extra_world': [((0.0, 0.25, 1.0), '#5fd6ff', 1.0, 0.05)],
               'tint': ('#9fc0ff', 0.12)},
}
rows = []
meta = {'cell': [CW, CH], 'anchor': list(ANCHOR), 'dirs': DIRS,
        'dirNote': 'column d = camera orbit yaw d*22.5deg around the character; 0 = camera in front (front view), 4 = camera on character LEFT side (+X) -> character faces screen-left, 12 = faces screen-right, 8 = back view',
        'variants': {}}
row = 0
for vname, L in LIGHTS.items():
    meta['variants'][vname] = {}
    for aname, poses in ANIMS:
        meta['variants'][vname][aname] = {'row': row, 'frames': len(poses)}
        for pose in poses:
            cells = []
            for d in range(DIRS):
                yaw = np.radians(d * 22.5)
                img, _ = render(C.build(pose), C.RAMPS, CW, CH, origin=(0, 23 + (CH / 2 - ANCHOR[1]) * 0 + 0), yaw=yaw, lights=L)
                cells.append(img)
            rows.append(np.concatenate(cells, 1)); row += 1
        print(vname, aname, flush=True)
sheet = np.concatenate(rows, 0)
Image.fromarray(sheet).save(os.path.join(OUT, 'explorer_sheet.png'))
# find feet anchor empirically from the front idle frame
alpha = sheet[:CH, :CW, 3]
ys = np.where(alpha.any(1))[0]
meta['anchor'] = [CW // 2, int(ys.max())]
json.dump(meta, open(os.path.join(OUT, 'explorer_sheet.json'), 'w'), indent=1)

# ---------------------------------------------------------- portraits (close-ups)
PW = PH = 72
blue_soft = {'key': (-0.5, 0.65, 0.55), 'extra': [((0.85, 0.15, 0.5), '#6fd8ff', 0.55, 0.15)]}
blue_full = {'key': (-0.35, 0.6, 0.6), 'extra': [((0.55, 0.2, 0.8), '#7fe0ff', 0.9, 0.0)], 'tint': ('#9fc0ff', 0.1)}
PORTRAITS = [
    ('neutral', dict(detail=2), -25, None),
    ('blink', dict(detail=2, eyeOpen=0), -25, None),
    ('lookR', dict(detail=2, eyeX=1.0, eyeY=0.1, brow=0.3), -25, None),
    ('lookR_glow', dict(detail=2, eyeX=1.0, eyeY=0.1, brow=0.5), -25, blue_soft),
    ('surprised', dict(detail=2, eyeOpen=1.25, brow=1.0, mouth='open', headPitch=4), -18, blue_full),
    ('surprised_blink', dict(detail=2, eyeOpen=0, brow=1.0, mouth='open', headPitch=4), -18, blue_full),
    ('awe', dict(detail=2, eyeOpen=1.1, brow=0.7, mouth='closed', headPitch=5), -18, blue_full),
]
cells = []; pmeta = {'cell': [PW, PH], 'frames': {}}
for i, (name, pose, yaw, L) in enumerate(PORTRAITS):
    img, _ = render(C.build(pose), C.RAMPS, PW, PH, origin=(0, 34.6), scale=5, yaw=np.radians(yaw), lights=L)
    cells.append(img); pmeta['frames'][name] = i
Image.fromarray(np.concatenate(cells, 1)).save(os.path.join(OUT, 'explorer_portraits.png'))
json.dump(pmeta, open(os.path.join(OUT, 'explorer_portraits.json'), 'w'), indent=1)
print('done', sheet.shape)
