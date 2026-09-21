#!/usr/bin/env python3
"""tools/ 스크립트 테스트 — 정상 경로와 오류 경로를 각각 확인한다.  실행: python3 tools/test_tools.py"""
import http.client, json, os, pathlib, re, socket, subprocess, sys, tempfile, time, unittest, urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable
sys.path.insert(0, str(HERE))
import check_copy  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class CheckCopy(unittest.TestCase):
    def test_real_page_is_clean(self):                     # 정상 경로: 현재 페이지에 위반이 없어야 한다
        self.assertEqual(check_copy.main(['--root', str(ROOT)]), 0)

    def test_banned_terms_are_caught(self):                # 오류 경로: 금지 표현을 실제로 잡는지
        for bad in ['무MSG 육수', '5분이면 완성', '타사 제품과 비교', '한정 수량 판매', '건강한 국물', '생성형 AI로 제작']:
            self.assertTrue(check_copy.check_text('t', bad), bad)

    def test_approved_sentences_pass(self):
        ok = '육수 50g에 물 450g이면 2인분 한 냄비. 330g 한 병으로 6번, 12인분을 끓입니다.'
        self.assertFalse(check_copy.check_text('t', ok))
        self.assertFalse(check_copy.check_numbers('t', ok))

    def test_unknown_number_is_caught(self):
        self.assertTrue(check_copy.check_numbers('t', '단 99g이면 됩니다'))

    def test_identifiers_are_not_numbers(self):
        self.assertFalse(check_copy.check_numbers('t', '인증번호 제2021-3-0546호 · 유효기간 2027.05.06 · 0507-1343-3918 · hello@sauce101.co.kr'))

    def test_other_platform_links_are_caught(self):
        self.assertTrue(check_copy.check_links('t', '<a href="https://smartstore.naver.com/x">'))
        self.assertFalse(check_copy.check_links('t', '<a href="https://sauce101.co.kr/product/detail.html?product_no=55">'))

    def test_local_brand_list_is_loaded(self):             # 브랜드명은 공개 저장소에 두지 않고 선택 파일에서 읽는다
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'brands.txt'; p.write_text('# 주석\n가짜브랜드\n', encoding='utf-8')
            rule = check_copy.load_brand_rule(p)
            self.assertTrue(re.search(rule[0], '가짜브랜드 육수와 비교'))
            self.assertIsNone(check_copy.load_brand_rule(pathlib.Path(d) / 'none.txt'))

    def test_buy_link_host_is_checked(self):               # 구매 링크(config.json 의 buy_url)도 허용 목록으로 확인
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for sub in ('data', 'snippets', 'js', 'i18n'):
                (root / sub).mkdir()
            (root / 'index.html').write_text('<p>ok</p>', encoding='utf-8')
            (root / 'js' / 'main.js').write_text('', encoding='utf-8')
            (root / 'data' / 'config.json').write_text(json.dumps({'buy_url': 'https://smartstore.naver.com/x'}), encoding='utf-8')
            self.assertEqual(check_copy.main(['--root', str(root)]), 1)


class PublishGate(unittest.TestCase):
    """예시 후기가 게시본에 남지 않게: 기본은 경고, --publish 는 실패."""

    def root_with(self, d, items):
        (pathlib.Path(d) / 'data').mkdir()
        (pathlib.Path(d) / 'data' / 'reviews.json').write_text(json.dumps({'meta': {}, 'items': items}), encoding='utf-8')
        return d

    def test_sample_reviews_warn_by_default_and_fail_on_publish(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_with(d, [{'sample': True, 'rating': 5, 'text': 'x'}])
            self.assertEqual(check_copy.main(['--root', d]), 0)
            self.assertEqual(check_copy.main(['--root', d, '--publish']), 1)

    def test_real_reviews_pass_publish(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_with(d, [{'rating': 5, 'text': 'x', 'verified': True}])
            self.assertEqual(check_copy.main(['--root', d, '--publish']), 0)

    def test_english_banned_terms_in_review_data_are_caught(self):
        with tempfile.TemporaryDirectory() as d:
            self.root_with(d, [{'rating': 5, 'text': {'ko': 'x', 'en': 'A healthy, MSG-free broth ready in 5 minutes', 'es': 'x'}}])
            self.assertEqual(check_copy.main(['--root', d]), 1)


class I18nTools(unittest.TestCase):
    def run_py(self, *args):
        return subprocess.run([PY, *map(str, args)], capture_output=True, text=True)

    def test_extract_is_idempotent(self):                  # 키가 밀리거나 새로 붙지 않아야 한다
        r = self.run_py(HERE / 'i18n_extract.py', '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn('새 키 0개', r.stdout)

    def test_runtime_data_is_up_to_date(self):             # i18n/*.json 을 고치고 빌드를 잊지 않았는지
        r = self.run_py(HERE / 'i18n_build.py', '--check')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_real_translations_pass_the_checker(self):     # 정상 경로: 실제 en/es 번역이 검증을 통과
        r = self.run_py(HERE / 'i18n_check.py')
        self.assertEqual(r.returncode, 0, r.stdout)

    def make_root(self, d, en):
        i = pathlib.Path(d) / 'i18n'; i.mkdir()
        (i / 'ko.json').write_text(json.dumps({'a.1': '육수 <b>50g</b>에 물 450g'}), encoding='utf-8')
        (i / 'ko.app.json').write_text(json.dumps({'js.x': '{n}원'}), encoding='utf-8')
        (i / 'en.json').write_text(json.dumps(en), encoding='utf-8')
        (i / 'es.json').write_text(json.dumps({'a.1': 'Base <b>50g</b> con agua 450g', 'js.x': '{n} KRW'}), encoding='utf-8')
        return d

    def test_checker_accepts_a_clean_pair(self):
        with tempfile.TemporaryDirectory() as d:
            self.make_root(d, {'a.1': 'Soup base <b>50g</b> with 450g of water', 'js.x': '{n} KRW'})
            self.assertEqual(self.run_py(HERE / 'i18n_check.py', '--root', d).returncode, 0)

    def test_checker_catches_broken_translations(self):    # 오류 경로: 태그 누락 · 자리표시자 누락 · 금지 표현 · 한글 잔존 · 키 누락
        bad = [
            {'a.1': 'Soup base 50g with 450g of water', 'js.x': '{n} KRW'},                          # <b> 누락
            {'a.1': 'Soup base <b>50g</b> with 450g of water', 'js.x': 'KRW'},                      # {n} 누락
            {'a.1': 'A healthy soup base <b>50g</b> with 450g', 'js.x': '{n} KRW'},                # 금지 표현
            {'a.1': '육수 <b>50g</b> with 450g', 'js.x': '{n} KRW'},                                # 한글 잔존
            {'a.1': 'Soup base <b>50g</b> with 450g of water'},                                    # 키 누락
        ]
        for en in bad:
            with tempfile.TemporaryDirectory() as d:
                self.make_root(d, en)
                self.assertEqual(self.run_py(HERE / 'i18n_check.py', '--root', d).returncode, 1, en)


class BowlFill(unittest.TestCase):
    """회귀: 계산기 그릇 수위는 육수+물 합계에 비례해야 한다(연하게=물 많음 → 가장 높음). 2026-09-21 거꾸로 되어 있던 버그."""
    FILES = [ROOT / 'js' / 'main.js', ROOT / 'snippets' / '03-dilution-calculator.html']

    def read(self, path):
        import re
        t = path.read_text(encoding='utf-8')
        fill = re.search(r'FILL\s*=\s*\{\s*light:\s*([\d.]+),\s*base:\s*([\d.]+),\s*rich:\s*([\d.]+)', t)
        water = re.search(r'(?:WATER|water)\s*[=:]\s*\{\s*light:\s*(\d+),\s*base:\s*(\d+),\s*rich:\s*(\d+)', t)
        self.assertTrue(fill and water, f'{path.name}: FILL/WATER 정의를 찾지 못함')
        return [float(x) for x in fill.groups()], [int(x) for x in water.groups()]

    def test_lighter_broth_has_the_fullest_bowl(self):
        for f in self.FILES:
            (fl, fb, fr), _ = self.read(f)
            self.assertGreater(fl, fb, f.name); self.assertGreater(fb, fr, f.name)

    def test_fill_is_proportional_to_total_grams(self):
        for f in self.FILES:
            fills, water = self.read(f)
            totals = [25 + w for w in water]                       # 1인 육수 25g + 물
            for fl, tot in zip(fills, totals):
                self.assertAlmostEqual(fl / fills[1], tot / totals[1], delta=0.02, msg=f.name)


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.p = subprocess.Popen(['node', str(HERE / 'serve.mjs'), str(cls.port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(('127.0.0.1', cls.port), 0.2).close(); break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.p.terminate(); cls.p.wait(5)

    def get(self, path, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        c.request('GET', path, headers=headers or {})
        r = c.getresponse(); body = r.read(); c.close()
        return r, body

    def test_index_served(self):                           # 정상 경로
        r, body = self.get('/')
        self.assertEqual(r.status, 200); self.assertIn('text/html', r.getheader('Content-Type')); self.assertIn('한 병, 여섯 냄비'.encode(), body)

    def test_range_request(self):                          # 정상 경로: 영상 재생용 Range
        r, body = self.get('/assets/clips/gv-add.mp4', {'Range': 'bytes=0-9'})
        self.assertEqual(r.status, 206); self.assertEqual(len(body), 10); self.assertTrue(r.getheader('Content-Range').startswith('bytes 0-9/'))

    def test_missing_is_404(self):                         # 오류 경로
        self.assertEqual(self.get('/nope.html')[0].status, 404)

    def test_path_traversal_is_blocked(self):              # 오류 경로: 폴더 밖 접근
        self.assertEqual(self.get('/../../../../etc/hosts')[0].status, 403)

    def test_dotfiles_are_not_served(self):                # 오류 경로: .git · .gitignore 같은 점 파일
        self.assertEqual(self.get('/.gitignore')[0].status, 404)
        self.assertEqual(self.get('/.git/config')[0].status, 404)

    def test_docs_folder_is_not_served(self):              # 오류 경로: 내부 문서는 로컬 서버로도 내보내지 않는다
        self.assertEqual(self.get(urllib.parse.quote('/docs/04-확인-필요.md'))[0].status, 404)     # http.client 는 ASCII 경로만 보낸다

    def test_huge_suffix_range_does_not_crash(self):       # 오류 경로: 시작점이 음수가 되는 Range 로 서버가 죽지 않는다
        r, body = self.get('/assets/clips/gv-add.mp4', {'Range': 'bytes=-999999999'})
        self.assertEqual(r.status, 206); self.assertGreater(len(body), 0)
        self.assertEqual(self.get('/')[0].status, 200)


class BottleTools(unittest.TestCase):
    def run_py(self, *args):
        return subprocess.run([PY, *map(str, args)], capture_output=True, text=True)

    def test_render_rejects_wrong_label_size(self):        # 오류 경로: 규격 다른 라벨
        with tempfile.TemporaryDirectory() as d:
            from PIL import Image
            Image.new('RGB', (100, 50)).save(pathlib.Path(d) / 'bad.png')
            r = self.run_py(HERE / 'render_turn.py', '--base', 'x.png', '--zone', 'x.json', '--label', pathlib.Path(d) / 'bad.png', '--out-dir', d)
            self.assertNotEqual(r.returncode, 0); self.assertIn('라벨 규격 불일치', r.stderr + r.stdout)

    def test_export_rejects_empty_dir(self):               # 오류 경로: 프레임 없음
        with tempfile.TemporaryDirectory() as d:
            r = self.run_py(HERE / 'export_turn.py', '--frames-dir', d, '--out', pathlib.Path(d) / 'o')
            self.assertNotEqual(r.returncode, 0); self.assertIn('프레임이 없습니다', r.stderr + r.stdout)

    def test_export_makes_all_outputs(self):               # 정상 경로: 작은 합성 프레임으로 산출물 4종
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            fr = pathlib.Path(d) / 'f'; fr.mkdir()
            for i in range(4):
                Image.new('RGBA', (60, 180), (100 + i * 30, 140, 60, 255)).save(fr / f'turn-{i:03d}.png')
            out = pathlib.Path(d) / 'o'
            r = self.run_py(HERE / 'export_turn.py', '--frames-dir', fr, '--out', out, '--gif-height', '90', '--gif-step', '1')
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ['bottle-front.png', 'bottle-turn.webp', 'bottle-turn.gif', 'turn/turn-000.webp', 'turn/turn-003.webp']:
                self.assertTrue((out / name).exists(), name)

    def test_render_two_frames_from_real_assets(self):     # 정상 경로: 실제 병 자산이 있으면 2프레임 렌더
        base = pathlib.Path(os.environ.get('S101_BOTTLE_BASE', '/nonexistent')); label = pathlib.Path(os.environ.get('S101_LABEL', '/nonexistent'))
        if not (base / 'dak.png').exists() or not label.exists():
            self.skipTest('병 원본 자산 없음 — S101_BOTTLE_BASE(dak.png·dak-zone.json 이 든 폴더)와 S101_LABEL(라벨 PNG)을 지정하면 실행')
        with tempfile.TemporaryDirectory() as d:
            r = self.run_py(HERE / 'render_turn.py', '--base', base / 'dak.png', '--zone', base / 'dak-zone.json', '--label', label, '--out-dir', d, '--frames', 2)
            self.assertEqual(r.returncode, 0, r.stderr)
            meta = json.loads((pathlib.Path(d) / 'turn.json').read_text())
            self.assertEqual(meta['frames'], 2); self.assertTrue((pathlib.Path(d) / 'turn-001.png').exists())


class I18nRuntime(unittest.TestCase):
    def test_every_key_used_by_main_js_exists_in_ko_runtime_dictionary(self):   # 한국어에서 t('키')가 키 이름 그대로 나오지 않게
        data = json.loads(re.search(r'window\.S101_I18N=(\{.*\});', (ROOT / 'js' / 'i18n-data.js').read_text(encoding='utf-8'), re.S).group(1))
        js = (ROOT / 'js' / 'main.js').read_text(encoding='utf-8')
        keys = set(re.findall(r"'((?:js|ui|cta|meta)\.[\w.]*\w|[a-z]+\.\d+)'", js))     # js.* 등 앱 키 + HTML 에서 자동 추출한 <구역>.<번호> 키
        self.assertTrue(keys, '키를 하나도 찾지 못했습니다')
        self.assertEqual(sorted(k for k in keys if k not in data['ko']), [])
        for lang in ('en', 'es'):
            self.assertEqual(sorted(k for k in keys if k not in data[lang]), [], lang)


class StoryVars(unittest.TestCase):
    def test_story_js_and_css_agree_on_variables(self):    # JS 가 넣는 변수와 CSS 가 읽는 변수가 어긋나 장면 일부가 멈추는 일을 막는다
        js = (ROOT / 'js' / 'main.js').read_text(encoding='utf-8')
        css = (ROOT / 'css' / 'style.css').read_text(encoding='utf-8')
        call = re.search(r'setVars\(\{(.*?)\}\);', js, re.S).group(1)
        from_js = set(re.findall(r'\b(\w+):', call))
        defaults = set(re.findall(r'--(\w+):', re.search(r'\.story__panel\{(--lv:.*?)\}', css).group(1)))
        used = set(re.findall(r'var\(--(\w+)', css))
        self.assertTrue(len(from_js) > 15, from_js)
        self.assertEqual(sorted(from_js - defaults), [], 'JS 가 넣지만 CSS 기본값이 없는 변수')
        self.assertEqual(sorted(defaults - from_js), [], 'CSS 기본값만 있고 JS 가 넣지 않는 변수')
        self.assertEqual(sorted(defaults - used), [], 'CSS 가 읽지 않는 변수')

    def test_story_svg_has_every_element_the_script_drives(self):   # main.js 가 찾는 요소가 마크업에 있는지
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        js = (ROOT / 'js' / 'main.js').read_text(encoding='utf-8')
        block = js[js.index('── 7. 냄비 스토리'):js.index('── 8. 계산기')]
        sels = sorted(set(re.findall(r"\$\$?\('\.([\w-]+)', svg\)", block)))
        self.assertTrue(sels, '스크립트가 찾는 요소를 하나도 읽지 못했습니다')
        for sel in sels:
            self.assertTrue(re.search(r'class="[^"]*\b' + re.escape(sel) + r'\b', html), f'index.html 에 .{sel} 가 없습니다')
        self.assertEqual(len(re.findall(r'class="rpi"', html)), 3)               # 재료 착수 물결 3개
        self.assertEqual(len(re.findall(r'class="ing ing--\d"', html)), 3)       # 재료 3개

    def test_story_class_names_do_not_collide_with_other_sections(self):   # 스토리 그림의 이름이 계산기·히어로 같은 다른 구역 규칙을 덮어쓰는 사고(.gb1 · .ruler)를 막는다
        css = (ROOT / 'css' / 'style.css').read_text(encoding='utf-8')
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        a = css.index('/* ── 냄비 스토리 그림'); b = css.index('/* ── 계산기(저울 패널) ── */')
        block, outside = css[a:b], css[:a] + css[b:]

        def sel_classes(text):
            text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
            for _ in range(3):
                text = re.sub(r'\{[^{}]*\}', '{}', text)                           # 선언·중첩을 지우고 선택자만 남긴다
            return set(re.findall(r'\.([A-Za-z_][\w-]*)', text))
        tokens = lambda h: {c for m in re.findall(r'class="([^"]*)"', h) for c in m.split()}
        s0 = html.index('<svg class="story__svg"'); s1 = html.index('</svg>', s0) + 6
        mine = (sel_classes(block) | tokens(html[s0:s1])) - {'story', 'story__svg', 'is-off'}      # 구역 이름 자체는 함께 쓴다
        self.assertEqual(sorted(mine & sel_classes(outside)), [], '스토리 그림이 다른 구역 CSS 와 같은 이름을 씁니다')
        self.assertEqual(sorted(mine & tokens(html[:s0] + html[s1:])), [], '스토리 CSS 이름을 다른 구역 마크업이 씁니다')


def keyframe_names(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    return re.findall(r'@keyframes\s+([\w-]+)', css)


def animation_names(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    skip = {'none', 'infinite', 'forwards', 'backwards', 'both', 'normal', 'reverse', 'alternate', 'alternate-reverse', 'paused', 'running',
            'ease', 'ease-in', 'ease-out', 'ease-in-out', 'linear', 'step-start', 'step-end', 'initial', 'inherit', 'unset'}
    names = set()
    for value in re.findall(r'animation(?:-name)?\s*:\s*([^;}]+)', css):
        for one in re.split(r',(?![^(]*\))', value):                                   # 괄호 안의 쉼표는 나누지 않는다
            for tok in one.split():
                if re.fullmatch(r'[A-Za-z_][\w-]*', tok) and tok not in skip:
                    names.add(tok); break
    return names


class CssAnimations(unittest.TestCase):
    def test_keyframes_names_are_unique(self):             # 같은 이름을 두 번 정의하면 뒤의 것이 이긴다 — 냄비 스토리의 rise 가 히어로 제목의 rise 를 덮어 제목이 사라진 사고(fb72d5c)를 막는다
        css = (ROOT / 'css' / 'style.css').read_text(encoding='utf-8')
        names = keyframe_names(css)
        self.assertTrue(len(names) > 5, names)
        self.assertEqual(sorted({n for n in names if names.count(n) > 1}), [], '같은 이름의 @keyframes 가 두 번 이상 있습니다')

    def test_every_animation_uses_a_defined_keyframes(self):   # 이름 오타·삭제로 애니메이션이 조용히 안 돌아가는 일을 막는다
        css = (ROOT / 'css' / 'style.css').read_text(encoding='utf-8')
        self.assertEqual(sorted(animation_names(css) - set(keyframe_names(css))), [], '정의되지 않은 @keyframes 를 쓰는 animation 이 있습니다')

    def test_duplicate_keyframes_check_catches_the_old_bug(self):   # 위 검사가 실제로 그 사고를 잡는지 — 사고 당시 CSS 조각으로 확인
        broken = '@keyframes rise{to{transform:none}} .a{animation:rise 1s} @keyframes rise{0%{opacity:0}}'
        names = keyframe_names(broken)
        self.assertEqual([n for n in set(names) if names.count(n) > 1], ['rise'])
        self.assertEqual(animation_names('.a{animation:rise 1s var(--ease) .1s forwards} .b{animation:spin var(--d) ease-in infinite, fade 2s cubic-bezier(.2, .8, .2, 1)}'), {'rise', 'spin', 'fade'})


def webp_size(path):
    b = pathlib.Path(path).read_bytes()
    assert b[:4] == b'RIFF' and b[8:12] == b'WEBP', f'{path}: WebP 가 아닙니다'
    kind = b[12:16]
    if kind == b'VP8 ':
        return int.from_bytes(b[26:28], 'little') & 0x3fff, int.from_bytes(b[28:30], 'little') & 0x3fff
    if kind == b'VP8L':
        bits = int.from_bytes(b[21:25], 'little')
        return (bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1
    if kind == b'VP8X':
        return int.from_bytes(b[24:27], 'little') + 1, int.from_bytes(b[27:30], 'little') + 1
    raise AssertionError(f'{path}: 알 수 없는 WebP 형식 {kind!r}')


class TopBanner(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.css = (ROOT / 'css' / 'style.css').read_text(encoding='utf-8')
        pic = re.search(r'<figure class="topbanner">\s*<picture>(.*?)</picture>', self.html, re.S)
        self.assertTrue(pic, '상단 배너(<figure class="topbanner"><picture>)를 index.html 에서 찾지 못했습니다')
        src = re.search(r'<source media="\(min-width:(\d+)px\)" srcset="([^"]+)" width="(\d+)" height="(\d+)">', pic.group(1))
        img = re.search(r'<img src="([^"]+)" width="(\d+)" height="(\d+)" alt="([^"]+)"', pic.group(1))
        self.assertTrue(src and img, '배너의 <source media srcset width height> 또는 <img src width height alt> 형식이 바뀌었습니다')
        self.pc = (src.group(2), int(src.group(3)), int(src.group(4))); self.pc_min = int(src.group(1))
        self.mo = (img.group(1), int(img.group(2)), int(img.group(3))); self.alt = img.group(4)

    def test_declared_sizes_match_the_real_files(self):    # width/height 가 실제 파일과 다르면 배너 자리가 어긋나 화면이 밀린다
        for path, w, h in (self.mo, self.pc):
            self.assertEqual(webp_size(ROOT / path), (w, h), path)

    def test_css_aspect_ratios_match_the_files(self):      # CSS 가 미리 잡아 두는 비율이 두 그림의 실제 비율과 같아야 한다
        (_, mw, mh), (_, pw, ph) = self.mo, self.pc
        base = re.search(r'\.topbanner img\{[^}]*aspect-ratio:(\d+)/(\d+)', self.css)
        wide = re.search(r'min-width:(\d+)px\)\{\s*\.topbanner\{.*?\.topbanner img\{aspect-ratio:(\d+)/(\d+)\}', self.css, re.S)
        self.assertEqual(int(base.group(1)) * mh, int(base.group(2)) * mw)
        self.assertEqual(int(wide.group(2)) * ph, int(wide.group(3)) * pw)
        self.assertEqual(int(wide.group(1)), self.pc_min, '그림을 바꾸는 너비(<source media>)와 CSS 카드 전환 너비가 다릅니다')

    def test_head_preloads_match_the_picture_sources(self):   # 미리 불러오는 그림이 실제로 그려지는 그림과 같아야 대역폭이 낭비되지 않는다
        pre = re.findall(r'<link rel="preload" as="image" href="(assets/img/top-banner[^"]*)" media="\(([a-z-]+):(\d+)px\)"', self.html)
        self.assertEqual(sorted(pre), sorted([(self.mo[0], 'max-width', str(self.pc_min - 1)), (self.pc[0], 'min-width', str(self.pc_min))]))

    def test_alt_text_is_translated_and_has_no_health_claims(self):   # 안내 문구는 번역 키가 있어야 하고, 이미지에 없는 효능을 말하지 않는다
        self.assertRegex(self.html, r'alt="' + re.escape(self.alt) + r'"[^>]*data-ta="alt:(hero\.\d+)"')
        key = re.search(r'alt="' + re.escape(self.alt) + r'"[^>]*data-ta="alt:(hero\.\d+)"', self.html).group(1)
        for lang in ('ko', 'en', 'es'):
            self.assertIn(key, json.loads((ROOT / 'i18n' / f'{lang}.json').read_text(encoding='utf-8')), f'{lang}.json 에 {key} 가 없습니다')
        self.assertFalse(check_copy.check_text('배너 안내', self.alt))
        self.assertFalse(check_copy.check_numbers('배너 안내', self.alt))


class HeroFirstPaint(unittest.TestCase):
    """브라우저로만 잡히는 회귀: 첫 화면이 로드 뒤에도 보이는가. 제목이 투명하게 끝나거나(fb72d5c, keyframes 이름 충돌) 구매 버튼이
    스크롤 전까지 투명하게 남는(배너가 밀어 낸 등장 문턱) 사고를 막는다. Playwright(Chromium)가 없으면 건너뛴다."""
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
            cls.pw = sync_playwright().start(); cls.browser = cls.pw.chromium.launch()
        except Exception as e:                                # 설치 안 됨 · 브라우저 없음
            raise unittest.SkipTest(f'Playwright(Chromium) 없음 — pip install playwright && playwright install chromium ({type(e).__name__})')
        cls.port = free_port()
        cls.p = subprocess.Popen(['node', str(HERE / 'serve.mjs'), str(cls.port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(('127.0.0.1', cls.port), 0.2).close(); break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.p.terminate(); cls.p.wait(5); cls.browser.close(); cls.pw.stop()

    def first_screen(self, width, height, **kw):
        ctx = self.browser.new_context(viewport={'width': width, 'height': height}, **kw)
        try:
            page = ctx.new_page(); errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))                 # 외부 글꼴 등 네트워크 오류는 세지 않는다
            page.goto(f'http://127.0.0.1:{self.port}/', wait_until='domcontentloaded'); page.wait_for_timeout(3500)     # 제목 1.45s · 등장 최대 1.2s
            state = page.evaluate("""() => ({
                title: [...document.querySelectorAll('.hero__title .ln>span')].map(s => [getComputedStyle(s).opacity, getComputedStyle(s).transform]),
                rv: [...document.querySelectorAll('#top .rv')].map(e => getComputedStyle(e).opacity),
                banner: (i => [i.complete && i.naturalWidth > 0, i.currentSrc.split('/').pop()])(document.querySelector('.topbanner img')),
                overflow: document.documentElement.scrollWidth - innerWidth })""")
            return state, errors
        finally:
            ctx.close()

    def check(self, width, height, banner, **kw):
        state, errors = self.first_screen(width, height, **kw)
        self.assertEqual(errors, [])
        self.assertEqual(len(state['title']), 2)
        for opacity, transform in state['title']:
            self.assertEqual(opacity, '1', '히어로 제목이 투명하게 끝났습니다'); self.assertIn(transform, ('none', 'matrix(1, 0, 0, 1, 0, 0)'))
        self.assertTrue(state['rv'] and all(o == '1' for o in state['rv']), f"히어로의 등장 요소가 투명하게 남았습니다: {state['rv']}")
        self.assertEqual(state['banner'], [True, banner])
        self.assertLessEqual(state['overflow'], 0, '가로 넘침')

    def test_phone_first_screen(self):
        self.check(393, 852, 'top-banner.webp', device_scale_factor=2, is_mobile=True, has_touch=True)

    def test_laptop_first_screen(self):                    # 노트북 높이에서는 배너 때문에 구매 버튼이 등장 문턱(-8%) 아래로 밀린다
        self.check(1440, 780, 'top-banner-pc.webp')


class ConfigDefaults(unittest.TestCase):
    def test_js_defaults_match_config_json(self):          # 설정을 못 불러올 때(file://) 쓰는 기본값이 config.json 과 어긋나지 않게
        js = (ROOT / 'js' / 'main.js').read_text(encoding='utf-8')
        block = re.search(r'const DEFAULTS = \{(.*?)\n\};', js, re.S).group(1)
        cfg = json.loads((ROOT / 'data' / 'config.json').read_text(encoding='utf-8'))
        text = lambda key: re.search(key + r": '([^']*)'", block).group(1)
        self.assertEqual(text('buy_url'), cfg['buy_url'])
        self.assertEqual(text('phone'), cfg['contact']['phone']); self.assertEqual(text('email'), cfg['contact']['email'])
        for k in ('list', 'sale', 'shipping_fee'):
            self.assertEqual(int(re.search(k + r': (\d+)', block).group(1)), cfg['price'][k], k)
        self.assertEqual(text('haccp_valid_until'), cfg['certs']['haccp_valid_until'])
        self.assertEqual(text('insurance_valid_until'), cfg['certs']['insurance_valid_until'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
