const {test,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');
const catalog=JSON.parse(fs.readFileSync('tests/fixtures/studio-catalog.json','utf8'));
async function mount(page,width=1500) {
  await page.setViewportSize({width,height:1100});
  const root=path.resolve('custom_components/lg_rs232_ip/www');
  await page.route('http://studio.test/**',route=>{
    const file=new URL(route.request().url()).pathname.split('/').pop();
    const mapping={'studio.js':'studio.js','studio.css':'studio.css','layout-runtime.js':'display-app/layout.js','layout.css':'display-app/layout.css'};
    return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html',body:mapping[file]?fs.readFileSync(path.join(root,mapping[file])):'<body style="margin:0"></body>'});
  });
  await page.goto('http://studio.test/');
  await page.addScriptTag({url:'http://studio.test/lg_rs232_ip/studio.js',type:'module'});
  await page.evaluate(catalog=>{
    window.saved=JSON.parse(JSON.stringify(catalog.presets[0].layout));window.revision=0;window.calls=[];
    const state=(id,value,attrs)=>({entity_id:id,state:value,attributes:attrs});
    window.hass={config:{time_zone:'Europe/Berlin'},states:{
      'sensor.temperature':state('sensor.temperature','22.5',{friendly_name:'Wohnzimmer',unit_of_measurement:'°C'}),
      'weather.home':state('weather.home','sunny',{friendly_name:'Wetter Zuhause',temperature:23,temperature_unit:'°C',humidity:48}),
      'calendar.family':state('calendar.family','off',{friendly_name:'Familie',message:'Abendessen',start_time:'2026-10-04T18:00:00+02:00'})
    },callApi:async(method,url,data)=>{
      window.calls.push([method,url,data]);
      if(url==='lg_rs232_ip/layouts')return catalog;
      if(method==='POST'){
        if(window.failSave)throw {status_code:409};
        if(url==='lg_rs232_ip/layout_validate')return {config:data.config};
        window.saved=JSON.parse(JSON.stringify(data.config));window.revision++;
      }
      return {config:window.saved,revision:window.revision,values:{},timezone:'Europe/Berlin'};
    },callWS:async()=>[{config_entry_id:'one',entity_id:'media_player.display'}],callService:async(...args)=>window.calls.push(args)};
    window.studio=document.createElement('lg-display-studio');studio.hass=hass;document.body.append(studio);
  },catalog);
  await expect(page.getByRole('heading',{name:'Display Studio',exact:true})).toBeVisible();
}

test('templates, entities, geometry and styling save a complete layout without losing edits',async({page})=>{
  await mount(page);
  await page.getByRole('button',{name:/Aurora/}).click();
  await page.getByRole('tab',{name:'Ohne HDMI',exact:true}).click();
  await page.locator('.layer .name').filter({hasText:'Draußen'}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('weather.home');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-weather')).toContainText('23 °C');
  await page.getByLabel('Links (%)',{exact:true}).fill('55');await page.getByLabel('Links (%)',{exact:true}).press('Tab');
  await expect(page.locator('.selection.selected')).toHaveCSS('left',/[0-9.]+px/);
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern & anwenden'}).click();
  await expect(page.getByRole('status')).toHaveText('Gespeichert');
  expect(await page.evaluate(()=>saved.scenes.no_signal.elements.find(i=>i.kind==='weather').x)).toBe(55);
  expect(await page.evaluate(()=>saved.scenes.no_signal.elements.find(i=>i.kind==='weather').entity_id)).toBe('weather.home');
  expect(await page.evaluate(()=>saved.enabled)).toBe(true);
  expect(await page.evaluate(()=>saved.scenes.overlay.elements.filter(i=>i.kind==='message').length)).toBe(1);
});

test('pointer move and resize are bounded; keyboard and undo restore exact geometry',async({page})=>{
  await mount(page);
  await page.getByRole('button',{name:/Aurora/}).click();
  await page.locator('.layer .name').filter({hasText:'HDMI / PiP'}).click();
  const selected=page.locator('.selection.selected');let box=await selected.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2-40,box.y+box.height/2+20);await page.mouse.up();
  const moved=await page.evaluate(()=>studio.item.x);expect(moved).toBeLessThan(35);
  box=await selected.locator('.resize').boundingBox();await page.mouse.move(box.x+6,box.y+6);await page.mouse.down();await page.mouse.move(box.x+90,box.y+60);await page.mouse.up();
  expect(await page.evaluate(()=>studio.item.width)).toBeGreaterThan(61);
  expect(await page.evaluate(()=>studio.item.x+studio.item.width)).toBeLessThanOrEqual(100.01);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='hdmi').width)).toBe(61);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='hdmi').x)).toBe(35);
});

test('HA updates preserve text editing; error keeps draft and prevents silent overwrite',async({page})=>{
  await mount(page);
  await page.getByRole('tab',{name:'Ohne HDMI',exact:true}).click();
  await page.locator('.layer .name').filter({hasText:'WILLKOMMEN'}).click();
  const input=page.getByLabel('Text',{exact:true});await input.fill('<img src=x onerror="window.hacked=true">');
  await page.evaluate(()=>{studio.hass={...hass};});await page.waitForTimeout(400);
  await expect(input).toHaveValue('<img src=x onerror="window.hacked=true">');
  await input.press('Tab');await expect(page.locator('.scene .lg-text')).toContainText('<img');
  expect(await page.evaluate(()=>window.hacked)).toBeUndefined();
  await page.evaluate(()=>{window.failSave=true;});await page.getByRole('button',{name:'Speichern & anwenden'}).click();
  await expect(page.locator('.flash')).toContainText('andere Sitzung');await expect(page.getByRole('status')).toHaveText('Ungespeichert');
});

test('notification scene is editable, mandatory message cannot be deleted, test targets this display',async({page})=>{
  await mount(page);
  await page.getByRole('tab',{name:'Meldung · Overlay',exact:true}).click();
  await page.locator('.layer .name').filter({hasText:'Meldungsfenster'}).click();
  await expect(page.getByRole('button',{name:'Element entfernen'})).toBeDisabled();
  await page.getByLabel('Breite (%)',{exact:true}).fill('30');await page.getByLabel('Breite (%)',{exact:true}).press('Tab');
  await page.getByRole('button',{name:'Speichern & anwenden'}).click();
  await page.getByRole('button',{name:'10 Sekunden anzeigen'}).click();
  const call=await page.evaluate(()=>calls.find(c=>c[0]==='lg_rs232_ip'));
  expect(call[1]).toBe('show_display_app');expect(call[2].entity_id).toBe('media_player.display');expect(call[2].duration).toBe(10);
});

test('editor fits mobile and supports adding, ordering and deleting a selected entity',async({page})=>{
  await mount(page,390);
  await page.getByLabel('Elementtyp').selectOption('entity');await page.getByRole('button',{name:'＋',exact:true}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('sensor.temperature');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-entity')).toContainText('22.5 °C');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.getByRole('button',{name:'Element entfernen'}).click();await expect(page.locator('.scene .lg-entity')).toHaveCount(0);
});
