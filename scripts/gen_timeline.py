#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a self-contained, offline timeline page from the exported shuoshuo.

Reads   data/shuoshuo.json, data/images.json, data/auth.json (optional)
Writes  QQ空间时间轴.html  at <root>/QQ空间时间轴.html

The page embeds all text as JSON and points at images/ by relative path, so
keep the .html and images/ together. It needs no network and no server:
double-click it.

Environment overrides:  QZONE_OUT             root dir
                        QZONE_TIMELINE_TITLE  page title (also the file name)
                        QZONE_TIMELINE_FILE   file name without .html, if it
                                              should differ from the title
Stdlib only. Python 3.8+.
"""
import html
import json
import os
import time
from urllib.parse import quote

from gen_markdown import clean_text, post_link

BASE = os.environ.get('QZONE_OUT') or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
TITLE = os.environ.get('QZONE_TIMELINE_TITLE') or 'QQ空间时间轴'
OUTFILE = os.path.join(BASE, (os.environ.get('QZONE_TIMELINE_FILE') or TITLE) + '.html')
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'timeline_template.html')

TITLE_MARK = '__TITLE__'
DATA_MARK = '__DATA__'


def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def fmt(ts):
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))


def pic_list(m, images):
    """One entry per picture: a local file if it was downloaded, else its URL."""
    per = images.get(str(m.get('tid')), {})
    out = []
    for i, pic in enumerate(m.get('pic') or []):
        rec = per.get(str(i)) or {}
        if rec.get('ok') and rec.get('file'):
            out.append({'f': 'images/' + quote(rec['file'])})
        else:
            out.append({'u': rec.get('url') or (pic or {}).get('url2') or ''})
    return out


def comment_list(clist):
    out = []
    for c in clist or []:
        item = {
            'n': clean_text(c.get('name') or ''),
            't': c.get('createTime2') or c.get('createTime') or '',
            'c': clean_text(c.get('content') or ''),
        }
        replies = [{
            'n': clean_text(r.get('name') or ''),
            't': r.get('createTime2') or r.get('createTime') or '',
            'c': clean_text(r.get('content') or ''),
        } for r in c.get('list_3') or []]
        if replies:
            item['r'] = replies
        out.append(item)
    return out


def build_item(m, images, uin):
    """Turn one raw shuoshuo record into the compact shape the page reads."""
    ts = int(m.get('created_time') or 0)
    it = {'ts': ts, 'd': fmt(ts) if ts else '', 'c': clean_text(m.get('content') or '')}

    rt = m.get('rt_con')
    if rt:
        it['rt'] = {
            'n': clean_text(m.get('rt_uinname') or ''),
            'c': clean_text(rt.get('content') if isinstance(rt, dict) else str(rt)),
        }

    ims = pic_list(m, images)
    if ims:
        it['im'] = ims

    videos = [v.get('url3') or v.get('url1') or '' for v in m.get('video') or []]
    if videos:
        it['v'] = videos
    audios = []
    for a in m.get('audio') or []:
        name = clean_text(a.get('name') or '')
        singer = clean_text(a.get('singername') or '')
        audios.append('%s — %s' % (singer, name) if singer and name else singer or name)
    if audios:
        it['au'] = audios

    lbs = m.get('lbs') or {}
    loc = clean_text(lbs.get('idname') or lbs.get('name') or '')
    if loc:
        it['loc'] = loc
    if m.get('source_name'):
        it['src'] = clean_text(m['source_name'])
    if m.get('cmtnum'):
        it['cm'] = int(m['cmtnum'])
    if m.get('fwdnum'):
        it['fw'] = int(m['fwdnum'])
    comments = comment_list(m.get('commentlist'))
    if comments:
        it['co'] = comments
    if m.get('tid'):
        it['l'] = post_link(uin, 'mood', m['tid'])
    return it


def build_items(shuoshuo, images, uin):
    items = [build_item(m, images, uin) for m in shuoshuo]
    items.sort(key=lambda e: -e['ts'])
    return items


def json_for_script(obj):
    """JSON that is safe inside <script type="application/json">.

    '<' is escaped everywhere, so neither '</script>' nor '<!--' can occur;
    U+2028/2029 are escaped for older parsers. All of these are plain JSON
    string escapes, so JSON.parse reads back the original text.
    """
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return (s.replace('<', '\\u003c')
             .replace(' ', '\\u2028')
             .replace(' ', '\\u2029'))


def render_page(template, title, payload):
    """Fill the template. The data is inserted last so it is never re-scanned."""
    head, sep, tail = template.partition(DATA_MARK)
    if not sep or DATA_MARK in tail:
        raise ValueError('template must contain %s exactly once' % DATA_MARK)
    safe_title = html.escape(title)
    return (head.replace(TITLE_MARK, safe_title) + json_for_script(payload)
            + tail.replace(TITLE_MARK, safe_title))


def main():
    shuoshuo = load('shuoshuo.json')
    if not shuoshuo:
        raise SystemExit('no shuoshuo found in %s — run fetch_shuoshuo.js first' % DATA)
    images = load('images.json') or {}
    auth = load('auth.json') or {}

    # Same fallback as gen_markdown: auth.json first, then the posts' own uin.
    uin = str(auth.get('uin') or '').strip()
    if not uin:
        for m in shuoshuo:
            if str(m.get('uin') or '').strip().isdigit():
                uin = str(m['uin']).strip()
                break

    items = build_items(shuoshuo, images, uin)
    payload = {
        'title': TITLE,
        'nick': clean_text(shuoshuo[0].get('name') or ''),
        'exported': time.strftime('%Y-%m-%d %H:%M'),
        'items': items,
    }
    with open(TEMPLATE, encoding='utf-8') as f:
        page = render_page(f.read(), TITLE, payload)
    with open(OUTFILE, 'w', encoding='utf-8') as f:
        f.write(page)

    n_img = sum(len(i.get('im', [])) for i in items)
    n_dead = sum(1 for i in items for p in i.get('im', []) if 'u' in p)
    print('wrote %s' % OUTFILE)
    print('  shuoshuo: %d, images: %d (dead %d)' % (len(items), n_img, n_dead))
    print('  size: %.2f MB' % (len(page.encode('utf-8')) / 1048576.0))
    print('  open it in a browser; keep it next to images/')


if __name__ == '__main__':
    main()
