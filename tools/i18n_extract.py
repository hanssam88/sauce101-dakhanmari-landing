#!/usr/bin/env python3
"""index.html 의 한국어 문구를 번역 단위로 찾아 data-t / data-ta 키를 붙이고 i18n/ko.json 을 만든다.

  i18n_extract.py [--root 폴더] [--dry-run]

- 번역 단위: 한글이 직접 들어 있는 '가장 바깥' 요소. 안쪽의 <b>·<br>·아이콘 같은 인라인 표시는 한 덩어리로 옮긴다.
- 속성 단위: alt · aria-label · aria-roledescription · title 의 한글 → data-ta="속성:키;속성:키"
- 제외: <head> · <script> · <style> · <svg> 안쪽 · data-notranslate 요소 · data-cfg 요소(설정값이 채움)
- 이미 붙은 키는 유지하고 새 요소에만 새 번호를 붙인다(키가 밀리지 않음). ko.json 은 항상 HTML 을 그대로 반영한다.
종료 코드 0 = 성공. 부작용: index.html · i18n/ko.json 을 쓴다(--dry-run 이면 쓰지 않음).
"""
import argparse, json, pathlib, re, sys
from html.parser import HTMLParser

HANGUL = re.compile(r'[가-힣ㄱ-ㅎ㈜]')
VOID = {'br', 'img', 'meta', 'link', 'input', 'hr', 'source', 'area', 'base', 'col', 'embed', 'param', 'track', 'wbr'}
ATTRS = ('alt', 'aria-label', 'aria-roledescription', 'title')
SKIP = {'head', 'script', 'style', 'noscript'}
GENERIC = {'sec', 'sec--tone', 'sec--deep', 'wrap'}


class Node:
    def __init__(self, tag, attrs, s, se, parent):
        self.tag, self.attrs, self.s, self.se, self.parent = tag, dict(attrs), s, se, parent
        self.children, self.text, self.inner_end = [], [], None


class Tree(HTMLParser):
    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.src = src
        self.lines = [0] + [m.end() for m in re.finditer('\n', src)]
        self.root = Node('#root', {}, 0, 0, None)
        self.stack = [self.root]

    def pos(self):
        ln, off = self.getpos()
        return self.lines[ln - 1] + off

    def handle_starttag(self, tag, attrs):
        s = self.pos()
        n = Node(tag, attrs, s, s + len(self.get_starttag_text()), self.stack[-1])
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack[i].inner_end = self.pos()
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].text.append(data)


def prefix_of(n):
    cur = n
    while cur is not None and cur.tag != '#root':
        cls = [c for c in cur.attrs.get('class', '').split() if c]
        if cur.tag in ('section', 'header', 'footer') or set(cls) & {'dock', 'skip'}:
            i = cur.attrs.get('id')
            if i and i != 'top':
                return i
            for c in cls:
                if c not in GENERIC:
                    return c
            return cur.tag
        cur = cur.parent
    return 'page'


def collect(root):
    units, attrs, warns = [], [], []

    def walk(n, in_unit):
        if n.tag in SKIP or 'data-notranslate' in n.attrs:
            return
        for a in ATTRS:
            v = n.attrs.get(a)
            if v and HANGUL.search(v):
                attrs.append((n, a, v))
                if in_unit:
                    warns.append(f'번역 단위 안쪽 요소의 속성 {a}="{v[:20]}…" — 번역 문자열에서 직접 옮겨야 함')
        if n.tag == 'svg':
            return
        here = False
        if not in_unit and 'data-cfg' not in n.attrs and any(HANGUL.search(t) for t in n.text):
            units.append(n)
            here = True
        for c in n.children:
            walk(c, in_unit or here)

    walk(root, False)
    return units, attrs, warns


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    html_path = root / 'index.html'
    src = html_path.read_text(encoding='utf-8')
    tree = Tree(src); tree.feed(src); tree.close()
    units, attrs, warns = collect(tree.root)

    counters, used = {}, set()

    def bump(prefix, key=None):
        if key:
            used.add(key); m = re.match(r'^(.*)\.(\d+)$', key)
            if m: counters[m.group(1)] = max(counters.get(m.group(1), 0), int(m.group(2)))
            return key
        counters[prefix] = counters.get(prefix, 0) + 1
        return f'{prefix}.{counters[prefix]}'

    # 1) 이미 있는 키를 먼저 등록해 번호 충돌을 막는다
    def existing_t(n): return n.attrs.get('data-t')
    def existing_ta(n):
        return dict(p.split(':', 1) for p in n.attrs.get('data-ta', '').split(';') if ':' in p)

    def scan(n):
        if existing_t(n): bump('', existing_t(n))
        for k in existing_ta(n).values(): bump('', k)
        for c in n.children: scan(c)
    scan(tree.root)

    ko, edits = {}, {}
    for n in units:
        key = existing_t(n) or bump(prefix_of(n))
        ko[key] = re.sub(r'\s+', ' ', src[n.se:n.inner_end]).strip()
        if not existing_t(n):
            edits.setdefault(id(n), [n, [], {}])[1].append(f'data-t="{key}"')
    by_node = {}
    for n, attr, val in attrs:
        by_node.setdefault(id(n), (n, {}))[1][attr] = val
    for _, (n, m) in by_node.items():
        have = existing_ta(n); pairs = []
        for attr, val in m.items():
            key = have.get(attr) or bump(prefix_of(n))
            ko[key] = val
            if attr not in have: pairs.append(f'{attr}:{key}')
        if pairs:
            if have: warns.append(f'{n.tag}: data-ta 가 이미 있어 새 속성 {pairs} 는 수동으로 추가해야 함')
            else: edits.setdefault(id(n), [n, [], {}])[1].append('data-ta="' + ';'.join(pairs) + '"')

    out = src
    for n, parts, _ in sorted(edits.values(), key=lambda e: -e[0].se):
        out = out[:n.se - 1] + ' ' + ' '.join(parts) + out[n.se - 1:]

    ko_path = root / 'i18n' / 'ko.json'
    old = json.loads(ko_path.read_text(encoding='utf-8')) if ko_path.exists() else {}
    stale = sorted(set(old) - set(ko))
    print(f'번역 단위 {len(units)}개 · 속성 {len(attrs)}개 · 새 키 {len(edits)}개 · 사라진 키 {len(stale)}개')
    for w in warns: print('⚠', w)
    if stale: print('⚠ 사라진 키(번역 파일에서 정리 필요):', ', '.join(stale[:12]), '…' if len(stale) > 12 else '')
    if not a.dry_run:
        if out != src: html_path.write_text(out, encoding='utf-8')
        ko_path.parent.mkdir(exist_ok=True)
        ko_path.write_text(json.dumps(ko, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
