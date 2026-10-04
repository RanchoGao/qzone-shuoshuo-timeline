/**
 * Close the debug browser started for this export.
 * Always run this — otherwise the Chromium process stays resident.
 * Usage: NODE_PATH=<mods> node scripts/close.js
 */
const { connect } = require('./lib');

(async () => {
  const browser = await connect();
  await browser.close();
  console.log('browser closed');
})().catch((e) => {
  console.log('nothing to close / ' + e.message);
});
