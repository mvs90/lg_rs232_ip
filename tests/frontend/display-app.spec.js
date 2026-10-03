const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assets = path.resolve('custom_components/lg_rs232_ip/www/display-app');
const content = () => ({id: 'test', title: 'Welcome <script>window.injected=true</script>', message: 'Your home', duration: 30, remaining: 30, rendered: false, layout: 'fullscreen', hdmi: 'ext://hdmi:1', cards: [{name: 'Temperature', value: '21', unit: '°C'}]});
async function mount(page, state) {
  const events = [];
  await page.route('http://display-app.test/**', async route => {
    const name = new URL(route.request().url()).pathname.split('/').pop();
    if (state.offline && ['state','event'].includes(name)) return route.fulfill({status:503,body:''});
    if (name === 'state') {
      return route.fulfill({contentType: 'application/json', body: JSON.stringify({version: '1.3.2', revision: 1, input_request: state.input_request || null, idle_hdmi: state.idle_hdmi || null, capture: state.capture || null, layout: state.layout || null, content: state.content})});
    }
    if (name === 'event') {
      const event = route.request().postDataJSON(); events.push(event);
      if (event.type === 'rendered' && state.content) state.content.rendered = true;
      return route.fulfill({contentType: 'application/json', body: '{"ok":true}'});
    }
    return route.fulfill({contentType: name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html', body: fs.readFileSync(path.join(assets, name)), headers: {'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src ext:; frame-ancestors 'none'"}});
  });
  await page.goto('http://display-app.test/index.html');
  return events;
}

test('paired app renders plain text, confirms paint and clears withdrawn content', async ({page}) => {
  const state = {content: content()};
  const events = await mount(page, state);
  await expect(page.locator('#title')).toHaveText(state.content.title);
  await expect(page.locator('.card')).toContainText('21 °C');
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  await expect.poll(() => events.some(e => e.type === 'rendered')).toBe(true);
  state.content = null;
  await expect(page.locator('#title')).toHaveText('Display bereit', {timeout: 5000});
  await expect(page.locator('.card')).toHaveCount(0);
});

test('paired app blanks private content on loss of HA connection', async ({page}) => {
  const state = {content: content()};
  await mount(page, state);
  await expect(page.locator('.card')).toHaveCount(1);
  state.offline = true;
  await page.waitForTimeout(150);
  await page.clock.install();
  await page.clock.fastForward(16000);
  await expect(page.locator('.card')).toHaveCount(0);
  await expect(page.locator('#title')).toHaveText('Display bereit');
});

test('missing HDMI signal does not delay overlay acknowledgement or PiP layout', async ({page}) => {
  await page.addInitScript(() => {
    window.hdmiReady = false;
    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {get: () => window.hdmiReady ? 3840 : 0});
    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {get: () => window.hdmiReady ? 2160 : 0});
    Object.defineProperty(HTMLVideoElement.prototype, 'error', {get: () => null});
  });
  const state = {content: {...content(), layout: 'overlay'}};
  const events = await mount(page, state);
  await expect(page.locator('#hdmi-slot source')).toHaveAttribute('src', 'ext://hdmi:1');
  await expect.poll(() => events.some(e => e.type === 'rendered')).toBe(true);
  await page.evaluate(() => { window.hdmiReady = true; });
  await expect.poll(() => events.some(e => e.type === 'rendered')).toBe(true);
  state.content.layout = 'pip';
  await expect(page.locator('body')).toHaveClass('pip');
  await expect(page.locator('#hdmi-slot video')).toHaveCount(1);
});

test('resident idle, overlay, PiP and expired/offline message retain the same HDMI element', async ({page}) => {
  await page.addInitScript(() => {
    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {get: () => 3840});
    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {get: () => 2160});
    Object.defineProperty(HTMLVideoElement.prototype, 'error', {get: () => null});
  });
  const state = {content: null, idle_hdmi: 'ext://hdmi:1'};
  await mount(page, state);
  await expect(page.locator('body')).toHaveClass('hdmi');
  await page.evaluate(() => {window.originalHDMI = document.querySelector('video');});
  state.content = {...content(), layout:'overlay'};
  await expect(page.locator('body')).toHaveClass('overlay');
  state.content = {...content(), layout:'pip'};
  await expect(page.locator('body')).toHaveClass('pip');
  state.content = null;
  await expect(page.locator('body')).toHaveClass('hdmi');
  expect(await page.evaluate(() => document.querySelector('video') === window.originalHDMI)).toBe(true);
  state.content = {...content(), id:'second-overlay', layout:'overlay'};
  await expect(page.locator('body')).toHaveClass('overlay');
  state.offline = true;
  await page.waitForTimeout(150);
  await page.clock.install(); await page.clock.fastForward(16000);
  await expect(page.locator('body')).toHaveClass('hdmi');
  expect(await page.evaluate(() => document.querySelector('video') === window.originalHDMI)).toBe(true);
  await expect(page.locator('#message')).toHaveText('');
});

test('app uploads one binary screenshot for a ticket and reports capture failures', async ({page}) => {
  await page.addInitScript(() => {
    window.captureCalls = 0;
    window.PalmServiceBridge = function() {
      this.call = () => {
        window.captureCalls++;
        this.onservicecallback(JSON.stringify({returnValue:true, encoding:'base64', data:btoa('\xff\xd8\xffimage\xff\xd9')}));
      };
      this.cancel = () => {};
    };
  });
  let uploads = [];
  const state = {content:null, capture:null};
  const events = await mount(page, state);
  // Route registered last takes precedence over the generic fixture route.
  await page.route('http://display-app.test/frame?*', async route => {
    uploads.push(route.request().postDataBuffer());
    await route.fulfill({contentType:'application/json',body:'{"ok":true}'});
  });
  state.capture = {id:'two',height:720};
  await expect.poll(() => uploads.length).toBe(1);
  expect(uploads[0].equals(Buffer.from([255,216,255,...Buffer.from('image'),255,217]))).toBe(true);
  await page.waitForTimeout(300);
  expect(uploads.length).toBe(1);
  await page.evaluate(() => {
    window.PalmServiceBridge = function() {
      this.call = () => this.onservicecallback(JSON.stringify({returnValue:false}));
      this.cancel = () => {};
    };
  });
  state.capture = {id:'failure',height:720};
  await expect.poll(() => events.some(e => e.type === 'capture_error' && e.id === 'failure')).toBe(true);
});

test('capture polls leave video, cards and unchanged DOM untouched', async ({page}) => {
  const state = {content: {...content(), layout:'overlay'}, idle_hdmi:'ext://hdmi:1'};
  await mount(page, state);
  await expect(page.locator('.card')).toHaveCount(1);
  await page.evaluate(() => {
    window.originalHDMI = document.querySelector('video');
    window.originalCard = document.querySelector('.card');
    window.mutations = 0;
    new MutationObserver(changes => { window.mutations += changes.length; }).observe(document.querySelector('main'), {subtree:true,childList:true,characterData:true,attributes:true});
  });
  await page.waitForTimeout(600);
  expect(await page.evaluate(() => window.mutations)).toBe(0);
  state.content.cards[0].value = '22';
  await expect(page.locator('.card')).toContainText('22 °C');
  expect(await page.evaluate(() => document.querySelector('.card') === window.originalCard && document.querySelector('video') === window.originalHDMI)).toBe(true);
});

test('HDMI selection reloads the same element once and acknowledges without signal', async ({page}) => {
  await page.addInitScript(() => {
    window.loads = 0;
    HTMLMediaElement.prototype.load = function() {window.loads++;};
    HTMLMediaElement.prototype.play = function() {};
    HTMLMediaElement.prototype.pause = function() {};
  });
  const state = {content:null, idle_hdmi:'ext://hdmi:1'};
  const events = await mount(page, state);
  await expect(page.locator('video source')).toHaveAttribute('src','ext://hdmi:1');
  await page.evaluate(() => {window.originalHDMI = document.querySelector('video');});
  state.idle_hdmi = 'ext://hdmi:2'; state.input_request = 'selection-two';
  await expect.poll(() => events.some(e => e.type === 'input_applied' && e.id === 'selection-two')).toBe(true);
  await page.waitForTimeout(200);
  expect(await page.evaluate(() => window.loads)).toBe(1);
  expect(await page.evaluate(() => document.querySelector('video') === window.originalHDMI)).toBe(true);
  await expect(page.locator('body')).toHaveClass('hdmi');
});

test('new content immediately replaces old content; expired content cannot reappear', async ({page}) => {
  const state = {content:content(),idle_hdmi:'ext://hdmi:1'};
  await mount(page,state);
  await expect(page.locator('#message')).toHaveText('Your home');
  state.content = {...content(),id:'new',message:'Latest',duration:1};
  await expect(page.locator('#message')).toHaveText('Latest');
  await expect(page.locator('body')).toHaveClass('hdmi',{timeout:3000});
  await page.waitForTimeout(200);
  await expect(page.locator('#message')).toHaveText('');
});

test('repeated screenshots release native bridges and retain one HDMI element', async ({page}) => {
  await page.addInitScript(() => {
    window.liveBridges = 0; window.maxBridges = 0; window.captureCalls = 0;
    window.PalmServiceBridge = function() {
      window.liveBridges++; window.maxBridges = Math.max(window.maxBridges, window.liveBridges);
      let cancelled = false;
      this.cancel = () => { if (!cancelled) {cancelled = true; window.liveBridges--;} };
      this.call = () => {
        window.captureCalls++;
        setTimeout(() => this.onservicecallback(JSON.stringify({returnValue:true,encoding:'base64',data:btoa('\xff\xd8\xffframe\xff\xd9')})), 5);
      };
    };
  });
  const state = {content:null,idle_hdmi:'ext://hdmi:1',capture:null};
  await mount(page,state);
  let uploads = 0;
  await page.route('http://display-app.test/frame?*', async route => {
    uploads++; await route.fulfill({contentType:'application/json',body:'{"ok":true}'});
  });
  await expect(page.locator('video')).toHaveCount(1);
  await page.evaluate(() => {window.originalHDMI = document.querySelector('video');});
  for (let i=0; i<30; i++) {
    state.capture = {id:'capture-'+i,height:720};
    await expect.poll(() => uploads).toBe(i+1);
    await expect.poll(() => page.evaluate(() => window.liveBridges)).toBe(0);
  }
  expect(await page.evaluate(() => window.maxBridges)).toBe(1);
  expect(await page.evaluate(() => window.captureCalls)).toBe(30);
  expect(await page.evaluate(() => document.querySelector('video') === window.originalHDMI)).toBe(true);
});

const studioPresets = require('../fixtures/studio-catalog.json').presets;
function designed(mode='signal') {
  const config=JSON.parse(JSON.stringify(studioPresets[1].layout));
  config.enabled=true; config.mode=mode; config.signal_delay=1;
  config.scenes.signal.elements.find(e=>e.kind==='entity').entity_id='sensor.temperature';
  return {config,revision:1,timezone:'Europe/Berlin',now:new Date().toISOString(),values:{'sensor.temperature':{state:'22',unit:'°C'}}};
}

test('designed scenes keep one HDMI plane through data updates, notifications and deactivation', async ({page}) => {
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed()};
  await mount(page,state);
  await expect(page.locator('body')).toHaveClass('designed');
  await expect(page.locator('.lg-entity')).toContainText('22 °C');
  expect(await page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('61%');
  await page.evaluate(()=>{window.originalHDMI=document.querySelector('video');window.originalWidget=document.querySelector('.lg-entity');window.mutations=0;new MutationObserver(changes=>window.mutations+=changes.length).observe(document.querySelector('.lg-entity'),{subtree:true,attributes:true,childList:true,characterData:true});});
  await page.waitForTimeout(350);
  expect(await page.evaluate(()=>window.mutations)).toBe(0);
  state.layout.values['sensor.temperature'].state='23';
  await expect(page.locator('.lg-entity')).toContainText('23 °C');
  expect(await page.evaluate(()=>document.querySelector('.lg-entity')===window.originalWidget)).toBe(true);
  state.content={...content(),layout:'overlay',duration:1};
  await expect(page.locator('.lg-message')).toContainText('Your home');
  expect(await page.evaluate(()=>window.injected)).toBeUndefined();
  await expect(page.locator('.lg-message')).toHaveCount(0,{timeout:3000});
  expect(await page.evaluate(()=>document.querySelector('video')===window.originalHDMI)).toBe(true);
  state.layout=null;
  await expect(page.locator('body')).toHaveClass('hdmi');
  expect(await page.locator('#hdmi-slot').getAttribute('style')).toBeNull();
});

test('automatic no-signal debounce and manual dashboard mode do not reload HDMI', async ({page}) => {
  await page.addInitScript(()=>{
    window.ready=true;window.loads=0;
    Object.defineProperty(HTMLVideoElement.prototype,'videoWidth',{get:()=>window.ready?1920:0});
    Object.defineProperty(HTMLVideoElement.prototype,'videoHeight',{get:()=>window.ready?1080:0});
    Object.defineProperty(HTMLVideoElement.prototype,'error',{get:()=>null});
    HTMLMediaElement.prototype.load=function(){window.loads++;};
  });
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed('auto')};
  await mount(page,state);
  await expect(page.locator('#hdmi-slot')).toBeVisible();
  await page.evaluate(()=>{window.ready=false;});
  await page.waitForTimeout(200);
  await expect(page.locator('#hdmi-slot')).toBeVisible();
  await expect(page.locator('#hdmi-slot')).toBeHidden({timeout:3500});
  await page.evaluate(()=>{window.ready=true;});
  await expect(page.locator('#hdmi-slot')).toBeVisible({timeout:2000});
  state.layout.config.mode='no_signal';
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  await expect(page.locator('.lg-clock')).toBeVisible();
  expect(await page.evaluate(()=>window.loads)).toBe(0);
});

test('layouts work without resident HDMI and plain text/calendar data cannot inject markup', async ({page}) => {
  const state={content:{...content(),layout:'pip'},layout:designed(),idle_hdmi:null};
  state.layout.config.scenes.pip.elements.push({...state.layout.config.scenes.signal.elements.find(e=>e.kind==='calendar'),entity_id:'calendar.test'});
  state.layout.values['calendar.test']={state:'on',events:[{summary:'<img src=x onerror=window.injected=true>',start:'2026-10-04'}]};
  const events=await mount(page,state);
  await expect(page.locator('#hdmi-slot source')).toHaveAttribute('src','ext://hdmi:1');
  await expect(page.locator('.lg-calendar')).toContainText('<img src=x');
  await expect(page.locator('.lg-calendar img')).toHaveCount(0);
  expect(await page.evaluate(()=>window.injected)).toBeUndefined();
  await expect.poll(()=>events.some(e=>e.type==='rendered')).toBe(true);
});

test('unchanged dashboard polls do not repeat calendar date formatting', async ({page}) => {
  await page.addInitScript(()=>{
    window.dateFormats=0;const original=Date.prototype.toLocaleDateString;
    Date.prototype.toLocaleDateString=function(...args){window.dateFormats++;return original.apply(this,args);};
  });
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed()};
  state.layout.config.scenes.signal.elements.find(e=>e.kind==='calendar').entity_id='calendar.family';
  state.layout.values['calendar.family']={state:'off',events:[{summary:'Dinner',start:'2026-10-04T19:00:00+02:00'}]};
  await mount(page,state);
  await expect(page.locator('.lg-calendar')).toContainText('Dinner');
  const count=await page.evaluate(()=>window.dateFormats);
  await page.waitForTimeout(400);
  expect(await page.evaluate(()=>window.dateFormats)).toBe(count);
  state.layout.values['calendar.family'].events[0].summary='Latest';
  await expect(page.locator('.lg-calendar')).toContainText('Latest');
});
