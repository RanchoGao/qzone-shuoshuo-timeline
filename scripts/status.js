/**
 * Check Qzone login state and print uin / g_tk.
 * Usage: NODE_PATH=<mods> node scripts/status.js
 */
const path = require('path');
const fs = require('fs');
const { connect, getQzonePage, getAuth, OUT } = require('./lib');

(async () => {
  const browser = await connect();
  const pages = await browser.pages();
  console.log('open tabs:');
  for (const p of pages) console.log('  -', p.url());

  const page = await getQzonePage(browser);
  const auth = await getAuth(page);

  console.log('\ncurrent url:', page.url());
  console.log('loggedIn  :', auth.loggedIn);
  console.log('uin       :', auth.uin);
  console.log('has p_skey:', Boolean(auth.p_skey));
  console.log('g_tk      :', auth.g_tk);

  if (auth.loggedIn) {
    fs.mkdirSync(OUT, { recursive: true });
    // cookieStr is a live credential: do NOT persist it here
    fs.writeFileSync(
      path.join(OUT, 'auth.json'),
      JSON.stringify({ uin: auth.uin, g_tk: auth.g_tk }, null, 1)
    );
    console.log('\nauth written to', path.join(OUT, 'auth.json'));
  } else {
    console.log('\nnot logged in — ask the user to scan the QR code in the open window,');
    console.log('then re-run this script. Never ask for the password in chat.');
  }

  browser.disconnect();
})().catch((e) => {
  console.error('ERR', e.message);
  console.error('\nIs Chrome running with --remote-debugging-port=9222?');
  process.exit(1);
});
