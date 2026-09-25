/* Opt-in browser-to-OracleVS integration test. Makes real, billable model calls. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const existingRun = process.env.APPBOOK_EXISTING_RUN;
if (process.env.RUN_APPBOOK_LIVE !== '1' && !existingRun) {
  console.log('SKIP: set RUN_APPBOOK_LIVE=1 to authorize one live reranking question.');
  process.exit(0);
}
const {chromium} = require('playwright');
const base = process.env.APPBOOK_URL || 'http://127.0.0.1:8878';
const cases = Number(process.env.APPBOOK_TEST_CASES || '1');
assert.ok(Number.isInteger(cases) && cases >= 1 && cases <= 40);
const output = process.env.EVIDENCE_DIR || path.resolve(__dirname, '../.data/browser');
fs.mkdirSync(output, {recursive: true});
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1512, height: 1100}});
    const errors = [], updates = [];
    page.on('pageerror', error => errors.push(error.message));
    let runId;
    page.on('response', async response => {
      if (!runId || !response.url().endsWith('/api/runs/' + runId)) return;
      try {
        const data = await response.json();
        updates.push({status: data.status, rows: data.results.length});
      } catch {}
    });
    const journal = await (await page.request.get(base + '/api/database/activity')).json();
    let cursor = existingRun ? Math.max(1, journal.retained_from - 1) : journal.cursor;
    await page.goto(base + '/?lab=reranking&tab=experiment' + (existingRun ? '&run=' + existingRun : ''));
    if (existingRun) runId = existingRun;
    else {
      await page.waitForFunction(() => !document.querySelector('#run').disabled);
      await page.fill('#case-count', String(cases));
      const submitted = page.waitForResponse(r => r.url().endsWith('/api/run') && r.request().method() === 'POST');
      await page.click('#run');
      const response = await submitted;
      assert.equal(response.status(), 202);
      runId = (await response.json()).id;
    }
    console.log('Live OracleVS reranking run:', runId);
    await page.waitForFunction(id => {
      const text = document.querySelector('#status-line').textContent;
      return text.includes(id) && /^(COMPLETED|FAILED)/.test(text);
    }, runId, {timeout: 360000});
    const run = await (await page.request.get(base + '/api/runs/' + runId)).json();
    assert.equal(run.status, 'completed', run.error);
    assert.equal(run.results.length, cases * 7);
    assert.equal(run.protocol_version, 3);
    assert.match(run.storage_backend, /langchain-oracledb 1\.5\.0/);
    assert.ok(run.calls.every(call => call.status === 'completed'));
    assert.ok(run.calls.filter(call => call.provider === 'openai').every(call => call.model === 'gpt-6-luna'));
    assert.equal(run.calls.filter(call => call.lane === 'embedding_ingest').length, 1, 'No hidden dimension-probe call');
    for (const id of new Set(run.results.map(row => row.case_id))) {
      assert.equal(new Set(run.results.filter(row => row.case_id === id).map(row => row.candidates_hash)).size, 1);
    }
    if (!existingRun) assert.ok(updates.some(update => update.status === 'running' && update.rows > 0 && update.rows < cases * 7));
    assert.match(await page.locator('#protocol-note').textContent(), /OracleVS/);
    const table = await (await page.request.get(base + '/api/database/table/S1_VECTORS?run=' + runId)).json();
    assert.equal(table.total, 30);
    const key = encodeURIComponent(JSON.stringify(table.rows[0].key));
    const record = await (await page.request.get(base + '/api/database/row/S1_VECTORS?key=' + key)).json();
    assert.equal(record.record.METADATA.run_id, runId);
    const events = [];
    let activity;
    do {
      activity = await (await page.request.get(base + '/api/database/activity?after=' + cursor)).json();
      events.push(...activity.events);
      cursor = activity.cursor;
    } while (activity.has_more);
    for (const kind of ['READ', 'WRITE']) {
      assert.ok(events.some(e => e.run_id === runId && e.tables.includes('S1_VECTORS') && e.kind === kind));
    }
    assert.deepEqual(errors, []);
    await page.locator('#stats').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(output, 'oraclevs-live.png')});
    fs.writeFileSync(path.join(output, 'oraclevs-live.json'), JSON.stringify({run_id: runId, mode: existingRun ? 'saved-run verification' : 'live', updates, calls: run.calls.length}, null, 2));
    console.log('PASS: real OracleVS ingestion, live charts, Luna calls, frozen pools and inspectable database rows.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
