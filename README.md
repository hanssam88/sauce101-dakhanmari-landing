# 소스101 닭한마리육수 — 코드형 설득 상세페이지

이미지 슬라이스가 아니라 **HTML·CSS·JS로 만든 상세페이지**입니다(의존성 없음). 기존 승인 소스101 톤(크림·올리브·명조)을 유지하고, 주방 저울의 눈금 어법을 서명 요소로 얹었습니다. 한국어가 기본이고 상단 **KO · EN · ES** 버튼(구매하기 옆)으로 영어·스페인어로 바꿔 볼 수 있습니다.

Node.js만 있으면 실행됩니다(의존성 없음). 터미널 위치와 무관하게 동작하고, 스크립트는 자기 폴더만 제공합니다(영상용 Range 지원).

```bash
node tools/serve.mjs 3000      # 저장소 루트에서. 다른 위치라면 tools/serve.mjs 경로만 바꾸세요
```

브라우저에서 http://localhost:3000 을 여세요(`?lang=en` · `?lang=es` 로 바로 언어 지정). Ctrl+C 로 서버가 꺼집니다. 서버는 기본적으로 이 컴퓨터에서만 열리며, 같은 와이파이의 휴대폰으로 보려면 `HOST=0.0.0.0 node tools/serve.mjs 3000` 으로 실행하세요. 도구 중 `check_copy`·`i18n_*`는 Python 3 표준 라이브러리만, 병 회전 도구(`render_turn`·`export_turn`)는 Pillow·numpy가 필요합니다.

## 구성 요약

| 요소 | 어디에 |
|---|---|
| 설득 구조 페이지(코드) | `index.html` + `css/` + `js/` |
| 경쟁 빈틈을 반영한 비교·FAQ | 페이지 안 — 궁금한 점 6행 · 비교 인포그래픽 · 정직한 맛 표기 |
| 레퍼런스 질감 | `css/style.css` 맨 위 토큰 (소스101 톤 + 종이 결·아치 무대·눈금) |
| 투명 PNG · 회전 루프 | `assets/bottle/` (아래) |
| SVG 인터랙션 | 페이지 안 4곳 + `snippets/` 독립 코드 4개 |
| 행동심리 카피 | `index.html` · `i18n/` — 라벨·승인된 사실과 숫자만 쓰고 `tools/check_copy.py`로 점검 |

## 구조

```
index.html          페이지 본문 (한국어 원문 + 번역용 data-t 키)
css/style.css       토큰·컴포넌트 (맨 위 :root 가 팔레트·서체)
js/main.js          아이콘·스크롤 스크럽·병 뷰어·냄비 스토리·계산기·후기·언어 전환·하단 바
js/i18n-data.js     번역 데이터 (자동 생성 — 직접 고치지 않음)
i18n/               ko.json(자동 추출) · ko.app.json(JS 문구·메타) · en.json · es.json
data/config.json    구매 링크·가격·환불 배지·연락처·인증 유효기간 (값 null이면 숨김)
data/reviews.json   후기 데이터 (지금은 '예시' 6건 — 아래 「후기」)
assets/bottle/      bottle-front.png(투명) · bottle-turn.webp/.gif(루프) · turn/(뷰어 프레임 72장)
assets/img · clips  연출 사진(WebP) · 연출 영상(MP4, 화면에 들어올 때만 재생)
snippets/           복붙용 SVG 인터랙션 4종 + index.html
tools/              render_turn · export_turn · serve · check_copy · i18n_extract · i18n_check · i18n_build · test_tools
```

## 언어 (KO · EN · ES)

한국어 원문은 `index.html`에 그대로 있고, 번역 단위마다 `data-t="키"`가 붙어 있습니다. 영어·스페인어는 `i18n/en.json`·`es.json`이 담당합니다. 선택한 언어는 브라우저에 기억됩니다.

문구를 고칠 때:

```bash
python3 tools/i18n_extract.py   # 1) index.html 을 고친 뒤 실행 — 새 요소에 키를 붙이고 i18n/ko.json 갱신(기존 키는 유지)
#  2) i18n/en.json · es.json 에서 바뀐 키의 번역을 고친다 (JS가 만드는 문구는 ko.app.json 이 원본)
python3 tools/i18n_check.py     # 3) 키 누락·HTML 태그·{자리표시자}·한글 잔존·금지 표현 검증
python3 tools/i18n_build.py     # 4) js/i18n-data.js 생성 (이걸 빼먹으면 test_tools 가 알려 줍니다)
```

- 번역은 **참고 번역**입니다. 원재료·영양정보·환불 안내의 법적 기준은 한국어 라벨/상품 페이지이고, 원재료명은 영어·스페인어 화면에서도 한국어 공식 표시를 함께 보여 줍니다.
- 영어·스페인어 화면에는 "연결되는 상점 페이지는 한국어이며 국내 배송만 안내" 문구가 붙습니다(자사몰 상품 페이지 표기 기준, 2026-09-20 확인).
- 스페인어는 중남미 공통어(존칭)로 옮겼습니다. 게시 전 원어민 검수를 권장합니다.

## 후기

지금 `data/reviews.json`의 6건은 **실제 후기가 아닌 예시**입니다. 카드마다 `예시` 표시와 안내문이 붙고, 후기의 일반적인 형식·길이를 참고하되 문장은 새로 썼습니다. 실제 후기가 생기면 `items`를 실제 후기로 교체하세요(`sample` 항목을 지우면 카드에 `구매 확인` 표시가 붙습니다). **게시 직전에는 `python3 tools/check_copy.py --publish`** — 예시가 남아 있으면 실패합니다.

## 병 이미지 (투명 PNG · 회전 루프)

AI 생성 없이 **실제 병 사진 + 승인 라벨 원본**을 원통에 투영해 72프레임(5° 간격) 360° 회전을 만들었습니다. 라벨 픽셀은 승인 아트워크에서만 가져오므로 문구·서체가 변하지 않고, 0° 프레임은 기존 승인 정면 렌더와 픽셀 단위로 같습니다(평균차 0).

| 파일 | 용도 |
|---|---|
| `assets/bottle/bottle-front.png` | 투명 배경 PNG(정면, 458×1443) |
| `assets/bottle/bottle-turn.webp` | 루프 애니메이션, 알파 투명(2.1MB) — 현대 브라우저 |
| `assets/bottle/bottle-turn.gif` | 루프 GIF, `#EFEBDE` 매트 합성(1.4MB) — 배경이 같은 곳용 |
| `assets/bottle/turn/turn-000~071.webp` | 페이지 뷰어(드래그·방향키·자동 회전)용 프레임 |

```bash
# 재생성 — 병 원본 사진·라벨 아트는 이 저장소에 없으므로 경로를 직접 지정합니다(라벨은 1871×965)
python3 tools/render_turn.py --base <병 원본.png> --zone <라벨 띠 좌표.json> \
        --label <라벨.png> --out-dir /tmp/turn-raw --frames 72
python3 tools/export_turn.py --frames-dir /tmp/turn-raw --out assets/bottle
```

## 자주 하는 수정과 점검

- 가격·링크·연락처 → `data/config.json` · 후기 → `data/reviews.json` · 한국어 문구 → `index.html`(+ 번역 갱신)
- 점검: `python3 tools/check_copy.py`(금지 표현·근거 없는 숫자·타 플랫폼 링크·영어/스페인어 후기 문구) · `python3 tools/test_tools.py`
- 타사 브랜드명 금지 목록은 저장소에 두지 않습니다. `tools/banned_brands.local.txt`(한 줄에 하나, git 제외)를 만들면 `check_copy.py`가 함께 검사합니다.
- 실제 병 자산으로 렌더까지 시험하려면 `S101_BOTTLE_BASE`(병 원본·띠 좌표 폴더)와 `S101_LABEL`(라벨 PNG)을 지정해 `test_tools.py`를 실행하세요(없으면 그 시험만 건너뜁니다).
