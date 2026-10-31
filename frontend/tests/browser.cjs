const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || 'chrome', headless: true});
  const page = await browser.newPage({viewport:{width:1280,height:1000}});
  const batch = {id:'batch-1',directory:'/tmp/tts/1793325000',timestamp:1793325000,mode:'preset',concurrency:2,status:'running',tasks:[
    {id:'task-1',voice:'Zephyr',filename:'1793325000-Zephyr.wav',status:'running',size:0},
    {id:'task-2',voice:'Kore',filename:'1793325000-Kore.wav',status:'pending',size:0}
  ]};
  await page.route('http://127.0.0.1:8771/api/v1/config', route => route.fulfill({json:{
    default_text:'こんにちは。',default_instructions:'自然な日本語。',preset_model:'google/gemini-3.8-flash-tts',clone_model:'fish-audio/s2.1-pro',
    voices:Array.from({length:30},(_,i)=>({id:i===0?'Zephyr':i===1?'Kore':'Voice'+i,description:'说明'})),models:[],output_directory:'/tmp/tts',can_choose_directory:false
  }}));
  await page.route('http://127.0.0.1:8771/api/v1/batches', async route => {
    if(route.request().method()==='GET') return route.fulfill({json:[batch]});
    const payload=route.request().postDataJSON(); assert.deepEqual(payload.voices,['Zephyr','Kore']); assert.equal(payload.concurrency,2);
    return route.fulfill({status:202,json:batch});
  });
  await page.route('http://127.0.0.1:8771/api/v1/batches/batch-1', async route => {
    batch.status='completed'; batch.tasks[0].status='done'; batch.tasks[0].size=4844; batch.tasks[1].status='done'; batch.tasks[1].size=4844;
    return route.fulfill({json:batch});
  });
  await page.route('http://127.0.0.1:8771/api/v1/tasks/**/audio', route => route.fulfill({status:200,contentType:'audio/wav',body:Buffer.from('RIFFaudio')}));
  await page.goto('http://127.0.0.1:8770/');
  await page.waitForFunction(() => document.querySelectorAll('#voice-options input').length===30);
  await page.locator('#clear-voices').click();
  await page.locator('#voice-options input[value=Zephyr]').check();
  await page.locator('#voice-options input[value=Kore]').check();
  await page.locator('#concurrency').fill('2');
  await page.locator('#generate-button').click();
  await page.waitForFunction(() => document.querySelectorAll('.task-row[data-status=done]').length===2);
  assert.equal(await page.locator('.batch-group').count(),1);
  assert.equal(await page.locator('.task-row a[download]').count(),2);
  assert.equal(await page.locator('#history-list').textContent().then(text=>text.includes('/tmp/tts/1793325000')),true);
  console.log('refactored browser: PASS');
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
