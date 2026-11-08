// Optional real Chromium smoke test; run after generating the research demo.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 try {
  const page=await browser.newPage({viewport:{width:1365,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(process.env.RESEARCH_HTML||'runs/p0-demo/report.html','utf8'));
  assert.equal(await page.locator('#fund-chart svg').count(),1);
  assert.equal(await page.locator('#pe-chart svg').count(),1);
  await page.locator('#mode').selectOption('rebased');
  assert.equal(await page.locator('#fund-chart svg').count(),1);
  await page.locator('#fund-chart [data-ref]').first().click();
  assert.equal(await page.locator('dialog').evaluate(e=>e.open),true);
  assert.match(await page.locator('#source-detail').innerText(),/合成/);
  assert.match(await page.locator('#source-detail').innerText(),/营业总收入TTM/);
  assert.match(await page.locator('#source-detail').innerText(),/总市值/);
  assert.equal(await page.locator('#source-links a').count(),1);
  await page.getByRole('button',{name:'关闭证据'}).click();
  // Real hit-testing at the actual overlapping baseline marker, not dispatchEvent
  // or force:true. This is the regression that jsdom alone cannot establish.
  await page.locator('#fund-chart').scrollIntoViewIfNeeded();
  const marker=await page.locator('#fund-chart circle').first().boundingBox();
  assert.ok(marker);
  await page.mouse.click(marker.x+marker.width/2,marker.y+marker.height/2);
  assert.equal(await page.locator('dialog').evaluate(e=>e.open),true);
  assert.match(await page.locator('#source-detail').innerText(),/营业总收入TTM/);
  assert.match(await page.locator('#source-detail').innerText(),/总市值/);
  await page.getByRole('button',{name:'关闭证据'}).click();
  await page.locator('#video-lines').check();
  assert.match(await page.locator('#pe-note').innerText(),/待核实|未核实/);
  await page.getByRole('button',{name:'数据证据',exact:true}).click();
  assert.equal(await page.locator('#evidence').isVisible(),true);
  await page.locator('#evidence-metric').selectOption('revenue');
  assert.equal(await page.locator('#data-table tr').count(),8);
  await page.getByRole('button',{name:'视频与口径',exact:true}).click();
  assert.equal(await page.locator('#video-table tr').count(),14);
  await page.getByRole('button',{name:'图表研究',exact:true}).click();
  await page.screenshot({path:'runs/p0-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.waitForFunction(()=>Number(document.querySelector('#fund-chart svg').getAttribute('viewBox').split(' ')[2])<=390);
  const mobilePlot=await page.locator('#fund-chart svg').boundingBox(),bottomNav=await page.locator('.nav').boundingBox();
  assert.ok(mobilePlot.y+Math.min(100,mobilePlot.height)<=bottomNav.y,'at least 100px of the first chart must be visible above mobile navigation');
  assert.equal(await page.locator('#fund-chart').evaluate(e=>e.scrollWidth<=e.clientWidth),true);
  await page.screenshot({path:'runs/p0-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('#start').fill('2030-01-01');await page.locator('#start').dispatchEvent('change');
  assert.match(await page.locator('#pe-chart').innerText(),/没有有效数据/);
  if(process.env.RESEARCH_REAL_HTML){
   const realPage=await browser.newPage({viewport:{width:390,height:844}});realPage.on('pageerror',e=>errors.push(e.message));
   await realPage.setContent(fs.readFileSync(process.env.RESEARCH_REAL_HTML,'utf8'));
   assert.equal(await realPage.locator('#fund-chart svg').count(),0);
   assert.equal(await realPage.locator('#fund-chart .snapshot').count(),1);
   assert.equal(await realPage.locator('#pe-panel').evaluate(e=>e.style.order),'1');
   await realPage.evaluate(()=>window.scrollTo(0,0));
   const plot=await realPage.locator('#pe-chart svg').boundingBox(),nav=await realPage.locator('.nav').boundingBox();
   assert.ok(plot.y<nav.y,'real PE curve should reach the first screen');
   assert.equal(await realPage.locator('#pe-chart').evaluate(e=>e.scrollWidth<=e.clientWidth),true);
   await realPage.screenshot({path:'runs/p0-real-mobile.png'});
   await realPage.close();
  }
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('Research Chromium smoke passed: baseline hit-testing, both evidence sources, filters, video map and responsive plots.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
