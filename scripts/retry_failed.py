#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Retry images that failed, unwrapping the now-defunct p.qpimg.cn proxy.

That proxy returns 502 today, but it wraps the real address in its `url`
query parameter -- unescape it and fetch directly.

Reads   data/images.json
Writes  images/* (and updates data/images.json)
Stdlib only. Python 3.8+.
"""
import json
import os
import urllib.parse as up
import urllib.request

BASE = os.environ.get('QZONE_OUT') or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
IMGDIR = os.path.join(BASE, 'images')

UA = os.environ.get('QZONE_UA') or (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36')

MAGIC = [(b'\xff\xd8\xff', '.jpg'), (b'\x89PNG\r\n\x1a\n', '.png'),
         (b'GIF87a', '.gif'), (b'GIF89a', '.gif'), (b'BM', '.bmp')]


def ext_of(data):
    for sig, e in MAGIC:
        if data.startswith(sig):
            return e
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return '.webp'
    return '.jpg'


def candidates(url):
    """Look behind the dead proxy, then try both schemes."""
    out = [url]
    if 'cgi_imgproxy' in url:
        inner = up.parse_qs(up.urlparse(url).query).get('url', [''])[0]
        if inner:
            out.append(inner)
            if inner.startswith('http://'):
                out.append(inner.replace('http://', 'https://', 1))
    if url.startswith('http://'):
        out.append(url.replace('http://', 'https://', 1))
    return out


def try_get(u):
    req = urllib.request.Request(u, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    path = os.path.join(DATA, 'images.json')
    if not os.path.exists(path):
        print('no %s — run scripts/download_images.py first' % path)
        return
    mp = json.load(open(path, encoding='utf-8'))

    fixed, still = 0, []
    for owner, d in mp.items():
        for idx, v in d.items():
            if v.get('ok'):
                continue
            name = 'ss_%s_%s' % (owner, idx) if not str(owner).isdigit() \
                else 'blog_%s_%s' % (owner, idx)
            got = False
            for u in candidates(v['url']):
                try:
                    data = try_get(u)
                    if len(data) > 128:
                        fn = name + ext_of(data)
                        with open(os.path.join(IMGDIR, fn), 'wb') as f:
                            f.write(data)
                        v['file'] = fn
                        v['ok'] = True
                        v['resolvedUrl'] = u
                        fixed += 1
                        got = True
                        break
                except Exception as e:  # noqa: BLE001
                    v['error'] = str(e)
            if not got:
                still.append((name, v['url'][:110]))

    json.dump(mp, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('recovered: %d, still failing: %d' % (fixed, len(still)))
    if still:
        print('these are permanently gone (dead third-party hosts).')
        print('the Markdown will keep their original URL as a placeholder.')
        for n, u in still:
            print('  %s  %s' % (n, u))


if __name__ == '__main__':
    main()
