#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download every picture referenced by the exported Qzone data.

Reads   data/shuoshuo.json, data/blog.json
Writes  images/*, data/images.json

Environment overrides:  QZONE_OUT (root dir), QZONE_WORKERS (default 8)
Stdlib only. Python 3.8+.
"""
import json
import os
import re
import sys
import html as htmlmod
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

# <root>/data and <root>/images ; allow relocation via QZONE_OUT
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get('QZONE_OUT') or BASE
DATA = os.path.join(BASE, 'data')
IMGDIR = os.path.join(BASE, 'images')
# Both must exist up front: images.json is written next to the data files, and
# failing there after a long download run would throw away all the work.
os.makedirs(DATA, exist_ok=True)
os.makedirs(IMGDIR, exist_ok=True)

WORKERS = int(os.environ.get('QZONE_WORKERS') or 8)
UA = os.environ.get('QZONE_UA') or (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36')

MAGIC = [
    (b'\xff\xd8\xff', '.jpg'),
    (b'\x89PNG\r\n\x1a\n', '.png'),
    (b'GIF87a', '.gif'),
    (b'GIF89a', '.gif'),
    (b'BM', '.bmp'),
]


def guess_ext(data, ctype=''):
    """File type comes from magic bytes, never from the URL extension."""
    for sig, ext in MAGIC:
        if data.startswith(sig):
            return ext
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return '.webp'
    ct = (ctype or '').lower()
    for key, ext in (('jpeg', '.jpg'), ('jpg', '.jpg'), ('png', '.png'),
                     ('gif', '.gif'), ('webp', '.webp'), ('bmp', '.bmp')):
        if key in ct:
            return ext
    return '.jpg'


def build_manifest():
    """Return a list of download jobs and backfill blog original image URLs."""
    jobs = []

    # ---- shuoshuo: url2 is the full-size original ----
    shuoshuo_path = os.path.join(DATA, 'shuoshuo.json')
    if os.path.exists(shuoshuo_path):
        ss = json.load(open(shuoshuo_path, encoding='utf-8'))
        for m in ss:
            for i, p in enumerate(m.get('pic') or []):
                url = p.get('url2') or p.get('url3') or p.get('url1') or p.get('smallurl')
                if not url:
                    continue
                jobs.append({
                    'name': 'ss_%s_%d' % (m['tid'], i),
                    'url': htmlmod.unescape(url),
                    'kind': 'shuoshuo',
                    'owner': m['tid'],
                    'idx': i,
                })
    else:
        print('note: %s not found, skipping shuoshuo pictures' % shuoshuo_path)

    # ---- blog: real image lives in the lazy-loading orgsrc attribute ----
    blog_path = os.path.join(DATA, 'blog.json')
    if os.path.exists(blog_path):
        bl = json.load(open(blog_path, encoding='utf-8'))
        for it in bl:
            h = it.get('contentHtml') or ''
            urls = []
            for tag in re.findall(r'<img[^>]*>', h, re.I):
                m = re.search(r'orgsrc\s*=\s*"([^"]+)"', tag, re.I) \
                    or re.search(r"orgsrc\s*=\s*'([^']+)'", tag, re.I) \
                    or re.search(r'\bsrc\s*=\s*"([^"]+)"', tag, re.I)
                if not m:
                    continue
                u = htmlmod.unescape(m.group(1))
                if 'loading.gif' in u or u.startswith('data:'):
                    continue
                urls.append(u)
            it['contentImgsOrg'] = urls
            for i, u in enumerate(urls):
                jobs.append({
                    'name': 'blog_%s_%d' % (it['blogId'], i),
                    'url': u,
                    'kind': 'blog',
                    'owner': it['blogId'],
                    'idx': i,
                })
        json.dump(bl, open(blog_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    else:
        print('note: %s not found, skipping blog pictures' % blog_path)

    return jobs


def fetch(job):
    url = job['url']
    last = None
    for _ in range(3):
        # try the URL as given, then https (some redirects refuse the cert)
        variants = [url]
        if url.startswith('http://'):
            variants.append(url.replace('http://', 'https://', 1))
        for candidate in variants:
            try:
                req = urllib.request.Request(candidate, headers={
                    'User-Agent': UA,
                    'Referer': 'https://user.qzone.qq.com/',
                    'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8',
                })
                with urllib.request.urlopen(req, timeout=40) as r:
                    data = r.read()
                    ctype = r.headers.get('Content-Type', '')
                if len(data) < 128:
                    last = 'response too small (%d bytes)' % len(data)
                    continue
                fname = job['name'] + guess_ext(data, ctype)
                with open(os.path.join(IMGDIR, fname), 'wb') as f:
                    f.write(data)
                job['file'] = fname
                job['bytes'] = len(data)
                job['ok'] = True
                return job
            except Exception as e:  # noqa: BLE001 - report per-job failures
                last = str(e)
    job['ok'] = False
    job['error'] = last
    return job


def main():
    jobs = build_manifest()
    print('images referenced by export: %d' % len(jobs))

    existing = {os.path.splitext(f)[0]: f for f in os.listdir(IMGDIR)}
    todo = []
    for j in jobs:
        if j['name'] in existing:
            j['file'] = existing[j['name']]
            j['ok'] = True
            j['bytes'] = os.path.getsize(os.path.join(IMGDIR, existing[j['name']]))
        else:
            todo.append(j)
    print('already on disk: %d, to fetch: %d' % (len(jobs) - len(todo), len(todo)))

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for _ in ex.map(fetch, todo):
            done += 1
            if done % 25 == 0 or done == len(todo):
                sys.stdout.write('\r  downloaded %d/%d' % (done, len(todo)))
                sys.stdout.flush()
    print('')

    ok = [j for j in jobs if j.get('ok')]
    bad = [j for j in jobs if not j.get('ok')]
    total_mb = sum(j.get('bytes', 0) for j in ok) / 1024.0 / 1024.0
    print('success: %d  failed: %d  total: %.1f MB' % (len(ok), len(bad), total_mb))
    if bad:
        print('next step: run scripts/retry_failed.py to unwrap dead image proxies')
        for j in bad[:10]:
            print('  %s  %s  %s' % (j['name'], j.get('error'), j['url'][:100]))

    mapping = {}
    for j in jobs:
        mapping.setdefault(str(j['owner']), {})[str(j['idx'])] = {
            'file': j.get('file'),
            'url': j['url'],
            'ok': bool(j.get('ok')),
        }
    json.dump(mapping, open(os.path.join(DATA, 'images.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('mapping -> %s' % os.path.join(DATA, 'images.json'))


if __name__ == '__main__':
    main()
