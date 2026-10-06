const {test,expect}=require('@playwright/test');
const fs=require('node:fs');const path=require('node:path');
const catalog=JSON.parse(fs.readFileSync('tests/fixtures/studio-catalog.json','utf8'));
async function mount(page,width=1500) {
  await page.setViewportSize({width,height:1100});
  const root=path.resolve('custom_components/lg_rs232_ip/www');
  await page.route('http://studio.test/**',route=>{
    const file=new URL(route.request().url()).pathname.split('/').pop();
    const mapping={'studio.js':'studio.js','studio.css':'studio.css','weather.js':'display-app/weather.js','cards.js':'display-app/cards.js','layout-runtime.js':'display-app/layout.js','layout.css':'display-app/layout.css','grain.png':'display-app/grain.png'};
    return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html',body:mapping[file]?fs.readFileSync(path.join(root,mapping[file])):'<body style="margin:0"></body>'});
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
      if(url==='states/media_player.display')return {attributes:{hdmi_source:window.currentHdmi}};
      if(url.startsWith('lg_rs232_ip/layout_suggestions/'))return {areas:[{area_id:'living',name:'Wohnzimmer'}],area_id:'living',suggestions:[{entity_id:'media_player.sonos',kind:'media',name:'Sonos Wohnzimmer',state:'idle'},{entity_id:'sensor.temperature',kind:'status',name:'Raumtemperatur',state:'22.5',unit:'°C'}]};
      if(method==='POST'){
        if(window.failSave)throw {status_code:409};
        if(url==='lg_rs232_ip/layout_validate')return {config:data.config};
        window.saved=JSON.parse(JSON.stringify(data.config));window.revision++;
        if(saved.views)hass.states['media_player.display']={entity_id:'media_player.display',state:'on',attributes:{view_sources:Object.fromEntries(saved.views.filter(v=>!['hdmi_full','startup','overlay','pip','fullscreen'].includes(v.id)).map(v=>[v.id,v.name]))}};
      }
      return {config:window.saved,revision:window.revision,values:{},timezone:'Europe/Berlin',startup_design:window.startupStatus};
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
  await openView(page,'Dashboard');
  await page.locator('.sidebar').getByRole('button',{name:/Aurora/}).click();
  await page.locator('.layer .name').filter({hasText:'Dein Wetter'}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('weather.home');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-weather')).toContainText('23 °C');
  await page.getByLabel('Links (%)',{exact:true}).fill('40');await page.getByLabel('Links (%)',{exact:true}).press('Tab');
  await expect(page.locator('.selection.selected')).toHaveCSS('left',/[0-9.]+px/);
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern'}).click();
  await expect(page.locator('.status')).toHaveText('Gespeichert');
  expect(await page.evaluate(()=>saved.scenes.dashboard.elements.find(i=>i.kind==='weather').x)).toBe(40);
  expect(await page.evaluate(()=>saved.scenes.dashboard.elements.find(i=>i.kind==='weather').entity_id)).toBe('weather.home');
  expect(await page.evaluate(()=>saved.enabled)).toBe(true);
  expect(await page.evaluate(()=>saved.scenes.overlay.elements.filter(i=>i.kind==='message').length)).toBe(1);
});

test('selected widget remains editable after successive saves without reopening it',async({page})=>{
  await mount(page);await openView(page,'Dashboard');
  await page.locator('.layer .name').filter({hasText:'Text'}).click();
  const text=page.getByLabel('Text',{exact:true});
  for(const value of ['Erster Entwurf','Weiter bearbeitet']){
    await text.fill(value);await text.press('Tab');
    await page.getByRole('button',{name:'Speichern',exact:true}).click();
    await expect(page.locator('.status')).toHaveText('Gespeichert');
    expect(await page.evaluate(()=>saved.scenes.dashboard.elements.find(i=>i.kind==='text').text)).toBe(value);
  }
  await page.getByLabel('Widget-Typ').selectOption('clock');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.dashboard.elements.some(i=>i.kind==='text'))).toBe(false);
  await page.getByLabel('Breite (%)',{exact:true}).fill('25');await page.getByLabel('Breite (%)',{exact:true}).press('Tab');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.dashboard.elements.find(i=>i.id===studio.selected).width)).toBe(25);
});

test('pointer move and resize are bounded; keyboard and undo restore exact geometry',async({page})=>{
  await mount(page);
  await openView(page,'Dashboard PiP');
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
  await openView(page,'Dashboard');
  await page.locator('.layer .name').filter({hasText:'Text'}).click();
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
  await openView(page,'Mitteilung');
  await page.locator('.layer .name').filter({hasText:'Meldungsfenster'}).click();
  await expect(page.getByRole('button',{name:'Element entfernen'})).toBeEnabled();
  await page.getByRole('button',{name:'Element entfernen'}).click();
  await expect(page.locator('.scene .lg-message')).toHaveCount(0);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await page.locator('.layer .name').filter({hasText:'Meldungsfenster'}).click();
  await page.getByLabel('Breite (%)',{exact:true}).fill('25');await page.getByLabel('Breite (%)',{exact:true}).press('Tab');
  await page.getByRole('button',{name:'Speichern'}).click();
  await page.getByRole('button',{name:'10 Sekunden anzeigen'}).click();
  const call=await page.evaluate(()=>calls.find(c=>c[0]==='lg_rs232_ip'));
  expect(call[1]).toBe('show_display_app');expect(call[2].entity_id).toBe('media_player.display');expect(call[2].duration).toBe(10);
});

test('editor fits mobile and supports adding, ordering and deleting a selected entity',async({page})=>{
  await mount(page,390);
  await openView(page,'Dashboard PiP');
  await page.getByLabel('Elementtyp').selectOption('entity');await page.getByRole('button',{name:'＋',exact:true}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('sensor.temperature');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-entity').filter({hasText:'22.5 °C'})).toHaveCount(1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.getByRole('button',{name:'Element entfernen'}).click();await expect(page.locator('.scene .lg-entity').filter({hasText:'22.5 °C'})).toHaveCount(0);
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

test('overview creates, renames, duplicates and deletes independent source views with undo',async({page})=>{
  await mount(page);
  await expect(page.locator('.view-card')).toHaveCount(8);
  await expect(page.getByText('Wann wird welche Ansicht angezeigt?',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'＋ Neue Ansicht',exact:true}).click();
  await page.getByLabel('Name',{exact:true}).fill('Mein Sonnenplatz');
  await page.getByLabel('Vorlage',{exact:true}).selectOption('morning');
  await page.getByRole('button',{name:'Ansicht anlegen',exact:true}).click();
  await expect(page.getByLabel('Hintergrund',{exact:true})).toHaveValue('solar');
  await page.getByLabel('Name der Ansicht').fill('Mein Tageslicht');await page.getByLabel('Name der Ansicht').press('Tab');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  const id=await page.evaluate(()=>studio.viewId);
  expect(await page.evaluate(id=>saved.scenes[id].background,id)).toBe('solar');
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByRole('button',{name:'Mein Tageslicht duplizieren',exact:true}).click();
  await expect(page.locator('.view-card')).toHaveCount(10);
  await openView(page,'Mein Tageslicht · Kopie');
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.dashboard.background)).toBe('midnight');
  expect(await page.evaluate(id=>saved.scenes[id].background,id)).toBe('solar');
  expect(await page.evaluate(()=>saved.views.find(v=>v.name==='Mein Tageslicht · Kopie').scene.background)).toBe('ocean');
  await page.getByRole('button',{name:'Mein Tageslicht löschen',exact:true}).click();
  await expect(page.locator('.view-card')).toHaveCount(9);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await expect(page.locator('.view-card')).toHaveCount(10);
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{studio.remove();document.body.append(studio);});
  await expect(page.locator('.view-card')).toHaveCount(10);
  await expect(page.locator('.overview')).toBeVisible();
});

test('solar view follows live HA updates without reload and preserves edited fields',async({page})=>{
  await mount(page);await openView(page,'Dashboard');
  await page.locator('.sidebar').getByRole('button',{name:/Sonnenstand/}).click();
  await page.evaluate(()=>{hass.states['sun.sun']={entity_id:'sun.sun',state:'above_horizon',attributes:{elevation:35,azimuth:130,rising:true}};studio.hass={...hass};});
  const day=await page.locator('.scene').evaluate(n=>n.style.background);
  await page.locator('.layer .name').filter({hasText:'Text'}).click();
  await page.getByLabel('Text',{exact:true}).fill('Noch im Entwurf');
  await page.evaluate(()=>{hass.states['sun.sun']={entity_id:'sun.sun',state:'below_horizon',attributes:{elevation:-18,azimuth:320,rising:false}};studio.hass={...hass};});
  await expect.poll(()=>page.locator('.scene').evaluate(n=>n.style.background)).not.toBe(day);
  await expect(page.getByLabel('Text',{exact:true})).toHaveValue('Noch im Entwurf');
  await expect(page.locator('.workspace')).toBeVisible();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='POST').length)).toBe(0);
});

test('eight fixed views are protected, reset independently and support undo on a phone',async({page})=>{
  await mount(page,390);
  const names=['Nur HDMI','Dashboard','Dashboard PiP','Mediaplayer','Startanzeige','Mitteilung','Mitteilung PiP','Mitteilung Vollbild'];
  for(const name of names){
    await expect(page.getByRole('button',{name:name+' löschen',exact:true})).toHaveCount(0);
    await expect(page.getByRole('button',{name:name+' Standard wiederherstellen',exact:true})).toHaveCount(1);
  }
  await openView(page,'Dashboard');
  await expect(page.getByLabel('Name der Ansicht')).toBeDisabled();
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  const others=await page.evaluate(()=>JSON.stringify(studio.config.views.filter(v=>v.id!=='dashboard')));
  await page.getByRole('button',{name:'Dashboard Standard wiederherstellen',exact:true}).click();
  expect(await page.evaluate(()=>studio.config.scenes.dashboard.background)).toBe('midnight');
  expect(await page.evaluate(()=>JSON.stringify(studio.config.views.filter(v=>v.id!=='dashboard')))).toBe(others);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.config.scenes.dashboard.background)).toBe('ocean');
  expect(await page.evaluate(()=>studio.dirty)).toBe(false);
  await page.evaluate(()=>studio.deleteView('dashboard'));
  await expect(page.locator('.view-card')).toHaveCount(8);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('themes change colours only, palette is editable and top buttons preserve drafts without source changes',async({page})=>{
  await mount(page);await openView(page,'Dashboard PiP');
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
  await page.locator('.context-tabs').getByRole('button',{name:'Nur HDMI',exact:true}).click();
  await expect(page.getByLabel('Name der Ansicht')).toBeDisabled();
  await expect(page.locator('.selection')).toHaveCount(1);
  await expect(page.locator('.sidebar')).toBeVisible();
  await expect(page.locator('[data-action=reset-view]')).toBeVisible();
  expect(await page.locator('.lg-hdmi-placeholder').evaluate(n=>n.style.width)).toBe('100%');
  await page.locator('.context-tabs').getByRole('button',{name:'Dashboard PiP',exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='weather').entity_id)).toBe('weather.home');
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='weather').x)).toBe(5);
  expect(await page.evaluate(()=>calls.some(c=>['POST','media_player'].includes(c[0])))).toBe(false);
  await page.screenshot({path:'test-results/studio-themes-'+test.info().project.name+'.png',fullPage:true});
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByRole('button',{name:'Dashboard PiP anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='media_player'&&c[2].source==='Dashboard PiP'))).toBe(true);
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
  await expect(page.getByLabel('Farben für den Hintergrund')).toHaveValue('edges');
  await page.getByLabel('Farben für den Hintergrund').selectOption('cover');
  await page.getByLabel('Cover darstellen').selectOption('stretch');
  await expect(page.locator('.scene .lg-cover-background img')).toHaveCSS('object-fit','fill');
  await page.locator('.sidebar').getByRole('button',{name:/Aurora/}).click();
  expect(await page.evaluate(()=>studio.scene.media_background_entity)).toBe('media_player.sonos');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await expect(page.locator('.status')).toHaveText('Gespeichert');
  expect(await page.evaluate(()=>saved.scenes.dashboard.media_background_fit)).toBe('stretch');
  expect(await page.evaluate(()=>saved.scenes.dashboard.media_background_color_source)).toBe('cover');
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
  await expect(page.getByLabel('Farben für den Hintergrund')).toHaveValue('cover');
  await page.getByLabel('Farben für den Hintergrund').selectOption('edges');
  await page.getByTitle('Rückgängig',{exact:true}).click();
  await expect(page.getByLabel('Farben für den Hintergrund')).toHaveValue('cover');
  expect(await page.evaluate(()=>window.coverRequests)).toBeLessThanOrEqual(4);
});

test('Mediaplayer context configures full-screen view, saves and selects its own source',async({page})=>{
  await mount(page);await openView(page,'Dashboard');
  await page.getByRole('button',{name:'Mediaplayer',exact:true}).click();
  await expect(page.getByLabel('Name der Ansicht')).toHaveValue('Mediaplayer');
  await page.locator('.layer .name').filter({hasText:'JETZT LÄUFT'}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('media_player.sonos');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await expect(page.locator('.scene .lg-media')).toHaveAttribute('data-media-style','stage');
  await page.getByLabel('Eigenes Layout verwenden').check();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.media_view.elements.find(i=>i.kind==='media').entity_id)).toBe('media_player.sonos');
  await page.getByRole('button',{name:'Mediaplayer anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='media_player'&&c[1]==='select_source'&&c[2].source==='Mediaplayer'))).toBe(true);
  await page.getByRole('button',{name:'Element entfernen',exact:true}).click();
  await expect(page.locator('.scene .lg-media')).toHaveCount(0);
});


test('gallery displays assigned music view without replacing Dashboard',async({page})=>{
  await mount(page);
  await page.locator('.view-card').filter({has:page.getByRole('heading',{name:'Mediaplayer',exact:true})}).getByRole('button',{name:'Anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='media_player'&&c[1]==='select_source'&&c[2].source==='Mediaplayer'))).toBe(true);
  expect(await page.evaluate(()=>studio.config.assignments)).toBeUndefined();
});


test('source buttons switch saved views without reassigning the open music view or saving drafts',async({page})=>{
  await mount(page);await openView(page,'Mediaplayer');
  await page.getByLabel('Eigenes Layout verwenden').check();await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{calls.length=0;});
  const dashboard=await page.evaluate(()=>JSON.stringify(studio.config.scenes.dashboard));
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  for(const source of ['Mediaplayer','Dashboard','Dashboard PiP','Dashboard']){
    await page.getByRole('button',{name:source+' anzeigen',exact:true}).click();
    expect(await page.evaluate(()=>calls.filter(c=>c[0]==='media_player').at(-1)[2].source)).toBe(source);
    expect(await page.evaluate(()=>JSON.stringify(studio.config.scenes.dashboard))).toBe(dashboard);
  }
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='POST').length)).toBe(0);
  await expect(page.getByLabel('Hintergrund',{exact:true})).toHaveValue('ocean');
  await expect(page.locator('.status')).toHaveText('Ungespeichert');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.assignments)).toBeUndefined();
  expect(await page.evaluate(()=>saved.scenes.media_view.background)).toBe('ocean');
});

test('source selection failure and unassigned defaults do not alter the library',async({page})=>{
  await mount(page);await openView(page,'Mediaplayer');
  await page.getByLabel('Eigenes Layout verwenden').check();await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{calls.length=0;});
  await page.evaluate(()=>{hass.callService=async()=>{throw Error('offline');};});
  await page.getByRole('button',{name:'Dashboard anzeigen',exact:true}).click();
  await expect(page.locator('.flash')).toContainText('Quelle nicht erreichbar');
  expect(await page.evaluate(()=>studio.config.views[0].id)).toBe('hdmi_full');
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='POST').length)).toBe(0);
});

test('custom gallery and editor select their own source without replacing fixed views',async({page})=>{
  await mount(page);await page.getByRole('button',{name:'Mediaplayer duplizieren',exact:true}).click();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  const card=page.locator('.view-card').filter({has:page.getByRole('heading',{name:'Mediaplayer · Kopie',exact:true})});
  await card.getByRole('button',{name:'Anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='media_player').at(-1)[2].source)).toBe('Mediaplayer · Kopie');
  await openView(page,'Mediaplayer · Kopie');
  await page.getByRole('button',{name:'Ansicht anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='media_player').at(-1)[2].source)).toBe('Mediaplayer · Kopie');
  expect(await page.evaluate(()=>saved.views[0].id)).toBe('hdmi_full');
  expect(await page.evaluate(()=>saved.assignments)).toBeUndefined();
});

test('music view saves colour-only background and optional timeline state without changing other views',async({page})=>{
  await mount(page);
  await page.evaluate(png=>{
    hass.states['media_player.sonos']={entity_id:'media_player.sonos',state:'playing',attributes:{friendly_name:'Sonos Wohnzimmer',entity_picture:'/private-art',media_title:'First'}};
    hass.fetchWithAuth=async()=>new Response(Uint8Array.from(atob(png),c=>c.charCodeAt(0)),{headers:{'Content-Type':'image/png'}});
  },fs.readFileSync('tests/fixtures/media-cover.png').toString('base64'));
  await openView(page,'Mediaplayer');
  await expect(page.getByLabel('Cover darstellen')).toHaveValue('colors');
  await page.getByLabel('Hintergrund-Medienplayer').selectOption('media_player.sonos');
  await page.getByLabel('Bei Wiedergabe anzeigen').check();
  await expect(page.locator('.scene .lg-cover-background')).toHaveClass(/loaded/);
  await expect(page.locator('.scene .lg-cover-background img')).toBeHidden();
  await page.locator('.layer .name').filter({hasText:'JETZT LÄUFT'}).click();
  await expect(page.getByLabel('Play-/Pause-Symbol anzeigen')).toBeChecked();
  await page.getByLabel('Play-/Pause-Symbol anzeigen').uncheck();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.media_view.elements[0].show_playback_icon)).toBe(false);
  expect(await page.evaluate(()=>saved.scenes.media_view.media_background_fit)).toBe('colors');
  expect(await page.evaluate(()=>saved.assignments)).toBeUndefined();
  await page.getByLabel('Play-/Pause-Symbol anzeigen').check();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.media_view.elements[0].show_playback_icon)).toBe(true);
});


test('HDMI is the first editable resettable view; notifications have a separate lower section',async({page})=>{
  await mount(page);
  await expect(page.locator('.primary-gallery .view-card h3')).toHaveText(['Nur HDMI','Dashboard','Dashboard PiP','Mediaplayer','Startanzeige']);
  await expect(page.locator('.notification-gallery .view-card h3')).toHaveText(['Mitteilung','Mitteilung PiP','Mitteilung Vollbild']);
  await page.getByRole('button',{name:'Mitteilung duplizieren',exact:true}).click();
  await expect(page.locator('.primary-gallery .view-card h3').last()).toHaveText('Mitteilung · Kopie');
  const main=await page.locator('.primary-views').boundingBox(),notices=await page.locator('.notification-views').boundingBox();
  expect(notices.y).toBeGreaterThanOrEqual(main.y+main.height);
  await openView(page,'Nur HDMI');
  await page.locator('.layer .name').filter({hasText:'HDMI / PiP'}).click();
  await page.getByLabel('Breite (%)',{exact:true}).fill('75');await page.getByLabel('Breite (%)',{exact:true}).press('Tab');
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.hdmi_full.elements[0].width)).toBe(75);
  const others=await page.evaluate(()=>JSON.stringify(saved.views.slice(1)));
  await page.getByRole('button',{name:'Standard wiederherstellen',exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements[0].width)).toBe(100);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements[0].width)).toBe(75);
  await expect(page.locator('.status')).toHaveText('Gespeichert');
  await page.getByRole('button',{name:'Standard wiederherstellen',exact:true}).click();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.hdmi_full.elements[0].width)).toBe(100);
  expect(await page.evaluate(()=>JSON.stringify(saved.views.slice(1)))).toBe(others);
});


test('Nur HDMI display buttons use the latest renamed input and preserve drafts',async({page})=>{
  await mount(page);await openView(page,'Nur HDMI');
  await page.getByLabel('Eigenes Layout verwenden').check();await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{calls.length=0;window.currentHdmi='Konsole';hass.states['media_player.display'].attributes.hdmi_source='HDMI 1';});
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.locator('.view-card').filter({has:page.getByRole('heading',{name:'Nur HDMI',exact:true})}).getByRole('button',{name:'Anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='media_player').at(-1)[2].source)).toBe('Konsole');
  await openView(page,'Nur HDMI');
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  await page.evaluate(()=>window.currentHdmi='HDMI 3');
  await page.getByRole('button',{name:'Nur HDMI anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='media_player').at(-1)[2].source)).toBe('HDMI 3');
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='POST').length)).toBe(0);
  await expect(page.getByLabel('Hintergrund',{exact:true})).toHaveValue('ocean');
  await expect(page.locator('.status')).toHaveText('Ungespeichert');
  expect(await page.evaluate(()=>saved.scenes.hdmi_full.background)).toBe('midnight');
});

test('Nur HDMI never guesses an input when the backend has no current HDMI',async({page})=>{
  await mount(page);await openView(page,'Nur HDMI');
  await page.getByLabel('Eigenes Layout verwenden').check();await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{calls.length=0;window.currentHdmi=null;});
  await page.getByRole('button',{name:'Nur HDMI anzeigen',exact:true}).click();
  await expect(page.locator('.flash')).toContainText('HDMI-Eingang ist noch nicht bekannt');
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='media_player'||c[0]==='POST'))).toBe(false);
});

test('Anzeigen dropdown sends one animated saved-view action and keeps editor drafts',async({page})=>{
  await mount(page);await openView(page,'Nur HDMI');
  await page.getByLabel('Eigenes Layout verwenden').check();await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByLabel('Übergang für Dashboard PiP',{exact:true}).selectOption('smooth');
  await page.evaluate(()=>calls.length=0);
  await page.locator('.view-card').filter({has:page.getByRole('heading',{name:'Dashboard PiP',exact:true})}).getByRole('button',{name:'Anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='lg_rs232_ip'))).toEqual([['lg_rs232_ip','show_view',{entity_id:'media_player.display',view:'pip_view',transition:'smooth'}]]);
  await openView(page,'Nur HDMI');
  await expect(page.getByLabel('Übergang beim Anzeigen')).toHaveValue('smooth');
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  await page.getByRole('button',{name:'Nur HDMI anzeigen',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>c[0]==='lg_rs232_ip').at(-1)[2])).toEqual({entity_id:'media_player.display',view:'hdmi_full',transition:'smooth'});
  expect(await page.evaluate(()=>calls.some(c=>c[0]==='POST'||c[0]==='media_player'))).toBe(false);
  await expect(page.locator('.status')).toHaveText('Ungespeichert');
  await expect(page.getByLabel('Hintergrund',{exact:true})).toHaveValue('ocean');
});

test('camera widget can be configured, bounded to one and removed without fetching camera content',async({page})=>{
  await mount(page);await openView(page,'Nur HDMI');
  await page.evaluate(()=>studio.insertCard('camera'));
  await expect(page.getByLabel('Kameraquelle')).toBeVisible();
  await page.getByLabel('Kameraquelle').selectOption('entity');
  await page.getByLabel('Home-Assistant-Entität').fill('camera.door');
  await page.getByLabel('Home-Assistant-Entität').press('Tab');
  await page.getByLabel('Wiedergabe',{exact:true}).selectOption('snapshot');
  await page.getByLabel('Einzelbild-Abstand (s)').fill('3');
  await page.getByLabel('Einzelbild-Abstand (s)').press('Tab');
  await page.evaluate(()=>studio.insertCard('camera'));
  expect(await page.evaluate(()=>studio.scene.elements.filter(i=>i.kind==='camera').length)).toBe(1);
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.hdmi_full.elements.find(i=>i.kind==='camera').camera_interval)).toBe(3);
  expect(await page.locator('.scene video').count()).toBe(0);
  await page.getByRole('button',{name:'Element entfernen',exact:true}).click();
  await expect(page.locator('.scene .lg-camera')).toHaveCount(0);
});

test('multicast widget exposes its address, preserves it on save and blocks HDMI overlap',async({page})=>{
  await mount(page);await openView(page,'Nur HDMI');
  await page.evaluate(()=>studio.insertCard('camera'));
  await page.getByLabel('Kameraquelle').selectOption('multicast');
  await page.getByLabel('Multicast-Adresse').fill('udp://239.255.20.35:15000');
  await page.getByLabel('Multicast-Adresse').press('Tab');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await expect(page.locator('.flash')).toContainText('überlappen');
  await page.evaluate(()=>{studio.scene.elements=studio.scene.elements.filter(e=>e.kind!=='hdmi');studio.changed(true);});
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await expect(page.locator('.status')).toHaveText('Gespeichert');
  expect(await page.evaluate(()=>saved.scenes.hdmi_full.elements.find(e=>e.kind==='camera').multicast_url)).toBe('udp://239.255.20.35:15000');
  await expect(page.locator('.scene video')).toHaveCount(0);
});

test('fixed startup view exposes only offline content, persists edits, resets and cannot be deleted',async({page})=>{
  await mount(page);
  const card=page.locator('.view-card').filter({has:page.getByRole('heading',{name:'Startanzeige',exact:true})});
  await expect(card.getByRole('button',{name:'Löschen',exact:true})).toHaveCount(0);
  await expect(card.getByRole('button',{name:'Anzeigen',exact:true})).toHaveCount(0);
  await openView(page,'Startanzeige');
  await expect(page.getByLabel('Name der Ansicht')).toBeDisabled();
  expect(await page.getByLabel('Elementtyp',{exact:true}).locator('option').evaluateAll(nodes=>nodes.map(n=>n.value))).toEqual(['text','clock']);
  await expect(page.locator('.cover-background-tools')).toBeHidden();
  await expect(page.locator('.room-suggestions')).toBeHidden();
  await expect(page.locator('#sun-entity')).toBeHidden();
  await expect(page.getByLabel('Hintergrund',{exact:true}).locator('option[value=solar]')).toHaveCount(0);
  await page.locator('.layer .name').first().click();
  expect(await page.getByLabel('Widget-Typ').locator('option').evaluateAll(nodes=>nodes.map(n=>n.value))).toEqual(['text','clock']);
  await page.getByLabel('Text',{exact:true}).fill('Willkommen zuhause');await page.getByLabel('Text',{exact:true}).press('Tab');
  await page.locator('.sidebar').getByRole('button',{name:'Sonnenstand',exact:true}).click();
  await expect(page.getByLabel('Hintergrund',{exact:true})).toHaveValue('dawn');
  await page.getByLabel('Elementtyp',{exact:true}).selectOption('clock');await page.getByRole('button',{name:'＋',exact:true}).click();
  await expect(page.locator('.scene .lg-clock')).toBeVisible();
  const before=await page.evaluate(()=>JSON.stringify(studio.scene));
  await page.evaluate(()=>studio.insertCard('weather','weather.home'));
  expect(await page.evaluate(()=>JSON.stringify(studio.scene))).toBe(before);
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  expect(await page.evaluate(()=>saved.scenes.startup.elements.some(i=>i.text==='Willkommen zuhause'))).toBe(true);
  expect(await page.evaluate(()=>saved.scenes.startup.elements.every(i=>['text','clock'].includes(i.kind)))).toBe(true);
  await page.getByRole('button',{name:'Element entfernen',exact:true}).click();
  await expect(page.locator('.scene .lg-clock')).toHaveCount(0);
  await page.getByRole('button',{name:'Standard wiederherstellen',exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements.some(i=>i.text==='Willkommen zuhause'))).toBe(false);
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.elements.some(i=>i.text==='Willkommen zuhause'))).toBe(true);
  await page.evaluate(()=>studio.deleteView('startup'));
  expect(await page.evaluate(()=>studio.config.views.some(v=>v.id==='startup'))).toBe(true);
  await expect(page.locator('.scene .lg-value').filter({hasText:'Willkommen zuhause'})).toBeVisible();
  await expect(page.locator('.scene')).toHaveCSS('background-image',/gradient/);
  const stage=await page.locator('.stage').boundingBox(),preview=await page.locator('.scene').boundingBox();
  expect(preview.height).toBeGreaterThan(300);expect(Math.abs(preview.height-stage.height)).toBeLessThan(2);
  await page.screenshot({path:test.info().outputPath('startup-editor.png'),fullPage:true});
});


test('startup editor distinguishes unsaved, pending and display-confirmed offline designs',async({page})=>{
  await mount(page);await openView(page,'Startanzeige');
  await expect(page.locator('.startup-cache-status')).toContainText('nicht verbunden');
  await page.evaluate(async()=>{window.startupStatus={connected:true,stored:false};await studio.refreshValues();});
  await expect(page.locator('.startup-cache-status')).toContainText('ausstehend');
  await page.evaluate(async()=>{window.startupStatus={connected:true,stored:true};await studio.refreshValues();});
  await expect(page.locator('.startup-cache-status')).toContainText('Auf dem Display gespeichert');
  await page.evaluate(()=>{studio.scene.color='#123456';studio.changed();});
  await expect(page.locator('.startup-cache-status')).toContainText('Entwurf noch nicht gespeichert');
  await page.evaluate(async()=>{window.revision++;await studio.refreshValues();});
  await expect(page.locator('.startup-cache-status')).toContainText('anderen Sitzung');
  await openView(page,'Dashboard');
  await expect(page.locator('.startup-cache-status')).toBeHidden();
});

test('Studio buffers covers during authenticated fetches and exposes confirmed failures',async({page})=>{
  await mount(page);await openView(page,'Mediaplayer');
  await page.evaluate(png=>{
    window.fetches=[];window.replies=[];
    const player={entity_id:'media_player.sonos',state:'playing',attributes:{entity_picture:'/art',media_title:'One'}};hass.states[player.entity_id]=player;
    studio.scene.elements[0].entity_id=player.entity_id;
    Object.assign(studio.scene,{media_background_enabled:true,media_background_entity:player.entity_id,media_background_fit:'colors'});
    hass.fetchWithAuth=(url,options)=>new Promise((resolve,reject)=>{
      fetches.push({title:player.attributes.media_title,url,signal:options.signal});
      options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));
      replies.push(ok=>resolve(ok?new Response(Uint8Array.from(atob(png),c=>c.charCodeAt(0)),{headers:{'Content-Type':'image/png'}}):new Response('',{status:500})));
    });
    studio.paint();
  },fs.readFileSync('tests/fixtures/media-cover.png').toString('base64'));
  await expect.poll(()=>page.evaluate(()=>fetches.length)).toBeGreaterThan(0);
  await expect(page.locator('.scene .lg-media-placeholder')).toBeHidden();
  await page.evaluate(()=>{replies.splice(0).forEach(reply=>reply(true));});
  await expect(page.locator('.scene .lg-media-art')).toHaveClass(/loaded/);
  await expect(page.locator('.scene .lg-cover-background')).toHaveClass(/loaded/);
  const previous=await page.locator('.scene .lg-media-art img').getAttribute('src');
  const background=await page.locator('.scene .lg-cover-background').evaluate(n=>n.style.background);
  await page.evaluate(()=>{hass.states['media_player.sonos'].attributes.media_title='Two';studio.paint();});
  await expect.poll(()=>page.evaluate(()=>fetches.some(f=>f.title==='Two'))).toBe(true);
  await expect(page.locator('.scene .lg-media-art img')).toHaveAttribute('src',previous);
  expect(await page.locator('.scene .lg-cover-background').evaluate(n=>n.style.background)).toBe(background);
  await expect(page.locator('.scene .lg-media-placeholder')).toBeHidden();
  await page.evaluate(()=>{hass.states['media_player.sonos'].attributes.media_title='Three';studio.paint();});
  await expect.poll(()=>page.evaluate(()=>fetches.filter(f=>f.title==='Two').every(f=>f.signal.aborted))).toBe(true);
  await expect.poll(()=>page.evaluate(()=>fetches.some(f=>f.title==='Three'))).toBe(true);
  // Releasing old rejected requests must not clear the latest pending fetch.
  await page.evaluate(()=>{replies.splice(0).forEach(reply=>reply(true));});
  await expect(page.locator('.scene .lg-media-art img')).not.toHaveAttribute('src',previous);
  await expect(page.locator('.scene .lg-media-placeholder')).toBeHidden();
  await page.evaluate(()=>{hass.states['media_player.sonos'].attributes.media_title='Bad';studio.paint();});
  await expect.poll(()=>page.evaluate(()=>fetches.some(f=>f.title==='Bad'))).toBe(true);
  await page.evaluate(()=>{replies.splice(0).forEach(reply=>reply(false));});
  await expect(page.locator('.scene .lg-media-placeholder')).toBeVisible();
  await expect(page.locator('.scene .lg-cover-background')).not.toHaveClass(/loaded/);
  const failed=await page.evaluate(()=>fetches.length);
  await page.evaluate(()=>studio.paint());await page.waitForTimeout(1100);
  expect(await page.evaluate(()=>fetches.length)).toBe(failed);
});

test('Studio cancels pending cover fetches when disconnected',async({page})=>{
  await mount(page);await openView(page,'Mediaplayer');
  await page.evaluate(()=>{
    hass.states['media_player.sonos']={entity_id:'media_player.sonos',state:'playing',attributes:{entity_picture:'/art',media_title:'Pending'}};
    Object.assign(studio.scene,{media_background_enabled:true,media_background_entity:'media_player.sonos'});
    window.signals=[];hass.fetchWithAuth=(url,options)=>new Promise((resolve,reject)=>{signals.push(options.signal);options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')));});studio.paint();
  });
  await expect.poll(()=>page.evaluate(()=>signals.length)).toBeGreaterThan(0);
  await page.evaluate(()=>studio.remove());
  expect(await page.evaluate(()=>signals.every(signal=>signal.aborted))).toBe(true);
});

const viewContent=page=>page.evaluate(()=>studio.config.views.map(v=>({id:v.id,elements:v.scene.elements.map(({color,background,accent_color,...item})=>item)})));

test('global themes preserve layout and content, manual appearance overrides can return to inheritance',async({page})=>{
  await mount(page);
  const before=await viewContent(page);
  await expect(page.getByRole('heading',{name:'Themes & Hintergründe'})).toBeVisible();
  await expect(page.locator('.theme-card')).toHaveCount(4);
  await page.getByRole('button',{name:'Aurora als Standard-Theme',exact:true}).click();
  expect(await viewContent(page)).toEqual(before);
  expect(await page.evaluate(()=>studio.config.views.every(v=>v.scene.background==='aurora'&&!v.theme_override))).toBe(true);
  await openView(page,'Dashboard');
  await page.locator('.layer .name').filter({hasText:'Text'}).click();
  await page.getByLabel('Text',{exact:true}).fill('Bleibt erhalten');await page.getByLabel('Text',{exact:true}).press('Tab');
  expect(await page.evaluate(()=>studio.view.theme_override)).toBe(false);
  await page.getByLabel('Hintergrund',{exact:true}).selectOption('ocean');
  expect(await page.evaluate(()=>studio.view.theme_override)).toBe(true);
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByRole('button',{name:'Sonnenstand als Standard-Theme',exact:true}).click();
  expect(await page.evaluate(()=>studio.config.scenes.dashboard.background)).toBe('ocean');
  expect(await page.evaluate(()=>studio.config.scenes.pip_view.background)).toBe('solar');
  expect(await page.evaluate(()=>studio.config.scenes.startup.background)).toBe('dawn');
  await openView(page,'Dashboard');
  await page.locator('[data-action=theme-follow]').click();
  expect(await page.evaluate(()=>studio.view.theme_override)).toBe(false);
  expect(await page.evaluate(()=>studio.scene.background)).toBe('solar');
  expect(await page.evaluate(()=>studio.scene.elements.find(i=>i.kind==='text').text)).toBe('Bleibt erhalten');
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{studio.remove();document.body.append(studio);});
  await expect(page.locator('.theme-manager-status')).toContainText('Standard: Sonnenstand');
  expect(await page.evaluate(()=>saved.active_theme)).toBe('morning');
});

test('saved custom theme manages Sonos backgrounds and palette, supports reset delete and undo on mobile',async({page})=>{
  await mount(page,390);
  await page.evaluate(()=>{hass.states['media_player.sonos']={entity_id:'media_player.sonos',state:'idle',attributes:{friendly_name:'Sonos Wohnzimmer'}};studio.hass={...hass};});
  await page.getByRole('button',{name:'＋ Neues Theme',exact:true}).click();
  await expect(page.locator('.inspector')).toBeHidden();
  await expect(page.locator('.context-tabs')).toBeHidden();
  await page.getByLabel('Name des Themes').fill('Wohnzimmer');await page.getByLabel('Name des Themes').press('Tab');
  await page.locator('#background').selectOption('solar');
  await page.locator('#media-background-enabled').check();
  await page.locator('#media-background-entity').selectOption('media_player.sonos');
  await page.locator('#media-background-fit').selectOption('colors');
  await page.locator('#media-background-color-source').selectOption('cover');
  await page.locator('#theme-ink').fill('#fedcba');
  await page.locator('[data-action=theme-use]').click();
  const id=await page.locator('#theme-id').inputValue();
  const settings=await page.evaluate(()=>({theme:studio.theme,views:studio.config.views}));
  expect(settings.theme.style.media_background_entity).toBe('media_player.sonos');
  for(const v of settings.views){
    expect(v.scene.media_background_enabled).toBe(v.id!=='startup');
    expect(v.scene.media_background_color_source).toBe('cover');
    if(v.id==='startup')expect(v.scene.media_background_entity).toBe('');
    for(const item of v.scene.elements)if(item.kind!=='hdmi')expect(item.color).toBe('#fedcba');
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.getByRole('button',{name:'Wohnzimmer Theme löschen',exact:true}).click();
  expect(await page.evaluate(()=>studio.config.active_theme)).toBe('cinema');
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.config.active_theme)).toBe(id);
  await page.getByRole('button',{name:'＋ Neue Ansicht',exact:true}).click();
  await page.getByLabel('Name',{exact:true}).fill('Neue Quelle');
  await page.getByRole('button',{name:'Ansicht anlegen',exact:true}).click();
  expect(await page.evaluate(()=>studio.scene.media_background_entity)).toBe('media_player.sonos');
  expect(await page.evaluate(()=>studio.view.theme_override)).toBe(false);
});

test('theme palette remains editable without any dashboard widgets and undo restores theme draft',async({page})=>{
  await mount(page);
  await page.evaluate(()=>{studio.config.views.find(v=>v.id==='dashboard').scene.elements=[];studio.compileViews();studio.renderOverview();});
  await page.getByRole('button',{name:'Cinema Theme bearbeiten',exact:true}).click();
  await page.locator('#theme-ink').fill('#112233');
  expect(await page.evaluate(()=>studio.theme.style.ink)).toBe('#112233');
  await page.getByTitle('Rückgängig',{exact:true}).click();
  expect(await page.evaluate(()=>studio.theme.style.ink)).not.toBe('#112233');
  await page.getByTitle('Wiederholen',{exact:true}).click();
  await expect(page.locator('#theme-ink')).toHaveValue('#112233');
  await page.locator('[data-action=theme-use]').click();
  expect(await page.evaluate(()=>studio.config.scenes.overlay.elements.find(i=>i.kind!=='hdmi').color)).toBe('#112233');
  await page.getByRole('button',{name:'← Alle Ansichten',exact:true}).click();
  await page.locator('[data-reset-theme=cinema]').click();
  expect(await page.evaluate(()=>studio.config.themes[0].style.ink)).not.toBe('#112233');
  expect(await page.evaluate(()=>studio.config.scenes.dashboard.elements)).toEqual([]);
});

async function widgetEditor(page,label) {
  await page.getByRole('button',{name:label+' Inhalt bearbeiten',exact:true}).click();
  return page.getByRole('dialog',{name:'Widget bearbeiten',exact:true});
}

test('clock pencil opens independent date/time composition with content, fonts, geometry and reset',async({page})=>{
  await mount(page);await openView(page,'Dashboard');
  const original=await page.evaluate(()=>JSON.parse(JSON.stringify(studio.scene.elements.find(i=>i.kind==='clock'))));
  const editor=await widgetEditor(page,'GUTEN MORGEN');
  await editor.getByLabel('Uhr-Anzeige').selectOption('date');
  await expect(editor.locator('.lg-value')).toBeHidden();await expect(editor.locator('.lg-detail')).toBeVisible();
  await editor.getByLabel('Inhaltselement',{exact:true}).selectOption('date');
  await editor.getByLabel('Inhalt links (%)').fill('15');await editor.getByLabel('Inhalt links (%)').press('Tab');
  await editor.getByLabel('Inhalt Schriftgröße (%)').fill('18');await editor.getByLabel('Inhalt Schriftgröße (%)').press('Tab');
  await editor.getByLabel('Inhalt Schrift',{exact:true}).selectOption('serif');
  await editor.getByLabel('Datumsformat').selectOption('iso');
  await expect(editor.locator('.lg-detail')).toHaveText(/\d{4}-\d{2}-\d{2}/);
  await expect(editor.locator('.lg-detail')).toHaveCSS('font-family',/Georgia/);
  await editor.getByRole('button',{name:'Fertig',exact:true}).click();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  const savedClock=await page.evaluate(()=>saved.scenes.dashboard.elements.find(i=>i.kind==='clock'));
  expect(savedClock.parts.time.visible).toBe(false);expect(savedClock.parts.date.font_size).toBe(18);expect(savedClock.x).toBe(original.x);expect(savedClock.width).toBe(original.width);
  expect(await page.evaluate(()=>studio.view.theme_override)).toBe(false);
  await widgetEditor(page,'GUTEN MORGEN');
  await editor.getByRole('button',{name:'Inhalt-Layout zurücksetzen'}).click();
  await expect(editor.locator('.lg-value')).toBeVisible();
  expect(await page.evaluate(()=>studio.item.parts)).toBeUndefined();
  await editor.getByTitle('Widget-Änderung rückgängig').click();
  await expect(editor.getByLabel('Uhr-Anzeige')).toHaveValue('date');
  await editor.getByRole('button',{name:'Fertig',exact:true}).click();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();
  await page.evaluate(()=>{studio.remove();document.body.append(studio);});await openView(page,'Dashboard');await widgetEditor(page,'GUTEN MORGEN');
  await expect(editor.getByLabel('Uhr-Anzeige')).toHaveValue('date');
});

test('media widget parts drag and resize independently, can be removed and restored without losing entity or cover',async({page})=>{
  await mount(page);await openView(page,'Mediaplayer');
  await page.locator('.layer .name').filter({hasText:'JETZT LÄUFT'}).click();
  await page.getByLabel('Home-Assistant-Entität').fill('media_player.sonos');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  const editor=await widgetEditor(page,'JETZT LÄUFT');
  await editor.getByLabel('Inhaltselement',{exact:true}).selectOption('title');
  const before=await editor.locator('.lg-media-art').boundingBox();
  let box=await editor.locator('.part-outline').boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2-20,box.y+box.height/2+12);await page.mouse.up();
  expect(await page.evaluate(()=>studio.item.parts.title.x)).toBeLessThan(53);
  const after=await editor.locator('.lg-media-art').boundingBox();for(const key of ['x','y','width','height'])expect(after[key]).toBeCloseTo(before[key],1);
  box=await editor.locator('.part-resize').boundingBox();await page.mouse.move(box.x+6,box.y+6);await page.mouse.down();await page.mouse.move(box.x-30,box.y+15);await page.mouse.up();
  const changed=await page.evaluate(()=>studio.item.parts.title);
  expect(changed.width+changed.x).toBeLessThanOrEqual(100.01);
  await editor.getByLabel('Textquelle').selectOption('custom');
  await editor.getByLabel('Eigener Inhalt').fill('<img src=x onerror=window.hacked=true>');await editor.getByLabel('Eigener Inhalt').press('Tab');
  await expect(editor.locator('.lg-value')).toHaveText('<img src=x onerror=window.hacked=true>');
  expect(await page.evaluate(()=>window.hacked)).toBeUndefined();
  await editor.getByLabel('Inhaltselement',{exact:true}).selectOption('cover');
  await editor.getByRole('button',{name:'Inhalt entfernen',exact:true}).click();await expect(editor.locator('.lg-media-art')).toBeHidden();
  await editor.getByLabel('Element anzeigen').check();await expect(editor.locator('.lg-media-art')).toBeVisible();
  await editor.getByRole('button',{name:'Inhalt-Layout zurücksetzen'}).click();
  expect(await page.evaluate(()=>studio.item.entity_id)).toBe('media_player.sonos');expect(await page.evaluate(()=>studio.item.media_style)).toBe('stage');
  await expect(editor.locator('.lg-value')).not.toHaveText('<img src=x onerror=window.hacked=true>');
  await editor.getByRole('button',{name:'Fertig',exact:true}).click();
  expect(await page.evaluate(()=>calls.filter(c=>['media_player','lg_rs232_ip'].includes(c[0])))).toEqual([]);
});

test('widget editor remains usable on a phone, updates live and exposes all weather and calendar parts',async({page})=>{
  await mount(page,390);await openView(page,'Dashboard');
  await page.locator('.layer .name').filter({hasText:'Dein Wetter'}).click();await page.getByLabel('Home-Assistant-Entität').fill('weather.home');await page.getByLabel('Home-Assistant-Entität').press('Tab');
  const editor=await widgetEditor(page,'Dein Wetter');
  await editor.getByLabel('Inhaltselement',{exact:true}).selectOption('temperature');
  await expect(editor.locator('.lg-value')).toHaveText('23 °C');
  await page.evaluate(()=>{hass.states['weather.home'].attributes.temperature=24;studio.hass={...hass};});
  await expect(editor.locator('.lg-value')).toHaveText('24 °C');
  await editor.getByLabel('Inhaltselement',{exact:true}).selectOption('forecast_4_rain');
  await editor.getByRole('button',{name:'Inhalt entfernen',exact:true}).click();
  expect(await page.evaluate(()=>studio.item.parts.forecast_4_rain.visible)).toBe(false);
  expect(await editor.evaluate(n=>n.scrollWidth<=n.clientWidth)).toBe(true);
  await editor.getByRole('button',{name:'Fertig',exact:true}).click();
  await widgetEditor(page,'DEIN TAG');
  await editor.getByLabel('Inhaltselement',{exact:true}).selectOption('row_6_value');
  await editor.getByLabel('Textquelle').selectOption('custom');await editor.getByLabel('Eigener Inhalt').fill('Kalendertext');await editor.getByLabel('Eigener Inhalt').press('Tab');
  expect(await page.evaluate(()=>studio.item.parts.row_6_value.text)).toBe('Kalendertext');
  await editor.getByRole('button',{name:'Fertig',exact:true}).click();
  await page.getByRole('button',{name:'Speichern',exact:true}).click();await expect(page.locator('.status')).toHaveText('Gespeichert');
});
