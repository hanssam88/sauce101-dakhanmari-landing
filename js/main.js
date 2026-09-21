/* 소스101 닭한마리육수 — 설득형 상세페이지 · 의존성 없음
   구성: 0 도우미 · 1 다국어(KO/EN/ES) · 2 설정 · 3 아이콘 · 4 등장/카운트 · 5 스크롤 스크럽 · 6 병 360° · 7 냄비 스토리
         8 계산기 · 9 활용 · 10 후기 · 11 상단·하단 바 · 12 시작 */
(() => {
'use strict';

/* ── 0. 도우미 ── */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const loadJSON = url => fetch(url, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : Promise.reject(r.status)));
const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

/* ── 1. 다국어 — 한국어는 문서에 그대로 있고, EN/ES 는 data-t 키로 바꿔 끼운다(js/i18n-data.js) ── */
const I18N = window.S101_I18N || { ko: {}, en: {}, es: {} };
const LANGS = ['ko', 'en', 'es'];
const NUMLOC = { ko: 'ko-KR', en: 'en-US', es: 'es' };
let LANG = 'ko';
const hooks = [];                                            // 언어가 바뀔 때 다시 그릴 함수들
const onLang = fn => hooks.push(fn);
const dict = () => I18N[LANG] || {};
const t = (key, vars) => {
  let s = dict()[key];
  if (s == null) s = (I18N.ko || {})[key];
  if (s == null) s = key;
  if (vars) for (const k in vars) s = s.split('{' + k + '}').join(vars[k]);
  return s;
};
const fmt = n => { try { return new Intl.NumberFormat(NUMLOC[LANG], { useGrouping: 'always' }).format(n); } catch (e) { return String(n); } };
const money = n => t('js.money', { n: fmt(n) });

// 한국어 원문을 아이콘이 채워지기 전에 저장한다(번역 후 한국어로 되돌릴 때 사용)
const textUnits = $$('[data-t]').map(el => { const ko = el.innerHTML; el.__html = ko; return { el, key: el.dataset.t, ko, keep: el.hasAttribute('data-keep-ko') }; });
const attrUnits = $$('[data-ta]').map(el => ({
  el, pairs: el.dataset.ta.split(';').map(p => p.split(':')).map(([attr, key]) => ({ attr, key, ko: el.getAttribute(attr) }))
}));
const META = {
  title: document.title, desc: $('meta[name="description"]').content,
  ogDesc: $('meta[property="og:description"]').content
};

function applyText() {
  const d = dict();
  textUnits.forEach(({ el, key, ko, keep }) => {
    const tr = LANG === 'ko' ? null : d[key];
    let html = tr != null ? tr : ko;
    if (keep && LANG !== 'ko') html += `<br><small class="ko-orig">${t('ui.official_ko')} ${ko}</small>`;   // 법정 표시는 한국어 원문을 함께
    if (el.__html !== html) { el.innerHTML = html; el.__html = html; hydrateIcons(el); }
  });
  attrUnits.forEach(({ el, pairs }) => pairs.forEach(({ attr, key, ko }) => {
    const tr = LANG === 'ko' ? null : d[key];
    el.setAttribute(attr, tr != null ? tr : ko);
  }));
}
function applyMeta() {
  const d = dict(), ko = LANG === 'ko';
  document.title = ko ? META.title : (d['meta.title'] || META.title);
  $('meta[name="description"]').content = ko ? META.desc : (d['meta.desc'] || META.desc);
  $('meta[property="og:title"]').content = document.title;
  $('meta[property="og:description"]').content = ko ? META.ogDesc : (d['meta.og_desc'] || META.ogDesc);
}
function setLang(lang, persist = true) {
  LANG = LANGS.includes(lang) ? lang : 'ko';
  document.documentElement.lang = LANG;
  applyText(); applyMeta();
  $$('.lang__btn').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lang === LANG)));
  hooks.forEach(fn => { try { fn(); } catch (e) { console.warn('[s101] 언어 훅 오류', e); } });   // 한 훅이 실패해도 계산기·후기와 아래 재배치는 계속 진행
  if (persist) {
    try { localStorage.setItem('s101-lang', LANG); } catch (e) { /* 저장 불가 환경 */ }
    try { const u = new URL(location.href); if (LANG === 'ko') u.searchParams.delete('lang'); else u.searchParams.set('lang', LANG); history.replaceState(null, '', u); } catch (e) { /* file:// 등 */ }
  }
  revealNow(); kick();                                          // 문구 길이가 달라지므로 위치·스크럽을 다시 계산
}
function initialLang() {
  const q = new URLSearchParams(location.search).get('lang');
  if (LANGS.includes(q)) return q;
  try { const s = localStorage.getItem('s101-lang'); if (LANGS.includes(s)) return s; } catch (e) { /* 무시 */ }
  return 'ko';
}

/* ── 2. 설정 — fetch 실패·file:// 에서도 동작하도록 기본값 내장 ── */
const DEFAULTS = {
  buy_url: 'https://sauce101.co.kr/product/detail.html?product_no=55',
  buy_label: '자사몰에서 구매하기',
  price: { list: 11900, sale: 9900, shipping_fee: 3000 },
  uses_per_bottle: 6,
  refund: { guarantee_days: null, guarantee_note: null },
  contact: { phone: '0507-1343-3918', email: 'hello@sauce101.co.kr' },
  certs: { haccp_valid_until: '2027-05-06', insurance_valid_until: '2027-06-23' },
  availability_note: null
};
const merge = (a, b) => {
  const o = { ...a };
  for (const k in b) o[k] = b[k] && typeof b[k] === 'object' && !Array.isArray(b[k]) ? merge(a[k] || {}, b[k]) : b[k];
  return o;
};
let CFG = DEFAULTS;

function applyConfig() {
  const cfg = CFG, contact = cfg.contact || {}, certs = cfg.certs || {};
  $$('[data-buy]').forEach(a => { a.href = cfg.buy_url; });
  $$('[data-cfg="buy_label"]').forEach(n => { n.textContent = LANG === 'ko' ? cfg.buy_label : t('cta.buy'); });
  $$('[data-cfg="phone"]').forEach(n => { n.textContent = contact.phone || ''; });
  $$('[data-cfg="email"]').forEach(n => { n.textContent = contact.email || ''; });

  const p = cfg.price || {}, uses = cfg.uses_per_bottle || 6;
  if (p.sale) {
    const per = Math.round(p.sale / uses);
    $('#priceBox').hidden = false;
    $('#priceSale').innerHTML = fmt(p.sale).replace(/[.,]/g, m => `<span class="cm">${m}</span>`);   // 고정폭 서체에서 구분 기호 간격이 벌어지지 않게
    const hasList = !!(p.list && p.list > p.sale);
    $('#priceList').hidden = !hasList; $('#priceOff').hidden = !hasList;
    if (hasList) { $('#priceList').textContent = money(p.list); $('#priceOff').textContent = Math.round((p.list - p.sale) / p.list * 100) + '%'; }
    $('#dockPrice').textContent = t('js.dock.price', { price: money(p.sale) });
    const perEl = $('#pricePer');
    perEl.hidden = !p.show_per_use;                            // 회당 원 환산은 계산값이라 기본은 숨김(data/config.json 의 show_per_use)
    if (p.show_per_use) {
      perEl.textContent = t('js.price.per', { uses, per: money(per) });
      $('#dockPrice').textContent = t('js.dock.price_per', { price: money(p.sale), per: money(per) });
    }
    const ship = $('#shipNote');
    ship.hidden = !p.shipping_fee;
    if (p.shipping_fee) ship.textContent = t('js.price.ship', { fee: money(p.shipping_fee) });
  } else {                                                       // 판매가가 null 이면 가격 문구를 모두 숨긴다(기본값으로 먼저 그려진 뒤 설정이 null 로 덮어써도 남지 않게)
    $('#priceBox').hidden = true; $('#shipNote').hidden = true;
    $('#dockPrice').textContent = t('js.dock.base');             // 하단 바는 용량·횟수만(한국어 사전에는 js.* 키만 있으므로 js.dock.base)
  }
  const note = LANG === 'ko' ? cfg.availability_note : (cfg.availability_note_i18n || {})[LANG];
  $('#availNote').hidden = !note; if (note) $('#availNote').textContent = note;
  const foreign = LANG === 'ko' ? '' : t('js.store.foreign');
  $('#foreignNote').hidden = !foreign; $('#foreignNote').textContent = foreign;

  const g = cfg.refund || {}, badge = $('#guaranteeBadge');
  badge.hidden = typeof g.guarantee_days !== 'number';
  if (!badge.hidden) badge.textContent = t('js.guarantee', { days: g.guarantee_days }) + (g.guarantee_note ? ` · ${g.guarantee_note}` : '');

  /* 인증·보험 유효기간이 지나면 만료 사실을 그대로 주장하지 않도록 표시 */
  const today = new Date();
  $$('.cert__v').forEach(v => { v.dataset.expired = t('js.cert.expired'); });
  [['haccp', certs.haccp_valid_until], ['insurance', certs.insurance_valid_until]].forEach(([k, d]) => {
    const el = $(`[data-until="${k}"]`); if (!el || !d) return;
    el.textContent = '~ ' + d.replace(/-/g, '.');
    const expired = today > new Date(d + 'T23:59:59+09:00');
    el.closest('.cert').classList.toggle('is-expired', expired);
    if (expired) console.warn(`[s101] ${k} 유효기간(${d})이 지났습니다 — data/config.json 의 certs 를 갱신하세요`);
  });
}
onLang(applyConfig);

/* ── 3. 순수 SVG 아이콘 — 선 그리기(--p 0→1)를 .d 요소가 이어받는다 ── */
const ICONS = {
  pot: '<path d="M12 27h40v17c0 6-4.5 10-10.5 10h-19C16.5 54 12 50 12 44z"/><path d="M16 27c0-7 7-11 16-11s16 4 16 11"/><path d="M29 12h6"/><path d="M12 33H6M52 33h6"/>',
  bottle: '<path d="M27 5h10v8H27z"/><path d="M28 13v6c-5 3-8 6-8 12v21a5 5 0 0 0 5 5h14a5 5 0 0 0 5-5V31c0-6-3-9-8-12v-6"/><path d="M20 34h24M20 46h24"/>',
  scale: '<path d="M9 36h46v16a4 4 0 0 1-4 4H13a4 4 0 0 1-4-4z"/><path d="M20 30c0-3 5-5 12-5s12 2 12 5"/><path d="M22 46a10 10 0 0 1 20 0"/><path d="M32 46l5-6"/>',
  cup: '<path d="M18 12h28l-4 40a3 3 0 0 1-3 3H25a3 3 0 0 1-3-3z"/><path d="M23 24h8M24 34h8M25 44h8"/>',
  drop: '<path d="M32 8c9 10 15 18 15 26a15 15 0 0 1-30 0c0-8 6-16 15-26z"/><path d="M25 38a7 7 0 0 0 5 6"/>',
  bowl: '<path d="M7 30h50c0 15-10 25-25 25S7 45 7 30z"/><path d="M23 58h18"/><path d="M23 22c-4-4 3-5-1-10M32 22c-4-4 3-5-1-10M41 22c-4-4 3-5-1-10"/>',
  noodle: '<path d="M7 32h50c0 14-10 23-25 23S7 46 7 32z"/><path d="M23 58h18"/><path d="M36 6l-8 24M43 8l-8 22"/><path d="M16 42q4-4 8 0t8 0t8 0"/>',
  porridge: '<path d="M7 32h50c0 14-10 23-25 23S7 46 7 32z"/><path d="M23 58h18"/><path d="M46 8l-9 20"/><path d="M45 4c4-1 7 1 7 4.5s-3 5-6 4"/><path d="M20 42h.01M28 46h.01M36 42h.01M44 46h.01"/>',
  dumpling: '<path d="M7 32h50c0 14-10 23-25 23S7 46 7 32z"/><path d="M23 58h18"/><path d="M18 32c0-8 6-12 12-12s12 4 12 12"/><path d="M46 32a5 3.5 0 0 1 10 0"/>',
  shield: '<path d="M32 6l20 7v15c0 14-9 24-20 30-11-6-20-16-20-30V13z"/><path d="M22 32l7 7 13-14"/>',
  calendar: '<path d="M11 14h42a3 3 0 0 1 3 3v34a3 3 0 0 1-3 3H11a3 3 0 0 1-3-3V17a3 3 0 0 1 3-3z"/><path d="M8 26h48M22 8v10M42 8v10"/><path d="M24 41l6 6 11-12"/>',
  thermo: '<path d="M27 12a5 5 0 0 1 10 0v26.5a11 11 0 1 1-10 0z"/><path d="M32 24v22"/>',
  drumstick: '<circle cx="41" cy="22" r="13"/><path d="M32 31L17 46"/><circle cx="13" cy="46" r="3.5"/><circle cx="18" cy="51" r="3.5"/>',
  shake: '<g transform="rotate(25 32 32)"><path d="M27 5h10v8H27z"/><path d="M28 13v6c-5 3-8 6-8 12v21a5 5 0 0 0 5 5h14a5 5 0 0 0 5-5V31c0-6-3-9-8-12v-6"/><path d="M20 34h24"/></g><path d="M9 24a24 24 0 0 1 6-11M55 40a24 24 0 0 1-6 11"/>',
  salt: '<path d="M22 22h20l4 8v22a4 4 0 0 1-4 4H22a4 4 0 0 1-4-4V30z"/><path d="M28 14h.01M32 10h.01M36 14h.01"/><path d="M18 30h28"/>',
  check: '<path d="M12 34l13 13 27-29"/>',
  info: '<circle cx="32" cy="32" r="23"/><path d="M32 29v15M32 21.5h.01"/>',
  arrow: '<path d="M10 32h42M40 18l14 14-14 14"/>'
};
function icon(name) {
  const body = ICONS[name]; if (!body) return '';
  let n = 0;
  const shapes = body.replace(/<(path|circle|ellipse|line|rect)\b/g, (m, tg) => `<${tg} class="d" pathLength="1" style="--s:${(n++ * .09).toFixed(2)}"`);
  return `<svg class="ico" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${shapes}</svg>`;
}
function hydrateIcons(root = document) { $$('[data-i]', root).forEach(el => { if (!el.firstElementChild) el.innerHTML = icon(el.dataset.i); }); }
hydrateIcons();
$$('.steam path').forEach(p => p.setAttribute('pathLength', '1'));

/* ── 4. 등장 · 카운트업 ── */
const stagger = new Map();
$$('.rv').forEach(el => {
  const n = stagger.get(el.parentElement) || 0; stagger.set(el.parentElement, n + 1);
  el.style.setProperty('--rd', Math.min(n, 4) * .07 + 's');
});
const reveal = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  e.target.classList.add('is-in'); reveal.unobserve(e.target);
}), { rootMargin: '0px 0px -8% 0px', threshold: .08 });
$$('.rv,[data-draw]').forEach(el => (RM ? el.classList.add('is-in') : reveal.observe(el)));
/* 히어로 문구는 화면 안이든 밖이든 처음부터 드러낸다 — 상단 배너 때문에 버튼이 관찰 문턱(-8%) 아래로 밀려도 스크롤 전까지 투명하게 남지 않게 */
requestAnimationFrame(() => requestAnimationFrame(() => $$('#top .rv').forEach(el => el.classList.add('is-in'))));
/* 보험: 관찰자 콜백이 늦게 와도 이미 화면에 들어온 요소는 드러낸다 */
const revealNow = () => $$('.rv:not(.is-in),[data-draw]:not(.is-in)').forEach(el => {
  const r = el.getBoundingClientRect();
  if (r.top < innerHeight * .92 && r.bottom > 0) { el.classList.add('is-in'); reveal.unobserve(el); }
});
addEventListener('load', () => { revealNow(); setTimeout(revealNow, 500); setTimeout(revealNow, 1500); });

function countUp(el) {
  const to = +el.dataset.count;
  if (RM) { el.textContent = to; return; }
  const t0 = performance.now(), dur = 1150;
  const step = now => {
    const k = clamp((now - t0) / dur);
    el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step); else el.textContent = to;
  };
  el.textContent = 0; requestAnimationFrame(step);
}
const counter = new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting) { countUp(e.target); counter.unobserve(e.target); }
}), { threshold: .6 });
$$('[data-count]').forEach(el => counter.observe(el));

/* ── 5. 스크롤 스크럽 — 목표값을 부드럽게 따라가며 --p 를 갱신 ── */
const progressOf = (el, startVh = .85, endVh = .35) => {
  const r = el.getBoundingClientRect(), vh = innerHeight;
  const a = vh * startVh, b = vh * endVh;
  return clamp((a - r.top) / (a - b + r.height));
};
const scrubs = [];
function addScrub(get, set) { const s = { get, set, cur: RM ? 1 : 0, target: 0 }; scrubs.push(s); return s; }
let looping = false;
function loop() {
  let moving = false;
  for (const s of scrubs) {
    s.target = s.get();
    const d = s.target - s.cur;
    if (Math.abs(d) > .0008) { s.cur += RM ? d : d * .14; moving = true; } else s.cur = s.target;
    s.set(s.cur);
  }
  looping = moving;
  if (moving) requestAnimationFrame(loop);
}
const kick = () => { if (!looping) { looping = true; requestAnimationFrame(loop); } };

$$('[data-track]').forEach(box => {
  const tracks = $$('.track', box);
  addScrub(() => progressOf(box, .88, .3), p => tracks.forEach(tr => {
    const rate = tr.classList.contains('track--short') ? 2.2 : 1;
    tr.style.setProperty('--p', clamp(p * rate).toFixed(4));
  }));
});

/* ── 6. 병 360° 뷰어 — 실제 병 사진 + 승인 라벨을 원통 투영한 72프레임 ── */
class Turntable {
  constructor(root) {
    this.root = root; this.cv = $('canvas', root); this.ctx = this.cv.getContext('2d'); this.img = $('img', root);
    this.N = 72; this.step = 360 / this.N; this.frames = new Array(this.N).fill(null);
    this.angle = 0; this.vel = 0; this.drag = false; this.lastX = 0; this.lastT = 0;
    this.lastInput = -1e9; this.visible = true; this.last = performance.now(); this.drawn = -1; this.raf = 0;
    this.bind(); this.load(); this.start();
  }
  src(i) { return `assets/bottle/turn/turn-${String(i).padStart(3, '0')}.webp`; }
  load() {
    const order = [], seen = new Set();
    for (const s of [18, 9, 3, 1]) for (let i = 0; i < this.N; i += s) if (!seen.has(i)) { seen.add(i); order.push(i); }
    const next = () => {
      const i = order.shift(); if (i === undefined) return;
      const im = new Image(); im.decoding = 'async';
      im.onload = () => { this.frames[i] = im; if (i === 0) { this.root.classList.add('is-live'); this.drawn = -1; this.render(); } next(); };
      im.onerror = next; im.src = this.src(i);
    };
    const go = () => { for (let k = 0; k < 4; k++) next(); };
    (window.requestIdleCallback || (f => setTimeout(f, 200)))(go);
  }
  nearest(idx) {
    for (let d = 0; d <= this.N / 2; d++) {
      const a = this.frames[(idx + d) % this.N]; if (a) return [a, (idx + d) % this.N];
      const b = this.frames[(idx - d + this.N) % this.N]; if (b) return [b, (idx - d + this.N) % this.N];
    }
    return [null, -1];
  }
  render() {
    const idx = ((Math.round(this.angle / this.step) % this.N) + this.N) % this.N;
    if (idx === this.drawn) return;
    const [f, real] = this.nearest(idx); if (!f) return;
    this.ctx.clearRect(0, 0, this.cv.width, this.cv.height);
    this.ctx.drawImage(f, 0, 0, this.cv.width, this.cv.height);
    this.drawn = idx === real ? idx : -1;
  }
  bind() {
    const r = this.root;
    r.addEventListener('pointerdown', e => {
      if (e.button !== 0 || e.ctrlKey) return;                   // 오른쪽 클릭·Ctrl+클릭(macOS 컨텍스트 메뉴)은 드래그가 아니다
      this.drag = true; this.vel = 0; this.lastX = e.clientX; this.lastT = performance.now(); this.lastInput = this.lastT;
      r.setPointerCapture(e.pointerId);
    });
    r.addEventListener('pointermove', e => {
      if (!this.drag) return;
      if (e.pointerType === 'mouse' && !e.buttons) { up(); return; }      // 버튼을 뗀 이벤트를 놓친 경우(창 밖에서 뗌 등) 드래그가 붙어 있지 않게
      const now = performance.now(), dx = e.clientX - this.lastX, dt = Math.max(1, now - this.lastT);
      this.angle -= dx * .62; this.vel = -dx * .62 / dt * 16; this.lastX = e.clientX; this.lastT = now; this.lastInput = now;
    });
    const up = () => { this.drag = false; this.lastInput = performance.now(); };
    r.addEventListener('pointerup', up); r.addEventListener('pointercancel', up);
    r.addEventListener('keydown', e => {
      if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !e.metaKey && !e.altKey && !e.ctrlKey) {     // Cmd/Alt+화살표(뒤로·앞으로 가기)는 가로채지 않는다
        e.preventDefault(); this.angle += (e.key === 'ArrowRight' ? -1 : 1) * this.step * 2; this.vel = 0; this.lastInput = performance.now();
      }
    });
    new IntersectionObserver(es => { this.visible = es[es.length - 1].isIntersecting; if (this.visible) this.start(); }).observe(r);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) this.start(); });
  }
  start() { if (!this.raf) { this.last = performance.now(); this.raf = requestAnimationFrame(tm => this.tick(tm)); } }
  tick(now) {
    this.raf = 0;
    if (!this.visible || document.hidden) return;
    const dt = Math.min(48, now - this.last); this.last = now;
    if (!this.drag) {
      if (Math.abs(this.vel) > .04) { this.angle += this.vel * dt / 16; this.vel *= Math.pow(.94, dt / 16); }
      else if (!RM && now - this.lastInput > 2600) {
        /* 정면 근처에서는 느리게 머물고, 나머지는 천천히 한 바퀴 */
        const m = ((this.angle % 360) + 360) % 360, d = Math.min(m, 360 - m);
        const s = clamp(d / 25), speed = 34 * (.18 + .82 * s * s * (3 - 2 * s));
        this.angle += speed * dt / 1000;
      }
    }
    this.render();
    this.start();
  }
}
const turntable = $('#turntable');
if (turntable) new Turntable(turntable);

/* ── 7. 냄비 스토리 — 스크롤 위치(p 0→1)가 장면을 정한다 ──
   ① 병을 흔든다(층이 섞인다) ② 수도에서 물 450g(눈금자가 켜진다) → 저울 영점 → 병을 옮겨 육수 50g ③ 재료를 넣고 불을 켜 끓인다.
   저울 표시창이 물 0→450g, 육수 0→50g 을 센다. 값은 모두 p 에서 계산해 .story__panel 의 CSS 변수와 몇 개의 transform 으로 넣는다. */
const story = $('#how');
if (story) try {
  const svg = $('#storySvg'), panel = $('.story__panel', story), steps = $$('.step', story), steps0 = $('.story__steps', story);
  const el = { bottle: $('.bottle', svg), num: $('.ro-n', svg), ing: $$('.ing', svg), rip: $$('.rpi', svg) };
  const seg = (p, a, b) => clamp((p - a) / (b - a));
  const lerp = (a, b, k) => a + (b - a) * k;
  const spring = k => (k <= 0 ? 0 : k >= 1 ? 1 : 1 - Math.exp(-7 * k) * Math.cos(2.5 * Math.PI * k));      // 살짝 넘쳤다 자리 잡는 움직임
  const back = k => { const c = 1.25, x = clamp(k) - 1; return 1 + (c + 1) * x * x * x + c * x * x; };     // 천천히 출발해 조금 지나쳤다 돌아오는 이동
  const REST = [{ x: 190, y: 223, r: -10 }, { x: 294, y: 229, r: 6 }, { x: 242, y: 213, r: -2 }];        // 재료가 뜨는 자리(닭 · 감자 · 대파)
  const DROP = [{ at: .74, land: .795, dx: 34, spin: -150 }, { at: .775, land: .83, dx: -26, spin: 120 }, { at: .81, land: .865, dx: 14, spin: -90 }];
  const state = p => {
    const sh = seg(p, .08, .285), env = Math.min(sh / .1, 1) * Math.min((1 - sh) / .12, 1);
    const shk = sh > 0 && sh < 1 ? Math.sin(sh * Math.PI * 14) * env : 0;                                  // 위아래로 흔들기
    const water = ease(seg(p, .36, .5)), glide = back(seg(p, .285, .34)), lift = Math.sin(seg(p, .52, .56) * Math.PI);
    const tilt = ease(seg(p, .55, .62)) * (1 - spring(seg(p, .68, .76))), exit = ease(seg(p, .74, .8));
    const flow = seg(p, .6, .665), broth = p >= .515, bs = lerp(2.3, 1.5, glide), pour = seg(p, .595, .63), pend = seg(p, .665, .7);
    return {
      shk, water, bs, bmix: ease(seg(p, .1, .27)),
      tap: ease(seg(p, .345, .375)) * (1 - ease(seg(p, .5, .53))),
      pour, pend, pourOn: p > .595 && p < .7 ? 1 : 0, splash: clamp((pour - .85) / .15) * (1 - clamp((pend - .3) / .3)),   // splash: 줄기가 수면에 닿은 동안만
      cloud: ease(seg(p, .61, .72)), mixo: ease(seg(p, .64, .75)),
      bx: lerp(240, 372, glide) + exit * 60, by: lerp(96, 98, glide) - lift * 10 + shk * 10, ba: tilt * -128 + lift * 8 + shk * 5, bo: 1 - exit,
      ro: ease(seg(p, .345, .38)) * (1 - ease(seg(p, .7, .74))), rob: seg(p, .51, .52),
      num: broth ? Math.round(50 * flow) : Math.round(450 * water), rofrac: broth ? flow : water,                // 물 0→450 · 영점 · 육수 0→50
      roflash: Math.sin(seg(p, .505, .535) * Math.PI),
      fire: ease(seg(p, .79, .87)), boil: seg(p, .86, .95), steam: seg(p, .85, 1),
      ing: DROP.map((d, i) => {
        const f = seg(p, d.at, d.land), k = seg(p, d.land, d.land + .045), r = REST[i];
        return { x: r.x + (1 - f) * d.dx, y: r.y - 250 * (1 - f * f) + Math.sin(k * Math.PI * 2.4) * (1 - k) * 7, r: r.r + (1 - f) * d.spin,
                 o: clamp(f * 40), rk: seg(p, d.land, d.land + .055), ron: p >= d.land ? 1 : 0 };
      })
    };
  };
  const setVars = o => { for (const k in o) panel.style.setProperty('--' + k, +o[k].toFixed(4)); };
  const apply = s => {
    setVars({ lv: s.water > 0 ? .06 + .68 * s.water : 0, fillr: s.water, tap: s.tap, pour: s.pour, pend: s.pend, pourOn: s.pourOn, splash: s.splash, cloud: s.cloud, mixo: s.mixo,
      shk: s.shk, shkA: Math.abs(s.shk), bmix: s.bmix, ro: s.ro, rob: s.rob, rofrac: s.rofrac, roflash: s.roflash,
      fire: s.fire, boil: s.boil, steam: s.steam, bsw: 3 / s.bs });                                          // bsw: 병이 커져도 선 굵기는 그대로
    el.bottle.style.transform = `translate(${s.bx.toFixed(1)}px,${s.by.toFixed(1)}px) rotate(${s.ba.toFixed(2)}deg) scale(${s.bs.toFixed(3)}) translate(-32px,-32px)`;
    el.bottle.style.opacity = s.bo.toFixed(3);
    if (el.num.textContent !== String(s.num)) el.num.textContent = s.num;
    s.ing.forEach((g, i) => {
      el.ing[i].style.transform = `translate(${g.x.toFixed(1)}px,${g.y.toFixed(1)}px) rotate(${g.r.toFixed(1)}deg)`;
      el.ing[i].style.opacity = g.o.toFixed(3);
      el.rip[i].style.setProperty('--rk', g.rk.toFixed(3)); el.rip[i].style.setProperty('--ron', g.ron);
    });
  };
  /* 읽는 기준선: 데스크톱은 화면 가운데, 모바일은 고정 패널 아래 영역의 가운데 */
  const stick = $('.story__stick', story), narrow = matchMedia('(max-width: 899px)');
  const readLine = () => (narrow.matches ? (stick.getBoundingClientRect().bottom + innerHeight) / 2 : innerHeight * .5);
  const prog = () => {
    const r = steps0.getBoundingClientRect(), mid = readLine(), a = mid + innerHeight * .12, b = mid - innerHeight * .08;
    return clamp((a - r.top) / (a - b + r.height));
  };
  if (RM) apply(state(1));
  else { apply(state(0)); addScrub(prog, p => apply(state(Number.isFinite(p) ? p : 0))); }
  /* 기준선에 가장 가까운 단계를 강조 */
  const mark = () => {
    const mid = readLine(); let best = 0, bd = 1e9;
    steps.forEach((s, i) => { const r = s.getBoundingClientRect(), d = Math.abs(r.top + r.height / 2 - mid); if (d < bd) { bd = d; best = i; } });
    steps.forEach((s, i) => s.classList.toggle('is-active', i === best));
    story.dataset.active = best;
  };
  addScrub(() => { mark(); return 0; }, () => {});
  /* 화면 밖에서는 물결·김·불꽃 같은 반복 움직임을 멈춘다 */
  new IntersectionObserver(es => story.classList.toggle('is-off', !es[es.length - 1].isIntersecting), { rootMargin: '120px' }).observe(story);
} catch (e) { console.warn('[s101] 냄비 스토리를 시작하지 못했습니다 — 나머지 구역은 계속 동작합니다', e); }

/* ── 8. 계산기 — 2인분(육수 50g + 물 450g) 비율을 그대로 곱한 값 ── */
(() => {
  const panel = $('#calcPanel'); if (!panel) return;
  const st = { people: 2, s: 'base' };
  const WATER = { light: 250, base: 225, rich: 200 };          // 1인당 물(g): 2인분 500 / 450 / 400
  const FILL = { light: .88, base: .8, rich: .72 };            // 그릇 수위 ∝ 육수+물 합계(연하게 550g : 기본 500g : 진하게 450g). 물이 많은 연하게가 가장 높다
  const render = () => {
    const base = 25 * st.people, water = WATER[st.s] * st.people;
    const uses = Math.floor(330 / base), left = 330 - uses * base;
    $('#peopleVal').textContent = st.people;
    $('#outBase').textContent = base; $('#outWater').textContent = water;
    $('#outTimes').textContent = uses; $('#outLeft').textContent = left;
    const bowl = $('.bowl', panel); bowl.dataset.s = st.s; bowl.style.setProperty('--fill', FILL[st.s]);
    const name = t('js.calc.name.' + st.s);
    $('#calcNote').textContent = st.people === 2
      ? t('js.calc.note.two', { name, quarter: st.s === 'base' ? t('js.calc.quarter') : '', water, cup: t('js.calc.cup.' + st.s) })
      : t('js.calc.note.n', { name, n: st.people, base, water });
    $$('[data-strength]', panel).forEach(b => b.setAttribute('aria-checked', b.dataset.strength === st.s));
  };
  $$('[data-people]', panel).forEach(b => b.addEventListener('click', () => { st.people = clamp(st.people + +b.dataset.people, 1, 6); render(); }));
  $$('[data-strength]', panel).forEach(b => b.addEventListener('click', () => { st.s = b.dataset.strength; render(); }));
  onLang(render);
  render();
})();

/* ── 9. 활용 — 사진 위 점과 목록을 함께 움직인다 · 영상은 화면에 들어올 때만 재생 ── */
(() => {
  const dots = $$('.hot'), items = $$('.menu');
  const pick = i => { dots.forEach(d => d.classList.toggle('is-on', +d.dataset.menu === i)); items.forEach(m => m.classList.toggle('is-on', +m.dataset.menu === i)); };
  dots.forEach(d => d.addEventListener('click', () => pick(+d.dataset.menu)));
  items.forEach(m => m.addEventListener('click', () => pick(+m.dataset.menu)));
  pick(0);
  const vio = new IntersectionObserver(es => es.forEach(e => {
    const v = e.target;
    if (e.isIntersecting) { if (!v.src) v.src = v.dataset.src; v.play().catch(() => {}); } else v.pause();
  }), { threshold: .35 });
  $$('.clip video').forEach(v => { if (RM) { v.controls = true; v.src = v.dataset.src; } else vio.observe(v); });
})();

/* ── 10. 후기 — 실제 후기만 싣는다. 예시(sample:true)는 표시가 붙고, 데이터가 없으면 안내를 보여 준다 ── */
const REV = { loaded: false, items: [], meta: {} };
const nn = (a, b) => (a != null ? a : b);                        // ?? 는 오래된 인앱 브라우저에서 문법 오류라 쓰지 않는다
const pick = v => (v && typeof v === 'object' ? nn(v[LANG], nn(v.ko, '')) : nn(v, ''));
function renderReviews() {
  if (!REV.loaded) return;                                     // 불러오기 전에는 빈 안내가 깜빡이지 않게
  const list = $('#revList'), head = $('#revHead'), tagsBox = $('#revTags'), note = $('#revNote'), empty = $('#revEmpty');
  const items = REV.items, labels = REV.meta.tag_labels || {};
  list.textContent = '';
  empty.hidden = items.length > 0;
  if (!items.length) { head.hidden = true; tagsBox.hidden = true; note.hidden = true; return; }
  note.hidden = !items.some(r => r.sample);
  items.forEach(r => {
    const c = mk('article', 'rev'), top = mk('div', 'rev__top');
    const n = clamp(Math.round(Number(r.rating) || 0), 0, 5);        // 범위 밖·누락된 별점이 목록 전체를 깨뜨리지 않게
    const stars = mk('span', 'rev__stars', '★'.repeat(n) + '☆'.repeat(5 - n));
    stars.setAttribute('aria-label', t('js.rev.stars', { n }));
    top.append(stars);
    if (r.sample) top.append(mk('span', 'rev__badge rev__badge--sample', t('js.rev.sample')));
    else if (r.verified) top.append(mk('span', 'rev__badge', t('js.rev.verified')));
    c.append(top);
    if (r.option) c.append(mk('p', 'rev__opt', t('js.rev.option', { opt: pick(r.option) })));
    c.append(mk('p', 'rev__text', pick(r.text)));
    if (r.tags && r.tags.length) { const tg = mk('div', 'rev__tags'); r.tags.forEach(id => tg.append(mk('span', '', pick(labels[id]) || id))); c.append(tg); }
    c.append(mk('small', '', [pick(r.name), r.date].filter(Boolean).join(' · ')));
    list.append(c);
  });
  /* 요약: 예시만 있을 때는 가상의 평균·총건수를 만들지 않고 '예시 N건'만 보여 준다. 실제 후기는 출처·기준일이 있어야 평균을 계산한다 */
  const allSample = items.every(r => r.sample), src = pick(REV.meta.source);
  const rated = items.map(r => Number(r.rating)).filter(v => v >= 1 && v <= 5);      // 별점이 없거나 범위 밖인 후기는 평균에서 뺀다
  head.textContent = '';
  if (allSample) {
    head.hidden = false; head.append(mk('span', 'rev-head__sample', t('js.rev.sample_count', { n: items.length })));
  } else if (src && REV.meta.as_of && rated.length) {
    const avg = (rated.reduce((a, v) => a + v, 0) / rated.length).toFixed(1);
    const b = mk('b', 'mono', avg); b.setAttribute('aria-label', t('js.rev.avg', { avg }));
    head.hidden = false; head.append(b, mk('span', '', t('js.rev.count', { n: items.length, source: src, asof: REV.meta.as_of })));
  } else head.hidden = true;
  const counts = {};
  items.forEach(r => (r.tags || []).forEach(id => { counts[id] = (counts[id] || 0) + 1; }));
  const ids = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
  tagsBox.hidden = !ids.length; tagsBox.textContent = '';
  ids.forEach(id => {
    const chip = mk('span', 'rev-tag', pick(labels[id]) || id);
    if (!allSample) chip.append(' ', mk('b', 'mono', String(counts[id])));       // 예시의 키워드에는 건수를 붙이지 않는다
    tagsBox.append(chip);
  });
}
onLang(renderReviews);

/* ── 11. 상단 바 · 하단 구매 바 · 히어로 준비 ── */
(() => {
  const bar = $('#bar'), dock = $('#dock'), hero = $('#top'), fin = $('#final');
  let finalOn = false;
  const upd = () => {
    bar.classList.toggle('is-solid', scrollY > 24);
    const on = scrollY > hero.offsetHeight * .7 && !finalOn;
    dock.classList.toggle('is-on', on); dock.setAttribute('aria-hidden', !on);
    $$('a', dock).forEach(a => { a.tabIndex = on ? 0 : -1; });
  };
  new IntersectionObserver(es => { finalOn = es[es.length - 1].isIntersecting; upd(); }, { threshold: .25 }).observe(fin);
  addEventListener('scroll', upd, { passive: true }); upd();
  const ready = () => hero.classList.add('is-ready');
  if (document.readyState === 'complete') setTimeout(ready, 120); else addEventListener('load', () => setTimeout(ready, 120));
})();

/* ── 12. 시작 ── */
$$('.lang__btn').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));
addEventListener('scroll', kick, { passive: true });
addEventListener('resize', kick);
setLang(initialLang(), false);                                 // 훅으로 설정·계산기·후기가 모두 한 번 그려진다
loadJSON('data/config.json').then(c => { CFG = merge(DEFAULTS, c); applyConfig(); }).catch(e => console.warn('[s101] data/config.json 을 적용하지 못해 기본값을 씁니다', e));
loadJSON('data/reviews.json').then(d => { REV.items = d.items || []; REV.meta = d.meta || {}; }).catch(e => console.warn('[s101] data/reviews.json 을 불러오지 못했습니다', e)).then(() => { REV.loaded = true; renderReviews(); });
kick();
window.S101_READY = true;                                   // index.html 의 4초 안전장치가 이 표시를 본다(스크립트가 죽으면 본문을 강제로 보이게)
})();
