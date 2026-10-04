/**
 * Sniff the real CGI endpoints a Qzone page uses.
 *
 * Endpoint paths have changed over the years — sniff instead of guessing.
 * Usage: NODE_PATH=<mods> node scripts/sniff.js [pathAfterUin]
 *          node scripts/sniff.js              -> the Qzone home page
 *          node scripts/sniff.js blog         -> the blog list
 *          node scripts/sniff.js blog/<id>    -> one blog post
 */
const { connect, getQzonePage, getAuth } = require('./lib');

(async () => {
  const browser = await connect();
  const page = await getQzonePage(browser);
  const { uin } = await getAuth(page);
  const sub = process.argv[2] || '';
  const target = `https://user.qzone.qq.com/${uin}${sub ? '/' + sub : ''}`;

  const hits = [];
  const seen = new Set();
  const noisy = /report\.huatuo|pingfore|huatuocode|\.js(\?|$)|qzonestyle/;
  page.on('request', (req) => {
    const u = req.url();
    if (seen.has(u)) return;
    seen.add(u);
    if (/cgi-bin|\/proxy\/domain/.test(u) && !noisy.test(u)) hits.push(u);
  });

  console.log('opening', target);
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await new Promise((r) => setTimeout(r, 12000));

  console.log('\n--- candidate CGI endpoints ---');
  hits.forEach((h) => console.log(h));
  console.log('\n--- frames ---');
  for (const f of page.frames()) console.log(f.url().slice(0, 160));
  browser.disconnect();
})().catch((e) => {
  console.error('ERR', e.stack);
  process.exit(1);
});
