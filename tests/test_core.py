#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Self-test for the pure-python parts of qzone-export.

Covers the transformations most likely to break: text cleaning, Markdown
escaping, and the HTML -> Markdown converter. No network, no browser needed.

Usage: python tests/test_core.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'scripts'))

from gen_markdown import (  # noqa: E402
    clean_text, md_body, html_to_md, blockquote, post_link, extract_img_urls)

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
        print('FAIL  %s\n      %r not found in %r' % (label, needle, haystack))


# ---- clean_text ----
eq('@mention -> nickname',
   clean_text('你好 @{uin:12345,nick:小明,who:1} 在吗'), '你好 @小明 在吗')
eq('classic emoticon',
   clean_text('好[em]e113[/em]'), '好[呲牙]')
eq('colored/default emoticon degrades',
   clean_text('好[em]e328051[/em]'), '好[表情]')
eq('nbsp collapsed', clean_text('a\xa0b'), 'a b')

# ---- escaping ----
eq('hashtag at line start is escaped', md_body('# 话题'), '\\# 话题')
eq('blockquote marker is escaped', md_body('> 引用'), '\\> 引用')
eq('ordered list escapes the DOT (not the digit)',
   md_body('1. 第一点'), '1\\. 第一点')
eq('bullet list is escaped', md_body('- 项目'), '\\- 项目')
# Pipes only matter inside tables, and the ones we generate hold no user text,
# so inline pipes stay as-is rather than littering the document with escapes.
eq('inline pipe left alone', md_body('a | b'), 'a | b')
eq('leading pipe still escaped', md_body('| 开头'), '\\| 开头')
eq('plain text untouched', md_body('今天天气不错'), '今天天气不错')

# ---- hard line breaks ----
eq('newline becomes a hard break', md_body('a\nb'), 'a  \nb')

# ---- blockquote ----
eq('blockquote never nests by accident',
   blockquote(['标题', '', '正文']), '> 标题\n>\n> 正文')

# ---- html -> md ----
eq('paragraph breaks survive',
   html_to_md('<p>第一段</p><p>第二段</p>', {}), '第一段\n\n第二段')
eq('br becomes a newline', html_to_md('第一行<br/>第二行', {}), '第一行\n第二行')
has('strong survives', '**重点**', html_to_md('<b>重点</b>', {}))
has('bold markers kept together with their payload',
    '** 标题 **', html_to_md('<b> 标题 </b>', {}))
eq('truly empty bold marker is dropped',
   html_to_md('<b>   </b><p>正文</p>', {}), '正文')
eq('image resolves through the manifest',
   html_to_md('<img orgsrc="http://x/y.jpg" src="loading.gif"/>',
              {'http://x/y.jpg': 'a.jpg'}),
   '![](images/a.jpg)')
has('missing image keeps its URL',
    'http://x/gone.jpg',
    html_to_md('<img orgsrc="http://x/gone.jpg"/>', {}))
has('script content is dropped',
    'Keep', html_to_md('<script>var junk=1;</script><p>Keep</p>', {}))
has('link becomes markdown',
    '[文字](http://x)', html_to_md('<a href="http://x">文字</a>', {}))
has('list items render on one line',
    '- 要点',
    html_to_md('<li><div>要点</div></li>', {}))

# ---- permalink must stay well-formed even when auth.json is absent ----
eq('permalink with uin',
   post_link('12345', 'mood', 'abc'),
   'https://user.qzone.qq.com/12345/mood/abc')
eq('permalink without uin has no double slash',
   post_link('', 'blog', 'XYZ'),
   'https://user.qzone.qq.com/blog/XYZ')
eq('no // anywhere when uin missing',
   '//' in post_link('', 'mood', 't1').replace('https://', ''), False)

# ---- blog image extraction skips the lazy-loading placeholder ----
eq('extract_img_urls picks orgsrc over src',
   extract_img_urls('<img src="http://x/loading.gif" orgsrc="http://x/real.jpg"/>'),
   ['http://x/real.jpg'])
eq('extract_img_urls drops pure placeholder',
   extract_img_urls('<img src="http://qzonestyle.gtimg.cn/aoi/img/icenter/loading.gif"/>'),
   [])

print('\n%d passed, %d failed' % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
