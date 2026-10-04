/**
 * Shared helpers for the Qzone exporter.
 *
 * puppeteer-core is required lazily inside connect(), so this module can be
 * imported (and its pure helpers unit-tested) without the dependency present.
 *
 * Environment overrides:
 *   QZONE_HOST   CDP host        (default 127.0.0.1)
 *   QZONE_PORT   CDP port        (default 9222)
 *   QZONE_OUT    output ROOT     (default: the repo/skill root).
 *                                JSON lands in <QZONE_OUT>/data, matching what
 *                                the python scripts read.
 *   QZONE_DELAY  request spacing in ms (default 700)
 *   QZONE_UA     override User-Agent sent for downloads
 */

const HOST = process.env.QZONE_HOST || '127.0.0.1';
const PORT = process.env.QZONE_PORT || '9222';
// QZONE_OUT is the *root* of the output tree; both the node and the python
// scripts put their JSON in <root>/data so they can be pointed at each other.
const ROOT = process.env.QZONE_OUT || require('path').join(__dirname, '..');
const OUT = require('path').join(ROOT, 'data');
const DELAY = Number(process.env.QZONE_DELAY || 700) || 700;
const CDP_URL = `http://${HOST}:${PORT}`;

const fs = require('fs');

async function connect() {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
  let puppeteer;
  try {
    puppeteer = require('puppeteer-core');
  } catch (e) {
    throw new Error(
      "Cannot find module 'puppeteer-core'. Install it (npm install puppeteer-core) "
      + 'and point NODE_PATH at the node_modules folder that contains it.'
    );
  }
  return puppeteer.connect({ browserURL: CDP_URL, defaultViewport: null });
}

/** Find the Qzone page (or fall back to any open tab). */
async function getQzonePage(browser) {
  const pages = await browser.pages();
  let page = pages.find((p) => /qzone\.qq\.com|qq\.com/.test(p.url()));
  if (!page) {
    page = pages[0] || (await browser.newPage());
  }
  return page;
}

/** Qzone g_tk / bkn hash derived from p_skey (falls back to skey). */
function gtk(skey) {
  let hash = 5381;
  for (let i = 0; i < skey.length; i++) {
    hash += (hash << 5) + skey.charCodeAt(i);
    hash = hash & 0xffffffff; // keep intermediate value 32-bit
  }
  return hash & 0x7fffffff;
}

async function getAuth(page) {
  const client = await page.createCDPSession();
  const { cookies } = await client.send('Network.getAllCookies');
  await client.detach();

  const pick = (name, domainRe) => {
    const c = cookies.filter(
      (x) => x.name === name && (!domainRe || domainRe.test(x.domain))
    );
    return c.length ? c[c.length - 1].value : null;
  };

  const p_skey = pick('p_skey', /qzone\.qq\.com|qq\.com/);
  const skey = pick('skey');
  const uinRaw = pick('uin') || pick('p_uin');
  const uin = uinRaw ? uinRaw.replace(/^o0*/, '').replace(/^o/, '') : null;

  const cookieStr = cookies
    .filter((c) => /qq\.com$/.test(c.domain.replace(/^\./, '')))
    .map((c) => `${c.name}=${c.value}`)
    .join('; ');

  return {
    uin,
    p_skey,
    skey,
    g_tk: p_skey ? gtk(p_skey) : skey ? gtk(skey) : null,
    cookieStr,
    loggedIn: Boolean(uin && (p_skey || skey)),
  };
}

/** Run a fetch inside the page context: same-origin, cookies sent automatically. */
async function pageFetch(page, url) {
  return page.evaluate(async (u) => {
    const r = await fetch(u, { credentials: 'include' });
    const buf = await r.arrayBuffer();
    const ct = r.headers.get('content-type') || '';
    let text;
    try {
      text = new TextDecoder(/gbk|gb2312/i.test(ct) ? 'gbk' : 'utf-8').decode(buf);
    } catch (e) {
      text = new TextDecoder('utf-8').decode(buf);
    }
    return { status: r.status, contentType: ct, text };
  }, url);
}

/** Strip a jsonp wrapper like _Callback({...}); leaving an object. */
function unwrapJsonp(text) {
  if (!text) return null;
  let t = text.trim();
  const start = t.indexOf('(');
  const end = t.lastIndexOf(')');
  if (start > -1 && end > start) {
    t = t.slice(start + 1, end);
  }
  t = t.trim().replace(/;$/, '');
  try {
    return JSON.parse(t);
  } catch (e) {
    // Qzone sometimes returns non-strict JSON (unquoted keys, trailing commas)
    try {
      return Function('"use strict"; return (' + t + ')')();
    } catch (e2) {
      return { __parseError: e2.message, __raw: text.slice(0, 2000) };
    }
  }
}

/** Make sure we sit on a same-origin qzone page before calling any cgi. */
async function ensureOnQzone(page, uin) {
  if (!/^https:\/\/user\.qzone\.qq\.com/.test(page.url())) {
    await page.goto(`https://user.qzone.qq.com/${uin}`, {
      waitUntil: 'domcontentloaded',
    });
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = {
  connect,
  getQzonePage,
  getAuth,
  pageFetch,
  unwrapJsonp,
  ensureOnQzone,
  gtk,
  sleep,
  OUT,
  ROOT,
  DELAY,
  CDP_URL,
};
