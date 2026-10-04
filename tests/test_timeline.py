#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Self-test for the timeline page generator (scripts/gen_timeline.py).

Covers the data shaping, the script-embedding safety, and an end-to-end run
into a temp directory. No network, no browser needed. The inline page script
is syntax-checked with Node when Node is on PATH.

Usage: python tests/test_timeline.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')
sys.path.insert(0, SCRIPTS)

from gen_timeline import (  # noqa: E402
    build_item, build_items, json_for_script, render_page, pic_list,
    TITLE_MARK, DATA_MARK, TEMPLATE)

PASS, FAIL = 0, 0


def eq(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print('FAIL  %s\n      got : %r\n      want: %r' % (label, got, want))


def has(label, needle, haystack):
    global PASS, FAIL
    if needle in haystack:
        PASS += 1
    else:
        FAIL += 1
        print('FAIL  %s\n      %r not found in %r' % (label, needle, haystack[:200]))


def ts(text):
    return int(time.mktime(time.strptime(text, '%Y-%m-%d %H:%M:%S')))


# ---- text and time ----
it = build_item({'tid': 't1', 'created_time': ts('2020-03-12 18:30:00'),
                 'content': '你好 @{uin:1,nick:小明,who:1}[em]e113[/em]'}, {}, '123')
eq('text is cleaned like the markdown output', it['c'], '你好 @小明[呲牙]')
eq('timestamp becomes a local date string', it['d'], '2020-03-12 18:30')
eq('ts is kept for sorting', it['ts'], ts('2020-03-12 18:30:00'))

undated = build_item({'tid': 't2', 'content': 'x'}, {}, '')
eq('missing timestamp -> empty date, not 1970', undated['d'], '')

# ---- pictures ----
m = {'tid': 'a', 'pic': [{'url2': 'http://x/1.jpg'}, {'url2': 'http://x/2.jpg'},
                         {'url2': 'http://x/3.jpg'}]}
imgs = {'a': {'0': {'file': 'p.png', 'ok': True, 'url': 'http://x/1.jpg'},
              '1': {'file': None, 'ok': False, 'url': 'http://dead/2.jpg'}}}
eq('downloaded pic -> relative file', pic_list(m, imgs)[0], {'f': 'images/p.png'})
eq('failed pic keeps its original URL', pic_list(m, imgs)[1], {'u': 'http://dead/2.jpg'})
eq('pic unknown to images.json falls back to url2', pic_list(m, imgs)[2], {'u': 'http://x/3.jpg'})
eq('file names are URL-quoted',
   pic_list({'tid': 'b', 'pic': [{}]},
            {'b': {'0': {'file': '图 a.png', 'ok': True}}})[0],
   {'f': 'images/%E5%9B%BE%20a.png'})

# ---- repost, place, media ----
rt = build_item({'tid': 'r', 'rt_uinname': '某号', 'rt_con': {'content': '原文[em]e100[/em]'}}, {}, '')
eq('repost from a dict', rt['rt'], {'n': '某号', 'c': '原文[微笑]'})
eq('repost from a plain string',
   build_item({'tid': 'r', 'rt_con': '原文'}, {}, '')['rt'], {'n': '', 'c': '原文'})
eq('place prefers idname',
   build_item({'tid': 'l', 'lbs': {'idname': 'A', 'name': 'B'}}, {}, '')['loc'], 'A')
eq('place falls back to name',
   build_item({'tid': 'l', 'lbs': {'idname': '', 'name': 'B'}}, {}, '')['loc'], 'B')
media = build_item({'tid': 'v', 'video': [{'url3': 'http://v/1.mp4'}],
                    'audio': [{'singername': '歌手', 'name': '歌名'}]}, {}, '')
eq('video url', media['v'], ['http://v/1.mp4'])
eq('audio line', media['au'], ['歌手 — 歌名'])

# ---- comments ----
cm = build_item({'tid': 'c', 'cmtnum': 2, 'commentlist': [{
    'name': 'A', 'createTime2': '2020-01-01 10:00:00', 'content': '嗯 [em]e100[/em]',
    'list_3': [{'name': 'B', 'createTime2': '2020-01-01 10:05:00', 'content': '好'}]}]}, {}, '')
eq('comment count from the API', cm['cm'], 2)
eq('comment body is cleaned', cm['co'][0]['c'], '嗯 [微笑]')
eq('replies are nested', cm['co'][0]['r'], [{'n': 'B', 't': '2020-01-01 10:05:00', 'c': '好'}])

# ---- links and compactness ----
eq('permalink with uin',
   build_item({'tid': 'abc'}, {}, '12345')['l'], 'https://user.qzone.qq.com/12345/mood/abc')
eq('permalink without uin has no double slash',
   build_item({'tid': 'abc'}, {}, '')['l'], 'https://user.qzone.qq.com/mood/abc')
eq('empty fields are left out',
   sorted(build_item({'tid': 'z', 'created_time': 1, 'content': 'x'}, {}, '')),
   ['c', 'd', 'l', 'ts'])

# ---- ordering ----
order = build_items([{'tid': 'old', 'created_time': ts('2010-01-01 00:00:00')},
                     {'tid': 'new', 'created_time': ts('2020-01-01 00:00:00')}], {}, '')
eq('newest first', [i['l'].rsplit('/', 1)[1] for i in order], ['new', 'old'])

# ---- embedding safety ----
nasty = {'t': '</script><script>alert(1)</script><!-- x     "q" \\'}
blob = json_for_script(nasty)
eq('no < survives, so no </script> or <!--', '<' in blob, False)
eq('escaped JSON reads back unchanged', json.loads(blob), nasty)

tpl = '<title>' + TITLE_MARK + '</title><script>' + DATA_MARK + '</script>'
page = render_page(tpl, '<b>x</b>', {'items': [{'c': '__TITLE__'}]})
has('title is HTML-escaped', '&lt;b&gt;x&lt;/b&gt;', page)
has('data is never re-scanned for markers', '"c":"__TITLE__"', page)
eq('hostile text cannot add a closing script tag', page.count('</script>'), 1)
for bad in ('no marker here', DATA_MARK + DATA_MARK):
    try:
        render_page(bad, 't', {})
        eq('template without exactly one marker is rejected: %r' % bad, 'accepted', 'ValueError')
    except ValueError:
        eq('template without exactly one marker is rejected', True, True)

# ---- the real template ----
with open(TEMPLATE, encoding='utf-8') as f:
    real = f.read()
eq('template has one data marker', real.count(DATA_MARK), 1)
has('template puts the title in <title>', '<title>' + TITLE_MARK + '</title>', real)
eq('template loads nothing from the network',
   re.findall(r'(?:src|href)\s*=\s*"https?://', real), [])
eq('template has no external stylesheet/script', re.findall(r'<link[^>]+stylesheet', real), [])

node = shutil.which('node')
if node:
    code = re.findall(r'<script>\n(.*?)</script>', real, re.S)[-1]
    tmp = tempfile.mkdtemp()
    try:
        js = os.path.join(tmp, 'page.js')
        with open(js, 'w', encoding='utf-8') as f:
            f.write(code)
        r = subprocess.run([node, '--check', js], capture_output=True, text=True)
        eq('page script passes node --check', (r.returncode, r.stderr.strip()), (0, ''))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
else:
    print('skip  node not found, page script syntax not checked')

# ---- end to end, into a temp dir ----
tmp = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(tmp, 'data'))
    with open(os.path.join(tmp, 'data', 'shuoshuo.json'), 'w', encoding='utf-8') as f:
        json.dump([
            {'tid': 'a1', 'created_time': ts('2021-05-01 09:00:00'), 'name': '昵称',
             'content': '第一条 </script> 试试', 'pic': [{'url2': 'http://x/1.jpg'}]},
            {'tid': 'a2', 'created_time': ts('2022-06-02 10:00:00'), 'content': '第二条'},
        ], f, ensure_ascii=False)
    env = dict(os.environ, QZONE_OUT=tmp, PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'gen_timeline.py')],
                       env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    eq('generator exits 0', r.returncode, 0)
    out = os.path.join(tmp, 'QQ空间时间轴.html')
    eq('default output file is written', os.path.exists(out), True)
    if os.path.exists(out):
        with open(out, encoding='utf-8') as f:
            html_out = f.read()
        has('page title is set', '<title>QQ空间时间轴</title>', html_out)
        m = re.search(r'<script id="qzone-data" type="application/json">(.*?)</script>',
                      html_out, re.S)
        payload = json.loads(m.group(1)) if m else {}
        eq('embedded data has both posts', len(payload.get('items', [])), 2)
        eq('nickname is taken from the first post', payload.get('nick'), '昵称')
        eq('newest post comes first', payload['items'][0]['c'], '第二条')
        eq('closing-tag text survives as data',
           payload['items'][1]['c'], '第一条 </script> 试试')
        eq('page has exactly one data script closing tag',
           html_out.count('</script>'), real.count('</script>'))

    r2 = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'gen_timeline.py')],
                        env=dict(env, QZONE_OUT=os.path.join(tmp, 'empty'),
                                 QZONE_TIMELINE_FILE='custom'),
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    eq('no data -> non-zero exit, not a blank page', r2.returncode != 0, True)

    r3 = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'gen_timeline.py')],
                        env=dict(env, QZONE_TIMELINE_FILE='custom', QZONE_TIMELINE_TITLE='我的时间轴'),
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    eq('QZONE_TIMELINE_FILE sets the file name', os.path.exists(os.path.join(tmp, 'custom.html')), True)
    if os.path.exists(os.path.join(tmp, 'custom.html')):
        with open(os.path.join(tmp, 'custom.html'), encoding='utf-8') as f:
            has('QZONE_TIMELINE_TITLE sets the page title', '<title>我的时间轴</title>', f.read())
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print('\n%d passed, %d failed' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
