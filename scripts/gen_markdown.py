#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Merge the exported Qzone data into one Markdown document.

Reads   data/shuoshuo.json, data/blog.json, data/images.json, data/auth.json
Writes  QQ空间存档.md  at <root>/QQ空间存档.md

Environment overrides:  QZONE_OUT   root dir
                        QZONE_TITLE override the document title
Stdlib only. Python 3.8+.
"""
import json
import os
import re
import time
import collections
from html.parser import HTMLParser

BASE = os.environ.get('QZONE_OUT') or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
TITLE = os.environ.get('QZONE_TITLE') or 'QQ空间存档'
OUTFILE = os.path.join(BASE, TITLE + '.md')

# ---------------------------------------------------------------- emoji
# e100..e182 is the classic QQ emoticon set. Newer animated ones (e3xxxxx)
# have no public mapping, so they degrade to a plain marker.
_CLASSIC = (
    '微笑 撇嘴 色 发呆 得意 流泪 害羞 闭嘴 睡 大哭 尴尬 发怒 调皮 呲牙 惊讶 难过 酷 冷汗 抓狂 吐 '
    '偷笑 可爱 白眼 傲慢 饥饿 困 惊恐 流汗 憨笑 大兵 奋斗 咒骂 疑问 嘘 晕 折磨 衰 骷髅 敲打 再见 '
    '擦汗 抠鼻 鼓掌 糗大了 坏笑 左哼哼 右哼哼 哈欠 鄙视 委屈 快哭了 阴险 亲亲 吓 可怜 菜刀 西瓜 啤酒 篮球 乒乓 '
    '咖啡 饭 猪头 玫瑰 凋谢 示爱 爱心 心碎 蛋糕 闪电 炸弹 刀 足球 瓢虫 便便 月亮 太阳 礼物 拥抱 强 '
    '弱 握手 胜利 抱拳 勾引 拳头 差劲 爱你 NO OK 爱情 飞吻 跳跳 发抖 怄火 转圈 磕头 回头 跳绳 挥手 '
    '激动 街舞 献吻 左太极 右太极'
).split()
EMOJI = {'e%d' % (100 + i): n for i, n in enumerate(_CLASSIC)}


def clean_text(s):
    """Turn Qzone inline markup into readable plain text."""
    if not s:
        return ''
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    # @{uin:123,nick:Name,who:1} -> @Name
    s = re.sub(r'@\{uin:\s*(\d+)\s*,\s*nick:\s*([^,}]*?)\s*(?:,[^}]*)?\}', r'@\2', s)
    # [em]e113[/em] -> [呲牙]
    s = re.sub(r'\[em\](e\d+)\[/em\]',
               lambda m: '[%s]' % EMOJI.get(m.group(1), '表情'), s)
    return s.replace('\xa0', ' ').strip()


def _escape_line(t):
    """Escape leading markers so plain text is not parsed as Markdown structure.

    Backslash escapes only work before ASCII punctuation, so ordered lists
    escape the dot ("1\\. x") rather than the digit -- "\\1" would render
    literally.
    """
    m = re.match(r'^(\s*)(\d+)([.)])(\s)', t)
    if m:
        return '%s%s\\%s%s' % (m.group(1), m.group(2), m.group(3), t[m.end() - 1:])
    m = re.match(r'^(\s*)(#{1,6}\s|>|\||[-*+]\s|---+\s*$|===+\s*$)', t)
    if m:
        head = m.group(2)
        return '%s\\%s%s' % (m.group(1), head[0], t[m.start(2) + 1:])
    return t


def md_body(s):
    """Escape block-breaking prefixes and force hard line breaks."""
    lines = [_escape_line(ln.rstrip()) for ln in clean_text(s).split('\n')]
    # trailing two spaces = hard line break in Markdown
    return '  \n'.join(lines).strip()


def blockquote(lines):
    """Wrap lines in one blockquote level (no accidental nesting)."""
    return '\n'.join('> ' + ln if ln.strip() else '>' for ln in lines)


# ------------------------------------------------------------ html -> md
def _drop_unpaired(line):
    """Remove bold markers that lost their partner on this line."""
    n = line.count('**')
    return line.replace('**', '') if n % 2 else line


class Html2Md(HTMLParser):
    """Minimal HTML->Markdown converter for Qzone blog bodies. No deps."""

    SKIP = {'script', 'style', 'noscript', 'iframe'}
    BLOCK = {'p', 'div', 'tr', 'table', 'ul', 'ol', 'blockquote', 'section',
             'article', 'li', 'center', 'pre', 'td', 'dl', 'dt', 'dd', 'form'}
    HEAD = {'h1': 4, 'h2': 4, 'h3': 5, 'h4': 5, 'h5': 6, 'h6': 6}

    def __init__(self, url2file):
        super().__init__(convert_charrefs=True)
        self.url2file = url2file
        self.out = []
        self.skip = 0
        self.hrefs = []
        self.missing = []

    def _nl(self, n=2):
        while self.out and self.out[-1] == '\n':
            self.out.pop()
        self.out.append('\n' * n)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == 'br':
            self.out.append('\n')
        elif tag == 'hr':
            self._nl()
            self.out.append('---')
            self._nl()
        elif tag == 'img':
            u = a.get('orgsrc') or a.get('_src') or a.get('src') or ''
            if not u or u.startswith('data:') or 'loading.gif' in u:
                return
            self._nl()
            f = self.url2file.get(u)
            if f:
                self.out.append('![](images/%s)' % f)
            else:
                self.missing.append(u)
                self.out.append('*（图片已失效）* <%s>' % u)
            self._nl()
        elif tag == 'a':
            self.hrefs.append(a.get('href') or '')
            self.out.append('[')
        elif tag in ('b', 'strong'):
            self.out.append('**')
        elif tag in ('i', 'em'):
            self.out.append('*')
        elif tag in self.HEAD:
            self._nl()
            self.out.append('#' * self.HEAD[tag] + ' ')
        elif tag == 'li':
            self._nl()
            self.out.append('- ')
        elif tag in self.BLOCK:
            self._nl()

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == 'a':
            h = self.hrefs.pop() if self.hrefs else ''
            self.out.append('](%s)' % h if h else ']')
        elif tag in ('b', 'strong'):
            self.out.append('**')
        elif tag in ('i', 'em'):
            self.out.append('*')
        elif tag in self.HEAD or tag in self.BLOCK:
            self._nl()

    def handle_data(self, d):
        if self.skip or not d:
            return
        self.out.append(d.replace('\xa0', ' '))

    def result(self):
        s = ''.join(self.out)
        s = clean_text(s)
        # A pair separated only by whitespace wrapped nothing useful:
        # pull the inner text out and drop the markers around it.
        s = re.sub(r'\*\*(\s*)\*\*', lambda m: m.group(1), s)
        # Then remove any marker left without a partner on its line.
        s = '\n'.join(_drop_unpaired(line) for line in s.split('\n'))
        s = re.sub(r'\[\]\(\)', '', s)
        s = re.sub(r'[ \t]+', ' ', s)
        s = re.sub(r' *\n *', '\n', s)
        s = re.sub(r'\n{3,}', '\n\n', s)
        # a bullet whose content got pushed into the following block
        s = re.sub(r'\n[-*+]\n+(?=\S)', '\n- ', s)
        s = re.sub(r'^[-*+]\n+(?=\S)', '- ', s)
        return s.strip()


def html_to_md(html, url2file):
    p = Html2Md(url2file)
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - partial output beats nothing
        pass
    return p.result()


# ---------------------------------------------------------------- build
def ts_of(text):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return int(time.mktime(time.strptime(text, fmt)))
        except Exception:
            pass
    return 0


def fmt(ts):
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))


def render_comments(clist):
    out = []
    for c in clist or []:
        who = clean_text(c.get('name') or '')
        when = c.get('createTime2') or c.get('createTime') or ''
        body = md_body(c.get('content') or '').replace('\n', ' ')
        out.append('> **%s**（%s）：%s' % (who, when, body))
        for r in c.get('list_3') or []:
            out.append('> > **%s**（%s）：%s' % (
                clean_text(r.get('name') or ''),
                r.get('createTime2') or r.get('createTime') or '',
                md_body(r.get('content') or '').replace('\n', ' ')))
    return out


def extract_img_urls(html):
    """Real image URLs inside a blog body (src may just be a loading gif)."""
    urls = []
    for tag in re.findall(r'<img[^>]*>', html, re.I):
        m = (re.search(r'orgsrc\s*=\s*"([^"]+)"', tag, re.I)
             or re.search(r"orgsrc\s*=\s*'([^']+)'", tag, re.I)
             or re.search(r'\bsrc\s*=\s*"([^"]+)"', tag, re.I))
        if not m:
            continue
        u = m.group(1)
        if u.startswith('data:') or 'loading.gif' in u:
            continue
        urls.append(u)
    return urls


def post_link(uin, kind, post_id):
    """Build the permalink, tolerating a missing uin (no stray double slash)."""
    base = 'https://user.qzone.qq.com'
    return '%s/%s/%s/%s' % (base, uin, kind, post_id) if uin \
        else '%s/%s/%s' % (base, kind, post_id)


def load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def main():
    images = load('images.json') or {}
    auth = load('auth.json') or {}

    ss = load('shuoshuo.json')
    bl = load('blog.json')
    if ss is None and bl is None:
        raise SystemExit('no data found in %s — run the fetch scripts first' % DATA)
    ss = ss or []
    bl = bl or []

    # Prefer auth.json, but fall back to the uin carried on the posts themselves
    # so links stay well-formed even if auth.json was never written or was cleaned.
    uin = str(auth.get('uin') or '').strip()
    if not uin:
        for m in ss:
            if str(m.get('uin') or '').strip().isdigit():
                uin = str(m['uin']).strip()
                break

    entries = []
    dead = 0
    refs = 0

    # ---------------- 说说 ----------------
    for m in ss:
        ts = int(m.get('created_time') or 0)
        body = []
        txt = md_body(m.get('content') or '')
        if txt:
            body.append(txt)

        if m.get('rt_con'):  # forwarded original
            rt = m['rt_con']
            rtxt = md_body(rt.get('content') if isinstance(rt, dict) else str(rt))
            who = clean_text(m.get('rt_uinname') or '')
            head = '**转发自 @%s**' % who if who else '**转发内容**'
            body.append(blockquote([head, ''] + rtxt.split('\n')))

        pm = images.get(str(m['tid']), {})
        shots = []
        for i in range(len(m.get('pic') or [])):
            rec = pm.get(str(i)) or {}
            refs += 1
            if rec.get('ok') and rec.get('file'):
                shots.append('![](images/%s)' % rec['file'])
            else:
                dead += 1
                shots.append('*（图片已失效）* <%s>' % (rec.get('url') or ''))
        if shots:
            body.append('\n\n'.join(shots))

        for v in m.get('video') or []:
            link = v.get('url3') or v.get('url1') or ''
            body.append('🎬 视频：<%s>' % link if link else '🎬 （含视频）')
        for a in m.get('audio') or []:
            body.append('🎵 音乐：%s — %s' % (clean_text(a.get('singername') or ''),
                                            clean_text(a.get('name') or '')))

        meta = []
        lbs = m.get('lbs') or {}
        if lbs.get('idname') or lbs.get('name'):
            meta.append('📍 ' + clean_text(lbs.get('idname') or lbs.get('name')))
        if m.get('source_name'):
            meta.append('来自 ' + clean_text(m['source_name']))
        if m.get('cmtnum'):
            meta.append('评论 %d' % m['cmtnum'])
        if m.get('fwdnum'):
            meta.append('转发 %d' % m['fwdnum'])
        if meta:
            body.append('`' + ' · '.join(meta) + '`')

        cm = render_comments(m.get('commentlist'))
        if cm:
            body.append('\n'.join(cm))

        entries.append({
            'ts': ts,
            'kind': '说说',
            'title': '',
            'body': '\n\n'.join(x for x in body if x),
            'link': post_link(uin, 'mood', m['tid']),
        })

    # ---------------- 日志 ----------------
    for it in bl:
        ts = ts_of(it.get('pubTime') or '')
        bm = images.get(str(it['blogId']), {})
        url2file = {}
        for rec in bm.values():
            if rec.get('ok') and rec.get('file'):
                url2file[rec['url']] = rec['file']
        # Count the pictures this post references, not what images.json happens to
        # know about -- otherwise running with/without the download step disagrees.
        img_urls = it.get('contentImgsOrg')
        if img_urls is None:
            img_urls = extract_img_urls(it.get('contentHtml') or '')
        img_urls = set(img_urls)
        resolved = sum(1 for u in img_urls if u in url2file)
        refs += len(img_urls)
        dead += len(img_urls) - resolved

        md = html_to_md(it.get('contentHtml') or '', url2file)
        body = [md] if md else []
        meta = []
        if it.get('cate'):
            meta.append('分类：' + clean_text(it['cate']))
        if it.get('commentNum'):
            meta.append('评论 %d' % it['commentNum'])
        if meta:
            body.append('`' + ' · '.join(meta) + '`')
        cm = []
        for c in it.get('comments') or []:
            who = clean_text((c.get('poster') or {}).get('name') or c.get('name') or '')
            cm.append('> **%s**：%s' % (
                who, md_body(c.get('content') or '').replace('\n', ' ')))
        if cm:
            body.append('\n'.join(cm))
        entries.append({
            'ts': ts,
            'kind': '日志',
            'title': clean_text(it.get('title') or '(无标题)'),
            'body': '\n\n'.join(x for x in body if x),
            'link': post_link(uin, 'blog', it['blogId']),
        })

    entries.sort(key=lambda e: -e['ts'])

    # ---------------- header / stats ----------------
    per_year = collections.OrderedDict()
    for e in entries:
        y = time.strftime('%Y', time.localtime(e['ts'])) if e['ts'] else '未知'
        per_year.setdefault(y, {'说说': 0, '日志': 0})
        per_year[y][e['kind']] += 1

    n_ss = sum(1 for e in entries if e['kind'] == '说说')
    n_bl = sum(1 for e in entries if e['kind'] == '日志')
    ok_imgs = refs - dead
    nickname = clean_text(ss[0].get('name') if ss else '')

    L = ['# %s%s' % (TITLE, ' · ' + nickname if nickname else ''), '']
    L += ['| 项目 | 内容 |', '| --- | --- |']
    if uin:
        L.append('| QQ 号 | %s |' % uin)
    L.append('| 导出时间 | %s |' % time.strftime('%Y-%m-%d %H:%M'))
    L.append('| 说说 | %d 条 |' % n_ss)
    L.append('| 日志 | %d 篇 |' % n_bl)
    L.append('| 图片 | %d 张（本地 %d 张，失效 %d 张）|' % (refs, ok_imgs, dead))
    if entries:
        L.append('| 时间跨度 | %s ~ %s |' % (
            fmt(min(e['ts'] for e in entries if e['ts'])),
            fmt(max(e['ts'] for e in entries))))
    L += ['',
          '> 图片保存在同目录的 `images/` 文件夹，Markdown 用相对路径引用，',
          '> 移动时请把 `.md` 和 `images/` 一起移动。',
          '', '## 年度分布', '',
          '| 年份 | 说说 | 日志 | 合计 |', '| --- | ---: | ---: | ---: |']
    for y, c in per_year.items():
        L.append('| %s | %d | %d | %d |' % (y, c['说说'], c['日志'],
                                            c['说说'] + c['日志']))
    L += ['', '---', '']

    cur_year = None
    for e in entries:
        y = time.strftime('%Y', time.localtime(e['ts'])) if e['ts'] else '未知'
        if y != cur_year:
            cur_year = y
            L += ['', '# %s 年' % y, '']
        head = '## %s · %s' % (fmt(e['ts']) if e['ts'] else '时间未知', e['kind'])
        if e['title']:
            head += '：%s' % e['title']
        L += [head, '']
        if e['body']:
            L += [e['body'], '']
        L += ['[原文链接](%s)' % e['link'], '']

    text = re.sub(r'\n{4,}', '\n\n\n', '\n'.join(L))
    with open(OUTFILE, 'w', encoding='utf-8') as f:
        f.write(text)

    print('wrote %s' % OUTFILE)
    print('  entries: %d (说说 %d / 日志 %d)' % (len(entries), n_ss, n_bl))
    print('  images referenced: %d (local %d, dead %d)' % (refs, ok_imgs, dead))
    print('  size: %.2f MB, lines: %d' % (len(text.encode('utf-8')) / 1048576.0,
                                          text.count('\n')))


if __name__ == '__main__':
    main()
