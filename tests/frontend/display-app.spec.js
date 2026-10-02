const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assets = path.resolve('custom_components/lg_rs232_ip/www/display-app');
const content = () => ({id: 'test', title: 'Welcome <script>window.injected=true</script>', message: 'Your home', duration: 30, remaining: 30, rendered: false, layout: 'fullscreen', hdmi: 'ext://hdmi:1', cards: [{name: 'Temperature', value: '21', unit: '°C'}]});
async function mount(page, state) {
  const events = [];
  await page.route('http://display-app.test/**', async route => {
    const name = new URL(route.request().url()).pathname.split('/').pop();
    if (name === 'state') {
      if (state.offline) return route.fulfill({status: 503, body: ''});
      return route.fulfill({contentType: 'application/json', body: JSON.stringify({version: '1.1.0', revision: 1, idle_hdmi: state.idle_hdmi || null, capture: state.capture || null, content: state.content})});
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
  await page.clock.install();
  await page.clock.fastForward(16000);
  await expect(page.locator('.card')).toHaveCount(0);
  await expect(page.locator('#title')).toHaveText('Display bereit');
});

test('HDMI plane is required before overlay acknowledgement and supports PiP layout', async ({page}) => {
  await page.addInitScript(() => {
    window.hdmiReady = false;
    Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {get: () => window.hdmiReady ? 3840 : 0});
    Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {get: () => window.hdmiReady ? 2160 : 0});
    Object.defineProperty(HTMLVideoElement.prototype, 'error', {get: () => null});
  });
  const state = {content: {...content(), layout: 'overlay'}};
  const events = await mount(page, state);
  await expect(page.locator('#hdmi-slot source')).toHaveAttribute('src', 'ext://hdmi:1');
  expect(events.some(e => e.type === 'rendered')).toBe(false);
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
  state.content = {...content(), layout:'overlay'};
  await expect(page.locator('body')).toHaveClass('overlay');
  state.offline = true;
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
