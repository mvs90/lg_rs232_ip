/* Local Home Assistant layout editor. The LG only runs the small ES5 renderer. */
const VERSION = "2.7.0";
const clone = value => JSON.parse(JSON.stringify(value));
const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const SCENES = {signal:"Mit HDMI",no_signal:"Ohne HDMI",dashboard:"Dashboard",overlay:"Meldung · Overlay",pip:"Meldung · PiP",fullscreen:"Meldung · Vollbild"};
const KINDS = {hdmi:"HDMI / PiP",clock:"Uhr & Datum",weather:"Wetter",calendar:"Kalender",entity:"HA-Entität",text:"Text",message:"Meldungsfenster"};
const BACKGROUNDS = {solid:"Einfarbig",aurora:"Aurora",dawn:"Morgenlicht",ocean:"Ozean",sand:"Sand",midnight:"Mitternacht",solar:"Sonnenstand",gradient:"Eigener Verlauf",image:"Eigenes Bild"};
const icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4M5 6h7M5 9h4"/></svg>';
const options = (items, value) => Object.entries(items).map(([key,label]) => `<option value="${escapeHTML(key)}" ${key === value ? "selected" : ""}>${escapeHTML(label)}</option>`).join("");

class LGDisplayStudio extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this.sceneKey="signal"; this.selected=null;
    this.dirty=false; this.busy=false; this.history=[]; this.future=[]; this._generation=0;
  }
  set hass(value) {
    this._hass=value;
    if (this.isConnected && !this.started) this.start();
    else if (this.renderer && !this._updateTimer) this._updateTimer=setTimeout(() => {this._updateTimer=null; if(this.isConnected) this.paint();},300);
  }
  get hass() {return this._hass;}
  connectedCallback() {if(this._hass && !this.started) this.start();}
  disconnectedCallback() {
    this._generation++; this.started=false;
    clearTimeout(this._updateTimer); this._updateTimer=null; clearInterval(this._clock);
    clearInterval(this._dataTimer); clearTimeout(this._dataSoon);
    this._resize?.disconnect(); this._resize=null;this.releaseImages();
  }
  async start() {
    this.started=true; const generation=++this._generation;
    this.shadowRoot.innerHTML=`<link rel="stylesheet" href="/lg_rs232_ip/studio.css?v=${VERSION}"><link rel="stylesheet" href="/lg_rs232_ip/layout.css?v=${VERSION}"><div class="empty">Display Studio wird geladen …</div>`;
    try {
      await Promise.all([import(`/lg_rs232_ip/weather.js?v=${VERSION}`),import(`/lg_rs232_ip/layout-runtime.js?v=${VERSION}`)]);
      this.catalog=await this.hass.callApi("GET","lg_rs232_ip/layouts");
      if(generation!==this._generation || !this.isConnected) return;
      if(!this.catalog.entries.length) {this.shadowRoot.querySelector('.empty').textContent="Lege zuerst ein LG-Display in den Integrationseinstellungen an.";return;}
      this.entryId=this.entryId && this.catalog.entries.some(e=>e.entry_id===this.entryId) ? this.entryId : this.catalog.entries[0].entry_id;
      const doc=await this.hass.callApi("GET",`lg_rs232_ip/layout/${this.entryId}`);
      if(generation!==this._generation) return;
      this.accept(doc); this.mount();
    } catch(error) { if(generation===this._generation) this.shadowRoot.querySelector('.empty').textContent="Der Editor konnte nicht geladen werden. Bitte als Administrator anmelden und erneut öffnen."; }
  }
  accept(doc) {this.releaseImages();this.backgrounds=doc.backgrounds || [];this.backendSun=doc.sun;this.config=clone(doc.config);this.revision=doc.revision;this.saved=clone(doc.config);this.backendValues=doc.values || {};this.timezone=doc.timezone || this.hass.config?.time_zone || "Europe/Berlin";this.dirty=false;this.selected=null;this.history=[];this.future=[];}
  mount() {
    this.shadowRoot.innerHTML=`<link rel="stylesheet" href="/lg_rs232_ip/studio.css?v=${VERSION}"><link rel="stylesheet" href="/lg_rs232_ip/layout.css?v=${VERSION}">
      <header><button class="menu" aria-label="Seitenleiste öffnen">☰</button><div class="logo">${icon}</div><div><h1>Display Studio</h1><p>Dein Zuhause. Auf deinem Bildschirm.</p></div><div class="spacer"></div><select class="device" aria-label="Display">${this.catalog.entries.map(e=>`<option value="${escapeHTML(e.entry_id)}" ${e.entry_id===this.entryId?'selected':''}>${escapeHTML(e.name)}</option>`).join("")}</select><div class="toolbar"><span class="status" role="status"></span><button class="secondary" data-action="undo" title="Rückgängig">↶</button><button class="secondary" data-action="redo" title="Wiederholen">↷</button><button class="primary" data-action="save">Speichern & anwenden</button></div></header>
      <div class="notice" hidden></div><div class="workspace"><aside class="sidebar"><h2>Ein guter Anfang</h2><div class="presets">${this.catalog.presets.map(p=>`<button class="preset" data-preset="${escapeHTML(p.id)}"><div class="mini" data-mini="${escapeHTML(p.id)}"></div><strong>${escapeHTML(p.name)}</strong><span>${escapeHTML(p.description)}</span></button>`).join("")}</div><p class="note">Vorlagen ändern deinen Entwurf. Erst Speichern überträgt ihn auf das Display.</p><div class="links"><button class="small" data-action="export">Exportieren</button><button class="small" data-action="import">Importieren</button><input class="export" type="file" accept="application/json,.json"></div><h3>Ausgabe</h3><button class="secondary" data-action="dashboard">Dashboard anzeigen</button><div class="toggle"><label><input type="checkbox" id="enabled">Eigenes Layout verwenden</label></div><p class="note">Nur die hier ausgewählten Entitäten werden an das Display weitergegeben.</p></aside>
      <main class="main"><div class="scene-tabs" role="tablist">${Object.entries(SCENES).map(([key,name])=>`<button class="tab" role="tab" data-scene="${key}" aria-selected="false">${name}</button>`).join("")}</div><div class="mode-controls"><label>Ansicht auf dem Display<select id="mode">${options({auto:"Automatisch nach HDMI-Signal",signal:"Immer die HDMI-Ansicht",no_signal:"Immer die Ansicht ohne HDMI"},this.config.mode)}</select></label><label>Signalpause (s)<input id="signal-delay" type="number" min="0" max="30" value="${this.config.signal_delay}"></label></div><div class="preview-label"><span id="scene-title"></span><span>16:9 · HDMI-Platzhalter · Live-Entitäten</span></div><div class="frame"><div class="stage"><div class="scene"><div class="lg-hdmi-placeholder">HDMI</div></div><div class="selection-layer"></div></div></div><p class="hint">Element anklicken und ziehen · Größe über die Ecke ändern · Pfeiltasten: 1 %, mit Umschalt: 0,1 %</p><div class="flash" aria-live="polite"></div><section class="message-test"><h2>Meldung ausprobieren</h2><textarea id="test-message" aria-label="Testnachricht">Die Waschmaschine ist fertig.</textarea><div class="row"><select id="test-layout" aria-label="Nachrichtenlayout">${options({overlay:"Overlay",pip:"PiP",fullscreen:"Vollbild"},'overlay')}</select><button class="secondary" data-action="test">10 Sekunden anzeigen</button></div><p class="note">Verwendet das gespeicherte Layout. Für die Anzeige muss die App verbunden sein.</p></section></main><aside class="inspector"><section class="section"><h2>Szene gestalten</h2><div class="form-grid"><label class="full">Hintergrund<select id="background">${options(BACKGROUNDS,this.scene.background)}</select></label><label>Grundfarbe<input id="scene-color" type="color"></label><label>Akzent<input id="scene-accent" type="color"></label></div><label class="field">Verlaufswinkel<input id="gradient-angle" type="range" min="0" max="360" step="1"></label><label class="field">Sonnenstand-Entität<input id="sun-entity" list="sun-entities" placeholder="sun.sun"><datalist id="sun-entities">${Object.keys(this.hass.states).filter(id=>id.startsWith('sun.')).map(id=>`<option value="${escapeHTML(id)}"></option>`).join('')}</datalist></label><div class="background-tools"><label class="field">Eigenes Hintergrundbild<select id="bg-image"></select></label><label class="field">Bild einpassen<select id="image-fit">${options({cover:'Ausfüllen',contain:'Vollständig zeigen'},this.scene.image_fit)}</select></label><label class="field">Bild abdunkeln<input id="image-dim" type="range" min="0" max="0.9" step="0.05"></label><input id="bg-upload" class="export" type="file" accept="image/jpeg,image/png"><button class="small" data-action="upload-background">Bild hochladen</button><button class="small" data-action="clean-backgrounds">Unbenutzte Bilder entfernen</button><p class="note">JPEG/PNG, bis 5 MiB. Lokal auf maximal 1920 × 1080 verkleinert. Erst Speichern ändert das Display.</p></div><h3>Elemente · vorne zuerst</h3><div class="layers"></div><div class="add"><select aria-label="Elementtyp" id="new-kind">${options(KINDS,'entity')}</select><button class="small" data-action="add">＋</button></div></section><section class="properties"></section></aside></div>`;
    const $=selector=>this.shadowRoot.querySelector(selector);
    $('.menu').onclick=()=>this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true}));
    $('.device').onchange=event=>this.switchDisplay(event.target.value);
    this.shadowRoot.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>this.action(button.dataset.action));
    this.shadowRoot.querySelectorAll('[data-preset]').forEach(button=>{
      const preset=this.catalog.presets.find(p=>p.id===button.dataset.preset);button.querySelector('.mini').style.background=window.LGLayoutBackground(preset.layout.scenes.no_signal);
      button.onclick=()=>{this.checkpoint();const enabled=this.config.enabled;this.config=clone(preset.layout);this.config.enabled=enabled;this.selected=null;this.changed(true);this.flash(`${preset.name} übernommen. Du kannst jede Ansicht einzeln anpassen.`);};
    });
    this.shadowRoot.querySelectorAll('[data-scene]').forEach(button=>button.onclick=()=>{this.sceneKey=button.dataset.scene;this.selected=null;this.refreshScene();});
    $('#bg-upload').onchange=event=>this.uploadBackground(event.target.files[0]);
    $('#sun-entity').onchange=event=>{this.checkpoint();this.config.sun_entity=event.target.value;this.changed();};
    $('#enabled').onchange=event=>{this.checkpoint();this.config.enabled=event.target.checked;this.changed();};
    $('#mode').onchange=event=>{this.checkpoint();this.config.mode=event.target.value;this.changed();};
    $('#signal-delay').onchange=event=>{this.checkpoint();this.config.signal_delay=Math.max(0,Math.min(30,Number(event.target.value)||0));this.changed();};
    for(const [id,key] of [['background','background'],['scene-color','color'],['scene-accent','accent'],['gradient-angle','gradient_angle'],['bg-image','image_id'],['image-fit','image_fit'],['image-dim','image_dim']]) $("#"+id).onchange=event=>{this.checkpoint();this.scene[key]=['gradient_angle','image_dim'].includes(key)?Number(event.target.value):event.target.value;this.changed();};
    $('.export').onchange=event=>this.importFile(event.target.files[0]);
    $('#test-message').oninput=()=>this.paint();
    this.renderer=new window.LGLayoutRenderer($('.scene'),$('.lg-hdmi-placeholder'),true);
    this._resize=new ResizeObserver(()=>this.paint());this._resize.observe($('.stage'));
    this._clock=setInterval(()=>this.renderer?.tick(new Date()),1000);
    this._dataTimer=setInterval(()=>this.refreshValues(),30000);
    this.refreshScene();this.updateStatus();
  }
  get scene() {return this.config.scenes[this.sceneKey];}
  get item() {return this.scene.elements.find(item=>item.id===this.selected);}
  checkpoint() {this.history.push(clone(this.config));if(this.history.length>30)this.history.shift();this.future=[];}
  changed(refresh=false) {this.dirty=JSON.stringify(this.config)!==JSON.stringify(this.saved);if(refresh)this.refreshScene();else {this.paint();this.renderSelection();}this.updateStatus();}
  updateStatus() {
    const root=this.shadowRoot, status=root.querySelector('.status');if(!status)return;
    status.textContent=this.busy?'Wird gespeichert …':this.dirty?'Ungespeichert':'Gespeichert';status.dataset.dirty=String(this.dirty);
    root.querySelector('[data-action=save]').disabled=this.busy;
    root.querySelector('.device').disabled=this.busy;
    root.querySelector('[data-action=undo]').disabled=this.busy || !this.history.length;
    root.querySelector('[data-action=redo]').disabled=this.busy || !this.future.length;
    root.querySelector('[data-action=dashboard]').disabled=this.busy || !this.config.enabled;
    root.querySelector('#enabled').checked=this.config.enabled;root.querySelector('#mode').value=this.config.mode;root.querySelector('#signal-delay').value=this.config.signal_delay;
    const entry=this.catalog.entries.find(e=>e.entry_id===this.entryId), notice=root.querySelector('.notice');
    notice.hidden=!!entry?.resident_enabled;
    notice.innerHTML=entry?.resident_enabled?'':'Für dauerhafte Ansichten aktiviere <b>Display-App</b> und <b>SI-Dauerbetrieb</b> in den <a href="/config/integrations/integration/lg_rs232_ip">LG-Einstellungen</a>. Hier kannst du das Layout schon vorbereiten.';
  }
  async switchDisplay(entryId) {
    if(this.busy)return;
    if(this.dirty) {this.flash('Speichere deinen Entwurf oder mache die Änderungen rückgängig, bevor du das Display wechselst.',true);this.shadowRoot.querySelector('.device').value=this.entryId;return;}
    try {const doc=await this.hass.callApi('GET',`lg_rs232_ip/layout/${entryId}`);this.entryId=entryId;this.accept(doc);this.refreshScene();this.updateStatus();} catch(_) {this.flash('Display konnte nicht geladen werden.',true);}
  }
  refreshScene() {
    const root=this.shadowRoot;root.querySelectorAll('[data-scene]').forEach(tab=>tab.setAttribute('aria-selected',String(tab.dataset.scene===this.sceneKey)));
    root.querySelector('#scene-title').textContent=SCENES[this.sceneKey];root.querySelector('#background').value=this.scene.background;root.querySelector('#scene-color').value=this.scene.color;root.querySelector('#scene-accent').value=this.scene.accent;root.querySelector('#gradient-angle').value=this.scene.gradient_angle;root.querySelector('#sun-entity').value=this.config.sun_entity;root.querySelector('#image-fit').value=this.scene.image_fit;root.querySelector('#image-dim').value=this.scene.image_dim;this.renderBackgrounds();
    this.paint();this.renderLayers();this.renderSelection();this.renderProperties();
  }
  values() {
    const result=clone(this.backendValues || {});
    for(const scene of Object.values(this.config.scenes)) for(const item of scene.elements) {
      const state=this.hass.states[item.entity_id];if(!state)continue;
      const attrs=state.attributes;result[item.entity_id]={...result[item.entity_id],state:state.state,name:attrs.friendly_name || item.entity_id,unit:attrs.unit_of_measurement || ''};
      if(item.kind==='weather') for(const key of ['temperature','temperature_unit','humidity','wind_speed','wind_speed_unit'])result[item.entity_id][key]=String(attrs[key] ?? '');
      if(item.kind==='calendar' && !result[item.entity_id].events)result[item.entity_id].events=attrs.message?[{summary:attrs.message,start:attrs.start_time,end:attrs.end_time}]:[];
    }
    return result;
  }
  sun() {const id=this.config.sun_entity,state=this.hass.states[id];if(!id || state && !['above_horizon','below_horizon'].includes(state.state))return null;return state ? {is_daytime:state.state==='above_horizon',elevation:state.attributes.elevation,azimuth:state.attributes.azimuth,rising:state.attributes.rising} : id===this.saved.sun_entity ? this.backendSun : null;}
  paint() {if(this.renderer && this.config)this.renderer.render(this.scene,this.values(),{timezone:this.timezone,sun:this.sun(),imageUrl:id=>this.imageUrl(id),now:new Date(),message:{title:'Home Assistant',message:this.shadowRoot.querySelector('#test-message')?.value || 'Deine Benachrichtigung erscheint hier.'}});}
  async refreshValues() {
    if(this._dataBusy || !this.isConnected)return;
    this._dataBusy=true;const id=this.entryId,generation=this._generation;
    try {const doc=await this.hass.callApi('GET',`lg_rs232_ip/layout/${id}`);if(this.isConnected && this.entryId===id && generation===this._generation && doc.revision>=this.revision){this.backendValues=doc.values || {};this.backendSun=doc.sun;this.paint();}}
    catch(_){}finally{this._dataBusy=false;}
  }
  renderLayers() {
    const container=this.shadowRoot.querySelector('.layers');container.innerHTML=[...this.scene.elements].reverse().map(item=>`<div class="layer ${item.id===this.selected?'active':''}"><button class="name" data-select="${escapeHTML(item.id)}">${escapeHTML(item.label || KINDS[item.kind])}</button><button class="icon" data-up="${escapeHTML(item.id)}" title="Nach vorne">↑</button><button class="icon" data-down="${escapeHTML(item.id)}" title="Nach hinten">↓</button></div>`).join('');
    container.querySelectorAll('[data-select]').forEach(button=>button.onclick=()=>this.select(button.dataset.select));
    for(const direction of ['up','down'])container.querySelectorAll(`[data-${direction}]`).forEach(button=>button.onclick=()=>{const id=button.dataset[direction],i=this.scene.elements.findIndex(item=>item.id===id),j=i+(direction==='up'?1:-1);if(j<0||j>=this.scene.elements.length)return;this.checkpoint();[this.scene.elements[i],this.scene.elements[j]]=[this.scene.elements[j],this.scene.elements[i]];this.changed(true);});
  }
  select(id) {this.selected=id;this.renderLayers();this.renderSelection();this.renderProperties();}
  renderSelection() {
    const container=this.shadowRoot.querySelector('.selection-layer');container.innerHTML='';
    for(const item of this.scene.elements) {
      const node=document.createElement('div');node.className='selection'+(item.id===this.selected?' selected':'');node.tabIndex=0;node.setAttribute('role','button');node.setAttribute('aria-label',`${item.label || KINDS[item.kind]} verschieben`);node.dataset.id=item.id;
      Object.assign(node.style,{left:item.x+'%',top:item.y+'%',width:item.width+'%',height:item.height+'%'});
      const tag=document.createElement('span');tag.className='tag';tag.textContent=item.label || KINDS[item.kind];node.append(tag);
      if(item.id===this.selected){const handle=document.createElement('span');handle.className='resize';handle.title='Größe ändern';node.append(handle);}
      node.onpointerdown=event=>this.pointer(event,item.id,node,event.target.classList.contains('resize'));
      node.onkeydown=event=>{
        if(event.key==='Delete'||event.key==='Backspace'){event.preventDefault();this.removeItem(item.id);return;}
        if(event.key==='Enter'||event.key===' '){event.preventDefault();this.select(item.id);return;}
        if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;
        event.preventDefault();this.selected=item.id;this.checkpoint();const n=event.shiftKey ? 0.1 : 1;
        item.x=Math.max(0,Math.min(100-item.width,item.x+(event.key==='ArrowRight'?n:event.key==='ArrowLeft'?-n:0)));
        item.y=Math.max(0,Math.min(100-item.height,item.y+(event.key==='ArrowDown'?n:event.key==='ArrowUp'?-n:0)));
        this.changed();this.renderProperties();this.shadowRoot.querySelector(`.selection[data-id="${item.id}"]`)?.focus();
      };
      container.append(node);
    }
  }
  pointer(event,id,node,resize) {
    if(event.button!==0 || this.busy)return;event.preventDefault();this.selected=id;this.renderLayers();this.renderProperties();
    this.shadowRoot.querySelectorAll('.selection').forEach(el=>el.classList.toggle('selected',el.dataset.id===id));
    const item=this.item, original=clone(item), bounds=this.shadowRoot.querySelector('.stage').getBoundingClientRect(),startX=event.clientX,startY=event.clientY;
    this.checkpoint();node.setPointerCapture(event.pointerId);
    node.onpointermove=move=>{
      const dx=(move.clientX-startX)/bounds.width*100,dy=(move.clientY-startY)/bounds.height*100;
      if(resize){item.width=Math.max(2,Math.min(100-item.x,original.width+dx));item.height=Math.max(2,Math.min(100-item.y,original.height+dy));}
      else {item.x=Math.max(0,Math.min(100-item.width,original.x+dx));item.y=Math.max(0,Math.min(100-item.height,original.y+dy));}
      for(const key of ['x','y','width','height'])item[key]=Math.round(item[key]*100)/100;
      Object.assign(node.style,{left:item.x+'%',top:item.y+'%',width:item.width+'%',height:item.height+'%'});this.paint();
    };
    const end=()=>{node.onpointermove=node.onpointerup=node.onpointercancel=null;this.changed();this.renderProperties();};node.onpointerup=node.onpointercancel=end;
  }
  renderProperties() {
    const root=this.shadowRoot.querySelector('.properties'),item=this.item;
    if(!item){root.innerHTML='<h2>Dein Layout, dein Platz</h2><p class="empty">Wähle ein Element in der Vorschau oder füge eines hinzu. HDMI lässt sich wie jedes andere Element positionieren und skalieren.</p>';return;}
    const field=(key,label,min,max,step=1)=>`<label>${label}<input type="number" data-prop="${key}" min="${min}" max="${max}" step="${step}" value="${item[key]}"></label>`;
    let binding='';if(['entity','weather','calendar'].includes(item.kind)){
      const states=Object.values(this.hass.states).filter(s=>item.kind==='entity'||s.entity_id.startsWith(item.kind+'.')).sort((a,b)=>(a.attributes.friendly_name||a.entity_id).localeCompare(b.attributes.friendly_name||b.entity_id));
      binding=`<label class="field">Home-Assistant-Entität<input list="entity-options" data-prop="entity_id" value="${escapeHTML(item.entity_id)}" placeholder="${item.kind==='entity'?'sensor.wohnzimmer':item.kind+'.…'}"><datalist id="entity-options">${states.map(s=>`<option value="${escapeHTML(s.entity_id)}">${escapeHTML(s.attributes.friendly_name||s.entity_id)}</option>`).join('')}</datalist></label>`;
    }
    root.innerHTML=`<h2>${escapeHTML(KINDS[item.kind])}</h2><label class="field">Widget-Typ<select data-kind>${options(KINDS,item.kind)}</select></label><div class="form-grid">${field('x','Links (%)',0,98,.1)}${field('y','Oben (%)',0,98,.1)}${field('width','Breite (%)',2,100,.1)}${field('height','Höhe (%)',2,100,.1)}</div>${item.kind==='hdmi'?'<p class="hint">Das HDMI-Bild wird unverzerrt in dieses Rechteck eingepasst. Pro Szene ist ein HDMI-Bild möglich.</p>':`<h3>Inhalt</h3><label class="field">Beschriftung<input data-prop="label" value="${escapeHTML(item.label)}" maxlength="100"></label>${binding}${item.kind==='text'?`<label class="field">Text<textarea aria-label="Text" data-prop="text" maxlength="2000">${escapeHTML(item.text)}</textarea></label>`:''}${item.kind==='weather'?`<label class="field">Wetteransicht<select data-prop="forecast_type">${options({current:'Nur aktuell',daily:'Tagesvorschau',hourly:'Stundenvorschau'},item.forecast_type)}</select></label><div class="form-grid">${field('forecast_count','Prognoseabschnitte',1,8)}<label>Gestaltung<select data-prop="weather_style">${options({glass:'Karte',sky:'Himmel nach Sonnenstand',minimal:'Transparent'},item.weather_style)}</select></label></div><div class="toggle"><label><input type="checkbox" data-prop="animate" ${item.animate?'checked':''}>Aktuelles Wettersymbol animieren</label></div>`:''}<div class="toggle"><label><input type="checkbox" data-prop="show_label" ${item.show_label?'checked':''}>Beschriftung anzeigen</label></div><h3>Aussehen</h3><div class="form-grid">${field('font_size','Schriftgröße (% Höhe)',1,18,.1)}${field('radius','Rundung',0,80)}<label>Textfarbe<input type="color" data-prop="color" value="${item.color}"></label><label>Flächenfarbe<input type="color" data-prop="background" value="${item.background}"></label>${field('opacity','Deckkraft',0,1,.05)}<label>Ausrichtung<select data-prop="align">${options({left:'Links',center:'Mittig',right:'Rechts'},item.align)}</select></label><label class="full">Schrift<select data-prop="font">${options({sans:'Klar · Sans Serif',serif:'Editorial · Serif',mono:'Technisch · Monospace'},item.font)}</select></label></div>`}<div class="links"><button class="small delete" data-remove>Element entfernen</button></div>`;
    root.querySelector('[data-remove]').onclick=()=>this.removeItem(item.id);
    root.querySelector('[data-kind]').onchange=event=>{
      const kind=event.target.value;
      if(['hdmi','message'].includes(kind) && this.scene.elements.some(other=>other!==item && other.kind===kind)){event.target.value=item.kind;this.flash('Dieser Typ ist in der Szene bereits vorhanden.',true);return;}
      this.checkpoint();if(item.label===KINDS[item.kind])item.label=KINDS[kind];item.kind=kind;
      if(!['entity','weather','calendar'].includes(kind)||(['weather','calendar'].includes(kind)&&!item.entity_id.startsWith(kind+'.')))item.entity_id='';
      this.changed(true);
    };
    root.querySelectorAll('[data-prop]').forEach(input=>input.onchange=()=>{
      this.checkpoint();const key=input.dataset.prop;let value=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;
      if(input.type==='number')value=Math.max(Number(input.min),Math.min(Number(input.max),Number.isFinite(value)?value:Number(input.min)));
      item[key]=value;
      if(key==='x')item.x=Math.min(item.x,100-item.width);if(key==='y')item.y=Math.min(item.y,100-item.height);
      if(key==='width')item.width=Math.min(item.width,100-item.x);if(key==='height')item.height=Math.min(item.height,100-item.y);
      input.value=item[key];this.changed();this.renderLayers();
    });
  }
  async action(action) {
    if(action==='save')return this.save();
    if(action==='undo' && this.history.length){this.future.push(clone(this.config));this.config=this.history.pop();this.selected=null;this.changed(true);}
    if(action==='redo' && this.future.length){this.history.push(clone(this.config));this.config=this.future.pop();this.selected=null;this.changed(true);}
    if(action==='add'){
      const kind=this.shadowRoot.querySelector('#new-kind').value;
      if(this.scene.elements.length>=16 || (['hdmi','message'].includes(kind)&&this.scene.elements.some(i=>i.kind===kind))){this.flash('Maximal 16 Elemente, davon je ein HDMI- und Meldungsfenster.',true);return;}
      this.checkpoint();const id=kind+'_'+Math.random().toString(36).slice(2,10);this.scene.elements.push({id,kind,x:5,y:5,width:kind==='hdmi'?60:30,height:kind==='hdmi'?60:25,label:KINDS[kind],text:kind==='text'?'Dein Text':'',entity_id:'',font_size:3.5,color:'#f2f6fa',background:'#142335',opacity:.88,radius:24,align:'left',font:'sans',show_label:true,forecast_type:'daily',forecast_count:4,animate:true,weather_style:'glass'});this.selected=id;this.changed(true);
    }
    if(action==='export'){
      const blob=new Blob([JSON.stringify(this.config,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='lg-display-layout.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    if(action==='upload-background')this.shadowRoot.querySelector('#bg-upload').click();
    if(action==='clean-backgrounds')return this.cleanBackgrounds();
    if(action==='dashboard')return this.showDashboard();
    if(action==='import')this.shadowRoot.querySelector('.export').click();
    if(action==='test'){
      if(this.dirty){this.flash('Speichere zuerst, damit die Testmeldung dein aktuelles Layout verwendet.',true);return;}
      try {const result=await this.hass.callWS({type:'config/entity_registry/list'});const entity=result.find(e=>e.config_entry_id===this.entryId&&e.entity_id.startsWith('media_player.')&&!e.disabled_by);
        if(!entity)throw Error();await this.hass.callService('lg_rs232_ip','show_display_app',{entity_id:entity.entity_id,title:'Home Assistant',message:this.shadowRoot.querySelector('#test-message').value.slice(0,2000),layout:this.shadowRoot.querySelector('#test-layout').value,duration:10});this.flash('Testmeldung an das Display gesendet.');
      }catch(_){this.flash('Testmeldung nicht möglich. Prüfe App-Verbindung und SI-Dauerbetrieb.',true);}
    }
  }
  removeItem(id) {this.checkpoint();this.scene.elements=this.scene.elements.filter(item=>item.id!==id);this.selected=null;this.changed(true);}
  async showDashboard() {
    if(this.dirty){this.flash('Speichere zuerst deinen Entwurf.',true);return;}
    try {const registry=await this.hass.callWS({type:'config/entity_registry/list'});const player=registry.find(e=>e.config_entry_id===this.entryId&&e.entity_id.startsWith('media_player.')&&!e.disabled_by);if(!player)throw Error();await this.hass.callService('media_player','select_source',{entity_id:player.entity_id,source:this.hass.states[player.entity_id]?.attributes.dashboard_source || 'Dashboard'});this.flash('Quelle Dashboard ausgewählt. Über die Fernbedienung kannst du wieder HDMI wählen.');}catch(_){this.flash('Dashboard nicht erreichbar. Prüfe SI-Dauerbetrieb und Stromversorgung.',true);}
  }
  releaseImages() {for(const url of Object.values(this.imageUrls || {}))if(url)URL.revokeObjectURL(url);this.imageUrls={};this.imagePending=new Set();}
  imageUrl(id) {
    if(this.imageUrls[id]!==undefined)return this.imageUrls[id] || '';
    if(this.imagePending.has(id))return '';
    const generation=this._generation,entry=this.entryId;this.imagePending.add(id);
    this.hass.fetchWithAuth(`/api/lg_rs232_ip/layout_background/${entry}/${id}`).then(async response=>{
      if(!response.ok)throw Error();const url=URL.createObjectURL(await response.blob());
      if(!this.isConnected||generation!==this._generation||entry!==this.entryId){URL.revokeObjectURL(url);return;}
      this.imageUrls[id]=url;this.paint();
    }).catch(()=>{if(entry===this.entryId&&generation===this._generation)this.imageUrls[id]=null;}).finally(()=>this.imagePending.delete(id));return '';
  }
  renderBackgrounds() {const select=this.shadowRoot.querySelector('#bg-image');if(!select)return;select.innerHTML='<option value="">Kein Bild</option>'+this.backgrounds.map((id,i)=>`<option value="${id}">Hintergrund ${i+1} · ${id.slice(0,6)}</option>`).join('');select.value=this.scene.image_id || '';}
  async uploadBackground(file) {
    if(!file||this.busy)return;
    if(file.size>5*1024*1024){this.flash('Das Bild darf höchstens 5 MiB groß sein.',true);return;}
    const entry=this.entryId,key=this.sceneKey,generation=this._generation;this.busy=true;this.updateStatus();
    try {const response=await this.hass.fetchWithAuth(`/api/lg_rs232_ip/layout_background/${entry}/upload`,{method:'POST',body:file});if(!response.ok)throw Error(await response.text());const data=await response.json();if(generation!==this._generation||entry!==this.entryId)return;
      if(!this.backgrounds.includes(data.image_id))this.backgrounds.push(data.image_id);if(this.imageUrls[data.image_id]===null)delete this.imageUrls[data.image_id];this.checkpoint();this.config.scenes[key].image_id=data.image_id;this.config.scenes[key].background='image';this.changed(true);this.flash('Bild vorbereitet. Speichern überträgt den Hintergrund auf das Display.');
    }catch(_){this.flash('Bild konnte nicht importiert werden. JPEG/PNG, bis 5 MiB/20 Megapixel; maximal 24 Bilder. Entferne bei Bedarf unbenutzte Bilder.',true);}finally{this.busy=false;this.updateStatus();const input=this.shadowRoot.querySelector('#bg-upload');if(input)input.value='';}
  }
  async cleanBackgrounds() {
    if(this.busy)return;this.busy=true;this.updateStatus();const entry=this.entryId,generation=this._generation;
    const used=new Set([this.config,this.saved,...this.history,...this.future].flatMap(config=>Object.values(config.scenes).map(scene=>scene.image_id)));
    try {for(const id of [...this.backgrounds])if(!used.has(id)){await this.hass.callApi('DELETE',`lg_rs232_ip/layout_background/${entry}/${id}`);if(generation!==this._generation||entry!==this.entryId)return;URL.revokeObjectURL(this.imageUrls[id] || '');delete this.imageUrls[id];this.backgrounds=this.backgrounds.filter(value=>value!==id);}this.renderBackgrounds();this.flash('Unbenutzte Bilder entfernt. Gespeicherte Szenen und Rückgängig-Schritte bleiben erhalten.');}catch(_){this.flash('Ein Bild wird inzwischen verwendet oder konnte nicht entfernt werden.',true);}finally{this.busy=false;this.updateStatus();}
  }
  async save() {
    if(this.busy)return;this.busy=true;this.updateStatus();
    const sent=clone(this.config);
    try {const result=await this.hass.callApi('POST',`lg_rs232_ip/layout/${this.entryId}`,{config:sent,revision:this.revision});this.revision=result.revision;this.saved=clone(result.config);this.dirty=JSON.stringify(this.config)!==JSON.stringify(sent);if(!this.dirty)this.config=clone(result.config);this.flash(this.config.enabled?'Gespeichert. Die verbundene App übernimmt das Layout automatisch.':'Gespeichert. Eigene Layouts sind derzeit ausgeschaltet.');}
    catch(error){this.flash(error?.status_code===409?'Eine andere Sitzung hat das Layout geändert. Exportiere deinen Entwurf und lade den Editor neu.':'Speichern fehlgeschlagen. Prüfe Entitäten, Feldwerte und Verbindung. Dein Entwurf bleibt erhalten.',true);}
    finally{this.busy=false;this.updateStatus();clearTimeout(this._dataSoon);this._dataSoon=setTimeout(()=>this.refreshValues(),2500);}
  }
  async importFile(file) {
    if(!file)return;
    try {
      if(file.size>131072)throw Error();const config=JSON.parse(await file.text());
      // Rendering imported CSS/text before server validation is deliberately avoided.
      const result=await this.hass.callApi('POST',`lg_rs232_ip/layout_validate`,{config});
      this.checkpoint();this.config=result.config;this.selected=null;this.changed(true);this.flash('Layout als Entwurf importiert.');
    }catch(_){this.flash('Keine gültige Layout-Datei. Verwende einen Export aus Display Studio (maximal 128 KiB).',true);}
    finally{this.shadowRoot.querySelector('.export').value='';}
  }
  flash(message,error=false) {const node=this.shadowRoot.querySelector('.flash');if(node){node.textContent=message;node.classList.toggle('error',error);}}
}
if(!customElements.get('lg-display-studio'))customElements.define('lg-display-studio',LGDisplayStudio);
