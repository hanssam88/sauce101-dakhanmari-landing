import test from 'node:test';
import assert from 'node:assert/strict';
import { buildNaverLinks, appLinkForPlatform, STORE_URL } from '../go/naver/links.js';

test('full product URL survives scheme and Android fallback encoding', () => {
  const target = STORE_URL + '/products/123?utm_source=instagram&utm_content=스토리 & DM&next=a%26b#옵션';
  const links = buildNaverLinks(target);
  const scheme = new URL(links.ios);
  assert.equal(scheme.protocol, 'naversearchapp:');
  assert.equal(scheme.hostname, 'inappbrowser');
  assert.equal(scheme.searchParams.get('url'), target);
  assert.equal(scheme.searchParams.get('target'), 'new');
  assert.equal(scheme.searchParams.get('version'), '6');
  const [intent, extras] = links.android.split('#Intent;');
  assert.equal(new URL(intent).searchParams.get('url'), target);
  assert.equal(extras.match(/package=([^;]+)/)[1], 'com.nhn.android.search');
  assert.equal(decodeURIComponent(extras.match(/S.browser_fallback_url=([^;]+)/)[1]), target);
});

test('rejects non-HTTPS, lookalike hosts, credentials, ports, and other stores', () => {
  for (const target of ['http://m.smartstore.naver.com/sauce101', 'javascript:alert(1)',
    'https://m.smartstore.naver.com.evil.test/sauce101', 'https://evil.test/?next=' + STORE_URL,
    'https://user:pass@m.smartstore.naver.com/sauce101', 'https://m.smartstore.naver.com:8443/sauce101',
    'https://m.smartstore.naver.com/another-store', STORE_URL + '-fake', STORE_URL + '/../other',
    'https://m.smartstore.naver.com/sauce101%2f..%2fother']) {
    assert.throws(() => buildNaverLinks(target), TypeError, target);
  }
});

test('platform selection keeps unknown environments on the web', () => {
  assert.equal(appLinkForPlatform('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)').startsWith('naversearchapp:'), true);
  assert.equal(appLinkForPlatform('Mozilla/5.0 (Linux; Android 15) Instagram').startsWith('intent:'), true);
  assert.equal(appLinkForPlatform('Mozilla/5.0 (Macintosh)', 5).startsWith('naversearchapp:'), true);
  assert.equal(appLinkForPlatform('Mozilla/5.0 (Macintosh)', 0), STORE_URL);
  assert.equal(appLinkForPlatform('unknown'), STORE_URL);
});

test('slashless bridge redirects once so relative assets work', async () => {
  const { createServer } = await import('node:http');
  const { handler } = await import('./serve.mjs');
  const server = createServer(handler);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const base = `http://127.0.0.1:${server.address().port}`;
    const response = await fetch(base + '/go/naver?utm_source=instagram', { redirect: 'manual' });
    assert.equal(response.status, 301);
    assert.equal(response.headers.get('location'), '/go/naver/?utm_source=instagram');
    const page = await fetch(base + response.headers.get('location'), { redirect: 'manual' });
    assert.equal(page.status, 200);
    assert.match(await page.text(), /소스101 스마트스토어로 이동합니다/);
    for (const asset of ['page.js', 'links.js', 'page.css']) {
      assert.equal((await fetch(base + '/go/naver/' + asset)).status, 200);
    }
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
});
