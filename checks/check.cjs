// Fixed acceptance harness. The daily agent must NOT edit this file to make checks pass.
// Usage: node checks/check.cjs [path/to/index.html]  -> writes checks/report.json, exit 1 on any FAIL
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const FILE = path.resolve(process.argv[2] || 'index.html');
const ROUTES = { hub:'p_hub', atlas:'p_atl', power:'p_pwr', research:'p_rs', radar:'p_nw', chart:'p_ch',
  scanner:'p_sc', daytrade:'p_dt', backtest:'p_bt', options:'p_ob', ipo:'p_ipo', dhamma:'p_dha', about:'p_ab' };
const SIZE_LIMIT_MB = 20;
// Public commercial site: no internal-employer material, no advice-like wording.
const BANNED = [
  [/PFC Credit Policy Compendium/i, 'internal PFC policy document named on public site'],
  [/PFC[- ]NRD|LPCU|RMD-I|Resource Mobilisation Dep/i, 'internal PFC unit/app name'],
  [/PFC (Hub|Intelligence Hub|News Radar)|Power Sector &amp; PFC|&amp; PFC Hub/i, 'site branded around employer'],
  [/\b(sure[- ]shot|guaranteed returns?|buy now|sell now|jackpot)\b/i, 'advice-like wording (SEBI)'],
];
const REQUIRED = [/not investment advice/i, /SEBI/];
const results = []; const add = (level, check, detail) => results.push({ level, check, detail });

(async () => {
  const html = fs.readFileSync(FILE, 'utf8');
  const mb = fs.statSync(FILE).size / 1048576;
  add(mb <= SIZE_LIMIT_MB ? 'PASS' : 'FAIL', 'size', `${mb.toFixed(2)} MB (limit ${SIZE_LIMIT_MB})`);
  const visible = html.replace(/<script type="application\/octet-stream"[\s\S]*?<\/script>/g, '');
  for (const [re, why] of BANNED) {
    const m = visible.match(new RegExp(re.source, re.flags + 'g')) || [];
    add(m.length ? 'FAIL' : 'PASS', `wording: ${why}`, m.length ? `${m.length}x e.g. "${m[0]}"` : 'none');
  }
  for (const re of REQUIRED) add(re.test(visible) ? 'PASS' : 'FAIL', `required text ${re}`, '');

  const browser = await chromium.launch();
  for (const vp of [{ name: 'desktop', width: 1440, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    const errs = [];
    page.on('pageerror', e => errs.push('pageerror: ' + e.message));
    page.on('console', m => { if (m.type() === 'error' && !/net::|Failed to load resource|CORS|fetch|NetworkError|ERR_/i.test(m.text())) errs.push('console: ' + m.text()); });
    const t0 = Date.now();
    await page.goto('file://' + FILE, { waitUntil: 'load', timeout: 120000 });
    await page.waitForTimeout(2500);
    add(Date.now() - t0 < 30000 ? 'PASS' : 'WARN', `${vp.name} load time`, `${Date.now() - t0} ms`);
    for (const [hash, id] of Object.entries(ROUTES)) {
      const before = errs.length;
      await page.evaluate(h => { location.hash = h; }, hash);
      await page.waitForTimeout(1800);
      const st = await page.evaluate(id => {
        const el = document.getElementById(id); if (!el) return { missing: true };
        const cs = getComputedStyle(el);
        return { shown: cs.display !== 'none' && el.offsetHeight > 0, text: (el.innerText || '').trim().length,
          overflow: document.documentElement.scrollWidth - window.innerWidth };
      }, id);
      if (st.missing) { add('FAIL', `${vp.name} #${hash}`, `section ${id} missing`); continue; }
      add(st.shown && st.text > 80 ? 'PASS' : 'FAIL', `${vp.name} #${hash} renders`, `shown=${st.shown} chars=${st.text}`);
      if (vp.name === 'mobile') add(st.overflow <= 2 ? 'PASS' : 'FAIL', `mobile #${hash} no horizontal scroll`, `overflow ${st.overflow}px`);
      const newE = errs.slice(before);
      add(newE.length ? 'FAIL' : 'PASS', `${vp.name} #${hash} JS errors`, newE.slice(0, 3).join(' | ') || 'none');
    }
    await page.screenshot({ path: path.join(__dirname, `shot-${vp.name}.png`) });
    await page.close();
  }
  await browser.close();
  const fails = results.filter(r => r.level === 'FAIL');
  const report = { file: FILE, at: new Date().toISOString(), pass: results.filter(r => r.level === 'PASS').length,
    warn: results.filter(r => r.level === 'WARN').length, fail: fails.length, results };
  fs.writeFileSync(path.join(__dirname, 'report.json'), JSON.stringify(report, null, 2));
  console.log(`PASS ${report.pass}  WARN ${report.warn}  FAIL ${report.fail}`);
  fails.forEach(f => console.log('FAIL', f.check, '-', f.detail));
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
