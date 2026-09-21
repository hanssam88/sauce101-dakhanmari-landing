#!/usr/bin/env python3
"""고객 노출 문구 점검 — 금지 표현 · 근거 없는 숫자 · 타 플랫폼 링크를 찾는다.

  check_copy.py [--root 폴더] [--show-numbers] [--publish]   # 기본 root: 이 스크립트의 상위 폴더(= 페이지 폴더)
  --publish: 게시 직전 점검 — data/reviews.json 에 예시(sample:true) 후기가 남아 있으면 실패

검사 대상: index.html · js/main.js(문자열) · data/*.json · snippets/*.html 의 '화면에 보이는 문구'.
종료 코드 0 = 위반 없음, 1 = 위반 있음(무엇이 왜 걸렸는지 출력).

규칙의 근거: 브랜드 콘텐츠 표시 원칙(금지 표현), 제품 라벨(사실 원천). 숫자 허용 목록은 출처를 함께 적어 두며
새 숫자는 출처와 함께만 추가한다. 타사 브랜드명 목록은 공개 저장소에 두지 않고 tools/banned_brands.local.txt(선택, git 제외)에서 읽는다.
"""
import argparse, html, json, pathlib, re, sys

# 정규식(대소문자 무시) → 이유
BANNED = [
    (r'무\s?MSG|MSG\s?무|무첨가|무방부제|무보존료', '라벨에 L-글루탐산나트륨·보존료 표기가 있어 사실과 다름'),
    (r'천연|수제|저염|저나트륨|건강|다이어트|숙취|해장|효능|효과|면역|항산화|디톡스|보양|치유', '건강·효능 연상어(식품표시광고법·프로젝트 금지 표현)'),
    (r'전체\s?원료\s?국산|100\s?%\s?국산', '외국산 원료가 있어 사실과 다름'),
    (r'최고|최상|국내\s?최초|세계\s?최초|1\s?위|압도적|완벽', '최상급·과장 표현'),
    (r'황금\s?레시피', '프로젝트 금지 표현'),
    (r'생성형|AI\s?로|AI\s?제작|인공지능', 'AI 제작 고지 문장 금지(브랜드 콘텐츠 원칙)'),
    (r'홍보\s?글|광고입니다|자사\s?제품\s?홍보', '광고·홍보 고지 문장 금지(브랜드 콘텐츠 원칙)'),
    (r'내돈내산|체험단|먹어\s?보니|써\s?보니|직접\s?먹어', '체험담 위장 금지'),
    (r'\d+\s?분\s?(이면|만에|안에|이내)', '근거 없는 조리 시간 주장(사실표에 시간 없음)'),
    (r'타사|경쟁사|타\s?브랜드|타\s?제품', '타사·타 제품 언급/비교 금지'),          # 구체적인 브랜드명은 아래 load_brand_rule 이 선택 파일에서 합친다
    (r'마감\s?임박|한정\s?수량|재고\s?\d+|남은\s?수량|오늘만|타임\s?세일|단\s?\d+\s?개', '가짜 희소성·긴박 문구 금지'),
    (r'별점\s?\d|평점\s?\d(?!건)|\d+\s?만\s?명|\d+\s?명이\s?선택', '근거 없는 평점·판매 수치'),
]

BRANDS_FILE = pathlib.Path(__file__).resolve().parent / 'banned_brands.local.txt'


def load_brand_rule(path=BRANDS_FILE):
    """타사 브랜드명은 공개 저장소에 두지 않는다 — 선택 파일(한 줄에 하나, # 주석)이 있으면 금지 규칙으로 합친다."""
    if not path.exists():
        return None
    names = [ln.strip() for ln in path.read_text(encoding='utf-8').splitlines() if ln.strip() and not ln.lstrip().startswith('#')]
    return (r'|'.join(re.escape(n) for n in names), '타사·타 제품 언급/비교 금지') if names else None


_brand_rule = load_brand_rule()
if _brand_rule:
    BANNED.append(_brand_rule)

# 숫자 검사 전에 통째로 지우는 식별자(번호·날짜·주소 등 — 값 자체가 주장이 아닌 것)
STRIP = [
    r'\d{4}\.\d{2}\.\d{2}', r'\d{4}-\d{2}-\d{2}', r'0\d{3}-\d{4}-\d{4}', r'제\d{4}-\d-\d{4}호', r'\b20\d{13}\b',
    r'밀머리로 77', r'동탄대로5길 15', r'1단지 102동 31층 3103호', r'국번 없이 1399', r'(?i)sauce\s?101|소스101',
    r'\d+(?:px|vw|vh|rem|em|ms)\b',
]

# 화면에 나와도 되는 숫자 → 출처(라벨 · 확정 문구 · 자사몰 상품 페이지 · 계산). 새 숫자는 출처와 함께만 여기에 추가한다.
ALLOWED_NUMBERS = {
    '330': '내용량 [라벨]', '85': '열량 85kcal [라벨]', '50': '육수 1회 [라벨·제조사 권장]', '450': '물 450g [라벨·제조사 권장]',
    '500': '연하게 물 [확정 문구]', '400': '진하게 물 [확정 문구]', '225': '1인 기본 물(계산)', '250': '1인 연한 물·누적 눈금(계산)',
    '200': '1인 진한 물·누적 눈금(계산)', '25': '1인 육수(계산) · 100g당 25kcal [라벨]', '100': '눈금·100g당 [라벨]', '150': '눈금(계산)',
    '300': '눈금(계산)', '2': '2인분 [라벨]', '30': '잔량 30g [확정 문구] · 30일 정책 [자사몰 정책]', '4': '종이컵 4분의 1 [확정 문구]', '6': '6회 [확정 문구] · 6cm [확정 치수]', '12': '12인분·12개월 [확정 문구]',
    '18': '높이 18cm [확정 치수]', '1': '1℃·1회', '35': '35℃ [라벨]', '3': '3개월 [자사몰 정책]',
    '7': '7일 [자사몰 정책]', '180': '종이컵 180ml [확정 문구]', '5': '5억원 [보험증권]', '0': '영양표 0g [라벨]',
    '2.7': '닭고기 % [라벨]', '0.1': '추출물·지방 % [라벨]', '0.5': '지방 g [라벨]', '1.0': '단백질 g [라벨]',
    '2307': '나트륨 mg [라벨]', '2,307': '나트륨 mg [라벨]', '115': '기준치 % [라벨]', '2,000': '2,000kcal 기준 [라벨]',
    '9,900': '판매가 [자사몰 2026-09-20]', '11,900': '소비자가 [자사몰]', '3,000': '배송비 [자사몰]', '17': '할인율(계산: 소비자가·판매가)',
    '360': '360° 회전 표기',
}
NUM_RE = re.compile(r'\d[\d,]*(?:\.\d+)?')
HOSTS_OK = {'sauce101.co.kr', 'fonts.googleapis.com', 'fonts.gstatic.com', 'cdn.jsdelivr.net', 'www.w3.org'}


def visible_text(src: str) -> str:
    src = re.sub(r'<!--.*?-->', ' ', src, flags=re.S)
    src = re.sub(r'<(script|style)\b.*?</\1>', ' ', src, flags=re.S | re.I)
    src = re.sub(r'<[^>]+>', ' ', src)
    return re.sub(r'\s+', ' ', html.unescape(src))


def js_strings(src: str) -> str:
    """JS 문자열 리터럴만 모은다(주석 제외) — 화면에 붙는 문구 후보."""
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    src = re.sub(r'(^|[^:])//[^\n]*', r'\1', src)
    return ' '.join(a or b for a, b in re.findall(r"'((?:[^'\\\n]|\\.)*)'|`([^`]*)`", src))


def check_text(name: str, text: str):
    hits = []
    for pat, why in BANNED:
        for m in re.finditer(pat, text, flags=re.I):
            a, b = max(0, m.start() - 14), min(len(text), m.end() + 14)
            hits.append((name, f'금지 표현 「{m.group(0)}」 — {why}', text[a:b]))
    return hits


def strip_ids(text: str) -> str:
    for pat in STRIP:
        text = re.sub(pat, ' ', text)
    return text


def check_numbers(name: str, text: str):
    text = strip_ids(text)
    hits = []
    for m in NUM_RE.finditer(text):
        n = m.group(0).rstrip(',')
        if n in ALLOWED_NUMBERS:
            continue
        a, b = max(0, m.start() - 14), min(len(text), m.end() + 14)
        hits.append((name, f'출처 없는 숫자 「{n}」 — ALLOWED_NUMBERS 에 출처와 함께 추가하거나 문구를 고치세요', text[a:b]))
    return hits


def check_links(name: str, src: str):
    hits = []
    for m in re.finditer(r'(?:href|src)\s*=\s*["\'](https?://[^"\']+)', src):
        host = re.sub(r'^https?://([^/]+).*', r'\1', m.group(1))
        if host not in HOSTS_OK:
            hits.append((name, f'허용 목록 밖 외부 주소 「{host}」 — 자사몰 글에는 타 플랫폼 URL을 넣지 않습니다', m.group(1)))
    return hits


def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if not str(k).startswith('_'):
                yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)
    elif o is not None:
        yield o


def check_locale_text(name: str, text: str):
    """영어·스페인어 문구의 금지 표현(i18n_check 와 같은 규칙)."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from i18n_check import BANNED_LOCALE
    hits = []
    for pat, why in BANNED_LOCALE:
        for m in re.finditer(pat, text, flags=re.I):
            a, b = max(0, m.start() - 14), min(len(text), m.end() + 14)
            hits.append((name, f'금지 표현 「{m.group(0)}」 — {why}', text[a:b]))
    return hits


def check_sample_reviews(root: pathlib.Path, publish: bool):
    """예시 후기가 남아 있으면 알린다. --publish(게시 직전 점검)에서는 위반으로 본다."""
    p = root / 'data' / 'reviews.json'
    if not p.exists():
        return [], []
    d = json.loads(p.read_text(encoding='utf-8'))
    n = sum(1 for r in d.get('items', []) if r.get('sample'))
    if not n:
        return [], []
    msg = f'예시 후기 {n}건이 data/reviews.json 에 있습니다 — 게시 전에 실제 후기로 교체하거나 items 를 비우세요'
    return ([('data/reviews.json', msg, 'sample:true')] if publish else []), ([] if publish else [msg])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(pathlib.Path(__file__).resolve().parent.parent), help='페이지 폴더')
    ap.add_argument('--show-numbers', action='store_true', help='본문에서 발견한 숫자 목록 출력')
    ap.add_argument('--publish', action='store_true', help='게시 직전 점검: 예시 후기가 남아 있으면 실패')
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    files = [root / 'index.html', root / 'js' / 'main.js', root / 'i18n' / 'ko.app.json'] + sorted((root / 'data').glob('*.json')) + sorted((root / 'snippets').glob('*.html'))
    hits, seen, n_files = [], {}, 0
    for f in files:
        if not f.exists():
            continue
        n_files += 1
        raw = f.read_text(encoding='utf-8')
        rel = str(f.relative_to(root))
        if f.suffix == '.html':
            text = visible_text(raw)
            hits += check_links(rel, raw)
        elif f.suffix == '.js':
            text = js_strings(raw)
        else:
            data = json.loads(raw)
            text = ' '.join(str(v) for v in _walk(data))
            hits += check_locale_text(rel, text)                 # 후기 데이터에는 영어·스페인어 문구도 있다
            if isinstance(data, dict) and data.get('buy_url'):
                hits += check_links(rel, f'href="{data["buy_url"]}"')      # 구매 링크도 자사몰 주소여야 한다
        hits += check_text(rel, text)
        if rel == 'index.html':                  # 숫자 검사는 본문 페이지만(스니펫은 데모 문구)
            hits += check_numbers(rel, text)
            for m in NUM_RE.finditer(strip_ids(text)):
                seen[m.group(0)] = seen.get(m.group(0), 0) + 1
    if a.show_numbers:
        print(json.dumps(dict(sorted(seen.items(), key=lambda kv: -kv[1])), ensure_ascii=False))
    sample_hits, sample_warns = check_sample_reviews(root, a.publish)
    hits += sample_hits
    for w in sample_warns:
        print('⚠', w)
    for name, why, ctx in hits:
        print(f'✗ {name}: {why}\n    …{ctx}…')
    print(f'검사 파일 {n_files}개 · 위반 {len(hits)}건')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
