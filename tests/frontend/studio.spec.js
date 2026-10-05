const {test,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');
const catalog=JSON.parse(fs.readFileSync('tests/fixtures/studio-catalog.json','utf8'));
async function mount(page,width=1500) {
  await page.setViewportSize({width,height:1100});
  const root=path.resolve('custom_components/lg_rs232_ip/www');
  await page.route('http://studio.test/**',route=>{
    const file=new URL(route.request().url()).pathname.split('/').pop();
    const mapping={'studio.js':'studio.js','studio.css':'studio.css','weather.js':'display-app/weather.js','cards.js':'display-app/cards.js','layout-runtime.js':'display-app/layout.js','layout.css':'display-app/layout.css'};
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
      if(url.startsWith('lg_rs232_ip/layout_suggestions/'))return {areas:[{area_id:'living',name:'Wohnzimmer'}],area_id:'living',suggestions:[{entity_id:'media_player.sonos',kind:'media',name:'Sonos Wohnzimmer',state:'idle'},{entity_id:'sensor.temperature',kind:'status',name:'Raumtemperatur',state:'22.5',unit:'°C'}]};
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

async function openView(page,name) {
  if(await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).isVisible())await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByRole('button',{name:name+' bearbeiten',exact:true}).click();
}

test('templates, entities, geometry and styling save a complete layout without losing edits',async({page})=>{
  await mount(page);
  await openView(page,'Ohne HDMI');
  await page.locator('.sidebar').getByRole('button',{name:/Aurora/}).click();
  await page.locator('.layer .name').filter({hasText:'Draußen'}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('weather.home');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-weather')).toContainText('23 °C');
  await page.getByLabel('Links (%)',{exact:true}).fill('55');await page.getByLabel('Links (%)',{exact:true}).press('Tab');
  await expect(page.locator('.selection.selected')).toHaveCSS('left',/[0-9.]+px/);
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern'}).click();
  await expect(page.locator('.status')).toHaveText('Gespeichert');
  expect(await page.evaluate(()=>saved.scenes.no_signal.elements.find(i=>i.kind==='weather').x)).toBe(55);
  expect(await page.evaluate(()=>saved.scenes.no_signal.elements.find(i=>i.kind==='weather').entity_id)).toBe('weather.home');
  expect(await page.evaluate(()=>saved.enabled)).toBe(true);
  expect(await page.evaluate(()=>saved.scenes.overlay.elements.filter(i=>i.kind==='message').length)).toBe(1);
});

test('selected widget remains editable after successive saves without reopening it',async({page})=>{
  await mount(page);await openView(page,'Ohne HDMI');
  await page.locator('.layer .name').filter({hasText:'WILLKOMMEN'}).click();
  const text=page.getByLabel('Text',{exact:true});
  for(const value of ['Erster Entwurf','Weiter bearbeitet']){
    await text.fill(value);await text.press('Tab');
    await page.getByRole('button',{name:'Speichern',exact:true}).click();
    await expect(page.locator('.status')).toHaveText('Gespeichert');
    expect(await page.evaluate(()=>saved.scenes.no_signal.elements.find(i=>i.kind==='text').text)).toBe(value);
  }
  await page.getByLabel('Widget-Typ').selectOption('clock');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.no_signal.elements.some(i=>i.kind==='text'))).toBe(false);
  await page.getByLabel('Breite (%)',{exact:true}).fill('30');await page.getByLabel('Breite (%)',{exact:true}).press('Tab');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.no_signal.elements.find(i=>i.id===studio.selected).width)).toBe(30);
});

test('pointer move and resize are bounded; keyboard and undo restore exact geometry',async({page})=>{
  await mount(page);
  await openView(page,'PiP');
  await page.locator('.sidebar').getByRole('button',{name:/Aurora/}).click();
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
  await openView(page,'Ohne HDMI');
  await page.locator('.layer .name').filter({hasText:'WILLKOMMEN'}).click();
  const input=page.getByLabel('Text',{exact:true});await input.fill('<img src=x onerror="window.hacked=true">');
  await page.evaluate(()=>{studio.hass={...hass};});await page.waitForTimeout(400);
  await expect(input).toHaveValue('<img src=x onerror="window.hacked=true">');
  await input.press('Tab');await expect(page.locator('.scene .lg-text')).toContainText('<img');
  expect(await page.evaluate(()=>window.hacked)).toBeUndefined();
  await page.evaluate(()=>{window.failSave=true;});await page.getByRole('button',{name:'Speichern'}).click();
  await expect(page.locator('.flash')).toContainText('andere Sitzung');await expect(page.locator('.status')).toHaveText('Ungespeichert');
});

test('notification scene is editable, every widget can be deleted and restored',async({page})=>{
  await mount(page);
  await openView(page,'Meldung · Overlay');
  await page.locator('.layer .name').filter({hasText:'Meldungsfenster'}).click();
  await expect(page.getByRole('button',{name:'Element entfernen'})).toBeEnabled();
  await page.getByRole('button',{name:'Element entfernen'}).click();
  await expect(page.locator('.scene .lg-message')).toHaveCount(0);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await page.locator('.layer .name').filter({hasText:'Meldungsfenster'}).click();
  await page.getByLabel('Breite (%)',{exact:true}).fill('30');await page.getByLabel('Breite (%)',{exact:true}).press('Tab');
  await page.getByRole('button',{name:'Speichern'}).click();
  await page.getByRole('button',{name:'10 Sekunden anzeigen'}).click();
  const call=await page.evaluate(()=>calls.find(c=>c[0]==='lg_rs232_ip'));
  expect(call[1]).toBe('show_display_app');expect(call[2].entity_id).toBe('media_player.display');expect(call[2].duration).toBe(10);
});

test('editor fits mobile and supports adding, ordering and deleting a selected entity',async({page})=>{
  await mount(page,390);
  await openView(page,'Mit HDMI');
  await page.getByLabel('Elementtyp').selectOption('entity');await page.getByRole('button',{name:'＋',exact:true}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('sensor.temperature');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-entity')).toContainText('22.5 °C');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.getByRole('button',{name:'Element entfernen'}).click();await expect(page.locator('.scene .lg-entity')).toHaveCount(0);
});

test('widgets can change type and every element including messages can be removed; Dashboard is a source',async({page})=>{
  await mount(page);
  await openView(page,'Dashboard');
  await page.locator('.layer .name').filter({hasText:'Dein Wetter'}).click();
  await page.getByLabel('Widget-Typ').selectOption('text');
  await page.getByLabel('Text',{exact:true}).fill('Guten Morgen');await page.getByLabel('Text',{exact:true}).press('Tab');
  await expect(page.locator('.scene [data-layout-id=weather]')).toContainText('Guten Morgen');
  await page.getByLabel('Widget-Typ').selectOption('weather');
  await page.getByLabel('Wetteransicht').selectOption('hourly');
  await page.getByLabel('Aktuelles Wettersymbol animieren').uncheck();
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern'}).click();
  await page.getByRole('button',{name:'Dashboard anzeigen'}).click();
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='media_player'&&c[1]==='select_source'&&c[2].source==='Dashboard'))).toBe(true);
  expect(await page.evaluate(()=>saved.scenes.dashboard.elements.find(i=>i.kind==='weather').animate)).toBe(false);
  await page.getByRole('button',{name:'Element entfernen'}).click();
  await expect(page.locator('.scene .lg-weather')).toHaveCount(0);
});

test('own background uploads preview locally, survive save and undo, and cleanup preserves used images',async({page})=>{
  await mount(page);
  await page.evaluate(()=>{
    const id='a'.repeat(64), unused='b'.repeat(64), api=hass.callApi;
    studio.backgrounds=[unused];studio.imageUrls[id]=null;
    hass.fetchWithAuth=async(url,options)=>{
      calls.push([options?.method || 'GET',url]);
      if(options?.method==='POST')return new Response(JSON.stringify({image_id:id}));
      return new Response(new Uint8Array([137,80,78,71]),{headers:{'Content-Type':'image/png'}});
    };
    hass.callApi=async(method,url,data)=>method==='DELETE' ? (calls.push([method,url]),{ok:true}):api(method,url,data);
  });
  await openView(page,'Dashboard');
  await page.locator('#bg-upload').setInputFiles({name:'morning.png',mimeType:'image/png',buffer:Buffer.from([137,80,78,71])});
  await expect(page.locator('.flash')).toContainText('Bild vorbereitet');
  await expect.poll(()=>page.locator('.scene').evaluate(node=>node.style.background)).toContain('blob:');
  await page.getByRole('button',{name:'Speichern'}).click();
  expect(await page.evaluate(()=>saved.scenes.dashboard.image_id)).toBe('a'.repeat(64));
  await page.locator('[data-action=clean-backgrounds]').click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='DELETE').map(c=>c[1]))).toEqual(['lg_rs232_ip/layout_background/one/'+ 'b'.repeat(64)]);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.config.scenes.dashboard.image_id)).toBe('');
  await page.getByTitle('Wiederholen',{exact:true}).click();
  expect(await page.evaluate(()=>studio.config.scenes.dashboard.image_id)).toBe('a'.repeat(64));
});


test('room suggestions add styled media/status cards once, support editing and removal, and never auto-save',async({page})=>{
  await mount(page);
  await openView(page,'Dashboard');
  await expect(page.getByLabel('Raum für Kartenvorschläge')).toHaveValue('living');
  await page.getByRole('button',{name:/Medienplayer Sonos Wohnzimmer/}).click();
  await expect(page.locator('.scene .lg-media')).toHaveCount(1);
  await expect(page.getByLabel('Home-Assistant-Entität')).toHaveValue('media_player.sonos');
  await page.getByLabel('Mediengestaltung').selectOption('poster');
  await expect(page.locator('.scene .lg-media')).toHaveAttribute('data-media-style','poster');
  await expect(page.getByRole('button',{name:/Medienplayer Sonos Wohnzimmer/})).toBeDisabled();
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='POST'))).toBe(false);
  await page.getByRole('button',{name:/Statuskarte Raumtemperatur/}).click();
  await expect(page.locator('.scene .lg-status')).toContainText('22.5 °C');
  await page.getByRole('button',{name:'Raumtemperatur entfernen',exact:true}).click();
  await expect(page.locator('.scene .lg-status')).toHaveCount(0);
  await expect(page.getByRole('button',{name:/Statuskarte Raumtemperatur/})).toBeEnabled();
  await page.getByRole('button',{name:'Sonos Wohnzimmer entfernen',exact:true}).click();
  await expect(page.locator('.scene .lg-media')).toHaveCount(0);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await expect(page.locator('.scene .lg-media')).toHaveCount(1);
  await page.getByRole('button',{name:'Speichern'}).click();
  expect(await page.evaluate(()=>saved.scenes.dashboard.elements.some(i=>i.kind==='media'&&i.media_style==='poster'))).toBe(true);
});

test('overview manages independent named views, assignments, deletion undo and persistence',async({page})=>{
  await mount(page);
  await expect(page.locator('.overview')).toBeVisible();await expect(page.locator('.workspace')).toBeHidden();
  await expect(page.locator('.view-card')).toHaveCount(7);
  await page.getByRole('button',{name:'＋ Neue Ansicht',exact:true}).click();
  await page.getByLabel('Name',{exact:true}).fill('Mein Sonnenplatz');
  await page.getByLabel('Vorlage',{exact:true}).selectOption('morning');
  await page.getByRole('button',{name:'Ansicht anlegen',exact:true}).click();
  await expect(page.getByLabel('Name der Ansicht')).toHaveValue('Mein Sonnenplatz');
  await expect(page.getByLabel('Hintergrund',{exact:true})).toHaveValue('solar');
  await page.getByLabel('Name der Ansicht').fill('Mein Tageslicht');await page.getByLabel('Name der Ansicht').press('Tab');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await expect(page.locator('.view-card')).toHaveCount(8);
  await page.getByRole('button',{name:'Mein Tageslicht duplizieren',exact:true}).click();
  await expect(page.locator('.view-card')).toHaveCount(9);
  await openView(page,'Mein Tageslicht · Kopie');
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  const id=await page.evaluate(()=>studio.config.views.find(v=>v.name==='Mein Tageslicht').id);
  await page.getByLabel('Ansicht für Dashboard',{exact:true}).selectOption(id);
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.dashboard.background)).toBe('solar');
  expect(await page.evaluate(()=>saved.views.find(v=>v.name==='Mein Tageslicht · Kopie').scene.background)).toBe('ocean');
  await page.getByRole('button',{name:'Mein Tageslicht löschen',exact:true}).click();
  await expect(page.getByLabel('Ansicht für Dashboard',{exact:true})).toHaveValue('');
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await expect(page.getByLabel('Ansicht für Dashboard',{exact:true})).toHaveValue(id);
  await page.screenshot({path:'test-results/studio-views-'+test.info().project.name+'.png',fullPage:true});
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{studio.remove();document.body.append(studio);});
  await expect(page.locator('.view-card')).toHaveCount(9);
  await expect(page.locator('.overview')).toBeVisible();
});

test('solar view follows live HA updates without reload and preserves edited fields',async({page})=>{
  await mount(page);await openView(page,'Dashboard');
  await page.locator('.sidebar').getByRole('button',{name:/Sonnenstand/}).click();
  await page.evaluate(()=>{hass.states['sun.sun']={entity_id:'sun.sun',state:'above_horizon',attributes:{elevation:35,azimuth:130,rising:true}};studio.hass={...hass};});
  const day=await page.locator('.scene').evaluate(n=>n.style.background);
  await page.getByLabel('Name der Ansicht').fill('Noch im Entwurf');
  await page.evaluate(()=>{hass.states['sun.sun']={entity_id:'sun.sun',state:'below_horizon',attributes:{elevation:-18,azimuth:320,rising:false}};studio.hass={...hass};});
  await expect.poll(()=>page.locator('.scene').evaluate(n=>n.style.background)).not.toBe(day);
  await expect(page.getByLabel('Name der Ansicht')).toHaveValue('Noch im Entwurf');
  await expect(page.locator('.workspace')).toBeVisible();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='POST').length)).toBe(0);
});

test('empty overview remains usable, supports new views and fits a phone',async({page})=>{
  await mount(page,390);
  for(const name of ['Mit HDMI','Ohne HDMI','Dashboard','Meldung · Overlay','Meldung · PiP','Meldung · Vollbild','PiP'])await page.getByRole('button',{name:name+' löschen',exact:true}).click();
  await expect(page.locator('.view-card')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Neue Ansicht anlegen',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.views)).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.getByRole('button',{name:'Neue Ansicht anlegen',exact:true}).click();
  await page.getByRole('button',{name:'Ansicht anlegen',exact:true}).click();
  await expect(page.getByLabel('Name der Ansicht')).toHaveValue('Sonnenstand');
  await expect(page.locator('.scene .lg-clock')).toHaveCount(1);
});

test('themes change colours only, palette is editable and top buttons preserve drafts without source changes',async({page})=>{
  await mount(page);await openView(page,'PiP');
  await page.locator('.layer .name').filter({hasText:'Draußen'}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('weather.home');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await page.getByLabel('Links (%)',{exact:true}).fill('5');await page.getByLabel('Links (%)',{exact:true}).press('Tab');
  const before=await page.evaluate(()=>JSON.parse(JSON.stringify(studio.scene.elements)));
  await page.locator('.sidebar').getByRole('button',{name:'Paper & Sand',exact:true}).click();
  const after=await page.evaluate(()=>studio.scene.elements);
  const content=items=>items.map(({color,background,accent_color,...rest})=>rest);
  expect(content(after)).toEqual(content(before));expect(after[0].color).not.toBe(before[0].color);
  await expect(page.locator('.sidebar .room-suggestions')).toHaveCount(0);
  await page.getByLabel('Kartenfarbe',{exact:true}).fill('#234567');await page.getByLabel('Kartenfarbe',{exact:true}).press('Tab');
  expect(await page.evaluate(()=>studio.scene.elements.filter(i=>i.kind!=='hdmi').every(i=>i.background==='#234567'))).toBe(true);
  await page.locator('.context-tabs').getByRole('button',{name:'Dashboard',exact:true}).click();
  await expect(page.getByLabel('Name der Ansicht')).toHaveValue('Dashboard');
  await page.locator('.context-tabs').getByRole('button',{name:'Mitteilung',exact:true}).click();
  await expect(page.locator('.scene .lg-message')).toBeVisible();
  await page.locator('.context-tabs').getByRole('button',{name:'HDMI · Vollbild',exact:true}).click();
  await expect(page.getByLabel('Name der Ansicht')).toBeDisabled();
  await expect(page.locator('.selection')).toHaveCount(0);
  await expect(page.locator('.sidebar')).toBeHidden();
  expect(await page.locator('.lg-hdmi-placeholder').evaluate(n=>n.style.width)).toBe('100%');
  await page.locator('.context-tabs').getByRole('button',{name:'PiP',exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='weather').entity_id)).toBe('weather.home');
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='weather').x)).toBe(5);
  expect(await page.evaluate(()=>calls.some(c=>['POST','media_player'].includes(c[0])))).toBe(false);
  await page.screenshot({path:'test-results/studio-themes-'+test.info().project.name+'.png',fullPage:true});
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByRole('button',{name:'PiP anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='media_player'&&c[2].source==='PiP'))).toBe(true);
});

test('a background player is independent of cards, previews live, survives save, themes, undo and duplicate',async({page})=>{
  await mount(page);
  const png=fs.readFileSync('tests/fixtures/media-cover.png').toString('base64');
  await page.evaluate(png=>{
    hass.states['media_player.sonos']={entity_id:'media_player.sonos',state:'playing',attributes:{friendly_name:'Sonos Wohnzimmer',entity_picture:'/private-art',media_title:'First'}};
    window.coverRequests=0;
    hass.fetchWithAuth=async()=>{window.coverRequests++;return new Response(Uint8Array.from(atob(png),c=>c.charCodeAt(0)),{headers:{'Content-Type':'image/png'}});};
  },png);
  await openView(page,'Dashboard');
  const before=await page.evaluate(()=>JSON.stringify(studio.scene.elements));
  await page.getByLabel('Hintergrund-Medienplayer').selectOption('media_player.sonos');
  await page.getByLabel('Bei Wiedergabe anzeigen').check();
  await expect(page.locator('.scene .lg-cover-background')).toHaveClass(/loaded/);
  await page.getByLabel('Cover darstellen').selectOption('stretch');
  await expect(page.locator('.scene .lg-cover-background img')).toHaveCSS('object-fit','fill');
  await page.locator('.sidebar').getByRole('button',{name:/Aurora/}).click();
  expect(await page.evaluate(()=>studio.scene.media_background_entity)).toBe('media_player.sonos');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await expect(page.locator('.status')).toHaveText('Gespeichert');
  expect(await page.evaluate(()=>saved.scenes.dashboard.media_background_fit)).toBe('stretch');
  expect(await page.evaluate(()=>studio.scene.elements.map(i=>i.entity_id))).toEqual(JSON.parse(before).map(i=>i.entity_id));
  await page.evaluate(()=>{hass.states['media_player.sonos'].state='paused';studio.hass={...hass};});
  await expect(page.locator('.scene .lg-cover-background')).toHaveCount(0);
  await page.evaluate(()=>{hass.states['media_player.sonos'].state='playing';hass.states['media_player.sonos'].attributes.media_title='Second';studio.hass={...hass};});
  await expect(page.locator('.scene .lg-cover-background')).toHaveClass(/loaded/);
  await page.getByLabel('Bei Wiedergabe anzeigen').uncheck();
  await expect(page.locator('.scene .lg-cover-background')).toHaveCount(0);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await expect(page.getByLabel('Bei Wiedergabe anzeigen')).toBeChecked();
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByRole('button',{name:'Dashboard duplizieren',exact:true}).click();
  await openView(page,'Dashboard · Kopie');
  await expect(page.getByLabel('Hintergrund-Medienplayer')).toHaveValue('media_player.sonos');
  await expect(page.getByLabel('Cover darstellen')).toHaveValue('stretch');
  expect(await page.evaluate(()=>window.coverRequests)).toBeLessThanOrEqual(4);
});
