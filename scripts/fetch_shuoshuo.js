/**
 * Fetch every shuoshuo (说说) post into data/shuoshuo.json.
 * Resumable: already-fetched tids are skipped, so it is safe to re-run.
 * Usage: NODE_PATH=<mods> node scripts/fetch_shuoshuo.js
 */
const fs = require('fs');
const path = require('path');
const {
  connect, getQzonePage, getAuth, pageFetch, unwrapJsonp,
  ensureOnQzone, sleep, OUT, DELAY,
} = require('./lib');

const FILE = path.join(OUT, 'shuoshuo.json');
const PAGE_SIZE = 20;

function listUrl(uin, g_tk, pos, num) {
  return (
    `https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6` +
    `?uin=${uin}&ftype=0&sort=0&pos=${pos}&num=${num}&replynum=100&g_tk=${g_tk}` +
    `&callback=_preloadCallback&code_version=1&format=jsonp&need_private_comment=1` +
    `&r=${Math.random()}`
  );
}

function detailUrl(uin, g_tk, tid) {
  return (
    `https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msgdetail_v6` +
    `?uin=${uin}&tid=${tid}&t1_source=1&ftype=0&sort=0&pos=0&num=20&g_tk=${g_tk}` +
    `&callback=_preloadCallback&code_version=1&format=jsonp&need_private_comment=1` +
    `&r=${Math.random()}`
  );
}

(async () => {
  const browser = await connect();
  const page = await getQzonePage(browser);
  const { uin, g_tk } = await getAuth(page);
  if (!uin || !g_tk) throw new Error('not logged in — run scripts/status.js first');
  if (!/^https:\/\/user\.qzone\.qq\.com/.test(page.url())) {
    await page.goto(`https://user.qzone.qq.com/${uin}`, { waitUntil: 'domcontentloaded' });
  }
  await ensureOnQzone(page, uin);

  let all = [];
  const seen = new Set();
  if (fs.existsSync(FILE)) {
    try {
      all = JSON.parse(fs.readFileSync(FILE, 'utf8'));
      all.forEach((m) => seen.add(m.tid));
      console.log(`resume: ${all.length} already saved`);
    } catch (e) {
      all = [];
    }
  }

  let total = null;
  let pos = 0;
  let emptyStreak = 0;

  while (true) {
    let d = null;
    for (let attempt = 0; attempt < 4; attempt++) {
      const r = await pageFetch(page, listUrl(uin, g_tk, pos, PAGE_SIZE));
      d = unwrapJsonp(r.text);
      if (d && d.code === 0 && Array.isArray(d.msglist)) break;
      console.log(`  retry pos=${pos} (code=${d && d.code} msg=${d && d.message})`);
      await sleep(2500 * (attempt + 1));
      d = null;
    }
    if (!d) {
      console.log(`\nstopped fetching at pos=${pos} (repeated failures)`);
      break;
    }
    if (total === null) {
      total = d.total;
      console.log(`total shuoshuo reported by API: ${total}`);
    }
    const list = d.msglist || [];
    if (list.length === 0) {
      // Two consecutive empty pages means we are past the end of the list.
      emptyStreak++;
      if (emptyStreak >= 2) break;
    } else {
      emptyStreak = 0;
    }

    for (const m of list) {
      if (seen.has(m.tid)) continue;
      seen.add(m.tid);
      all.push(m);
    }
    process.stdout.write(`\rpos=${pos} collected=${all.length}/${total}   `);
    pos += PAGE_SIZE;
    if (total && pos >= total + PAGE_SIZE) break;
    if (pos > 20000) break;
    fs.writeFileSync(FILE, JSON.stringify(all, null, 1), 'utf8');
    await sleep(DELAY);
  }
  console.log('');

  // The list API only returns the first few pictures of multi-picture posts.
  const needDetail = all.filter(
    (m) => (m.pictotal || 0) > ((m.pic && m.pic.length) || 0)
  );
  console.log(`posts needing a full picture list: ${needDetail.length}`);
  let i = 0;
  for (const m of needDetail) {
    i++;
    try {
      const r = await pageFetch(page, detailUrl(uin, g_tk, m.tid));
      const d = unwrapJsonp(r.text);
      if (d && d.pic && d.pic.length > (m.pic || []).length) {
        m.pic = d.pic;
        m.__detailFetched = true;
      }
    } catch (e) {
      /* keep whatever the list gave us */
    }
    process.stdout.write(`\r  detail ${i}/${needDetail.length}   `);
    await sleep(DELAY);
  }
  console.log('');

  fs.writeFileSync(FILE, JSON.stringify(all, null, 1), 'utf8');
  console.log(`saved ${all.length} shuoshuo -> ${FILE}`);
  console.log(
    total && all.length < total
      ? `WARNING: got ${all.length} of ${total}. Some posts are invisible to this account, or rate limiting kicked in — re-run to retry.`
      : 'count matches the API total.'
  );
  browser.disconnect();
})().catch((e) => {
  console.error('\nERR', e.stack);
  process.exit(1);
});
