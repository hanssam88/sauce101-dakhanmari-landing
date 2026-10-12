import { appLinkForPlatform, STORE_URL } from './links.js';

const app = document.querySelector('#open-app');
const appStatus = document.querySelector('#app-status');
const help = document.querySelector('#app-help');
app.href = appLinkForPlatform(navigator.userAgent, navigator.maxTouchPoints);
if (app.href === STORE_URL) {
  appStatus.textContent = '이 환경에서는 웹 스토어로 이동합니다. 휴대폰에서 앱 연결을 시도할 수 있습니다.';
}
app.addEventListener('click', () => {
  // Keep the native anchor's user gesture. No timers, install detection or redirects.
  help.open = true;
  appStatus.textContent = app.href === STORE_URL
    ? '이 환경에서는 웹 스토어로 이동합니다.'
    : '앱이 열리지 않았다면 아래 안내를 확인하거나 ‘웹에서 보기’를 눌러 주세요.';
});

// Copy the clean HTTPS bridge, never an incoming target/query or a custom scheme.
const shareUrl = new URL('./', import.meta.url).href;
const copy = document.querySelector('#copy-link');
const copyStatus = document.querySelector('#copy-status');
const manual = document.querySelector('#manual-copy');
const input = document.querySelector('#copy-url');
input.value = shareUrl;
copy.hidden = false;
copy.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(shareUrl);
    manual.hidden = true;
    copyStatus.textContent = '링크를 복사했습니다. Safari 또는 Chrome의 주소창에 붙여넣어 주세요.';
  } catch {
    manual.hidden = false;
    copyStatus.textContent = '자동으로 복사하지 못했습니다. 아래 링크를 길게 눌러 복사해 주세요.';
    input.focus();
    input.select();
    input.setSelectionRange(0, input.value.length);
  }
});
