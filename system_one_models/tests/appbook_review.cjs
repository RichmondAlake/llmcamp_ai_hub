const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=process.env.APPBOOK_URL||'http://127.0.0.1:8878';
const out=process.env.EVIDENCE_DIR||path.resolve(__dirname,'../.data/browser');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1512,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/?lab=reranking&tab=learn');await page.waitForSelector('#reference-diagrams svg');
 assert.equal(await page.locator('.flow-figure').count(),3);
 assert.ok((await page.locator('#walkthrough').textContent()).includes('m08'));
 await page.locator('#use-case-diagram').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'reranking-diagram.png')});
 await page.click('[data-tab=experiment]');await page.waitForSelector('#aggregate-table tbody tr');
 assert.equal(await page.locator('#case-count').getAttribute('max'),'40');
 assert.equal(await page.locator('#case-count').inputValue(),'6');
 assert.match(await page.locator('#case-range').textContent(),/1–40 available/);
 // Exercise the real UI without authorizing another paid experiment.
 const submissions=[];
 await page.route('**/api/run',async route=>{
  submissions.push(route.request().postDataJSON());
  await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Submission captured by the browser test.'})});
 });
 for(const count of ['26','40']){
  await page.fill('#case-count',count);await page.click('#run');
  await page.waitForFunction(()=>document.querySelector('#error').textContent==='Submission captured by the browser test.');
 }
 assert.deepEqual(submissions.map(s=>s.limit),[26,40]);
 assert.match(await page.locator('#run-plan').textContent(),/280 result rows.*561 recorded calls/);
 for(const count of ['41','2.5']){
  await page.fill('#case-count',count);await page.click('#run');
  assert.match(await page.locator('#error').textContent(),/whole number from 1 to 40/);
 }
 assert.equal(submissions.length,2);
 await page.unroute('**/api/run');await page.fill('#case-count','40');
 assert.equal(await page.locator('#error').textContent(),'');
 await page.locator('.experiment-controls').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(out,'40-question-controls.png')});
 assert.ok((await page.locator('#run-models').textContent()).includes('rerank-2.5'));
 await page.locator('[data-sort=cost]').click();assert.equal(await page.locator('th:has([data-sort=cost])').getAttribute('aria-sort'),'ascending');
 let costs=await page.locator('#aggregate-table tbody tr td:last-child').evaluateAll(xs=>xs.map(x=>Number(x.dataset.value)));
 assert.deepEqual(costs,[...costs].sort((a,b)=>a-b));
 await page.locator('[data-sort=cost]').click();assert.equal(await page.locator('th:has([data-sort=cost])').getAttribute('aria-sort'),'descending');
 await page.locator('th:has([data-sort=recall]) .metric-help').focus();await page.waitForSelector('#metric-tooltip:not([hidden])');
 assert.ok((await page.locator('#metric-tooltip').textContent()).includes('fractional recall'));
 await page.keyboard.press('Escape');assert.ok(await page.locator('#metric-tooltip').isHidden());
 await page.selectOption('#quality-metric','precision');assert.ok((await page.locator('#quality-title').textContent()).includes('Precision@3'));
 await page.locator('#stats').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'reranking-metrics.png')});
 await page.click('[data-tab=build]');await page.waitForSelector('.notebook-diagram');
 assert.equal(await page.locator('.notebook-diagram').count(),3);
 assert.ok(!(await page.locator('#notebook-cells').textContent()).includes('```mermaid'));
 assert.ok(await page.locator('.notebook-output .output-scroll table').count()>0);
 await page.waitForFunction(()=>[...document.querySelectorAll('.notebook-output-image')].every(img=>img.complete&&img.naturalWidth>0));
 assert.equal(await page.locator('.notebook-output-image').count(),2);
 await page.locator('.notebook-output .output-scroll').first().scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(out,'notebook-dataset-preview.png')});
 for(const lab of ['summary','routing','selection','chunking','readers']){
  await page.locator(`nav [data-lab=${lab}]`).click();await page.waitForFunction(lab=>document.querySelector('nav button.active')?.dataset.lab===lab,lab);
  assert.ok(await page.locator('.flow-figure svg').count()>=2);
  await page.click('[data-tab=experiment]');await page.waitForSelector('#aggregate-table tbody tr');
  await page.waitForFunction(()=>document.querySelector('#history').value===selectedRun.id);
  if(lab==='summary'){
   assert.ok((await page.locator('#aggregate-table').textContent()).includes('Good rejected'));
   assert.ok(!(await page.locator('#aggregate-table').textContent()).includes('MRR'));
   await page.locator('#stats').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'summary-metrics.png')});
  }
  if(lab==='selection'){
   await page.selectOption('#catalog-kind','skill');
   assert.ok((await page.locator('#aggregate-table tbody').textContent()).includes('Full catalog'));
  }
 }
 await page.goto(base+'/?lab=routing&tab=learn');await page.waitForSelector('.flow-figure svg');
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:path.join(out,'routing-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'review-checks.json'),JSON.stringify({status:'passed',checks:['six diagrams and chapters','rendered notebook attachments','sort both directions','keyboard metric definitions','proper experiment metrics','actual Voyage model IDs','saved-run selection matches','mobile overflow','no runtime errors']},null,2));
 await browser.close();console.log('PASS: appbook read-only browser review');
})().catch(e=>{console.error(e);process.exit(1);});
