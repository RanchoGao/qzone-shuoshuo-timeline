/**
 * Fetch every blog post (日志) into data/blog.json.
 * Usage: NODE_PATH=<mods> node scripts/fetch_blog.js
 *
 * Note: get_abs requires a valid statYear even though it does not filter the list.
 */
const fs = require('fs');
const path = require('path');
const {
  connect, getQzonePage, getAuth, pageFetch, unwrapJsonp,
  ensureOnQzone, sleep, OUT, DELAY,
} = require('./lib');

const FILE = path.join(OUT, 'blog.json');
const YEAR = process.env.QZONE_STAT_YEAR || new Date().getFullYear();

function absUrl(uin, g_tk, pos, num) {
  return (
    `https://user.qzone.qq.com/proxy/domain/b.qzone.qq.com/cgi-bin/blognew/get_abs` +
    `?hostUin=${uin}&uin=${uin}&blogType=0&cateName=&cateHex=&statYear=${YEAR}&reqInfo=7` +
    `&pos=${pos}&num=${num}&sortType=0&source=0&rand=${Math.random()}&ref=qzone` +
    `&g_tk=${g_tk}&verbose=1`
  );
}

function contentUrl(uin, g_tk, blogid) {
  return (
    `https://user.qzone.qq.com/proxy/domain/b.qzone.qq.com/cgi-bin/blognew/blog_output_data` +
    `?uin=${uin}&blogid=${blogid}&styledm=qzonestyle.gtimg.cn` +
    `&imgdm=user.qzone.qq.com/proxy/domain/qzs.qq.com&bdm=b.qzone.qq.com` +
    `&mode=2&numperpage=15&timestamp=${Math.floor(Date.now() / 1000)}&dprefix=` +
    `&blogseed=${Math.random()}&inCharset=utf-8&outCharset=utf-8&ref=qzone&g_tk=${g_tk}`
  );
}

function commentUrl(uin, g_tk, blogid) {
  return (
    `https://user.qzone.qq.com/proxy/domain/b.qzone.qq.com/cgi-bin/blognew/get_comment_list` +
    `?uin=${uin}&num=100&topicId=${uin}_${blogid}&start=0&r=${Math.random()}` +
    `&iNotice=0&inCharset=utf-8&outCharset=utf-8&format=jsonp&ref=qzone&g_tk=${g_tk}`
  );
}

(async () => {
  const browser = await connect();
  const page = await getQzonePage(browser);
  const { uin, g_tk } = await getAuth(page);
  if (!uin || !g_tk) throw new Error('not logged in — run scripts/status.js first');
  await ensureOnQzone(page, uin);

  // ---- 1. list ----
  const items = [];
  let total = null;
  let pos = 0;
  while (true) {
    const r = await pageFetch(page, absUrl(uin, g_tk, pos, 15));
    const d = unwrapJsonp(r.text);
    const data = (d && d.data) || {};
    if (d && d.code && d.code !== 0) {
      console.log(`  get_abs returned code=${d.code} msg=${d.message}`);
      console.log('  Ids are usually a bad statYear — set QZONE_STAT_YEAR to a valid year.');
      break;
    }
    if (total === null) {
      total = data.totalNum || 0;
      console.log(`total blogs reported by API: ${total}`);
    }
    const list = data.list || [];
    if (!list.length) break;
    items.push(...list);
    pos += 15;
    if (items.length >= total) break;
    await sleep(DELAY);
  }
  console.log(`list collected: ${items.length}`);

  // ---- 2. content + comments per post ----
  let i = 0;
  for (const it of items) {
    i++;
    const r = await pageFetch(page, contentUrl(uin, g_tk, it.blogId));
    const html = r.text;

    // structured metadata is embedded in an inline script
    const m = html.match(/g_oBlogData\s*=\s*(\{[\s\S]*?\});\s*<\/script>/);
    if (m) {
      try {
        it.meta = JSON.parse(m[1]).data || null;
      } catch (e) {
        it.meta = null;
      }
    }

    // Parse with a real DOM — regex counting gets <td> nesting wrong.
    const parsed = await page.evaluate((raw) => {
      const doc = new DOMParser().parseFromString(raw, 'text/html');
      const el =
        doc.getElementById('blogDetailDiv') ||
        doc.querySelector('.blog_details') ||
        doc.getElementById('blogContainer');
      if (!el) return null;
      return {
        html: el.innerHTML,
        text: el.innerText || el.textContent || '',
        imgs: Array.from(el.querySelectorAll('img'))
          .map((n) => n.getAttribute('orgsrc') || n.getAttribute('src') || '')
          .filter((u) => u && !/loading\.gif/.test(u) && !u.startsWith('data:')),
      };
    }, html);

    it.contentHtml = parsed ? parsed.html : null;
    it.contentText = parsed ? parsed.text : null;
    it.contentImgs = parsed ? parsed.imgs : [];

    try {
      const rc = await pageFetch(page, commentUrl(uin, g_tk, it.blogId));
      const dc = unwrapJsonp(rc.text);
      it.comments = (dc && dc.data && dc.data.comments) || [];
    } catch (e) {
      it.comments = [];
    }

    console.log(
      `  [${i}/${items.length}] ${it.pubTime}  ${it.title}  ` +
        `(html=${it.contentHtml ? it.contentHtml.length : 0}ch, imgs=${it.contentImgs.length})`
    );
    await sleep(DELAY);
  }

  fs.writeFileSync(FILE, JSON.stringify(items, null, 1), 'utf8');
  console.log(`saved ${items.length} blogs -> ${FILE}`);
  browser.disconnect();
})().catch((e) => {
  console.error('ERR', e.stack);
  process.exit(1);
});
