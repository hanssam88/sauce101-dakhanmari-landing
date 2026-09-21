#!/usr/bin/env python3
"""render_turn.py 가 만든 RGBA 프레임 → 웹 배포용 파일.

  export_turn.py --frames-dir raw/ --out assets/bottle [--scale 0.75] [--matte EFEBDE]

산출(out 아래)
  bottle-front.png        투명 PNG(0° 정면, 원본 해상도) — 누끼 자산
  turn/turn-NNN.webp      캔버스 뷰어용 프레임(알파 WebP, --scale 적용)
  bottle-turn.webp        루프 애니메이션(알파 WebP) — 현대 브라우저 표준
  bottle-turn.gif         루프 애니메이션 GIF(--matte 배경에 합성 · 투명 GIF는 가장자리가 거칠어 매트 처리)
"""
import argparse, pathlib
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('--frames-dir', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--scale', type=float, default=0.75, help='뷰어 프레임 배율')
ap.add_argument('--quality', type=int, default=72)
ap.add_argument('--alpha-quality', type=int, default=70)
ap.add_argument('--loop-step', type=int, default=1, help='애니메이션에 쓸 프레임 간격(1=전부)')
ap.add_argument('--loop-ms', type=int, default=50)
ap.add_argument('--gif-height', type=int, default=560)
ap.add_argument('--gif-step', type=int, default=2)
ap.add_argument('--gif-ms', type=int, default=70)
ap.add_argument('--matte', default='EFEBDE', help='GIF 배경색 HEX')
a = ap.parse_args()

src = sorted(pathlib.Path(a.frames_dir).glob('turn-*.png'))
if not src:
    raise SystemExit('프레임이 없습니다: ' + a.frames_dir)
out = pathlib.Path(a.out); (out / 'turn').mkdir(parents=True, exist_ok=True)

frames = [Image.open(p).convert('RGBA') for p in src]
frames[0].save(out / 'bottle-front.png', optimize=True)

def sized(im, s):
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)

viewer = [sized(f, a.scale) for f in frames]
for i, f in enumerate(viewer):
    f.save(out / 'turn' / f'turn-{i:03d}.webp', 'WEBP', quality=a.quality, method=6, alpha_quality=a.alpha_quality)

loop = viewer[::a.loop_step]
loop[0].save(out / 'bottle-turn.webp', 'WEBP', save_all=True, append_images=loop[1:], duration=a.loop_ms,
             loop=0, quality=a.quality, method=6, alpha_quality=a.alpha_quality)

matte = tuple(int(a.matte[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
gif_src = frames[::a.gif_step]
gs = a.gif_height / gif_src[0].height
gif_frames = []
for f in gif_src:
    g = sized(f, gs)
    bg = Image.new('RGBA', g.size, matte)
    gif_frames.append(Image.alpha_composite(bg, g).convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=128))
gif_frames[0].save(out / 'bottle-turn.gif', save_all=True, append_images=gif_frames[1:], duration=a.gif_ms, loop=0, optimize=True, disposal=1)

def kb(p): return f'{p.stat().st_size / 1024:,.0f} KB'
tot = sum(p.stat().st_size for p in (out / 'turn').glob('*.webp'))
print('front png     ', kb(out / 'bottle-front.png'), frames[0].size)
print('viewer frames ', len(viewer), 'x', viewer[0].size, f'합계 {tot / 1024:,.0f} KB (평균 {tot / len(viewer) / 1024:,.0f} KB)')
print('loop webp     ', kb(out / 'bottle-turn.webp'), f'{len(loop)}프레임 {a.loop_ms}ms')
print('loop gif      ', kb(out / 'bottle-turn.gif'), f'{len(gif_frames)}프레임 {a.gif_ms}ms · {gif_frames[0].size} · 매트 #{a.matte}')
