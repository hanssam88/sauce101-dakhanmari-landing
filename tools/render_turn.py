#!/usr/bin/env python3
"""병 베이스 + 라벨 전개도 → 원통 투영 회전 프레임 (360° 턴테이블).

병 렌더(라벨 전개도 → 원통 투영) 방식을 그대로 쓰되,
라벨 x 좌표를 병 둘레 방향으로 감아(wrap) 임의 각도의 프레임을 만든다.
생성 모델을 쓰지 않는다 — 라벨 픽셀은 승인 아트워크 원본에서만 가져오므로 문구·서체가 변하지 않는다.

  render_turn.py --base dak.png --zone dak-zone.json --label 라벨.png --out-dir frames/ [--frames 72]

산출: <out-dir>/turn-000.png … (RGBA, 베이스와 같은 캔버스) · <out-dir>/turn.json (크롭 박스·각도 메타)
회전 방향: 병 정면 표면이 왼쪽으로 흐른다(라벨의 오른쪽 면이 차례로 정면에 온다).
"""
import argparse, json, math, pathlib
import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True)
ap.add_argument('--zone', required=True)
ap.add_argument('--label', required=True)
ap.add_argument('--out-dir', required=True)
ap.add_argument('--frames', type=int, default=72)
ap.add_argument('--front-cx', type=float, default=945.0, help='0° 프레임에서 정면에 오는 라벨 x')
ap.add_argument('--label-size', default='1871x965')
ap.add_argument('--label-w-mm', type=float, default=165.0)
ap.add_argument('--ambient', type=float, default=0.58)
ap.add_argument('--spec', type=float, default=0.42)
ap.add_argument('--pad', type=int, default=24, help='크롭 여백(px)')
a = ap.parse_args()

LW0, LH0 = (int(v) for v in a.label_size.lower().split('x'))
label = Image.open(a.label).convert('RGB')
if label.size != (LW0, LH0):
    raise SystemExit(f'라벨 규격 불일치: {label.size} (요구 {LW0}×{LH0})')
lab = np.array(label).astype(np.float32)
LH, LW, _ = lab.shape

base = Image.open(a.base).convert('RGBA')
B = np.array(base).astype(np.float32)
alpha = B[:, :, 3] / 255.0
H, W, _ = B.shape

z = json.loads(pathlib.Path(a.zone).read_text())
lt, lb = z['label_top'], z['label_bot']
px_per_mm = z['px_per_mm']
lab_px_per_mm = LW / a.label_w_mm

# 병 실제 둘레(label px). 라벨이 둘레보다 짧으면 그 차이가 이음매 틈이 된다.
circ_px = math.pi * z['diameter_mm'] * lab_px_per_mm

# 베이스 사진의 저주파 밝기 → 하이라이트 띠 (정면 렌더와 동일 · 광원 고정)
lum = B[:, :, :3].mean(axis=2)
lum_lp = np.array(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9))).astype(np.float32)
zone_vals = lum_lp[lt:lb + 1][alpha[lt:lb + 1] > 0.5]
lo, hi = np.percentile(zone_vals, 35), np.percentile(zone_vals, 99.5)
spec_map = np.clip((lum_lp - lo) / max(hi - lo, 1.0), 0, 1) ** 1.6

# 크롭 박스: 실루엣은 회전과 무관하므로 모든 프레임 공통
ys, xs_all = np.where(alpha > 0.02)
box = (max(int(xs_all.min()) - a.pad, 0), max(int(ys.min()) - a.pad, 0),
       min(int(xs_all.max()) + a.pad + 1, W), min(int(ys.max()) + a.pad + 1, H))

out_dir = pathlib.Path(a.out_dir)
out_dir.mkdir(parents=True, exist_ok=True)

for k in range(a.frames):
    phi = 360.0 * k / a.frames
    front_cx = a.front_cx + phi / 360.0 * circ_px
    out = B.copy()
    for y in range(lt, lb + 1):
        xs_row = np.where(alpha[y] > 0.5)[0]
        if len(xs_row) < 4:
            continue
        x0, x1 = xs_row.min(), xs_row.max()
        cx = (x0 + x1) / 2.0
        R = (x1 - x0) / 2.0
        xs = np.arange(x0, x1 + 1)
        u = np.clip((xs - cx) / R, -1, 1)
        theta = np.arcsin(u)
        lx = (front_cx + theta * (R / px_per_mm) * lab_px_per_mm) % circ_px   # 둘레 방향 wrap
        on_label = lx < (LW - 1)                                              # 아니면 이음매 틈(맨 병)
        ly = (y - lt) / max(lb - lt, 1) * (LH - 1)
        yi = int(round(ly))
        xi = np.clip(np.round(lx).astype(int), 0, LW - 1)
        src = lab[yi, xi]
        lam = a.ambient + (1 - a.ambient) * np.cos(theta) ** 0.7
        spec = spec_map[y, xs] * a.spec
        rgb = src * lam[:, None] * (1 - 0.35 * spec[:, None]) + 255.0 * spec[:, None] * 0.9
        edge = np.minimum(xs - x0, x1 - xs)
        w = np.clip(edge / 2.0, 0, 1)[:, None] * on_label[:, None]
        out[y, xs, :3] = np.clip(rgb * w + out[y, xs, :3] * (1 - w), 0, 255)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).crop(box).save(out_dir / f'turn-{k:03d}.png')

meta = {'frames': a.frames, 'step_deg': 360.0 / a.frames, 'crop_box': box, 'canvas': [W, H],
        'circumference_label_px': round(circ_px, 1), 'label_px': [LW, LH],
        'seam_gap_px': round(circ_px - LW, 1), 'front_cx': a.front_cx}
(out_dir / 'turn.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1))
print('frames', a.frames, 'crop', box, 'seam gap px', meta['seam_gap_px'])
