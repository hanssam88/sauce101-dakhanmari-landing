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
