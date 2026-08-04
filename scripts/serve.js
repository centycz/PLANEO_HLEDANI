#!/usr/bin/env node
/**
 * HOPLA — local preview server.
 *
 * Serves the site with gzip and long-lived asset caching, matching what a real
 * host (Netlify, Vercel, nginx) does. Plain `python3 -m http.server` sends
 * everything uncompressed, which makes Lighthouse measure the harness rather
 * than the site.
 *
 *   node scripts/serve.js . 8877
 */
const http = require('http'), fs = require('fs'), path = require('path'), zlib = require('zlib');
const ROOT = process.argv[2], PORT = +process.argv[3];
const TYPES = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8',
  '.js':'text/javascript; charset=utf-8', '.json':'application/json; charset=utf-8',
  '.webmanifest':'application/manifest+json', '.svg':'image/svg+xml', '.webp':'image/webp',
  '.png':'image/png', '.ico':'image/x-icon', '.woff2':'font/woff2', '.xml':'application/xml',
  '.txt':'text/plain; charset=utf-8' };
const COMPRESS = new Set(['.html','.css','.js','.json','.svg','.webmanifest','.xml','.txt']);
http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p.endsWith('/')) p += 'index.html';
  const file = path.join(ROOT, p);
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); return res.end('not found');
  }
  const ext = path.extname(file);
  const body = fs.readFileSync(file);
  const headers = { 'Content-Type': TYPES[ext] || 'application/octet-stream' };
  headers['Cache-Control'] = ext === '.html' ? 'no-cache' : 'public, max-age=31536000, immutable';
  if (COMPRESS.has(ext) && /gzip/.test(req.headers['accept-encoding'] || '')) {
    const gz = zlib.gzipSync(body, { level: 9 });
    res.writeHead(200, { ...headers, 'Content-Encoding': 'gzip', 'Content-Length': gz.length });
    return res.end(gz);
  }
  res.writeHead(200, { ...headers, 'Content-Length': body.length });
  res.end(body);
}).listen(PORT, () => console.log('serving', ROOT, 'on', PORT));
