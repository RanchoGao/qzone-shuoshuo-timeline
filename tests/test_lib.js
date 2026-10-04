#!/usr/bin/env node
/**
 * Self-test for the pure parts of scripts/lib.js.
 *
 * Deliberately needs NO dependencies — puppeteer-core is only required inside
 * connect(), so this runs on a bare Node install.
 *
 * Usage: node tests/test_lib.js
 */
const assert = require('assert');
const path = require('path');

let pass = 0;
let fail = 0;

function check(label, fn) {
  try {
    fn();
    pass++;
  } catch (e) {
    fail++;
    console.log('FAIL  ' + label + '\n      ' + e.message);
  }
}

// ------------------------------------------------------------------ g_tk
const { gtk, unwrapJsonp } = require('../scripts/lib.js');

check('g_tk is deterministic', () => {
  assert.strictEqual(gtk('abc'), gtk('abc'));
});

check('g_tk differs for different input', () => {
  assert.notStrictEqual(gtk('abc'), gtk('abd'));
});

check('g_tk stays a positive 32-bit int', () => {
  for (const s of ['a', 'p_skey_value', 'x'.repeat(200), '\u4e2d\u6587']) {
    const v = gtk(s);
    assert.ok(Number.isInteger(v), s + ' -> not an integer');
    assert.ok(v >= 0 && v <= 0x7fffffff, s + ' -> out of range: ' + v);
  }
});

check('g_tk matches the documented djb2 variant', () => {
  // Independent reimplementation of the algorithm written out in SOP.md.
  const ref = (skey) => {
    let h = 5381;
    for (let i = 0; i < skey.length; i++) {
      h = (h + ((h << 5) + skey.charCodeAt(i))) | 0;
    }
    return (h & 0x7fffffff) >>> 0 & 0x7fffffff;
  };
  for (const s of ['abc', 'hello world', 'x'.repeat(64)]) {
    assert.strictEqual(gtk(s), ref(s), 'mismatch for ' + s);
  }
});

// ------------------------------------------------------------- jsonp
check('unwrapJsonp handles the standard wrapper', () => {
  assert.deepStrictEqual(unwrapJsonp('_preloadCallback({"code":0,"a":1});'),
    { code: 0, a: 1 });
});

check('unwrapJsonp handles leading whitespace/newlines', () => {
  assert.deepStrictEqual(unwrapJsonp('\n_Callback( \n{"code":0} \n);'), { code: 0 });
});

check('unwrapJsonp accepts bare JSON', () => {
  assert.deepStrictEqual(unwrapJsonp('{"code":0}'), { code: 0 });
});

check('unwrapJsonp accepts non-strict JSON', () => {
  assert.deepStrictEqual(unwrapJsonp('_Callback({uin:123,name:"ab"});'),
    { uin: 123, name: 'ab' });
});

check('unwrapJsonp keeps parentheses inside string values', () => {
  assert.strictEqual(unwrapJsonp('_Callback({"c":"a(b)c"});').c, 'a(b)c');
});

check('unwrapJsonp returns null for empty input', () => {
  assert.strictEqual(unwrapJsonp(''), null);
});

check('unwrapJsonp degrades safely on an HTML error page', () => {
  const r = unwrapJsonp('<html>404</html>');
  assert.ok(r && r.__parseError, 'expected a parse-error marker');
});

// --------------------------------------------------- output path rules
// The regression this guards: node and python used to disagree about whether
// QZONE_OUT is the root or the data dir, which broke a documented workflow.
const LIB = path.join(__dirname, '..', 'scripts', 'lib.js');

function libWithEnv(env) {
  const saved = {};
  for (const k of Object.keys(env)) {
    saved[k] = process.env[k];
    if (env[k] === undefined) delete process.env[k];
    else process.env[k] = env[k];
  }
  delete require.cache[require.resolve(LIB)];
  const m = require(LIB);
  for (const k of Object.keys(saved)) {
    if (saved[k] === undefined) delete process.env[k];
    else process.env[k] = saved[k];
  }
  return m;
}

check('QZONE_OUT is treated as the ROOT, data goes in <root>/data', () => {
  const m = libWithEnv({ QZONE_OUT: path.join('D:', 'backup', 'qzone') });
  assert.strictEqual(m.ROOT, path.join('D:', 'backup', 'qzone'));
  assert.strictEqual(m.OUT, path.join('D:', 'backup', 'qzone', 'data'));
});

check('default output is <repo>/data', () => {
  const m = libWithEnv({ QZONE_OUT: undefined });
  assert.strictEqual(m.OUT, path.join(__dirname, '..', 'data'));
});

check('QZONE_PORT and QZONE_DELAY are honoured', () => {
  const m = libWithEnv({ QZONE_PORT: '9333', QZONE_DELAY: '1500' });
  assert.strictEqual(m.CDP_URL, 'http://127.0.0.1:9333');
  assert.strictEqual(m.DELAY, 1500);
});

check('bad QZONE_DELAY falls back instead of becoming NaN', () => {
  const m = libWithEnv({ QZONE_DELAY: 'not-a-number' });
  assert.ok(Number.isFinite(m.DELAY) && m.DELAY > 0, 'got ' + m.DELAY);
});

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
