#!/usr/bin/env python3
"""번역 파일 검증 — i18n/en.json · es.json 이 한국어 원본과 사실·구조가 같은지 확인한다.

  i18n_check.py [--root 폴더]

오류(종료 코드 1): 키 누락/초과 · HTML 태그 불일치 · {자리표시자} 불일치 · 한글 잔존 · 금지 표현(과장·효능·무MSG 등)
경고(종료 코드 영향 없음): 숫자 나열 불일치(분수 표기 등 정당한 차이 가능) · 짧은 UI 문구가 원문의 2.4배 초과(넘침 위험)
"""
import argparse, json, pathlib, re, sys
from collections import Counter

HANGUL = re.compile(r'[가-힣ㄱ-ㅎ]')
TAG = re.compile(r'<[^>]+>')
PH = re.compile(r'\{[a-z_]+\}')
NUM = re.compile(r'\d+(?:[.,]\d+)?')

# 영어·스페인어에서 금지하는 표현(한국어 규칙과 같은 취지: check_copy.py BANNED)
BANNED_LOCALE = [
    (r'MSG[- ]?free|no MSG|without MSG|additive[- ]free|preservative[- ]free|sin MSG|sin aditivos|sin conservantes|libre de MSG', '무MSG·무첨가류(라벨과 다름)'),
    (r'\bnatural\b|homemade|handmade|low[- ]sodium|low[- ]salt|healthy|health benefit|\bdiet\b|hangover|immun|antioxidant|detox|wellness|superfood', '건강·효능·천연 연상어(영어)'),
    (r'\bnatural(?:es)?\b|casero|artesanal|bajo en sodio|bajo en sal|saludable|\bsalud\b|\bdieta\b|resaca|inmun|antioxidante|desintoxic', '건강·효능·천연 연상어(스페인어)'),
    (r'\bbest\b|#1|number one|the finest|unbeatable|perfect|world[- ]class|\bmejor(?:es)?\b|el número uno|perfecto|insuperable', '최상급·과장 표현'),
    (r'\b\d+\s?(?:minutes?|mins?)\b|\b\d+\s?minutos?\b', '근거 없는 조리 시간 주장'),
    (r'\bAI\b|artificial intelligence|inteligencia artificial|generated', 'AI 고지 문장'),
    (r'limited (?:stock|quantity)|hurry|only today|last chance|stock limitado|últimas unidades|solo hoy', '가짜 희소성'),
]


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def norm_tags(s):
    return Counter(re.sub(r'\s+', ' ', t).strip() for t in TAG.findall(s))


def check_lang(lang, ko, tr):
    errors, warns = [], []
    for k in sorted(set(ko) - set(tr)):
        errors.append(f'[{lang}] 누락 키 {k}')
    for k in sorted(set(tr) - set(ko)):
        errors.append(f'[{lang}] 초과 키 {k}')
    for k, kv in ko.items():
        if k not in tr:
            continue
        v = tr[k]
        if not isinstance(v, str):
            errors.append(f'[{lang}] {k}: 문자열이 아님'); continue
        if kv == '':                                     # 한국어에서 비어 있는 키(외국어 전용 안내 등)는 번역이 있어도 됨
            continue
        if not v.strip():
            errors.append(f'[{lang}] {k}: 비어 있음'); continue
        if HANGUL.search(v):
            errors.append(f'[{lang}] {k}: 한글이 남아 있음 → {v[:50]}')
        if norm_tags(kv) != norm_tags(v):
            errors.append(f'[{lang}] {k}: HTML 태그가 다름\n      ko {dict(norm_tags(kv))}\n      {lang} {dict(norm_tags(v))}')
        if Counter(PH.findall(kv)) != Counter(PH.findall(v)):
            errors.append(f'[{lang}] {k}: {{자리표시자}}가 다름 ko {PH.findall(kv)} / {lang} {PH.findall(v)}')
        if Counter(NUM.findall(TAG.sub(' ', kv))) != Counter(NUM.findall(TAG.sub(' ', v))):
            warns.append(f'[{lang}] {k}: 숫자가 다름 — ko {NUM.findall(TAG.sub(" ", kv))} / {lang} {NUM.findall(TAG.sub(" ", v))}')
        if len(kv) <= 24 and len(v) > max(30, len(kv) * 2.4):
            warns.append(f'[{lang}] {k}: 짧은 UI 문구가 길어짐 ({len(kv)}자 → {len(v)}자) — 화면 넘침 확인')
        for pat, why in BANNED_LOCALE:
            m = re.search(pat, v, flags=re.I)
            if m:
                errors.append(f'[{lang}] {k}: 금지 표현 「{m.group(0)}」 — {why}')
    return errors, warns


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(pathlib.Path(__file__).resolve().parent.parent))
    a = ap.parse_args(argv)
    d = pathlib.Path(a.root) / 'i18n'
    ko = {**load(d / 'ko.json'), **load(d / 'ko.app.json')}
    errors, warns = [], []
    for lang in ('en', 'es'):
        p = d / f'{lang}.json'
        if not p.exists():
            errors.append(f'[{lang}] {p.name} 없음'); continue
        e, w = check_lang(lang, ko, load(p)); errors += e; warns += w
    for w in warns: print('⚠', w)
    for e in errors: print('✗', e)
    print(f'키 {len(ko)}개 × 2개 언어 · 오류 {len(errors)}건 · 경고 {len(warns)}건')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
