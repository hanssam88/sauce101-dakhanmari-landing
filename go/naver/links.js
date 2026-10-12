// NAVER: https://developers.naver.com/docs/utils/mobileapp/ (checked 2026-10-11)
// Chrome fallback: https://developer.chrome.com/docs/android/intents
export const STORE_URL = 'https://m.smartstore.naver.com/sauce101';

export function buildNaverLinks(target = STORE_URL) {
  const url = new URL(target);
  if (url.protocol !== 'https:' || url.hostname !== 'm.smartstore.naver.com' ||
      url.username || url.password || url.port ||
      !/^\/sauce101(?:\/|$)/.test(url.pathname) || /%2f|%5c/i.test(url.pathname)) {
    throw new TypeError('Only the Sauce101 HTTPS SmartStore is supported');
  }
  const encoded = encodeURIComponent(target);
  const command = `inappbrowser?url=${encoded}&target=new&version=6`;
  return {
    ios: `naversearchapp://${command}`,
    android: `intent://${command}#Intent;scheme=naversearchapp;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=com.nhn.android.search;S.browser_fallback_url=${encoded};end`,
    web: target
  };
}

export function appLinkForPlatform(userAgent, maxTouchPoints = 0) {
  const links = buildNaverLinks();
  if (/Android/i.test(userAgent)) return links.android;
  if (/iPhone|iPad|iPod/i.test(userAgent) || (/Macintosh/i.test(userAgent) && maxTouchPoints > 1)) return links.ios;
  return links.web;
}
