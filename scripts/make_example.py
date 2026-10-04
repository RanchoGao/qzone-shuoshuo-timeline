#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build examples/ demonstrating what the exporter outputs.

Everything here is SYNTHETIC. No QQ numbers, no nicknames, no images or URLs
taken from any real account -- safe to publish.

It writes examples/fixtures/*.json, then calls the real scripts/gen_markdown.py
against them, so examples/example-output.md is genuine tool output.

Usage: python scripts/make_example.py
"""
import base64
import json
import os
import subprocess
import sys

BASE = os.environ.get('QZONE_OUT') or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(BASE, 'examples')
# examples/ itself acts as the "root", so data/ and images/ land right beside
# example-output.md and the fixture images resolve via relative paths.
ROOT = EXAMPLES

UIN = '100000001'
PLACEHOLDER = 'https://example.com/not-a-real-image/%s.jpg'

# 1x1 grey PNG: a real file so the example actually renders.
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
    '+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


def shuoshuo():
    return [
        {
            'tid': 'aa0000000000000000000001',
            'created_time': 1766759121,
            'content': ('年底回头看了看今年，做了个小总结。\n'
                        '有些地方确实挺意外的。'),
            'pictotal': 2,
            'cmtnum': 1,
            'fwdnum': 0,
            'source_name': 'Android',
            'lbs': {'id': '', 'idname': '', 'name': '', 'pos_x': '', 'pos_y': ''},
            'pic': [{'url2': PLACEHOLDER % 'demo-p1'},
                    {'url2': PLACEHOLDER % 'demo-p2'}],
            'commentlist': [{
                'name': '示例好友',
                'createTime2': '2025-12-26 22:41:02',
                'content': '这个总结做得不错 @{uin:100000001,nick:示例用户,who:1}',
                'list_3': [{
                    'name': '示例用户',
                    'createTime2': '2025-12-26 22:55:11',
                    'content': '谢谢😄 [em]e113[/em]',
                }],
            }],
        },
        {
            'tid': 'aa0000000000000000000002',
            'created_time': 1660635000,
            'content': '随手记一句，配个表情 [em]e100[/em] [em]e179[/em]',
            'pictotal': 0,
            'cmtnum': 0,
            'fwdnum': 0,
            'lbs': {'id': '', 'idname': '示例城市', 'name': '示例城市',
                    'pos_x': '116.39', 'pos_y': '39.90'},
            'pic': [],
        },
        {
            'tid': 'aa0000000000000000000003',
            'created_time': 1419753600,
            'content': '说得好',
            'rt_uinname': '示例公众号',
            'rt_con': {'content': ('偶然看到一段采访，挺有意思。\n'
                                   '记者：你怎么看这件事？\n'
                                   '受访者：我觉得慢慢来比较好。')},
            'pictotal': 0,
            'cmtnum': 0,
            'fwdnum': 0,
            'pic': [],
        },
    ]


def blog():
    return [
        {
            'blogId': '1300000001',
            'title': '示例日志：一次小项目的复盘',
            'pubTime': '2015-03-15 12:12',
            'cate': '个人日记',
            'commentNum': 1,
            'contentHtml': (
                '<div id="blogDetailDiv">'
                '<p>这个项目做完快一个月了，趁还记得住写几句。</p>'
                '<div><br/></div>'
                '<div><span style="font-weight:bold">踩过的坑有：</span></div>'
                '<ul><li>一开始没定清楚目标，返工了两次</li>'
                '<li>沟通成本比想象中高很多</li></ul>'
                '<p>下次会先花时间对齐目标。</p>'
                '<div><img class="QZBLOG_IMG_LOADING" '
                'src="http://qzonestyle.gtimg.cn/aoi/img/icenter/loading.gif" '
                'orgsrc="' + PLACEHOLDER % 'demo-b1' + '"/></div>'
                '<p>就这些。</p>'
                '</div>'),
            'comments': [{'name': '示例好友',
                          'content': '写得很实在 @{uin:100000001,nick:示例用户,who:1}'}],
        },
    ]


def main():
    for d in (EXAMPLES, os.path.join(ROOT, 'data'), os.path.join(ROOT, 'images')):
        os.makedirs(d, exist_ok=True)

    ss, bl = shuoshuo(), blog()

    images = {}
    for m in ss:
        per = {}
        for i in range(len(m['pic'])):
            fn = 'ss_demo_%s_%d.png' % (m['tid'][-4:], i)
            with open(os.path.join(ROOT, 'images', fn), 'wb') as f:
                f.write(PNG)
            per[str(i)] = {'file': fn, 'url': m['pic'][i]['url2'], 'ok': True}
        if per:
            images[str(m['tid'])] = per

    # one deliberately dead image, to show how failures are represented
    images[str(ss[0]['tid'])]['1'] = {
        'file': None, 'ok': False,
        'url': 'http://p.qpimg.cn/cgi-bin/cgi_imgproxy?size=0&url=http://example.invalid/old.jpg',
    }

    for it in bl:
        fn = 'blog_demo_%s_0.png' % it['blogId'][-4:]
        with open(os.path.join(ROOT, 'images', fn), 'wb') as f:
            f.write(PNG)
        images[str(it['blogId'])] = {
            '0': {'file': fn, 'url': PLACEHOLDER % 'demo-b1', 'ok': True}}

    D = os.path.join(ROOT, 'data')
    json.dump(ss, open(os.path.join(D, 'shuoshuo.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump(bl, open(os.path.join(D, 'blog.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump(images, open(os.path.join(D, 'images.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump({'uin': UIN, 'g_tk': 1234567890},
              open(os.path.join(D, 'auth.json'), 'w', encoding='utf-8'), indent=1)

    # Run the real generator against the fixtures.
    env = dict(os.environ, QZONE_OUT=ROOT, QZONE_TITLE='example-output')
    r = subprocess.run([sys.executable, os.path.join(BASE, 'scripts', 'gen_markdown.py')],
                       env=env, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        raise SystemExit('generator failed')

    # ROOT == EXAMPLES, so the generator already wrote it into place.
    dst = os.path.join(EXAMPLES, 'example-output.md')
    print('example written to', dst)
    print('  fixtures populated from synthetic data only')


if __name__ == '__main__':
    main()
