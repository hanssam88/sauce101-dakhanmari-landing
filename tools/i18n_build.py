#!/usr/bin/env python3
"""i18n/*.json → js/i18n-data.js (런타임이 읽는 번역 데이터). file:// 로 열어도 동작하도록 <script> 로 싣는다.

  i18n_build.py [--root 폴더] [--check]

ko 는 앱 문자열(ko.app.json)만 싣는다(HTML 문구는 문서에 이미 있음). en · es 는 전체를 싣는다.
--check 이면 파일을 쓰지 않고 js/i18n-data.js 가 최신인지만 확인한다(오래됐으면 종료 코드 1).
"""
import argparse, json, pathlib, sys

HEAD = '/* 자동 생성 — tools/i18n_build.py. 직접 고치지 말고 i18n/*.json 을 고친 뒤 다시 생성하세요. */\n'


def build(root: pathlib.Path) -> str:
    d = root / 'i18n'
    data = {
        'ko': json.loads((d / 'ko.app.json').read_text(encoding='utf-8')),
        'en': json.loads((d / 'en.json').read_text(encoding='utf-8')),
        'es': json.loads((d / 'es.json').read_text(encoding='utf-8')),
    }
    return HEAD + 'window.S101_I18N=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(pathlib.Path(__file__).resolve().parent.parent))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    out = root / 'js' / 'i18n-data.js'
    text = build(root)
    if a.check:
        ok = out.exists() and out.read_text(encoding='utf-8') == text
        print('최신' if ok else 'js/i18n-data.js 가 오래됨 — i18n_build.py 를 다시 실행하세요')
        return 0 if ok else 1
    out.write_text(text, encoding='utf-8')
    print(f'{out.relative_to(root)}  {len(text) / 1024:.1f} KB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
