#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build examples/ demonstrating what the exporter outputs.

Everything here is SYNTHETIC. No QQ numbers, no nicknames, no images or URLs
taken from any real account -- safe to publish.

It writes the fixtures (examples/data/*.json, examples/images/*.png), then calls
the real scripts/gen_markdown.py and scripts/gen_timeline.py against them, so
examples/example-output.md and examples/example-timeline.html are genuine tool
output.

Usage: python scripts/make_example.py
"""
import colorsys
import json
import os
import struct
import subprocess
import sys
import time
import zlib

BASE = os.environ.get('QZONE_OUT') or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(BASE, 'examples')
# examples/ itself acts as the "root", so data/ and images/ land right beside
# example-output.md and the fixture images resolve via relative paths.
ROOT = EXAMPLES

UIN = '100000001'
PLACEHOLDER = 'https://example.com/not-a-real-image/%s.jpg'
DEAD_URL = 'http://p.qpimg.cn/cgi-bin/cgi_imgproxy?size=0&url=http://example.invalid/old.jpg'
SIZES = [(240, 180), (180, 240), (240, 240), (320, 180)]


def ts(text):
    """Local-time string -> epoch, so the examples read the same on any machine."""
    return int(time.mktime(time.strptime(text, '%Y-%m-%d %H:%M:%S')))


def png(w, h, seed):
    """A small gradient PNG, different per seed. Stdlib only."""
    hue = (seed * 0.137) % 1.0
    c1 = colorsys.hsv_to_rgb(hue, 0.35, 0.95)
    c2 = colorsys.hsv_to_rgb((hue + 0.12) % 1.0, 0.55, 0.78)
    rows = []
    for y in range(h):
        row = bytearray([1])  # filter type 1 (Sub): keeps smooth gradients tiny
        prev = (0, 0, 0)
        for x in range(w):
            t = (x / (w - 1) + y / (h - 1)) / 2
            px = tuple(int(255 * (a + (b - a) * t)) for a, b in zip(c1, c2))
            row.extend((px[k] - prev[k]) & 0xFF for k in range(3))
            prev = px
        rows.append(bytes(row))

    def chunk(tag, data):
        body = tag + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(rows), 9))
            + chunk(b'IEND', b''))


def pics(tag, n):
    return [{'url2': PLACEHOLDER % ('demo-%s-%d' % (tag, i))} for i in range(n)]


def post(tid, when, content, **extra):
    m = {'tid': tid, 'created_time': ts(when), 'content': content, 'name': '示例用户',
         'pictotal': len(extra.get('pic', [])), 'cmtnum': 0, 'fwdnum': 0,
         'lbs': {'id': '', 'idname': '', 'name': '', 'pos_x': '', 'pos_y': ''},
         'pic': []}
    m.update(extra)
    return m


def place(name, x, y):
    return {'id': '', 'idname': name, 'name': name, 'pos_x': x, 'pos_y': y}


# A few short lines to fill the busier months, so the heatmap has real contrast.
FILLER = [
    '今天也是普通的一天。', '晚饭吃了面条。', '突然想起一首老歌。', '周末终于可以睡个懒觉。',
    '又下雨了。', '在图书馆待了一整天。', '今天天气真好。', '加班中……',
    '路过一家新开的奶茶店。', '看完了一部很老的电影，居然很好看。',
    '地铁上看到有人在读纸质书。', '风有点大，出门记得带外套。',
]
BUSY_MONTHS = [(2025, 6, 3), (2023, 8, 5), (2019, 7, 9), (2016, 2, 4), (2014, 12, 2)]


def shuoshuo():
    out = [
        # --- the three entries the README and example-output.md quote ---
        post('aa0000000000000000000001', '2025-12-26 22:25:21',
             '年底回头看了看今年，做了个小总结。\n有些地方确实挺意外的。',
             cmtnum=1, source_name='Android', pic=pics('p', 2),
             commentlist=[{
                 'name': '示例好友', 'createTime2': '2025-12-26 22:41:02',
                 'content': '这个总结做得不错 @{uin:100000001,nick:示例用户,who:1}',
                 'list_3': [{'name': '示例用户', 'createTime2': '2025-12-26 22:55:11',
                             'content': '谢谢😄 [em]e113[/em]'}]}]),
        post('aa0000000000000000000002', '2022-08-16 15:30:00',
             '随手记一句，配个表情 [em]e100[/em] [em]e179[/em]',
             lbs=place('示例城市', '116.39', '39.90')),
        post('aa0000000000000000000003', '2014-12-28 16:00:00', '说得好',
             rt_uinname='示例公众号',
             rt_con={'content': ('偶然看到一段采访，挺有意思。\n'
                                 '记者：你怎么看这件事？\n'
                                 '受访者：我觉得慢慢来比较好。')}),
    ]

    n = [3]

    def tid():
        n[0] += 1
        return 'aa%022d' % n[0]

    out += [
        post(tid(), '2025-06-08 20:41:07',
             '下班路上看到一片特别好看的晚霞。\n拍了几张，都没拍出眼睛看到的一半。',
             source_name='iPhone', lbs=place('示例城市', '116.39', '39.90'),
             pic=pics('sunset', 3), cmtnum=2,
             commentlist=[
                 {'name': '示例好友', 'createTime2': '2025-06-08 20:55:00', 'content': '太好看了吧'},
                 {'name': '示例同事', 'createTime2': '2025-06-08 21:02:13', 'content': '在哪拍的？',
                  'list_3': [{'name': '示例用户', 'createTime2': '2025-06-08 21:10:40',
                              'content': '就在楼下天桥上'}]}]),
        post(tid(), '2024-11-03 07:55:30',
             '第一次跑完 10 公里！配速不算好看，但心情很好 [em]e179[/em]',
             source_name='iPhone', pic=pics('run', 1), cmtnum=1,
             commentlist=[{'name': '示例好友', 'createTime2': '2024-11-03 08:20:00',
                           'content': '厉害，下次带上我'}]),
        post(tid(), '2023-08-19 23:08:12',
             '最近在整理的小目标：\n1. 每周读一本书\n2. 早睡\n3. 把落下的运动补回来\n先从最简单的开始。'),
        post(tid(), '2023-02-14 12:20:45', '今天的午饭，四个菜，吃撑了。',
             source_name='Android', pic=pics('lunch', 4)),
        post(tid(), '2021-12-31 23:59:00', '2021 就到这里了，明年见。', fwdnum=1),
        post(tid(), '2020-03-12 18:30:00',
             '收藏一篇写得很好的文章，慢慢读：https://example.com/a-good-article 看完再来聊。'),
        post(tid(), '2019-07-14 21:30:00', '毕业快一年了，还是会想起宿舍楼下的那家小面馆。',
             pic=pics('noodle', 2), cmtnum=3,
             commentlist=[
                 {'name': '示例室友', 'createTime2': '2019-07-14 21:40:00', 'content': '老板还记得我们！'},
                 {'name': '示例好友', 'createTime2': '2019-07-14 22:05:00', 'content': '下次一起回去吃'},
                 {'name': '示例学长', 'createTime2': '2019-07-15 08:12:00', 'content': '想念他家的牛肉面'}]),
        post(tid(), '2018-05-04 09:00:00', '转发一下。',
             rt_uinname='示例公众号',
             rt_con={'content': '今天是青年节。愿每个人都还留着一点少年气。'}),
        post(tid(), '2017-09-01 08:10:00', '开学第一天。',
             video=[{'url3': 'https://example.com/not-a-real-video.mp4'}]),
        post(tid(), '2016-02-08 00:05:00',
             '新年快乐 [em]e100[/em][em]e100[/em] 愿大家都平平安安'),
        post(tid(), '2013-04-05 15:20:00', '下雨天，宿舍里听了一下午歌。',
             audio=[{'singername': '示例歌手', 'name': '示例歌曲'}]),
        post(tid(), '2012-10-10 22:10:00', '开通空间的第一条说说。'),
    ]

    k = 0
    for year, month, count in BUSY_MONTHS:
        for i in range(count):
            day = 1 + (i * 3 + month) % 27
            when = '%d-%02d-%02d %02d:%02d:00' % (year, month, day, 8 + (i * 5) % 14, (i * 7) % 60)
            t = tid()
            extra = {'pic': pics('f%d' % k, 1)} if k % 4 == 0 else {}
            out.append(post(t, when, FILLER[k % len(FILLER)], **extra))
            k += 1
    return out


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


def run(script, **overrides):
    env = dict(os.environ, QZONE_OUT=ROOT, PYTHONIOENCODING='utf-8', **overrides)
    r = subprocess.run([sys.executable, os.path.join(BASE, 'scripts', script)],
                       env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    print((r.stdout or r.stderr).strip())
    if r.returncode != 0:
        raise SystemExit('%s failed' % script)


def main():
    imgdir = os.path.join(ROOT, 'images')
    for d in (EXAMPLES, os.path.join(ROOT, 'data'), imgdir):
        os.makedirs(d, exist_ok=True)
    for f in os.listdir(imgdir):  # start clean so the output is reproducible
        if f.endswith('.png'):
            os.remove(os.path.join(imgdir, f))

    ss, bl = shuoshuo(), blog()
    seed = [0]

    def write_png(fn):
        w, h = SIZES[seed[0] % len(SIZES)]
        with open(os.path.join(imgdir, fn), 'wb') as f:
            f.write(png(w, h, seed[0]))
        seed[0] += 1

    images = {}
    for m in ss:
        per = {}
        for i, p in enumerate(m['pic']):
            fn = 'ss_demo_%s_%d.png' % (m['tid'][-4:], i)
            write_png(fn)
            per[str(i)] = {'file': fn, 'url': p['url2'], 'ok': True}
        if per:
            images[str(m['tid'])] = per

    # one deliberately dead image, to show how failures are represented
    dead = ss[0]['tid']
    os.remove(os.path.join(imgdir, 'ss_demo_%s_1.png' % dead[-4:]))
    images[str(dead)]['1'] = {'file': None, 'ok': False, 'url': DEAD_URL}

    for it in bl:
        fn = 'blog_demo_%s_0.png' % it['blogId'][-4:]
        write_png(fn)
        images[str(it['blogId'])] = {
            '0': {'file': fn, 'url': PLACEHOLDER % 'demo-b1', 'ok': True}}

    D = os.path.join(ROOT, 'data')
    for name, obj in (('shuoshuo.json', ss), ('blog.json', bl), ('images.json', images)):
        with open(os.path.join(D, name), 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    with open(os.path.join(D, 'auth.json'), 'w', encoding='utf-8') as f:
        json.dump({'uin': UIN, 'g_tk': 1234567890}, f, indent=1)

    # Run the real generators against the fixtures. ROOT == EXAMPLES, so they
    # write straight into place beside data/ and images/.
    run('gen_markdown.py', QZONE_TITLE='example-output')
    run('gen_timeline.py', QZONE_TIMELINE_TITLE='QQ空间时间轴（示例）',
        QZONE_TIMELINE_FILE='example-timeline')
    print('examples written to', EXAMPLES)
    print('  fixtures populated from synthetic data only')


if __name__ == '__main__':
    main()
