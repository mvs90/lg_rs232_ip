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
      return route.fulfill({contentType: 'application/json', body: JSON.stringify({version: '1.13.0', revision: 1, hdmi_fit: state.hdmi_fit || "contain", dashboard: state.dashboard || false, pip: state.pip || false, media_view: state.media_view || false, selected_view: state.selected_view || null, input_request: state.input_request || null, input_transition: state.input_transition || "none", idle_hdmi: state.idle_hdmi || null, capture: state.capture || null, layout: state.layout || null, content: state.content})});
    }
    if(name === 'cover.jpg')return route.fulfill(new URL(route.request().url()).searchParams.get('v')==='missing'?{status:204,body:''}:{contentType:'image/png',body:fs.readFileSync('tests/fixtures/media-cover.png')});
    if (name === 'event') {
      const event = route.request().postDataJSON(); events.push(event);
      if (event.type === 'rendered' && state.content) state.content.rendered = true;
      return route.fulfill({contentType: 'application/json', body: '{"ok":true}'});
    }
    return route.fulfill({contentType: name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : name.endsWith('.png') ? 'image/png' : 'text/html', body: fs.readFileSync(path.join(assets, name)), headers: {'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; media-src ext:; frame-ancestors 'none'"}});
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
  config.scenes.pip_view.elements.find(e=>e.kind==='entity').entity_id='sensor.temperature';
  return {config,revision:1,timezone:'Europe/Berlin',now:new Date().toISOString(),values:{'sensor.temperature':{state:'22',unit:'°C'}}};
}

test('designed scenes keep one HDMI plane through data updates, notifications and deactivation', async ({page}) => {
  const state={content:null,idle_hdmi:'ext://hdmi:1',pip:true,layout:designed()};
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

test('HDMI stays fullscreen despite signal loss or saved layouts; only explicit PiP enters its view', async ({page}) => {
  await page.addInitScript(()=>{
    window.ready=true;window.loads=0;
    Object.defineProperty(HTMLVideoElement.prototype,'videoWidth',{get:()=>window.ready?1920:0});
    Object.defineProperty(HTMLVideoElement.prototype,'videoHeight',{get:()=>window.ready?1080:0});
    Object.defineProperty(HTMLVideoElement.prototype,'error',{get:()=>null});
    HTMLMediaElement.prototype.load=function(){window.loads++;};
  });
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed('auto')};
  await mount(page,state);
  await expect(page.locator('body')).toHaveClass('designed');
  await page.evaluate(()=>{window.ready=false;window.originalHDMI=document.querySelector('video');});
  state.layout.config.mode='no_signal';
  await page.waitForTimeout(1500);
  await expect(page.locator('body')).toHaveClass('designed');
  await expect(page.locator('#hdmi-slot')).toBeVisible();
  await expect(page.locator('.lg-widget')).toHaveCount(0);
  state.pip=true;
  await expect(page.locator('body')).toHaveClass('designed');
  expect(await page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('61%');
  state.content={...content(),layout:'overlay',duration:1};
  await expect(page.locator('.lg-message')).toBeVisible();
  await expect(page.locator('.lg-message')).toHaveCount(0,{timeout:3000});
  expect(await page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('61%');
  state.pip=false;
  await expect(page.locator('body')).toHaveClass('designed');
  expect(await page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  expect(await page.evaluate(()=>document.querySelector('video')===window.originalHDMI)).toBe(true);
  expect(await page.evaluate(()=>window.loads)).toBe(0);
});

test('layouts work without resident HDMI and plain text/calendar data cannot inject markup', async ({page}) => {
  const state={content:{...content(),layout:'pip'},layout:designed(),idle_hdmi:null};
  state.layout.config.scenes.pip.elements.push({...state.layout.config.scenes.pip_view.elements.find(e=>e.kind==='calendar'),entity_id:'calendar.test'});
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
  const state={content:null,idle_hdmi:'ext://hdmi:1',pip:true,layout:designed()};
  state.layout.config.scenes.pip_view.elements.find(e=>e.kind==='calendar').entity_id='calendar.family';
  state.layout.values['calendar.family']={state:'off',events:[{summary:'Dinner',start:'2026-10-04T19:00:00+02:00'}]};
  await mount(page,state);
  await expect(page.locator('.lg-calendar')).toContainText('Dinner');
  const count=await page.evaluate(()=>window.dateFormats);
  await page.waitForTimeout(400);
  expect(await page.evaluate(()=>window.dateFormats)).toBe(count);
  state.layout.values['calendar.family'].events[0].summary='Latest';
  await expect(page.locator('.lg-calendar')).toContainText('Latest');
});

test('Dashboard source ignores HDMI signal, uses its own scene and preserves video identity on return', async ({page}) => {
  const state={content:null,idle_hdmi:'ext://hdmi:1',dashboard:true,layout:designed('auto')};
  state.layout.config.scenes.dashboard.elements=[];
  await mount(page,state);
  await expect(page.locator('body')).toHaveClass('designed');
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  await page.evaluate(()=>window.originalHDMI=document.querySelector('video'));
  state.content={...content(),layout:'overlay',duration:1};
  await expect(page.locator('.lg-message')).toBeVisible();
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  await expect(page.locator('.lg-message')).toHaveCount(0,{timeout:3000});
  state.dashboard=false;state.layout.config.mode='signal';
  await expect(page.locator('#hdmi-slot')).toBeVisible();
  expect(await page.evaluate(()=>document.querySelector('video')===window.originalHDMI)).toBe(true);
});

test('weather shows hourly night icons, bounded forecasts, solar gradients and switchable animation', async ({page}) => {
  const state={content:null,idle_hdmi:'ext://hdmi:1',dashboard:true,layout:designed()};
  const cfg=state.layout.config, weather=cfg.scenes.dashboard.elements.find(i=>i.kind==='weather');
  weather.entity_id='weather.test';weather.forecast_type='hourly';weather.forecast_count=6;weather.weather_style='sky';
  cfg.scenes.dashboard.background='solar';
  state.layout.sun={elevation:-14,azimuth:330,rising:false,is_daytime:false};
  state.layout.values['weather.test']={state:'clear-night',temperature:'8',temperature_unit:'°C',forecasts:{hourly:Array.from({length:12},(_,i)=>({datetime:'2026-10-04T'+String(i).padStart(2,'0')+':00:00+02:00',condition:'sunny',temperature:String(8+i),is_daytime:i>5,precipitation_probability:'5'}))}};
  await page.setViewportSize({width:1280,height:720});
  await mount(page,state);
  await expect(page.locator('.lg-weather .lg-value')).toHaveText('8 °C');
  await expect(page.locator('.lg-forecast-period')).toHaveCount(6);
  expect(await page.locator('.lg-weather>.lg-weather-icon').evaluate(node=>node._wxType)).toBe('moon');
  const night=await page.locator('#layout-root').evaluate(node=>node.style.background);
  await page.screenshot({path:'test-results/weather-dashboard-night-'+test.info().project.name+'.png'});
  state.layout.sun={elevation:35,azimuth:160,rising:true,is_daytime:true};state.layout.values['weather.test'].state='sunny';
  await expect.poll(()=>page.locator('#layout-root').evaluate(node=>node.style.background)).not.toBe(night);
  await expect(page.locator('.lg-weather>.lg-weather-icon')).toHaveClass(/wx-animated/);
  weather.animate=false;
  await expect(page.locator('.lg-weather>.lg-weather-icon')).not.toHaveClass(/wx-animated/);
  await page.screenshot({path:'test-results/weather-dashboard-day-'+test.info().project.name+'.png'});
  state.layout.values['weather.test'].state='unavailable';
  await expect(page.locator('.lg-forecast-period')).toHaveCount(0);
  await expect(page.locator('.lg-weather>.lg-weather-icon')).toBeHidden();
});

test('media cards render artwork and status, advance only playing progress and clear stale metadata',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',dashboard:true,layout:designed()};
  state.layout.now=null; // Use the live browser clock instead of this fixture's frozen server time.
  const base=state.layout.config.scenes.dashboard.elements[0];
  const card={...base,id:'music',kind:'media',entity_id:'media_player.music',label:'WOHNZIMMER',x:4,y:6,width:59,height:35,font_size:5,opacity:1,background:'#162938',media_style:'compact',show_cover:true,show_progress:true,show_volume:true,accent_color:'#80d4b7'};
  state.layout.config.scenes.dashboard.elements=[card,{...card,id:'poster',x:68,width:28,height:86,media_style:'poster',font_size:5}, {...card,id:'door',kind:'status',entity_id:'binary_sensor.door',label:'TERRASSE',x:4,y:50,width:28,height:42},{...card,id:'temp',kind:'status',entity_id:'sensor.temp',label:'RAUMKLIMA',x:35,y:50,width:28,height:42}];
  const media=state.layout.values['media_player.music']={state:'playing',domain:'media_player',name:'Sonos Wohnzimmer',media_title:'Morning Light',media_artist:'North Collective',media_album_name:'Slow Sundays',media_duration:240,media_position:60,media_position_updated_at:new Date().toISOString(),volume_level:.28,artwork:'one'};
  state.layout.values['binary_sensor.door']={domain:'binary_sensor',device_class:'door',state:'off'};
  state.layout.values['sensor.temp']={domain:'sensor',device_class:'temperature',state:'21.8',unit:'°C'};
  await page.setViewportSize({width:1280,height:720});await mount(page,state);
  await expect(page.locator('[data-layout-id=music] .lg-value')).toHaveText('Morning Light');
  await expect(page.locator('.lg-media-art.loaded')).toHaveCount(2);
  await expect(page.locator('[data-layout-id=door] .lg-value')).toHaveText('Geschlossen');
  await expect(page.locator('[data-layout-id=temp] .lg-value')).toHaveText('21.8 °C');
  await expect(page.locator('[data-layout-id=music] .lg-media-volume')).toHaveText('Lautstärke 28 %');
  const elapsed=await page.locator('[data-layout-id=music] .lg-media-elapsed').textContent();
  await expect(page.locator('[data-layout-id=music] .lg-media-elapsed')).not.toHaveText(elapsed,{timeout:3500});
  await page.screenshot({path:'test-results/media-dashboard-'+test.info().project.name+'.png'});
  await page.evaluate(()=>window.artNode=document.querySelector('.lg-media-art img'));
  media.state='paused';media.media_position=81;
  await expect(page.locator('.lg-media-state')).toHaveCount(0);
  await expect(page.locator('[data-layout-id=music] .lg-media-elapsed')).toHaveText('1:21');
  await page.waitForTimeout(1300);await expect(page.locator('[data-layout-id=music] .lg-media-elapsed')).toHaveText('1:21');
  expect(await page.evaluate(()=>window.artNode===document.querySelector('.lg-media-art img'))).toBe(true);
  state.layout.values['binary_sensor.door'].state='on';await expect(page.locator('[data-layout-id=door]')).toHaveAttribute('data-tone','warning');
  media.state='off';media.artwork=null;
  await expect(page.locator('[data-layout-id=music] .lg-value')).toHaveText('Sonos Wohnzimmer');
  await expect(page.locator('.lg-media-art.loaded')).toHaveCount(0);
  await expect(page.locator('[data-layout-id=music] .lg-media-progress')).toBeHidden();
  state.layout.config.scenes.dashboard.elements=[];await expect(page.locator('.lg-media')).toHaveCount(0);
});

test('missing cover uses local placeholder; media metadata is plain text',async({page})=>{
  const state={content:null,dashboard:true,idle_hdmi:'ext://hdmi:1',layout:designed()};
  state.layout.config.scenes.dashboard.elements=[{...state.layout.config.scenes.dashboard.elements[0],id:'media',kind:'media',entity_id:'media_player.music',x:5,y:5,width:80,height:60,show_cover:true}];
  state.layout.values['media_player.music']={state:'playing',media_title:'<img src=x onerror=window.injected=true>',media_artist:'Example',artwork:'missing'};
  await mount(page,state);
  await expect(page.locator('.lg-media .lg-value')).toContainText('<img');
  await expect(page.locator('.lg-media-art')).not.toHaveClass(/loaded/);
  await expect(page.locator('.lg-media-placeholder')).toBeVisible();
  expect(await page.evaluate(()=>window.injected)).toBeUndefined();
});

test('PiP with its video widget removed stays free of HDMI through notifications',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',pip:true,layout:designed()};
  state.layout.config.scenes.pip_view.elements=[];
  await mount(page,state);
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  state.content={...content(),layout:'overlay',duration:1};
  await expect(page.locator('.lg-message')).toBeVisible();
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  await expect(page.locator('.lg-message')).toHaveCount(0,{timeout:3000});
  state.pip=false;
  await expect(page.locator('body')).toHaveClass('designed');
  await expect(page.locator('#hdmi-slot')).toBeVisible();
});

test('aspect ratio updates the existing HDMI plane in full-screen and PiP without reloading video', async ({page}) => {
  const state = {content:null,idle_hdmi:'ext://hdmi:1',hdmi_fit:'contain'};
  await mount(page,state);
  const video = page.locator('#hdmi-slot video');
  await expect(video).toHaveCSS('object-fit','contain');
  await video.evaluate(el => { window.originalHdmiPlane = el; window.videoReloads = 0; el.load = () => window.videoReloads++; });
  state.hdmi_fit = 'fill';
  await expect(video).toHaveCSS('object-fit','fill');
  state.content = {...content(),layout:'pip'};
  await expect(page.locator('body')).toHaveClass('pip');
  await expect(video).toHaveCSS('object-fit','fill');
  state.hdmi_fit = 'contain';
  await expect(video).toHaveCSS('object-fit','contain');
  expect(await video.evaluate(el => el === window.originalHdmiPlane && window.videoReloads === 0)).toBe(true);
});

test('playing cover background follows tracks, modes and playback without replacing HDMI or repeating analysis',async({page})=>{
  await page.addInitScript(()=>{
    window.edgeSamples=0;
    const original=CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData=function(...args){window.edgeSamples++;return original.apply(this,args);};
  });
  const state={content:null,idle_hdmi:'ext://hdmi:1',dashboard:true,layout:designed()};
  const scene=state.layout.config.scenes.dashboard;
  Object.assign(scene,{elements:[],background:'solid',color:'#172535',media_background_enabled:true,media_background_entity:'media_player.music',media_background_fit:'contain',media_background_dim:.35});
  const media=state.layout.values['media_player.music']={state:'playing',artwork:'one'};
  await mount(page,state);
  const layer=page.locator('.lg-cover-background'),art=layer.locator('img');
  await expect(layer).toHaveClass(/loaded/);
  await expect(art).toHaveCSS('object-fit','contain');
  expect(await layer.evaluate(n=>n.style.background)).toContain('radial-gradient');
  await page.evaluate(()=>{window.coverNode=document.querySelector('.lg-cover-background img');window.hdmiNode=document.querySelector('video');});
  await page.waitForTimeout(1100);
  expect(await page.evaluate(()=>window.edgeSamples)).toBe(1);
  expect(await page.evaluate(()=>window.coverNode===document.querySelector('.lg-cover-background img'))).toBe(true);
  scene.media_background_fit='stretch';
  await expect(art).toHaveCSS('object-fit','fill');
  scene.media_background_fit='center';
  await expect(layer).toHaveAttribute('data-fit','center');
  expect(await art.evaluate(n=>parseFloat(n.style.width))).toBeLessThan(100);
  scene.media_background_dim=.7;
  await expect(layer.locator('.lg-cover-shade')).toHaveCSS('background-color','rgba(0, 0, 0, 0.7)');
  expect(await page.evaluate(()=>window.edgeSamples)).toBe(1);
  for(const playback of ['paused','idle','off','unavailable','unknown']){
    media.state=playback;await expect(layer).toHaveCount(0);
    media.state='playing';await expect(layer).toHaveClass(/loaded/);
  }
  media.artwork='two';await expect(art).toHaveAttribute('src',/v=two(?:&|$)/);
  scene.media_background_enabled=false;await expect(layer).toHaveCount(0);
  expect(await page.evaluate(()=>window.hdmiNode===document.querySelector('video'))).toBe(true);
  scene.media_background_enabled=true;media.artwork='missing';
  let requests=0;page.on('request',r=>{if(r.url().includes('cover.jpg'))requests++;});
  await expect(layer).toHaveCount(1);await page.waitForTimeout(1200);
  await expect(layer).not.toHaveClass(/loaded/);expect(requests).toBeLessThanOrEqual(1);
  media.artwork=null;await expect(layer).toHaveCount(0);
});

test('cover edge colours come from the actual borders and slow old artwork never returns after pause',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',dashboard:true,layout:designed()};
  const scene=state.layout.config.scenes.dashboard;
  Object.assign(scene,{elements:[],media_background_enabled:true,media_background_entity:'media_player.music'});
  state.layout.values['media_player.music']={state:'playing',artwork:'edges'};
  await mount(page,state);
  // Replace the fixture with a known red/blue-edged image; green center must not dominate.
  const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=c.height=32;const x=c.getContext('2d');x.fillStyle='#00ff00';x.fillRect(0,0,32,32);x.fillStyle='#ff0000';x.fillRect(0,0,4,32);x.fillStyle='#0000ff';x.fillRect(28,0,4,32);return c.toDataURL().split(',')[1];});
  await page.route('**/cover.jpg?**',r=>r.fulfill({contentType:'image/png',body:Buffer.from(png,'base64')}));
  state.layout.values['media_player.music'].artwork='edge-colours';
  const layer=page.locator('.lg-cover-background');
  await expect.poll(()=>layer.evaluate(n=>n.style.background)).toContain('rgb(255, 0, 0)');
  expect(await layer.evaluate(n=>n.style.background)).toContain('rgb(0, 0, 255)');
  let finish;const pending=new Promise(resolve=>finish=resolve);
  await page.route('**/cover.jpg?**',async r=>{await pending;await r.fulfill({contentType:'image/png',body:Buffer.from(png,'base64')}).catch(()=>{});});
  state.layout.values['media_player.music'].artwork='slow';
  await expect(layer.locator('img')).toHaveAttribute('src',/v=slow(?:&|$)/);
  await expect(layer).not.toHaveClass(/loaded/);
  state.layout.values['media_player.music'].state='paused';await expect(layer).toHaveCount(0);
  finish();await page.waitForTimeout(500);await expect(layer).toHaveCount(0);
});

test('4K media view keeps HDMI decoder, uses crisp artwork tiers and returns after notifications',async({page})=>{
  await page.setViewportSize({width:3840,height:2160});
  const state={content:null,idle_hdmi:'ext://hdmi:1',media_view:true,layout:designed()};
  const scene=state.layout.config.scenes.media_view;
  const item=scene.elements.find(i=>i.kind==='media');item.entity_id='media_player.music';
  Object.assign(scene,{media_background_enabled:true,media_background_entity:'media_player.music',media_background_fit:'contain',media_background_dim:.65});
  state.layout.values['media_player.music']={state:'playing',name:'Wohnzimmer',media_title:'A beautiful evening',media_artist:'The Artist',media_album_name:'Live Sessions',media_duration:240,media_position:42,artwork:'one'};
  const events=await mount(page,state);
  const media=page.locator('.lg-media'),art=media.locator('img');
  await expect(media).toHaveAttribute('data-media-style','stage');
  await expect(media).toContainText('A beautiful evening');
  await expect(art).toHaveAttribute('src',/size=2160/);
  await expect(page.locator('.lg-cover-background img')).toHaveAttribute('src',/size=2160/);
  await expect(page.locator('#hdmi-slot')).toHaveCSS('visibility','hidden');
  const geometry=await media.evaluate(n=>{const a=n.querySelector('.lg-media-art').getBoundingClientRect(),title=n.querySelector('.lg-value').getBoundingClientRect(),detail=n.querySelector('.lg-detail').getBoundingClientRect();return{art:a.width,overlap:a.right>title.left,titleBottom:title.bottom,detailTop:detail.top,scroll:document.documentElement.scrollWidth};});
  expect(geometry.art).toBeGreaterThan(1280);expect(geometry.overlap).toBe(false);expect(geometry.titleBottom).toBeLessThan(geometry.detailTop);expect(geometry.scroll).toBe(3840);
  await expect.poll(()=>events.some(e=>e.rendering?.width===3840&&e.rendering?.height===2160&&e.layout_scene==='media_view')).toBe(true);
  await page.evaluate(()=>{window.savedPlane=document.querySelector('video');});
  await page.screenshot({path:'test-results/media-4k-'+test.info().project.name+'.png'});
  state.content={...content(),layout:'overlay'};await expect(page.locator('.lg-message')).toBeVisible();
  await expect(page.locator('#hdmi-slot')).toHaveCSS('visibility','hidden');
  state.content=null;await expect(media).toBeVisible();
  state.layout.values['media_player.music'].media_title='Next track';state.layout.values['media_player.music'].artwork='two';
  await expect(media).toContainText('Next track');await expect(art).toHaveAttribute('src',/v=two&size=2160/);
  state.media_view=false;await expect(page.locator('body')).toHaveClass('designed');
  expect(await page.evaluate(()=>document.querySelector('video')===window.savedPlane)).toBe(true);
});

test('LG logical 1080p viewport at density two requests UHD artwork without scaling layout',async({browser})=>{
  const context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:2});
  const page=await context.newPage();
  try{
    const state={content:null,idle_hdmi:'ext://hdmi:1',media_view:true,layout:designed()};
    state.layout.config.scenes.media_view.elements[0].entity_id='media_player.music';
    state.layout.values['media_player.music']={state:'playing',artwork:'density',media_title:'A title long enough to wrap across multiple lines on the display without overlapping artist and album',media_artist:'Artist'};
    const events=await mount(page,state);
    await expect(page.locator('.lg-media-art img')).toHaveAttribute('src',/size=2160/);
    await expect.poll(()=>events.some(e=>e.rendering?.width===1920&&e.rendering?.pixel_ratio===2)).toBe(true);
    const boxes=await page.locator('.lg-media').evaluate(n=>({title:n.querySelector('.lg-value').getBoundingClientRect().bottom,artist:n.querySelector('.lg-detail').getBoundingClientRect().top,width:n.clientWidth}));
    expect(boxes.title).toBeLessThan(boxes.artist);expect(boxes.width).toBe(1728);
  }finally{await context.close();}
});

test('colour-only music backdrop hides the duplicate cover and reuses edge analysis at 4K',async({page})=>{
  await page.setViewportSize({width:3840,height:2160});
  await page.addInitScript(()=>{
    window.edgeSamples=0;
    const original=CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData=function(...args){window.edgeSamples++;return original.apply(this,args);};
  });
  const state={content:null,idle_hdmi:'ext://hdmi:1',media_view:true,layout:designed()};
  const scene=state.layout.config.scenes.media_view,card=scene.elements[0];
  card.entity_id='media_player.music';
  Object.assign(scene,{media_background_enabled:true,media_background_entity:card.entity_id});
  const media=state.layout.values[card.entity_id]={state:'playing',name:'Wohnzimmer',media_title:'Morning Light',media_artist:'North Collective',media_album_name:'Slow Sundays',media_duration:240,media_position:81,artwork:'one'};
  await mount(page,state);
  const layer=page.locator('.lg-cover-background'),backgroundArt=layer.locator('img');
  await expect(layer).toHaveClass(/loaded/);
  await expect(layer).toHaveAttribute('data-fit','colors');
  await expect(backgroundArt).toBeHidden();
  await expect(backgroundArt).toHaveAttribute('src',/size=640/);
  expect(await layer.evaluate(n=>n.style.background)).toContain('radial-gradient');
  await expect(page.locator('.lg-media-art.loaded img')).toBeVisible();
  await expect(page.locator('.lg-media-art img')).toHaveAttribute('src',/size=2160/);
  await expect(page.locator('.lg-media-playback')).toHaveAttribute('aria-label','Wiedergabe');
  await expect(page.locator('.lg-media-state')).toHaveCount(0);
  await page.screenshot({path:'test-results/media-colors-4k-'+test.info().project.name+'.png'});
  scene.media_background_dim=.5;
  await expect(layer.locator('.lg-cover-shade')).toHaveCSS('background-color','rgba(0, 0, 0, 0.5)');
  await page.waitForTimeout(1100);expect(await page.evaluate(()=>window.edgeSamples)).toBe(1);
  scene.media_background_fit='contain';await expect(backgroundArt).toBeVisible();
  scene.media_background_fit='colors';await expect(backgroundArt).toBeHidden();
  expect(await page.evaluate(()=>window.edgeSamples)).toBe(1);
  media.artwork='two';await expect(backgroundArt).toHaveAttribute('src',/v=two&size=640/);
  await expect.poll(()=>page.evaluate(()=>window.edgeSamples)).toBe(2);
  media.state='paused';await expect(layer).toHaveCount(0);
  media.state='playing';media.artwork='missing';await expect(layer).toHaveCount(1);
  await expect(layer).not.toHaveClass(/loaded/);await expect(backgroundArt).toBeHidden();
});

test('all media styles show an optional state icon beside the timeline without status text',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',dashboard:true,layout:designed()};
  const scene=state.layout.config.scenes.dashboard,base=state.layout.config.scenes.media_view.elements[0];
  const cards=['compact','poster','stage'].map((style,i)=>({...base,id:style,media_style:style,x:3+i*32,y:5,width:30,height:85,font_size:3,entity_id:'media_player.music',show_playback_icon:true}));
  scene.elements=cards;
  const media=state.layout.values['media_player.music']={state:'playing',name:'Wohnzimmer',media_title:'Morning Light',media_artist:'North Collective',media_album_name:'Slow Sundays',media_duration:240,media_position:60,artwork:'one'};
  await mount(page,state);
  for(const card of cards){
    const node=page.locator('[data-layout-id='+card.id+']');
    await expect(node.locator('.lg-media-playback')).toBeVisible();
    await expect(node.locator('.lg-media-playback')).toHaveAttribute('aria-label','Wiedergabe');
    const boxes=await node.evaluate(n=>{const icon=n.querySelector('.lg-media-playback').getBoundingClientRect(),bar=n.querySelector('.lg-media-bar').getBoundingClientRect(),album=n.querySelector('.lg-media-album');return {iconRight:icon.right,barLeft:bar.left,iconCenter:(icon.top+icon.bottom)/2,barCenter:(bar.top+bar.bottom)/2,albumFont:getComputedStyle(album).fontSize};});
    expect(boxes.iconRight).toBeLessThan(boxes.barLeft);expect(Math.abs(boxes.iconCenter-boxes.barCenter)).toBeLessThan(1);
    expect(parseFloat(boxes.albumFont)).toBeLessThan(20);
    await expect(node).not.toContainText(/Wiedergabe|Bereit|Pausiert/);
  }
  media.state='paused';
  await expect(page.locator('.lg-media-playback[aria-label=Pausiert]')).toHaveCount(3);
  await expect(page.locator('.lg-media-elapsed').first()).toHaveText('1:00');
  await page.waitForTimeout(1100);await expect(page.locator('.lg-media-elapsed').first()).toHaveText('1:00');
  // An unchanged paused state must not repeatedly mutate the SVG/state indicator.
  await page.evaluate(()=>{window.iconMutations=0;new MutationObserver(m=>window.iconMutations+=m.length).observe(document.querySelector('.lg-media-playback'),{subtree:true,attributes:true,childList:true});});
  await page.waitForTimeout(1100);expect(await page.evaluate(()=>window.iconMutations)).toBe(0);
  cards[0].show_playback_icon=false;await expect(page.locator('[data-layout-id=compact] .lg-media-playback')).toBeHidden();
  await expect(page.locator('[data-layout-id=compact] .lg-media-bar')).toHaveCSS('left','0px');
  cards[1].show_progress=false;await expect(page.locator('[data-layout-id=poster] .lg-media-progress')).toBeHidden();
  for(const playback of ['buffering','idle','off','unavailable']){
    media.state=playback;await expect(page.locator('[data-layout-id=stage] .lg-media-playback')).toBeHidden();
    await expect(page.locator('.lg-media-state')).toHaveCount(0);
  }
  media.state='playing';delete media.media_duration;
  await expect(page.locator('[data-layout-id=stage] .lg-media-progress')).toBeHidden();
});

test('custom source survives notifications, live edits and deletion fallback without rebuilding HDMI',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',selected_view:'view_extra',layout:designed()};
  const extra=JSON.parse(JSON.stringify(state.layout.config.scenes.dashboard));
  extra.elements=[{...extra.elements[0],kind:'text',label:'MEINE QUELLE',text:'Eigene Ansicht'}];
  state.layout.config.scenes.view_extra=extra;
  await mount(page,state);
  await expect(page.locator('.lg-text')).toContainText('Eigene Ansicht');
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  await page.evaluate(()=>window.originalPlane=document.querySelector('video'));
  state.content={...content(),layout:'overlay'};await expect(page.locator('.lg-message')).toBeVisible();
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  state.content=null;await expect(page.locator('.lg-text')).toContainText('Eigene Ansicht');
  extra.elements[0].text='Live geändert';await expect(page.locator('.lg-text')).toContainText('Live geändert');
  // Backend selects the protected Dashboard if the active custom view is removed.
  delete state.layout.config.scenes.view_extra;state.selected_view='dashboard';state.dashboard=true;
  await expect(page.locator('.lg-text')).not.toContainText('Live geändert');
  state.selected_view=null;state.dashboard=false;
  await expect(page.locator('body')).toHaveClass('designed');
  expect(await page.evaluate(()=>window.originalPlane===document.querySelector('video'))).toBe(true);
});


test('edited HDMI view updates all inputs, returns after messages and resets without rebuilding video',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed()};
  const scene=state.layout.config.scenes.hdmi_full;
  scene.elements[0].width=75;
  scene.elements.push({...state.layout.config.scenes.dashboard.elements[0],label:'HDMI ANSICHT'});
  await mount(page,state);
  await expect(page.locator('#hdmi-slot')).toBeVisible();
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('75%');
  await expect(page.locator('.lg-widget')).toContainText('HDMI ANSICHT');
  await page.evaluate(()=>window.originalHDMI=document.querySelector('video'));
  state.idle_hdmi='ext://hdmi:2';state.input_request='hdmi2';
  await expect(page.locator('#hdmi-slot source')).toHaveAttribute('src','ext://hdmi:2');
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('75%');
  state.content={...content(),layout:'pip',duration:1};
  await expect(page.locator('.lg-message')).toBeVisible();
  await expect(page.locator('.lg-message')).toHaveCount(0,{timeout:3000});
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('75%');
  scene.elements[0].width=100;scene.elements.splice(1);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  expect(await page.evaluate(()=>document.querySelector('video')===window.originalHDMI)).toBe(true);
  state.layout.config.enabled=false;
  await expect(page.locator('body')).toHaveClass('hdmi');
});

test('animated HDMI shrinks and grows without decoder reload; acknowledgement waits for final geometry',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed()};
  const pip=state.layout.config.scenes.pip_view.elements.find(e=>e.kind==='hdmi');
  Object.assign(pip,{x:40,y:12,width:55,height:55});
  const events=await mount(page,state);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  await page.evaluate(()=>{
    window.originalVideo=document.querySelector('video');window.moves=[];window.reloads=0;
    originalVideo.load=()=>window.reloads++;
    const slot=document.querySelector('#hdmi-slot');
    new MutationObserver(()=>{const w=parseFloat(slot.style.width);if(moves.at(-1)?.w!==w)moves.push({w,t:performance.now()});}).observe(slot,{attributes:true,attributeFilter:['style']});
  });
  state.selected_view='pip_view';state.input_request='shrink';state.input_transition='smooth';
  await expect.poll(()=>page.evaluate(()=>moves.some(m=>m.w>55&&m.w<100)),{intervals:[25]}).toBe(true);
  expect(events.some(e=>e.type==='input_applied'&&e.id==='shrink')).toBe(false);
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='shrink')).toBe(true);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('55%');
  const shrink=await page.evaluate(()=>moves);
  expect(shrink.length).toBeGreaterThan(3);expect(shrink.length).toBeLessThanOrEqual(24);
  expect(shrink.at(-1).t-shrink[0].t).toBeGreaterThan(550);
  await page.waitForTimeout(200);
  expect(await page.evaluate(()=>moves.length)).toBe(shrink.length);
  await page.evaluate(()=>moves=[]);
  state.selected_view=null;state.input_request='grow';
  await expect.poll(()=>page.evaluate(()=>moves.some(m=>m.w>55&&m.w<100)),{intervals:[25]}).toBe(true);
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='grow')).toBe(true);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  expect(await page.evaluate(()=>window.reloads===0&&originalVideo===document.querySelector('video'))).toBe(true);
  await expect(page.locator('#hdmi-slot')).toHaveCSS('z-index','1');
});

test('new direct targets, missing HDMI and decoder changes cancel or skip a smooth move',async({page})=>{
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed()};
  const pip=state.layout.config.scenes.pip_view.elements.find(e=>e.kind==='hdmi');
  Object.assign(pip,{x:40,y:12,width:55,height:55});
  const events=await mount(page,state);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  state.selected_view='pip_view';state.input_request='moving';state.input_transition='smooth';
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>parseFloat(e.style.width)<100&&parseFloat(e.style.width)>55),{intervals:[25]}).toBe(true);
  state.selected_view=null;state.input_request='interrupt';state.input_transition='none';
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='interrupt')).toBe(true);
  await page.waitForTimeout(1100);
  expect(events.some(e=>e.type==='input_applied'&&e.id==='moving')).toBe(false);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  state.selected_view='media_view';state.input_request='hide';state.input_transition='smooth';
  await expect(page.locator('#hdmi-slot')).toBeHidden();
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='hide')).toBe(true);
  state.selected_view='pip_view';state.input_request='unhide';
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='unhide')).toBe(true);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('55%');
  state.idle_hdmi='ext://hdmi:2';state.selected_view=null;state.input_request='new-input';
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='new-input')).toBe(true);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
});

test('reduced motion selects the exact HDMI target immediately',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});
  const state={content:null,idle_hdmi:'ext://hdmi:1',layout:designed()};
  const events=await mount(page,state);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe('100%');
  state.selected_view='pip_view';state.input_request='reduced';state.input_transition='smooth';
  const width=state.layout.config.scenes.pip_view.elements.find(e=>e.kind==='hdmi').width;
  await expect.poll(()=>events.some(e=>e.type==='input_applied'&&e.id==='reduced')).toBe(true);
  await expect.poll(()=>page.locator('#hdmi-slot').evaluate(e=>e.style.width)).toBe(width+'%');
});
