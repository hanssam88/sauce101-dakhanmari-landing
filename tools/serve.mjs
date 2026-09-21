#!/usr/bin/env node
// 정적 파일 서버 — 의존성 없음. 사용: node tools/serve.mjs [포트=3000]
// 이 폴더(index.html이 있는 곳)만 제공합니다. MP4 재생에 필요한 Range 요청을 지원합니다.
// 기본은 이 컴퓨터(127.0.0.1 · ::1)에서만 열립니다. 같은 와이파이의 휴대폰으로 보려면: HOST=0.0.0.0 node tools/serve.mjs
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { pipeline } from 'node:stream';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const port = Number(process.argv[2] || process.env.PORT || 3000);
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.md': 'text/markdown; charset=utf-8', '.txt': 'text/plain; charset=utf-8',
  '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml',
  '.mp4': 'video/mp4', '.ico': 'image/x-icon'
};

export function resolvePath(urlPath) {
  let rel;
  try { rel = decodeURIComponent(urlPath.split('?')[0]); } catch { return { status: 400 }; }
  let file = path.normalize(path.join(root, rel));
  if (file !== root && !file.startsWith(root + path.sep)) return { status: 403 };        // 폴더 밖 접근 차단
  const segs = path.relative(root, file).split(path.sep);
  if (segs.some(seg => seg.startsWith('.')) || segs[0] === 'docs') return { status: 404 };   // .git·.gitignore 같은 점 파일과 내부 문서(docs/)는 내보내지 않는다
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!fs.existsSync(file)) return { status: 404 };
  return { status: 200, file };
}

export function handler(req, res) {
  const r = resolvePath(req.url || '/');
  if (r.status !== 200) { res.writeHead(r.status, { 'Content-Type': 'text/plain; charset=utf-8' }); return res.end(`${r.status}`); }
  const size = fs.statSync(r.file).size;
  const type = MIME[path.extname(r.file).toLowerCase()] || 'application/octet-stream';
  const head = { 'Content-Type': type, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' };
  const send = opts => pipeline(fs.createReadStream(r.file, opts), res, () => {});        // 중간에 끊긴 요청에서도 파일 핸들이 남지 않게
  const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
  if (m && (m[1] || m[2])) {
    const start = m[1] ? Number(m[1]) : Math.max(0, size - Number(m[2]));             // bytes=-N 은 끝에서 N바이트(파일보다 크면 처음부터)
    let end = m[1] && m[2] ? Number(m[2]) : size - 1;
    if (start >= size || end < start) { res.writeHead(416, { 'Content-Range': `bytes */${size}` }); return res.end(); }
    end = Math.min(end, size - 1);
    res.writeHead(206, { ...head, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
    return send({ start, end });
  }
  res.writeHead(200, { ...head, 'Content-Length': size });
  send();
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const hosts = process.env.HOST ? [process.env.HOST] : ['127.0.0.1', '::1'];
  hosts.forEach((host, i) => {
    const server = http.createServer(handler);
    server.on('error', e => {
      if (i > 0 && (e.code === 'EAFNOSUPPORT' || e.code === 'EADDRNOTAVAIL')) return;   // ::1 은 IPv6 가 없는 환경이면 조용히 건너뛴다(포트 충돌 등은 알린다)
      console.error(`${host}: ${e.message}`);
      if (i === 0) process.exit(1);
    });
    server.listen(port, host, () => console.log(`http://localhost:${port}  ←  ${root}  (${host})`));
  });
}
