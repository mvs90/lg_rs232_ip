const { test, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs');
const { startPreviewServer } = require('./preview-server.cjs');
const root = path.resolve('custom_components/lg_rs232_ip/www');
const menu = JSON.parse(fs.readFileSync(path.join(root, 'device-menu.json')));
let server;
test.beforeAll(async () => { server = await startPreviewServer(); });
test.afterAll(async () => { await server.close(); });
const entry = (key, extra={}) => ({
  entity_id: `${key.split(':')[0]}.renamed_${key.split(':')[1]}`,
  unique_id: `entry_with_underscores_${key.split(':')[1]}`,
  platform:'lg_rs232_ip', entity_category:'config', device_id:'lg1',
  config_entry_id:'entry_with_underscores', stateName:key.split(':')[1],
  disabled_by:null, hidden_by:null, ...extra,
});
const initial = [entry('number:contrast'),entry('select:input'),entry('select:pm_mode'),
  entry('switch:auto_sleep'),entry('text:signage_name'),entry('select:osd_language'),
  entry('button:restore_si'),entry('switch:remote_lock'),entry('select:audio_out')];

async function mount(page,{ entries=initial, legacy=false, catalog=menu, before=false, status=200 }={}) {
  await page.route('**/lg_rs232_ip/device-menu.json',route=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(catalog)}));
  await page.goto(server.url);
  // Model both verified native contracts: modern render on hass update, and
  // HA 2025 forwarding hass to its rows while shouldUpdate() returns false.
  await page.evaluate(({entries,legacy})=>{
    window.calls=[];
    window.hass={language:'de', states:Object.fromEntries(entries.map(e=>[e.entity_id,{state:'on'}])),
      callService: (...args)=>{ calls.push(args); }};
    class NativeCard extends HTMLElement {
      constructor(){super();this.attachShadow({mode:'open'});this._props=new Map();this._showHidden=false;this._rows=[];}
      get hass(){return this._hass;} set hass(v){this._hass=v;this.requestUpdate('hass');}
      get entities(){return this._entities;} set entities(v){this._entities=v;this.requestUpdate('entities');}
      get header(){return this._header;} set header(v){if(this._header!==v){this._header=v;this.requestUpdate('header');}}
      get deviceName(){return this._deviceName;} set deviceName(v){if(this._deviceName!==v){this._deviceName=v;this.requestUpdate('deviceName');}}
      get showHidden(){return this._showHidden;} set showHidden(v){if(this._showHidden!==v){this._showHidden=v;this.requestUpdate('showHidden');}}
      shouldUpdate(changed){
        for(const row of this._rows) row.querySelector('output').textContent=this.hass?.states[row.dataset.entity]?.state || 'unavailable';
        return !(legacy && changed.size===1 && changed.has('hass'));
      }
      requestUpdate(prop='manual'){
        this._props.set(prop,true);
        if(this._pending)return;this._pending=true;
        queueMicrotask(()=>{this._pending=false;const changed=this._props;this._props=new Map();
          if(!this.shouldUpdate(changed))return;
          const result=this.render();
          if(this.shadowRoot.firstChild!==result)this.shadowRoot.replaceChildren(result);
        });
      }
      render(){
        const body=document.createElement('section'), heading=document.createElement('h3');
        heading.textContent=this.header || '';body.append(heading);this._rows=[];
        for(const e of this.entities || []){
          if(e.disabled_by && !this.showHidden)continue;
          const row=document.createElement('div');row.dataset.entity=e.entity_id;
          const label=document.createElement('label');label.textContent=e.stateName;
          const button=document.createElement('button');button.textContent=e.disabled_by ? 'Enable '+e.stateName:'Set '+e.stateName;
          button.onclick=()=>this.hass.callService(e.entity_id.split('.')[0],'native_action',{entity_id:e.entity_id});
          const output=document.createElement('output');output.textContent=this.hass?.states[e.entity_id]?.state || 'unavailable';
          row.append(label,button,output);body.append(row);this._rows.push(row);
        }
        if((this.entities||[]).some(e=>e.disabled_by)){
          const toggle=document.createElement('button');toggle.textContent=this.showHidden?'Hide disabled':'Show disabled';
          toggle.onclick=()=>{this.showHidden=!this.showHidden;};body.append(toggle);
        }
        return body;
      }
    }
    customElements.define('ha-device-entities-card',NativeCard);
    window.create=()=>{window.card=document.createElement('ha-device-entities-card');card.hass=hass;card.entities=entries;card.header='Konfiguration';card.deviceName='Display';card.showHidden=false;document.body.append(card);};
  },{entries,legacy});
  if(before)await page.evaluate(()=>create());
  await page.addScriptTag({path:path.join(root,'device-settings.js')});
  if(status===200 && catalog.version===1 && catalog.groups?.length) {
    // Invalid catalogs intentionally never install.
    if(!catalog.invalidTest) await page.waitForFunction(()=>customElements.get('lg-display-device-settings'));
  }
  if(!before)await page.evaluate(()=>create());
}
async function openAll(page){await page.locator('lg-display-device-settings details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));}
async function update(page,change){await page.evaluate(change);}
const view = page=>page.locator('lg-display-device-settings');

for (const legacy of [false,true]) {
  test.describe(legacy?'HA 2025 contract':'HA current contract',()=>{
    test('native device settings ordered by LG menu; renamed IDs still work',async({page})=>{
      await mount(page,{legacy});await openAll(page);
      await expect(view(page).locator('summary > span:first-child')).toHaveText(['Ez-Einstellungen','Allgemein','Bildschirm','Ton','Admin','Home Assistant']);
      const ids=await view(page).locator('[data-entity]').evaluateAll(nodes=>nodes.map(n=>n.dataset.entity));
      expect(ids).toEqual(['button.renamed_restore_si','select.renamed_osd_language','text.renamed_signage_name','switch.renamed_auto_sleep','select.renamed_pm_mode','number.renamed_contrast','select.renamed_audio_out','switch.renamed_remote_lock','select.renamed_input']);
      await page.getByRole('button',{name:'Set contrast',exact:true}).click();
      expect(await page.evaluate(()=>calls)).toEqual([['number','native_action',{entity_id:'number.renamed_contrast'}]]);
    });
    test('state-only updates reach native controls and retain focus/open state',async({page})=>{
      await mount(page,{legacy});await openAll(page);
      await page.getByRole('button',{name:'Set contrast',exact:true}).focus();
      await update(page,()=>{window.previousView=card.shadowRoot.firstChild;window.child=previousView.shadowRoot.querySelector('[data-group="display"] ha-device-entities-card');child.dataset.identity='kept';hass={...hass,states:{...hass.states,'number.renamed_contrast':{state:'72'}}};card.hass=hass;});
      await expect(page.locator('[data-entity="number.renamed_contrast"] output')).toHaveText('72');
      expect(await page.evaluate(()=>card.shadowRoot.firstChild===previousView)).toBe(true);
      await expect(view(page).locator('details[open]')).toHaveCount(6);
      await expect(view(page).locator('[data-identity="kept"]')).toHaveCount(1);
      // Native current frontend is permitted to rerender its own rows; the LG
      // grouping must retain its cards, not recreate the native controls itself.
    });
    test('disabled entries keep native enable dialog and individual expansion',async({page})=>{
      await mount(page,{legacy,entries:[...initial,entry('number:brightness',{disabled_by:'user'})]});await openAll(page);
      await expect(page.getByRole('button',{name:'Enable brightness'})).toHaveCount(0);
      await page.getByRole('button',{name:'Show disabled'}).click();
      await expect(page.getByRole('button',{name:'Enable brightness'})).toBeVisible();
      await update(page,()=>{card.hass={...hass};});
      await expect(page.getByRole('button',{name:'Enable brightness'})).toBeVisible();
    });
    test('entity additions/removals and locale changes preserve menu order',async({page})=>{
      await mount(page,{legacy,entries:[entry('select:pm_mode'),entry('number:contrast')]});await openAll(page);
      await page.evaluate(e=>{card.entities=[...card.entities,e];card.hass={...hass,language:'en'};},entry('select:osd_language'));
      await expect(view(page).locator('summary > span:first-child')).toHaveText(['General','Display']);
      await expect(view(page).locator('[data-group="general"] h3')).toHaveText(['Language','Power']);
      await update(page,()=>{card.entities=card.entities.filter(e=>e.entity_id.startsWith('number.'));});
      await expect(view(page).locator('summary > span:first-child')).toHaveText(['Display']);
      await expect(view(page).locator('[data-entity]')).toHaveCount(1);
    });
    test('same card switching between two devices cannot reuse old entity targets',async({page})=>{
      await mount(page,{legacy});await openAll(page);
      await page.evaluate(e=>{card.entities=[e];},entry('number:brightness',{device_id:'lg2',config_entry_id:'two',unique_id:'two_brightness',entity_id:'number.second'}));
      await openAll(page);await expect(view(page).locator('[data-entity]')).toHaveCount(1);
      await page.getByRole('button',{name:'Set brightness'}).click();
      expect(await page.evaluate(()=>calls[0][2])).toEqual({entity_id:'number.second'});
    });
  });
}

test('already mounted card is upgraded; duplicate module never nests recursively',async({page})=>{
  await mount(page,{before:true});await expect(view(page)).toHaveCount(1);
  await page.addScriptTag({path:path.join(root,'device-settings.js')});
  await update(page,()=>card.requestUpdate());await expect(view(page)).toHaveCount(1);
});
test('unknown keys and HTML names are preserved as inert native entity rows',async({page})=>{
  await mount(page,{entries:[...initial,entry('text:new_option',{stateName:'<img src=x onerror="window.injected=true">'})]});await openAll(page);
  await expect(view(page).locator('summary').last()).toContainText('Weitere Einstellungen');
  await expect(view(page).locator('label').last()).toHaveText('<img src=x onerror="window.injected=true">');
  expect(await page.evaluate(()=>window.injected)).toBeUndefined();
});
test('alphabetical fallback preserves exact original entities and can return',async({page})=>{
  await mount(page);await page.getByRole('button',{name:'Darstellung der Geräteeinstellungen wechseln'}).click();
  await expect(view(page).locator('.standard [data-entity]')).toHaveCount(initial.length);
  expect(await view(page).locator('.standard [data-entity]').evaluateAll(ns=>ns.map(n=>n.dataset.entity))).toEqual(initial.map(e=>e.entity_id));
  await page.getByRole('button',{name:'Darstellung der Geräteeinstellungen wechseln'}).click();
  await expect(view(page).locator('.menu')).toBeVisible();
});
for(const [name,entries] of [
  ['other integration',[entry('select:input',{platform:'other'})]],
  ['mixed integrations',[...initial,entry('select:input',{platform:'other'})]],
  ['diagnostics',[entry('sensor:temperature',{entity_category:'diagnostic'})]],
  ['controls',[entry('media_player:media_player',{entity_category:null})]],
  ['empty',[]],['missing identity',[entry('select:input',{unique_id:undefined})]],
])test(`native fallback for ${name}`,async({page})=>{
  await mount(page,{entries});await expect(view(page)).toHaveCount(0);
  await expect(page.locator('ha-device-entities-card').locator('h3')).toHaveText('Konfiguration');
});
test('unavailable catalog retains original device settings',async({page})=>{
  await mount(page,{status:503});await expect(view(page)).toHaveCount(0);
  await expect(page.locator('[data-entity]')).toHaveCount(initial.length);
});
test('duplicate catalog keys reject grouping instead of hiding/duplicating entities',async({page})=>{
  const catalog=structuredClone(menu);catalog.invalidTest=true;
  catalog.groups[0].sections[0].entities.push('select:input');
  await mount(page,{catalog});await expect(view(page)).toHaveCount(0);
  await expect(page.locator('[data-entity]')).toHaveCount(initial.length);
});
