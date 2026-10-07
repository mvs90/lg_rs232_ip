/* Local Home Assistant layout editor. The LG only runs the small ES5 renderer. */
const VERSION = "2.29.0";
const clone = value => JSON.parse(JSON.stringify(value));
const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const THEME_FIELDS = ['background','color','accent','image_id','image_fit','image_dim','gradient_angle','media_background_enabled','media_background_entity','media_background_fit','media_background_color_source','media_background_dim'];
const themeStyle = scene => {const item=scene.elements.find(i=>i.kind!=='hdmi') || {};return {...Object.fromEntries(THEME_FIELDS.map(k=>[k,clone(scene[k])])),ink:item.color || '#f2f6fa',surface:item.background || '#122333',card_accent:item.accent_color || scene.accent};};
const applyThemeStyle = (scene,style,startup=false) => {for(const key of THEME_FIELDS)scene[key]=clone(style[key]);if(startup){if(scene.background==='solar')scene.background='dawn';scene.media_background_enabled=false;scene.media_background_entity='';}for(const item of scene.elements)if(item.kind!=='hdmi'){Object.assign(item,{color:style.ink,background:style.surface,accent_color:style.card_accent});for(const part of Object.values(item.parts || {}))delete part.color;}return scene;};
const SCENES = {signal:"Mit HDMI",no_signal:"Ohne HDMI",dashboard:"Dashboard",overlay:"Meldung · Overlay",pip:"Meldung · PiP",fullscreen:"Meldung · Vollbild",pip_view:"PiP",media_view:"Mediaplayer"};
const CONTEXTS = {hdmi_full:"Nur HDMI",dashboard:"Dashboard",pip_view:"Dashboard PiP",media_view:"Mediaplayer",startup:"Startanzeige",overlay:"Mitteilung",pip:"Mitteilung PiP",fullscreen:"Mitteilung Vollbild"};
const NOTIFICATION_CONTEXTS = ["overlay","pip","fullscreen"];
const SOURCE_CONTEXTS = ["hdmi_full","dashboard","pip_view","media_view"];
const KINDS = {hdmi:"HDMI / PiP",camera:"Kamera / Teststream",clock:"Uhr & Datum",weather:"Wetter",calendar:"Kalender",entity:"HA-Entität",status:"Statuskarte",media:"Medienplayer",text:"Text",message:"Meldungsfenster"};
const BACKGROUNDS = {solid:"Einfarbig",aurora:"Aurora",dawn:"Warmer Verlauf",ocean:"Ozean",sand:"Sand",midnight:"Mitternacht",solar:"Sonnenstand",gradient:"Eigener Verlauf",image:"Eigenes Bild"};
const icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4M5 6h7M5 9h4"/></svg>';
const options = (items, value) => Object.entries(items).map(([key,label]) => `<option value="${escapeHTML(key)}" ${key === value ? "selected" : ""}>${escapeHTML(label)}</option>`).join("");

class LGDisplayStudio extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this.sceneKey="signal"; this.selected=null;
    this.transitionMode="none"; this.dirty=false; this.busy=false; this.history=[]; this.future=[]; this._generation=0;
  }
  set hass(value) {
    this._hass=value;
    if (this.isConnected && !this.started) this.start();
    else if (this.renderer && !this._updateTimer) this._updateTimer=setTimeout(() => {this._updateTimer=null; if(this.isConnected) this.paint();},300);
  }
  get hass() {return this._hass;}
  connectedCallback() {if(this._hass && !this.started) this.start();}
  disconnectedCallback() {
    this.widgetEditor?.close();this._generation++; this.started=false;this.renderer?.clear();
    clearTimeout(this._updateTimer); this._updateTimer=null; clearInterval(this._clock);
    clearInterval(this._dataTimer); clearTimeout(this._dataSoon);
    this._resize?.disconnect(); this._resize=null;this.releaseImages();
  }
  async start() {
    this.started=true; const generation=++this._generation;
    this.shadowRoot.innerHTML=`<link rel="stylesheet" href="/lg_rs232_ip/studio.css?v=${VERSION}"><link rel="stylesheet" href="/lg_rs232_ip/layout.css?v=${VERSION}"><div class="empty">Display Studio wird geladen …</div>`;
    try {
      await Promise.all([import(`/lg_rs232_ip/weather.js?v=${VERSION}`),import(`/lg_rs232_ip/cards.js?v=${VERSION}`),import(`/lg_rs232_ip/layout-runtime.js?v=${VERSION}`)]);
      this.catalog=await this.hass.callApi("GET","lg_rs232_ip/layouts");
      if(generation!==this._generation || !this.isConnected) return;
      if(!this.catalog.entries.length) {this.shadowRoot.querySelector('.empty').textContent="Lege zuerst ein LG-Display in den Integrationseinstellungen an.";return;}
      this.entryId=this.entryId && this.catalog.entries.some(e=>e.entry_id===this.entryId) ? this.entryId : this.catalog.entries[0].entry_id;
      const doc=await this.hass.callApi("GET",`lg_rs232_ip/layout_library/${this.entryId}`);
      if(generation!==this._generation) return;
      this.accept(doc); this.page="overview"; this.mount();
    } catch(error) { if(generation===this._generation) this.shadowRoot.querySelector('.empty').textContent="Der Editor konnte nicht geladen werden. Bitte als Administrator anmelden und erneut öffnen."; }
  }
  accept(doc) {this.startupStatus=doc.startup_design;this.suggestions=[];this.suggestionArea="";this._suggestionRequest=(this._suggestionRequest || 0)+1;this.releaseImages();this.backgrounds=doc.backgrounds || [];this.backendSun=doc.sun;this.config=this.withViews(clone(doc.config));this.viewId=this.config.views[0]?.id;this.revision=doc.revision;this.saved=clone(this.config);this.backendValues=doc.values || {};this.timezone=doc.timezone || this.hass.config?.time_zone || "Europe/Berlin";this.dirty=false;this.selected=null;this.history=[];this.future=[];}
  mount() {
    this.widgetEditor?.close();this.renderer?.clear();clearInterval(this._clock);clearInterval(this._dataTimer);this._resize?.disconnect();
    this.shadowRoot.innerHTML=`<link rel="stylesheet" href="/lg_rs232_ip/studio.css?v=${VERSION}"><link rel="stylesheet" href="/lg_rs232_ip/layout.css?v=${VERSION}">
      <header><button class="menu" aria-label="Seitenleiste öffnen">☰</button><div class="logo">${icon}</div><div><h1>Display Studio</h1><p>Dein Zuhause. Auf deinem Bildschirm.</p></div><div class="spacer"></div><select class="device" aria-label="Display">${this.catalog.entries.map(e=>`<option value="${escapeHTML(e.entry_id)}" ${e.entry_id===this.entryId?'selected':''}>${escapeHTML(e.name)}</option>`).join("")}</select><div class="toolbar"><span class="status" role="status"></span><button class="secondary" data-action="undo" title="Rückgängig">↶</button><button class="secondary" data-action="redo" title="Wiederholen">↷</button><button class="primary" data-action="save">Speichern</button></div></header>
      <div class="notice" hidden></div><div class="overview"><div class="gallery-heading"><div><p class="eyebrow">DEINE ANSICHTEN</p><h2>Ein Platz für jeden Moment.</h2><p>Gespeicherte Designs für Fernsehen, Alltag und Meldungen.</p></div><button class="primary" data-action="new-view">＋ Neue Ansicht</button></div><div class="gallery-flash" role="status"></div><section class="view-creator" hidden></section><section class="primary-views" aria-labelledby="views-heading"><h2 id="views-heading">Ansichten</h2><div class="view-gallery primary-gallery"></div></section><section class="notification-views" aria-labelledby="notifications-heading"><h2 id="notifications-heading">Mitteilungen</h2><p>Gestalte Überblendungen, PiP- und Vollbildmeldungen unabhängig von deinen Ansichten.</p><div class="view-gallery notification-gallery"></div></section><section class="template-gallery"><div class="gallery-heading"><div><h2>Themes & Hintergründe</h2><p>Ein gemeinsamer Stil für alle Ansichten. Eigene Abweichungen bleiben erhalten.</p></div><button class="small" data-action="new-theme">＋ Neues Theme</button></div><p class="theme-manager-status"></p><button class="small" data-action="all-follow-theme">Alle Ansichten dem Standard folgen lassen</button><div class="template-options"></div></section></div><div class="editor-navigation"><button class="secondary" data-action="overview">← Alle Ansichten</button><label><span id="editor-name-label">Name der Ansicht</span><input id="view-name" maxlength="80"></label><span class="view-usage"></span><button class="small" data-action="theme-follow">Theme-Standard wiederherstellen</button><button class="small" data-action="theme-use">Als Standard für alle Ansichten</button><label class="theme-id-field" hidden>Theme-ID für Automationen<input id="theme-id" readonly></label><button class="small" data-action="reset-view">Standard wiederherstellen</button><nav class="context-tabs" aria-label="Ansichten">${Object.entries(CONTEXTS).map(([key,label])=>`<button class="tab" data-context="${key}">${label}</button>`).join("")}</nav></div><div class="workspace"><aside class="sidebar"><section class="cover-background-tools"><h3>Coverfarben & Hintergrund</h3><label class="field"><input id="media-background-enabled" type="checkbox">Bei Wiedergabe anzeigen</label><label class="field">Hintergrund-Medienplayer<select id="media-background-entity"></select></label><label class="field">Cover darstellen<select id="media-background-fit">${options({colors:'Nur Coverfarben · ohne Bild',stretch:'Gestreckt · ganze Fläche',contain:'Skaliert · vollständig einpassen',center:'Mittig · ohne Vergrößern'},this.scene.media_background_fit || 'contain')}</select></label><label class="field">Farben für den Hintergrund<select id="media-background-color-source">${options({edges:"Coverränder",cover:"Gesamtes Cover"},this.scene.media_background_color_source || "edges")}</select></label><label class="field">Cover und Farbverlauf abdunkeln<input id="media-background-dim" type="range" min="0" max="0.9" step="0.05"></label><p class="note">Nur während der Wiedergabe. Wähle, ob die Coverränder oder die gesamte Bildfläche die Farben des Verlaufs bestimmen. Die Randerkennung überspringt schwarze Außenstreifen bis zum Bildinhalt. „Nur Coverfarben“ blendet das Hintergrundbild aus. Bei Pause, Stopp oder fehlendem Cover erscheint der normale Hintergrund. Der Player ist unabhängig von den Karten wählbar.</p></section><h2>Farbthemes</h2><div class="presets">${this.catalog.presets.map(p=>`<button class="preset theme" data-theme="${escapeHTML(p.id)}"><div class="mini" data-mini="${escapeHTML(p.id)}"></div><strong>${escapeHTML(p.name)}</strong></button>`).join("")}</div><p class="note">Ändert nur Farben und Hintergrund. Inhalte, Entitäten und Anordnung bleiben erhalten.</p><div class="form-grid theme-palette"><label>Textfarbe<input type="color" id="theme-ink"></label><label>Kartenfarbe<input type="color" id="theme-surface"></label><label class="full">Kartenakzent<input type="color" id="theme-accent"></label></div><h3>Hintergrund anpassen</h3><div class="form-grid"><label class="full">Hintergrund<select id="background" aria-label="Hintergrund">${options(BACKGROUNDS,this.scene.background)}</select></label><label>Grundfarbe<input id="scene-color" type="color"></label><label>Akzent<input id="scene-accent" type="color"></label></div><label class="field">Verlaufswinkel<input id="gradient-angle" type="range" min="0" max="360" step="1"></label><label class="field">Sonnenstand-Entität<input id="sun-entity" list="sun-entities" placeholder="sun.sun"><datalist id="sun-entities">${Object.keys(this.hass.states).filter(id=>id.startsWith('sun.')).map(id=>`<option value="${escapeHTML(id)}"></option>`).join('')}</datalist></label><div class="background-tools"><label class="field">Eigenes Hintergrundbild<select id="bg-image"></select></label><label class="field">Bild einpassen<select id="image-fit">${options({cover:'Ausfüllen',contain:'Vollständig zeigen'},this.scene.image_fit)}</select></label><label class="field">Bild abdunkeln<input id="image-dim" type="range" min="0" max="0.9" step="0.05"></label><input id="bg-upload" class="export" type="file" accept="image/jpeg,image/png"><button class="small" data-action="upload-background">Bild hochladen</button><button class="small" data-action="clean-backgrounds">Unbenutzte Bilder entfernen</button><p class="note">JPEG/PNG, bis 5 MiB. Lokal auf maximal 3840 × 2160 verkleinert. Erst Speichern ändert das Display.</p></div></aside>
      <main class="main"><p class="context-hint"></p><p class="startup-cache-status note" role="status" hidden></p><div class="output-controls">${this.transitionSelect("Übergang beim Anzeigen")}<button class="secondary" data-action="hdmi-view">Nur HDMI anzeigen</button><button class="secondary" data-action="dashboard">Dashboard anzeigen</button><button class="secondary" data-action="pip-view">Dashboard PiP anzeigen</button><button class="secondary" data-action="media-view">Mediaplayer anzeigen</button><button class="secondary" data-action="current-view">Ansicht anzeigen</button><div class="toggle"><label><input type="checkbox" id="enabled">Eigenes Layout verwenden</label></div><div class="links"><button class="small" data-action="export">Exportieren</button><button class="small" data-action="import">Importieren</button><input id="layout-import" class="export" type="file" accept="application/json,.json"></div></div><div class="preview-label"><span id="scene-title"></span><span>16:9 · HDMI-Platzhalter · Live-Entitäten</span></div><div class="frame"><div class="stage"><div class="scene"><div class="lg-hdmi-placeholder">HDMI</div></div><div class="selection-layer"></div></div></div><p class="hint">Element anklicken und ziehen · Größe über die Ecke ändern · Pfeiltasten: 1 %, mit Umschalt: 0,1 %</p><div class="flash" aria-live="polite"></div><details class="automation-help"><summary>Ansicht in Automationen verwenden</summary><label class="field">Ansichts-ID<input id="automation-view-id" readonly></label><p class="note">Unter Einstellungen → Automatisierungen &amp; Szenen → Blaupausen die Vorlage „LG Display · Ereignisansicht mit automatischer Rückkehr“ wählen. Auslöser, diese ID und Anzeigedauer eintragen. Manuelle Bedienung beendet die automatische Rückkehr. Die Aktion <code>lg_rs232_ip.show_view</code> unterstützt außerdem <code>theme</code>: Hier eine Theme-ID aus der Übersicht eintragen, um beim Anzeigen auch das globale Theme zu wählen. Individuelle Abweichungen bleiben erhalten; die Anzeigedauer setzt das Theme nicht zurück.</p></details><section class="message-test"><h2>Meldung ausprobieren</h2><textarea id="test-message" aria-label="Testnachricht">Die Waschmaschine ist fertig.</textarea><div class="row"><select id="test-layout" aria-label="Nachrichtenlayout">${options({overlay:"Overlay",pip:"PiP",fullscreen:"Vollbild"},'overlay')}</select><button class="secondary" data-action="test">10 Sekunden anzeigen</button></div><p class="note">Verwendet das gespeicherte Layout. Für die Anzeige muss die App verbunden sein.</p></section><details class="room-suggestions" open><summary>Karten aus deinem Raum</summary><label>Raum für Kartenvorschläge<select id="suggestion-room"><option value="">Raum wählen</option></select></label><button class="small" data-action="suggestions">Vorschläge aktualisieren</button><p class="note room-hint"></p><div class="suggestions"></div></details></main><aside class="inspector"><section class="section"><h3>Elemente · vorne zuerst</h3><div class="layers"></div><div class="add"><select aria-label="Elementtyp" id="new-kind">${options(KINDS,'entity')}</select><button class="small" data-action="add">＋</button></div></section><section class="properties"></section></aside></div>`;
    const $=selector=>this.shadowRoot.querySelector(selector);
    $('.menu').onclick=()=>this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true}));
    $('.device').onchange=event=>this.switchDisplay(event.target.value);
    this.shadowRoot.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>this.action(button.dataset.action));
    this.shadowRoot.querySelectorAll('[data-theme]').forEach(button=>{
      const preset=this.catalog.presets.find(p=>p.id===button.dataset.theme);button.querySelector('.mini').style.background=window.LGLayoutBackground(preset.layout.scenes.dashboard,{sun:this.sun()});
      button.onclick=()=>this.applyTheme(preset);
    });
    this.shadowRoot.querySelectorAll('[data-context]').forEach(button=>button.onclick=()=>this.openContext(button.dataset.context));
    for(const [id,key] of [['theme-ink','color'],['theme-surface','background'],['theme-accent','accent_color']]) $('#'+id).onchange=event=>{this.checkpoint();this.markThemeOverride();if(this.themeEditing)this.theme.style[{color:'ink',background:'surface',accent_color:'card_accent'}[key]]=event.target.value;for(const item of this.scene.elements)if(item.kind!=='hdmi')item[key]=event.target.value;this.changed(true);};
    $('#view-name').onchange=event=>{const name=event.target.value.trim();if(this.themeEditing){if(name){this.checkpoint();this.theme.name=name;this.changed();}return;}if(CONTEXTS[this.viewId] || !name){event.target.value=this.view.name;return;}this.checkpoint();this.view.name=name;this.changed();};
    $('#suggestion-room').onchange=event=>this.loadSuggestions(event.target.value);
    this.loadSuggestions();
    $('#bg-upload').onchange=event=>this.uploadBackground(event.target.files[0]);
    $('#sun-entity').onchange=event=>{this.checkpoint();this.config.sun_entity=event.target.value;this.changed();};
    $('#enabled').onchange=event=>{this.checkpoint();this.config.enabled=event.target.checked;this.changed();};
    for(const [id,key] of [['background','background'],['scene-color','color'],['scene-accent','accent'],['gradient-angle','gradient_angle'],['bg-image','image_id'],['image-fit','image_fit'],['image-dim','image_dim']]) $("#"+id).onchange=event=>{this.checkpoint();this.markThemeOverride();this.scene[key]=['gradient_angle','image_dim'].includes(key)?Number(event.target.value):event.target.value;this.changed();};
    $('#media-background-enabled').onchange=event=>{this.checkpoint();this.markThemeOverride();this.scene.media_background_enabled=event.target.checked;this.changed();};
    for(const [id,key] of [['media-background-entity','media_background_entity'],['media-background-fit','media_background_fit'],['media-background-color-source','media_background_color_source'],['media-background-dim','media_background_dim']]) $('#'+id).onchange=event=>{this.checkpoint();this.markThemeOverride();this.scene[key]=key==='media_background_dim'?Number(event.target.value):event.target.value;this.changed();};
    $('#layout-import').onchange=event=>this.importFile(event.target.files[0]);
    $('#test-message').oninput=()=>this.paint();
    this.renderer=new window.LGLayoutRenderer($('.scene'),$('.lg-hdmi-placeholder'),true);
    this._resize=new ResizeObserver(()=>this.paint());this._resize.observe($('.stage'));
    this._clock=setInterval(()=>{if(this.page!=="overview")this.renderer?.tick(new Date());this.widgetEditor?.tick(new Date());},1000);
    this._dataTimer=setInterval(()=>this.refreshValues(),30000);
    this.refreshScene();this.updateStatus();this.renderOverview();this.showPage();
  }
  get view() {return this.config.views.find(view=>view.id===this.viewId);}
  get scene() {return this.themeEditing ? this.themeScene : this.view?.scene || this.config.scenes[this.sceneKey];}
  get themeEditing() {return this.page==='theme';}
  get theme() {return this.config.themes.find(theme=>theme.id===this.themeId);}
  markThemeOverride() {if(!this.themeEditing && this.view)this.view.theme_override=true;}
  get startupView() {return !this.themeEditing && this.viewId==='startup';}
  get availableKinds() {return this.startupView ? {text:KINDS.text,clock:KINDS.clock} : KINDS;}
  get availableBackgrounds() {return this.startupView ? Object.fromEntries(Object.entries(BACKGROUNDS).filter(([id])=>id!=='solar')) : BACKGROUNDS;}
  get item() {return this.scene.elements.find(item=>item.id===this.selected);}
  checkpoint() {this.history.push(clone(this.config));if(this.history.length>30)this.history.shift();this.future=[];}
  changed(refresh=false) {this.compileViews();this.dirty=JSON.stringify(this.config)!==JSON.stringify(this.saved);if(refresh)this.refreshScene();else {this.paint();this.renderSelection();}this.renderSuggestions();this.updateStatus();if(this.page==="overview")this.renderOverview();}
  updateStatus() {
    const root=this.shadowRoot, status=root.querySelector('.status');if(!status)return;
    status.textContent=this.busy?'Wird gespeichert …':this.dirty?'Ungespeichert':'Gespeichert';status.dataset.dirty=String(this.dirty);
    root.querySelector('[data-action=save]').disabled=this.busy;
    root.querySelector('.device').disabled=this.busy;
    root.querySelector('[data-action=undo]').disabled=this.busy || !this.history.length;
    root.querySelector('[data-action=redo]').disabled=this.busy || !this.future.length;
    for(const action of ['hdmi-view','dashboard','pip-view','media-view'])root.querySelector('[data-action='+action+']').disabled=this.busy || !this.saved.enabled;
    root.querySelector('#enabled').checked=this.config.enabled;
    const reset=root.querySelector('[data-action=reset-view]');reset.hidden=this.themeEditing || !CONTEXTS[this.viewId];reset.disabled=this.busy;
    const current=root.querySelector('[data-action=current-view]');current.hidden=!!CONTEXTS[this.viewId];current.disabled=this.busy || !this.saved.enabled || !this.saved.views.some(v=>v.id===this.viewId);
    this.updateStartupStatus();this.updateThemeControls();
    const entry=this.catalog.entries.find(e=>e.entry_id===this.entryId), notice=root.querySelector('.notice');
    notice.hidden=!!entry?.resident_enabled;
    notice.innerHTML=entry?.resident_enabled?'':'Für dauerhafte Ansichten aktiviere <b>Display-App</b> und <b>SI-Dauerbetrieb</b> in den <a href="/config/integrations/integration/lg_rs232_ip">LG-Einstellungen</a>. Hier kannst du das Layout schon vorbereiten.';
  }
  updateStartupStatus() {
    const node=this.shadowRoot.querySelector('.startup-cache-status');if(!node)return;node.hidden=!this.startupView;
    const changed=this.startupView && JSON.stringify(this.scene)!==JSON.stringify(this.saved.views.find(v=>v.id==='startup')?.scene);
    node.textContent=this.startupStatus?.external ? 'Die Gestaltung wurde in einer anderen Sitzung geändert. Lade das Studio neu, um sie zu sehen.' : changed ? 'Entwurf noch nicht gespeichert.' : this.startupStatus?.stored ? 'Auf dem Display gespeichert · auch das gewählte Hintergrundbild ist lokal verfügbar.' : this.startupStatus?.connected ? 'Übertragung auf das Display ausstehend · Bestätigung wird automatisch aktualisiert.' : 'Die App ist nicht verbunden. Die Gestaltung wird beim nächsten Verbinden auf dem Display gespeichert.';
  }
  async switchDisplay(entryId) {
    if(this.busy)return;
    if(this.dirty) {this.flash('Speichere deinen Entwurf oder mache die Änderungen rückgängig, bevor du das Display wechselst.',true);this.shadowRoot.querySelector('.device').value=this.entryId;return;}
    try {const doc=await this.hass.callApi('GET',`lg_rs232_ip/layout_library/${entryId}`);this.entryId=entryId;this.accept(doc);this.page="overview";this.mount();} catch(_) {this.flash('Display konnte nicht geladen werden.',true);}
  }
  refreshScene() {
    const root=this.shadowRoot;root.querySelectorAll('[data-scene]').forEach(tab=>tab.setAttribute('aria-selected',String(tab.dataset.scene===this.sceneKey)));
    root.querySelector('#scene-title').textContent=this.view?.name || SCENES[this.sceneKey];root.querySelector('#view-name').value=this.view?.name || '';root.querySelector('.view-usage').textContent=this.usage(this.viewId);root.querySelector('#background').innerHTML=options(this.availableBackgrounds,this.scene.background);root.querySelector('#scene-color').value=this.scene.color;root.querySelector('#scene-accent').value=this.scene.accent;root.querySelector('#gradient-angle').value=this.scene.gradient_angle;root.querySelector('#sun-entity').value=this.config.sun_entity;root.querySelector('#image-fit').value=this.scene.image_fit;root.querySelector('#image-dim').value=this.scene.image_dim;this.renderBackgrounds();
    root.querySelector('#media-background-enabled').checked=!!this.scene.media_background_enabled;
    const players=Object.fromEntries(Object.entries(this.hass.states).filter(([id])=>id.startsWith('media_player.')).sort((a,b)=>(a[1].attributes.friendly_name || a[0]).localeCompare(b[1].attributes.friendly_name || b[0])).map(([id,state])=>[id,(state.attributes.friendly_name || id)+' · '+id]));
    const bound=this.scene.media_background_entity || '';if(bound&&!players[bound])players[bound]=bound+' · Nicht verfügbar';
    root.querySelector('#media-background-entity').innerHTML=options({'':'Medienplayer wählen',...players},bound);
    root.querySelector('#media-background-fit').value=this.scene.media_background_fit || 'contain';
    root.querySelector('#media-background-color-source').value=this.scene.media_background_color_source || 'edges';
    root.querySelector('#media-background-dim').value=this.scene.media_background_dim ?? .35;
    const palette=this.themeEditing?{color:this.theme.style.ink,background:this.theme.style.surface,accent_color:this.theme.style.card_accent}:this.scene.elements.find(i=>i.kind!=='hdmi');root.querySelector('#theme-ink').value=palette?.color || '#f2f6fa';root.querySelector('#theme-surface').value=palette?.background || '#142335';root.querySelector('#theme-accent').value=palette?.accent_color || this.scene.accent;
    root.querySelectorAll('[data-context]').forEach(b=>b.setAttribute('aria-current',String(b.dataset.context===this.viewId)));
    root.querySelector('.context-hint').textContent=this.viewId==='hdmi_full' ? 'Gemeinsame Ansicht für HDMI 1, 2 und 3. Standard: HDMI im Vollbild. Änderungen werden erst nach dem Speichern auf dem Display angezeigt.' : 'Diese Ansicht gestalten. Die Buttons oben öffnen die festen Ansichten; die Wiedergabe bleibt unverändert.';
    root.querySelector('#view-name').disabled=!!CONTEXTS[this.viewId];
    root.querySelector("#automation-view-id").value=this.viewId;root.querySelector(".automation-help").hidden=NOTIFICATION_CONTEXTS.includes(this.viewId);
    root.querySelector('#new-kind').innerHTML=options(this.availableKinds,this.startupView?'text':'entity');
    for(const selector of ['.cover-background-tools','.room-suggestions','.message-test','.automation-help'])root.querySelector(selector).hidden=this.startupView || (selector==='.automation-help' && NOTIFICATION_CONTEXTS.includes(this.viewId));
    root.querySelector('#sun-entity').closest('label').hidden=this.startupView;
    root.querySelector('.toggle').hidden=this.startupView;
    root.querySelectorAll('.output-controls > .display-transition,.output-controls > button').forEach(node=>node.hidden=this.startupView);
    root.querySelector('.preview-label span:last-child').textContent=this.startupView ? '16:9 · ausschließlich lokale Inhalte' : '16:9 · HDMI-Platzhalter · Live-Entitäten';
    if(this.startupView)root.querySelector('.context-hint').textContent='Gestalte die Anzeige während des App-Starts. Erlaubt sind Texte, lokale Uhr/Datum, Farben, Verläufe und gespeicherte Bilder. Bei HDMI-Vollbild bleibt sie ausgeblendet.';
    this.updateThemeControls();this.paint();this.renderLayers();this.renderSelection();this.renderProperties();this.renderSuggestions();
  }
  values() {
    const result=clone(this.backendValues || {});
    const backgroundPlayer=this.scene.media_background_enabled ? this.scene.media_background_entity : '';
    const backgroundState=this.hass.states[backgroundPlayer];
    if(backgroundPlayer)result[backgroundPlayer]=backgroundState ? {state:backgroundState.state,...this.cardData(backgroundState)} : {state:'unavailable'};
    for(const scene of [this.scene]) for(const item of scene.elements) {
      const state=this.hass.states[item.entity_id];if(!state)continue;
      const attrs=state.attributes;result[item.entity_id]={...result[item.entity_id],state:state.state,name:attrs.friendly_name || item.entity_id,unit:attrs.unit_of_measurement || ''};
      if(['media','status'].includes(item.kind))Object.assign(result[item.entity_id],this.cardData(state));
      if(item.kind==='weather') for(const key of ['temperature','temperature_unit','humidity','wind_speed','wind_speed_unit'])result[item.entity_id][key]=String(attrs[key] ?? '');
      if(item.kind==='calendar' && !result[item.entity_id].events)result[item.entity_id].events=attrs.message?[{summary:attrs.message,start:attrs.start_time,end:attrs.end_time}]:[];
    }
    return result;
  }
  sun() {const id=this.config.sun_entity,state=this.hass.states[id];if(!id || state && !['above_horizon','below_horizon'].includes(state.state))return null;if(id==='sun.sun' && id===this.saved.sun_entity && this.backendSun)return this.backendSun;return state ? {is_daytime:state.state==='above_horizon',elevation:state.attributes.elevation,azimuth:state.attributes.azimuth,rising:state.attributes.rising} : id===this.saved.sun_entity ? this.backendSun : null;}
  paint() {if(this.page==="overview"){this.paintGallery();return;}if(this.renderer && this.config)this.renderer.render(this.scene,this.values(),{timezone:this.timezone,sun:this.sun(),mediaUrl:(id,key,size)=>this.mediaUrl(id,key,size),imageUrl:id=>this.imageUrl(id),now:new Date(),message:{title:'Home Assistant',message:this.shadowRoot.querySelector('#test-message')?.value || 'Deine Benachrichtigung erscheint hier.'}});this.widgetEditor?.paint();}
  async refreshValues() {
    if(this._dataBusy || !this.isConnected)return;
    this._dataBusy=true;const id=this.entryId,generation=this._generation;
    try {const doc=await this.hass.callApi('GET',`lg_rs232_ip/layout/${id}`);if(this.isConnected && this.entryId===id && generation===this._generation && doc.revision>=this.revision){this.backendValues=doc.values || {};this.backendSun=doc.sun;this.startupStatus={...doc.startup_design,external:doc.revision>this.revision};this.updateStartupStatus();this.paint();}}
    catch(_){}finally{this._dataBusy=false;}
  }
  renderLayers() {
    const container=this.shadowRoot.querySelector('.layers');container.innerHTML=[...this.scene.elements].reverse().map(item=>`<div class="layer ${item.id===this.selected?'active':''}"><button class="name" data-select="${escapeHTML(item.id)}">${escapeHTML(item.label || KINDS[item.kind])}</button><button class="icon widget-edit" data-edit-widget="${escapeHTML(item.id)}" aria-label="${escapeHTML(item.label || KINDS[item.kind])} Inhalt bearbeiten" title="Inhalt bearbeiten">✎</button><button class="icon" data-up="${escapeHTML(item.id)}" title="Nach vorne">↑</button><button class="icon" data-down="${escapeHTML(item.id)}" title="Nach hinten">↓</button><button class="icon delete" data-delete="${escapeHTML(item.id)}" aria-label="${escapeHTML(item.label || KINDS[item.kind])} entfernen">×</button></div>`).join('');
    container.querySelectorAll('[data-edit-widget]').forEach(button=>button.onclick=()=>this.editWidget(button.dataset.editWidget));
    container.querySelectorAll('[data-delete]').forEach(button=>button.onclick=()=>this.removeItem(button.dataset.delete));
    container.querySelectorAll('[data-select]').forEach(button=>button.onclick=()=>this.select(button.dataset.select));
    for(const direction of ['up','down'])container.querySelectorAll(`[data-${direction}]`).forEach(button=>button.onclick=()=>{const id=button.dataset[direction],i=this.scene.elements.findIndex(item=>item.id===id),j=i+(direction==='up'?1:-1);if(j<0||j>=this.scene.elements.length)return;this.checkpoint();[this.scene.elements[i],this.scene.elements[j]]=[this.scene.elements[j],this.scene.elements[i]];this.changed(true);});
  }
  editWidget(id) {if(this.themeEditing)return;this.widgetEditor?.close();this.select(id);this.widgetEditor=new LGWidgetEditor(this,id);}
  select(id) {this.selected=id;this.renderLayers();this.renderSelection();this.renderProperties();this.renderSuggestions();}
  renderSelection() {
    const container=this.shadowRoot.querySelector('.selection-layer');container.innerHTML='';
    for(const item of this.scene.elements) {
      const node=document.createElement('div');node.className='selection'+(item.id===this.selected?' selected':'');node.tabIndex=0;node.setAttribute('role','button');node.setAttribute('aria-label',`${item.label || KINDS[item.kind]} verschieben`);node.dataset.id=item.id;
      Object.assign(node.style,{left:item.x+'%',top:item.y+'%',width:item.width+'%',height:item.height+'%'});
      const tag=document.createElement('span');tag.className='tag';tag.textContent=item.label || KINDS[item.kind];node.append(tag);const edit=document.createElement('button');edit.className='widget-edit';edit.textContent='✎';edit.title='Inhalt bearbeiten';edit.setAttribute('aria-label',(item.label || KINDS[item.kind])+' Inhalt öffnen');tag.append(edit);edit.onpointerdown=e=>e.stopPropagation();edit.onkeydown=e=>e.stopPropagation();edit.onclick=e=>{e.stopPropagation();this.editWidget(item.id);};
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
    if(!item){root.innerHTML='<h2>Dein Layout, dein Platz</h2><p class="empty">Wähle ein Element in der Vorschau oder füge eines hinzu. Position, Größe und Gestaltung lassen sich frei anpassen.</p>';return;}
    const field=(key,label,min,max,step=1)=>`<label>${label}<input type="number" data-prop="${key}" min="${min}" max="${max}" step="${step}" value="${item[key] ?? (key==='camera_interval'?2:'')}"></label>`;
    let binding='';if(['entity','status','media','weather','calendar','camera'].includes(item.kind)){
      const states=Object.values(this.hass.states).filter(s=>['entity','status'].includes(item.kind)||s.entity_id.startsWith((item.kind==='media'?'media_player':item.kind)+'.')).sort((a,b)=>(a.attributes.friendly_name||a.entity_id).localeCompare(b.attributes.friendly_name||b.entity_id));
      binding=`<label class="field">Home-Assistant-Entität<input list="entity-options" data-prop="entity_id" value="${escapeHTML(item.entity_id)}" placeholder="${['entity','status'].includes(item.kind)?'sensor.wohnzimmer':(item.kind==='media'?'media_player':item.kind)+'.…'}"><datalist id="entity-options">${states.map(s=>`<option value="${escapeHTML(s.entity_id)}">${escapeHTML(s.attributes.friendly_name||s.entity_id)}</option>`).join('')}</datalist></label>`;
    }
    root.innerHTML=`<h2 class="widget-property-title">${escapeHTML(KINDS[item.kind])}<button class="icon" data-widget-edit aria-label="Widget-Inhalt bearbeiten">✎</button></h2><label class="field">Widget-Typ<select data-kind>${options(this.availableKinds,item.kind)}</select></label><div class="form-grid">${field('x','Links (%)',0,98,.1)}${field('y','Oben (%)',0,98,.1)}${field('width','Breite (%)',2,100,.1)}${field('height','Höhe (%)',2,100,.1)}</div>${item.kind==='hdmi'?'<p class="hint">Das HDMI-Bild wird unverzerrt in dieses Rechteck eingepasst. Pro Szene ist ein HDMI-Bild möglich.</p>':`<h3>Inhalt</h3><label class="field">Beschriftung<input data-prop="label" value="${escapeHTML(item.label)}" maxlength="100"></label>${binding}${item.kind==='camera'?`<label class="field">Kameraquelle<select data-prop="camera_source">${options({test:'Lokaler HLS-Teststream',entity:'Home-Assistant-Kamera',multicast:'UDP-Multicast · lokales Netz'},item.camera_source || 'test')}</select></label><label class="field">Multicast-Adresse<input data-prop="multicast_url" value="${escapeHTML(item.multicast_url || '')}" placeholder="udp://239.1.2.3:5000" maxlength="80"></label><label class="field">Wiedergabe<select aria-label="Wiedergabe" data-prop="camera_mode">${options({auto:'Automatisch · Stream / Einzelbilder',stream:'Nur HLS-Stream',snapshot:'Nur Einzelbilder'},item.camera_mode || 'auto')}</select></label><label class="field">Bildformat<select data-prop="camera_fit">${options({contain:'Vollständig einpassen',cover:'Fläche füllen'},item.camera_fit || 'contain')}</select></label>${field('camera_interval','Einzelbild-Abstand (s)',1,30,1)}<p class="hint">Live-Video braucht einen eigenen Bereich neben HDMI. Bei Überlappung verwendet „Automatisch“ Einzelbilder einer HA-Kamera. Multicast: H.264/MPEG-TS auf einer 239.x.x.x-Gruppe; das Netzwerk muss Multicast weiterleiten. Wiedergabemodus und Einzelbild-Abstand gelten nur für HA-Kameras. Ein zusätzlicher Stream pro Ansicht. Wiedergabe stumm; HDMI-Ton bleibt erhalten. Die Vorschau startet keine Kamera. Die LG-Vorschaukamera ist als Quelle gesperrt.</p>`:''}${item.kind==='text'?`<label class="field">Text<textarea aria-label="Text" data-prop="text" maxlength="2000">${escapeHTML(item.text)}</textarea></label>`:''}${item.kind==='media'?`<label class="field">Mediengestaltung<select data-prop="media_style">${options({compact:'Cover neben Text',poster:'Großes Cover',stage:'Vollbild · Cover & Titel'},item.media_style || 'compact')}</select></label>${[['show_cover','Cover anzeigen'],['show_progress','Fortschritt anzeigen'],['show_playback_icon','Play-/Pause-Symbol anzeigen'],['show_volume','Lautstärke anzeigen']].map(([key,label])=>`<div class="toggle"><label><input type="checkbox" data-prop="${key}" ${(key==='show_playback_icon'?item[key]===true:item[key]!==false)?'checked':''}>${label}</label></div>`).join('')}`:''}${['media','status'].includes(item.kind)?`<label class="field">Akzentfarbe<input type="color" data-prop="accent_color" value="${item.accent_color || '#79e5c0'}"></label>`:''}${item.kind==='status'?`<div class="toggle"><label><input type="checkbox" data-prop="status_coloring" ${item.status_coloring!==false?'checked':''}>Status farblich hervorheben</label></div>`:''}${item.kind==='weather'?`<label class="field">Wetteransicht<select data-prop="forecast_type">${options({current:'Nur aktuell',daily:'Tagesvorschau',hourly:'Stundenvorschau'},item.forecast_type)}</select></label><div class="form-grid">${field('forecast_count','Prognoseabschnitte',1,8)}<label>Gestaltung<select data-prop="weather_style">${options({glass:'Karte',sky:'Himmel nach Sonnenstand',minimal:'Transparent'},item.weather_style)}</select></label></div><div class="toggle"><label><input type="checkbox" data-prop="animate" ${item.animate?'checked':''}>Aktuelles Wettersymbol animieren</label></div>`:''}<div class="toggle"><label><input type="checkbox" data-prop="show_label" ${item.show_label?'checked':''}>Beschriftung anzeigen</label></div><h3>Aussehen</h3><div class="form-grid">${field('font_size','Schriftgröße (% Höhe)',1,18,.1)}${field('radius','Rundung',0,80)}<label>Textfarbe<input type="color" data-prop="color" value="${item.color}"></label><label>Flächenfarbe<input type="color" data-prop="background" value="${item.background}"></label>${field('opacity','Deckkraft',0,1,.05)}<label>Ausrichtung<select data-prop="align">${options({left:'Links',center:'Mittig',right:'Rechts'},item.align)}</select></label><label class="full">Schrift<select data-prop="font">${options({sans:'Klar · Sans Serif',serif:'Editorial · Serif',mono:'Technisch · Monospace'},item.font)}</select></label></div>`}<div class="links"><button class="small delete" data-remove>Element entfernen</button></div>`;
    root.querySelector('[data-widget-edit]').onclick=()=>this.editWidget(item.id);
    root.querySelector('[data-remove]').onclick=()=>this.removeItem(item.id);
    root.querySelector('[data-kind]').onchange=event=>{
      const item=this.item;if(!item)return;
      const kind=event.target.value;
      if(!this.availableKinds[kind]){event.target.value=item.kind;return;}
      if(['hdmi','message','camera'].includes(kind) && this.scene.elements.some(other=>other!==item && other.kind===kind)){event.target.value=item.kind;this.flash('Dieser Typ ist in der Szene bereits vorhanden.',true);return;}
      this.checkpoint();if(item.label===KINDS[item.kind])item.label=KINDS[kind];item.kind=kind;delete item.parts;delete item.clock_date_format;delete item.clock_time_format;
      if(!['entity','status','media','weather','calendar','camera'].includes(kind)||(['media','weather','calendar','camera'].includes(kind)&&!item.entity_id.startsWith((kind==='media'?'media_player':kind)+'.')))item.entity_id='';
      this.changed(true);
    };
    root.querySelectorAll('[data-prop]').forEach(input=>input.onchange=()=>{
      const item=this.item;if(!item)return;
      this.checkpoint();const key=input.dataset.prop;let value=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;
      if(input.type==='number')value=Math.max(Number(input.min),Math.min(Number(input.max),Number.isFinite(value)?value:Number(input.min)));
      if(['color','background','accent_color'].includes(key))this.markThemeOverride();
      item[key]=value;
      if(key==='x')item.x=Math.min(item.x,100-item.width);if(key==='y')item.y=Math.min(item.y,100-item.height);
      if(key==='width')item.width=Math.min(item.width,100-item.x);if(key==='height')item.height=Math.min(item.height,100-item.y);
      input.value=item[key];this.changed();this.renderLayers();
    });
  }
  async action(action) {
    if(action==='new-theme')return this.duplicateTheme(this.config.active_theme || 'cinema');
    if(action==='theme-follow')return this.followTheme(this.viewId);
    if(action==='theme-use')return this.useTheme(this.themeId);
    if(action==='all-follow-theme')return this.useTheme(this.config.active_theme || 'cinema',true);
    if(action==='new-view')return this.showCreator();
    if(action==='overview'){this.page="overview";this.renderOverview();this.showPage();return;}
    if(action==='save')return this.save();
    if(action==='suggestions')return this.loadSuggestions(this.shadowRoot.querySelector('#suggestion-room').value);
    if(action==='undo' && this.history.length){this.future.push(clone(this.config));this.config=this.history.pop();this.selected=null;this.ensureView();this.changed(true);this.flash('Änderung zurückgenommen.');}
    if(action==='redo' && this.future.length){this.history.push(clone(this.config));this.config=this.future.pop();this.selected=null;this.ensureView();this.changed(true);this.flash('Änderung wiederhergestellt.');}
    if(action==='add'){
      const kind=this.shadowRoot.querySelector('#new-kind').value;
      if(this.scene.elements.length>=16 || (['hdmi','message','camera'].includes(kind)&&this.scene.elements.some(i=>i.kind===kind))){this.flash('Maximal 16 Elemente, davon je ein HDMI- und Meldungsfenster.',true);return;}
      this.insertCard(kind);
    }
    if(action==='export'){
      const blob=new Blob([JSON.stringify(this.config,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='lg-display-layout.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    if(action==='upload-background')this.shadowRoot.querySelector('#bg-upload').click();
    if(action==='clean-backgrounds')return this.cleanBackgrounds();
    if(action==='hdmi-view')return this.selectSource('hdmi_full');
    if(action==='dashboard')return this.selectSource('dashboard');
    if(action==='pip-view')return this.selectSource('pip_view');
    if(action==='media-view')return this.selectSource('media_view');
    if(action==='current-view')return this.selectSource(this.viewId);
    if(action==='reset-view')return this.resetView(this.viewId);
    if(action==='import')this.shadowRoot.querySelector('#layout-import').click();
    if(action==='test'){
      if(this.dirty){this.flash('Speichere zuerst, damit die Testmeldung dein aktuelles Layout verwendet.',true);return;}
      try {const result=await this.hass.callWS({type:'config/entity_registry/list'});const entity=result.find(e=>e.config_entry_id===this.entryId&&e.entity_id.startsWith('media_player.')&&!e.disabled_by);
        if(!entity)throw Error();await this.hass.callService('lg_rs232_ip','show_display_app',{entity_id:entity.entity_id,title:'Home Assistant',message:this.shadowRoot.querySelector('#test-message').value.slice(0,2000),layout:this.shadowRoot.querySelector('#test-layout').value,duration:10});this.flash('Testmeldung an das Display gesendet.');
      }catch(_){this.flash('Testmeldung nicht möglich. Prüfe App-Verbindung und SI-Dauerbetrieb.',true);}
    }
  }
  removeItem(id) {this.checkpoint();this.scene.elements=this.scene.elements.filter(item=>item.id!==id);this.selected=null;this.changed(true);}
  async showDashboard() {await this.selectSource('dashboard');}
  releaseImages() {for(const url of Object.values(this.imageUrls || {}))if(url)URL.revokeObjectURL(url);this.imageUrls={};this.imagePending=new Set();for(const record of Object.values(this.coverUrls || {}))if(record.url)URL.revokeObjectURL(record.url);this.coverUrls={};for(const request of (this.coverPending || new Map()).values())request.controller.abort();this.coverPending=new Map();}
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
    const entry=this.entryId,viewId=this.viewId,themeId=this.themeEditing?this.themeId:null,generation=this._generation;this.busy=true;this.updateStatus();
    try {const response=await this.hass.fetchWithAuth(`/api/lg_rs232_ip/layout_background/${entry}/upload`,{method:'POST',body:file});if(!response.ok)throw Error(await response.text());const data=await response.json();if(generation!==this._generation||entry!==this.entryId)return;
      if(!this.backgrounds.includes(data.image_id))this.backgrounds.push(data.image_id);if(this.imageUrls[data.image_id]===null)delete this.imageUrls[data.image_id];const view=this.config.views.find(v=>v.id===viewId),theme=this.config.themes.find(t=>t.id===themeId);if(!theme&&!view)return;this.checkpoint();const target=theme?theme.style:view.scene;if(view&&!theme)view.theme_override=true;target.image_id=data.image_id;target.background='image';if(theme&&this.themeEditing&&this.themeId===themeId)this.refreshThemePreview();this.changed(true);this.flash('Bild vorbereitet. Speichern überträgt den Hintergrund auf das Display.');
    }catch(_){this.flash('Bild konnte nicht importiert werden. JPEG/PNG, bis 5 MiB/20 Megapixel; maximal 24 Bilder. Entferne bei Bedarf unbenutzte Bilder.',true);}finally{this.busy=false;this.updateStatus();const input=this.shadowRoot.querySelector('#bg-upload');if(input)input.value='';}
  }
  async cleanBackgrounds() {
    if(this.busy)return;this.busy=true;this.updateStatus();const entry=this.entryId,generation=this._generation;
    const used=new Set([this.config,this.saved,...this.history,...this.future].flatMap(config=>[...Object.values(config.scenes),...(config.views || []).map(view=>view.scene),...(config.themes || []).map(theme=>theme.style)].map(scene=>scene.image_id)));
    try {for(const id of [...this.backgrounds])if(!used.has(id)){await this.hass.callApi('DELETE',`lg_rs232_ip/layout_background/${entry}/${id}`);if(generation!==this._generation||entry!==this.entryId)return;URL.revokeObjectURL(this.imageUrls[id] || '');delete this.imageUrls[id];this.backgrounds=this.backgrounds.filter(value=>value!==id);}this.renderBackgrounds();this.flash('Unbenutzte Bilder entfernt. Gespeicherte Szenen und Rückgängig-Schritte bleiben erhalten.');}catch(_){this.flash('Ein Bild wird inzwischen verwendet oder konnte nicht entfernt werden.',true);}finally{this.busy=false;this.updateStatus();}
  }
  cardData(state) {
    const a=state.attributes, data={domain:state.entity_id.split('.')[0],device_class:a.device_class || ''};
    for(const key of ['media_title','media_artist','media_album_name','app_name','source','media_position_updated_at','hvac_action'])data[key]=String(a[key] ?? '').slice(0,200);
    for(const key of ['media_duration','media_position','volume_level','brightness','current_temperature','temperature','current_position','percentage'])data[key]=typeof a[key]==='number'&&Number.isFinite(a[key])?a[key]:null;
    data.is_volume_muted=a.is_volume_muted===true;
    data.artwork=a.entity_picture&&!['off','standby','unavailable','unknown'].includes(state.state)?JSON.stringify([a.entity_picture,a.media_content_id,a.media_title,a.media_artist,a.media_album_name]):null;
    return data;
  }
  mediaUrl(entity,key,size=640) {
    const cacheId=entity+"/"+size;
    const cached=this.coverUrls[cacheId];if(cached?.key===key && (cached.url || Date.now()-cached.at<30000))return cached.url || null;
    const previous=this.coverPending.get(cacheId);if(previous?.key===key)return '';
    if(previous)previous.controller.abort();
    const entry=this.entryId,generation=this._generation,pendingMap=this.coverPending;
    const request={key,controller:new AbortController()};pendingMap.set(cacheId,request);
    const timeout=setTimeout(()=>request.controller.abort(),12000);
    const current=()=>this.isConnected&&entry===this.entryId&&generation===this._generation&&pendingMap===this.coverPending&&pendingMap.get(cacheId)===request;
    this.hass.fetchWithAuth(`/api/lg_rs232_ip/layout_media/${entry}/${encodeURIComponent(entity)}?v=preview&size=${size}`,{signal:request.controller.signal}).then(async response=>{
      if(!response.ok||response.status===204)throw Error();const url=URL.createObjectURL(await response.blob());
      const state=this.hass.states[entity];
      if(!current() || !state || this.cardData(state).artwork!==key){URL.revokeObjectURL(url);return;}
      if(this.coverUrls[cacheId]?.url)URL.revokeObjectURL(this.coverUrls[cacheId].url);this.coverUrls[cacheId]={key,url,at:Date.now()};const keys=Object.keys(this.coverUrls);if(keys.length>32){const old=keys.find(id=>id!==cacheId);if(this.coverUrls[old].url)URL.revokeObjectURL(this.coverUrls[old].url);delete this.coverUrls[old];}this.paint();
    }).catch(()=>{if(current()&&this.hass.states[entity]&&this.cardData(this.hass.states[entity]).artwork===key){if(this.coverUrls[cacheId]?.url)URL.revokeObjectURL(this.coverUrls[cacheId].url);this.coverUrls[cacheId]={key,url:null,at:Date.now()};}}).finally(()=>{clearTimeout(timeout);if(pendingMap.get(cacheId)===request)pendingMap.delete(cacheId);if(this.isConnected&&entry===this.entryId&&generation===this._generation&&pendingMap===this.coverPending)this.paint();});return '';
  }

  async loadSuggestions(area) {
    const entry=this.entryId,generation=this._generation,request=this._suggestionRequest=(this._suggestionRequest || 0)+1;
    try {const data=await this.hass.callApi('GET',`lg_rs232_ip/layout_suggestions/${entry}`+(area!==undefined?'?area_id='+encodeURIComponent(area):''));
      if(entry!==this.entryId||generation!==this._generation||request!==this._suggestionRequest||!this.isConnected)return;
      this.rooms=data.areas || [];this.suggestionArea=data.area_id || '';this.suggestions=data.suggestions || [];this.suggestionTotal=data.total || 0;
      const select=this.shadowRoot.querySelector('#suggestion-room');select.innerHTML='<option value="">Raum wählen</option>'+this.rooms.map(room=>`<option value="${escapeHTML(room.area_id)}">${escapeHTML(room.name)}</option>`).join('');select.value=this.suggestionArea;this.renderSuggestions();
    }catch(_){if(entry===this.entryId&&generation===this._generation)this.shadowRoot.querySelector('.room-hint').textContent='Raumvorschläge konnten nicht geladen werden.';}
  }
  renderSuggestions() {
    const list=this.shadowRoot.querySelector('.suggestions');if(!list)return;
    const selected=new Set(this.scene.elements.map(item=>item.entity_id));
    this.shadowRoot.querySelector('.room-hint').textContent=!this.suggestionArea?'Wähle einen Raum. Die Zuordnung des Displays wird automatisch vorgeschlagen.':this.suggestions?.length?'Passend zu deinem Raum. Anklicken fügt eine Karte zur aktuellen Ansicht hinzu.':'Keine passenden Entitäten. Prüfe die Raumzuordnung in Home Assistant.';
    list.innerHTML=(this.suggestions || []).map((card,index)=>{const state=this.hass.states[card.entity_id];const data=state?{...this.cardData(state),state:state.state,unit:state.attributes.unit_of_measurement || ''}:card;const value=window.LGCards.status(data);return `<button class="suggestion" data-suggestion="${index}" ${selected.has(card.entity_id)?'disabled':''}><span class="suggestion-type">${escapeHTML(KINDS[card.kind])}</span><strong>${escapeHTML(card.name)}</strong><span>${selected.has(card.entity_id)?'Bereits in dieser Ansicht':escapeHTML(value.value)}</span></button>`;}).join('');
    list.querySelectorAll('[data-suggestion]').forEach(button=>button.onclick=()=>{const card=this.suggestions[Number(button.dataset.suggestion)];this.insertCard(card.kind,card.entity_id,card.name);});
  }
  insertCard(kind,entity='',label=KINDS[kind]) {
    if(!this.availableKinds[kind] || (this.startupView && entity)){this.flash('Die Startanzeige unterstützt nur lokale Texte und Uhr/Datum.',true);return;}
    if(['hdmi','message','camera'].includes(kind)&&this.scene.elements.some(item=>item.kind===kind)){this.flash('Dieser Typ ist in der Ansicht bereits vorhanden.',true);return;}
    if(this.scene.elements.length>=16){this.flash('Maximal 16 Karten pro Ansicht. Entferne zuerst eine Karte.',true);return;}
    const dimensions={media:[50,28],status:[26,24],weather:[32,34],calendar:[40,34],hdmi:[60,60],camera:[34,34]},[width,height]=dimensions[kind] || [30,25];
    let spot=null;for(let y=4;y+height<=98&&!spot;y+=2)for(let x=4;x+width<=98;x+=2)if(!this.scene.elements.some(item=>x<item.x+item.width+1&&x+width+1>item.x&&y<item.y+item.height+1&&y+height+1>item.y)){spot={x,y};break;}
    this.checkpoint();const id=kind+'_'+Math.random().toString(36).slice(2,10),base=this.scene.elements.find(item=>item.kind!=='hdmi');
    this.scene.elements.push({id,kind,...(spot || {x:5,y:5}),width,height,label,text:kind==='text'?'Dein Text':'',entity_id:entity,font_size:kind==='status'?4:3.5,color:base?.color || '#f2f6fa',background:base?.background || '#142335',opacity:.92,radius:24,align:'left',font:'sans',show_label:true,forecast_type:'daily',forecast_count:4,animate:true,weather_style:'glass',media_style:'compact',show_cover:true,show_progress:true,show_playback_icon:false,show_volume:true,status_coloring:true,camera_source:entity.startsWith('camera.')?'entity':'test',camera_mode:'auto',camera_interval:2,camera_fit:'contain',accent_color:this.scene.accent});this.selected=id;this.changed(true);
    this.flash(spot?'Karte eingefügt. Du kannst sie frei gestalten und wieder entfernen.':'Karte eingefügt. Kein freier Platz: Verschiebe sie oder entferne andere Karten.');
  }
  async save() {
    if(this.busy)return;
    for(const view of this.config.views){
      const camera=view.scene.elements.find(i=>i.kind==='camera'),hdmi=view.scene.elements.find(i=>i.kind==='hdmi');
      if(camera&&hdmi&&camera.x<hdmi.x+hdmi.width&&hdmi.x<camera.x+camera.width&&camera.y<hdmi.y+hdmi.height&&hdmi.y<camera.y+camera.height&&(camera.camera_source!=='entity'||camera.camera_mode==='stream')){
        this.flash('„'+view.name+'“: Kamerastream und HDMI dürfen sich nicht überlappen. HDMI verkleinern oder für eine HA-Kamera Automatisch / Nur Einzelbilder wählen.',true);return;
      }
    }
    this.busy=true;this.updateStatus();
    this.compileViews();const sent=clone(this.config);
    try {const result=await this.hass.callApi('POST',`lg_rs232_ip/layout_library/${this.entryId}`,{config:sent,revision:this.revision});this.revision=result.revision;this.startupStatus=result.startup_design;this.saved=this.withViews(clone(result.config));this.dirty=JSON.stringify(this.config)!==JSON.stringify(sent);if(!this.dirty)this.config=this.withViews(clone(result.config));this.flash(this.startupView?'Startanzeige gespeichert. Die verbundene App speichert die Gestaltung lokal.':this.config.enabled?'Gespeichert. Die verbundene App übernimmt das Layout automatisch.':'Gespeichert. Eigene Layouts sind derzeit ausgeschaltet.');}
    catch(error){this.flash(error?.status_code===409?'Eine andere Sitzung hat das Layout geändert. Exportiere deinen Entwurf und lade den Editor neu.':'Speichern fehlgeschlagen. Prüfe Entitäten, Feldwerte und Verbindung. Dein Entwurf bleibt erhalten.',true);}
    finally{this.busy=false;this.updateStatus();if(this.page==="overview")this.renderOverview();clearTimeout(this._dataSoon);this._dataSoon=setTimeout(()=>this.refreshValues(),2500);}
  }
  async importFile(file) {
    if(!file)return;
    try {
      if(file.size>1048576)throw Error();const config=JSON.parse(await file.text());
      // Rendering imported CSS/text before server validation is deliberately avoided.
      const result=await this.hass.callApi('POST',`lg_rs232_ip/layout_validate`,{config});
      this.checkpoint();this.config=this.withViews(result.config);this.ensureView();this.selected=null;this.changed(true);this.flash('Layout als Entwurf importiert.');
    }catch(_){this.flash('Keine gültige Layout-Datei. Verwende einen Export aus Display Studio (maximal 1 MiB).',true);}
    finally{this.shadowRoot.querySelector('#layout-import').value='';}
  }
  applyTheme(preset) {
    const source=preset.layout.scenes.dashboard,colors=source.elements.find(i=>i.kind!=='hdmi');
    this.checkpoint();this.markThemeOverride();if(this.themeEditing)Object.assign(this.theme.style,{ink:colors.color,surface:colors.background,card_accent:source.accent});for(const key of ['background','color','accent'])this.scene[key]=source[key];
    if(this.startupView && this.scene.background==='solar')this.scene.background='dawn';
    for(const item of this.scene.elements)if(item.kind!=='hdmi'){item.color=colors.color;item.background=colors.background;item.accent_color=source.accent;}
    this.changed(true);this.flash(preset.name+'-Farben übernommen. Inhalte und Anordnung bleiben erhalten.');
  }
  refreshThemePreview() {
    if(!this.theme)return;
    this.themeScene=applyThemeStyle(clone(this.config.views.find(v=>v.id==='dashboard').scene),this.theme.style);
  }
  openTheme(id) {
    this.widgetEditor?.close();
    if(!this.config.themes.some(t=>t.id===id))return;
    this.themeId=id;this.page='theme';this.selected=null;this.refreshThemePreview();this.showPage();this.updateStatus();this.shadowRoot.querySelector('header').scrollIntoView({block:'start'});
  }
  updateThemeControls() {
    const root=this.shadowRoot,editing=this.themeEditing;
    root.querySelector('.workspace').classList.toggle('theme-editing',editing);
    for(const selector of ['.inspector','.selection-layer','.context-tabs','.output-controls','.main > .hint'])root.querySelector(selector).hidden=editing;
    root.querySelector('.theme-id-field').hidden=!editing;
    root.querySelector('#theme-id').value=editing?this.theme.id:'';
    root.querySelector('[data-action=theme-use]').hidden=!editing;
    root.querySelector('[data-action=theme-follow]').hidden=editing;
    root.querySelector('#editor-name-label').textContent=editing?'Name des Themes':'Name der Ansicht';
    if(editing){
      root.querySelector('#view-name').disabled=false;root.querySelector('#view-name').value=this.theme.name;
      root.querySelector('#scene-title').textContent=this.theme.name+' · Theme-Vorschau';
      root.querySelector('.view-usage').textContent='Gemeinsame Farben und Hintergründe';
      root.querySelector('.context-hint').textContent='Dieses Theme gestaltet alle folgenden Ansichten. Widgets und Anordnung werden nicht verändert. Speichern übernimmt den Entwurf.';
      for(const selector of ['.room-suggestions','.message-test','.automation-help'])root.querySelector(selector).hidden=true;
    }else if(this.view){
      const theme=this.config.themes.find(t=>t.id===this.config.active_theme);
      root.querySelector('.view-usage').textContent=this.usage(this.viewId)+(this.view.theme_override?' · Eigene Theme-Abweichung':theme?' · Folgt '+theme.name:' · Folgt dem gewählten Theme');
    }
  }
  useTheme(id,all=false) {
    if(!this.config.themes.some(t=>t.id===id))return;
    this.checkpoint();this.config.active_theme=id;if(all)for(const view of this.config.views)view.theme_override=false;
    this.changed(true);this.flash('Standard-Theme gewählt. '+(all?'Alle Ansichten folgen wieder. ':'Eigene Abweichungen bleiben erhalten. ')+'Speichern übernimmt die Änderung.');
  }
  followTheme(id) {
    const view=this.config.views.find(v=>v.id===id);if(!view)return;this.checkpoint();view.theme_override=false;
    const theme=this.config.themes.find(t=>t.id===(this.config.active_theme || 'cinema'));
    applyThemeStyle(view.scene,theme.style,id==='startup');this.changed(true);this.flash('Theme-Standard wiederhergestellt. Inhalte und Anordnung bleiben erhalten.');
  }
  duplicateTheme(id) {
    if(this.config.themes.length>=24){this.flash('Maximal 24 Themes.',true);return;}
    const source=this.config.themes.find(t=>t.id===id);if(!source)return;this.checkpoint();const copy=clone(source);copy.id='theme_'+Date.now().toString(36)+Math.random().toString(36).slice(2,10);copy.name=source.name.slice(0,68)+' · Kopie';this.config.themes.push(copy);this.changed();this.openTheme(copy.id);
  }
  resetTheme(id) {
    const preset=this.catalog.presets.find(p=>p.id===id);if(!preset)return;
    this.checkpoint();const theme=this.config.themes.find(t=>t.id===id);theme.name=preset.name;theme.style=themeStyle(preset.layout.scenes.dashboard);if(this.themeEditing)this.refreshThemePreview();this.changed(true);
  }
  deleteTheme(id) {
    if(this.catalog.presets.some(p=>p.id===id))return;
    this.checkpoint();this.config.themes=this.config.themes.filter(t=>t.id!==id);if(this.config.active_theme===id)this.config.active_theme='cinema';this.ensureView();this.changed(true);this.flash('Theme entfernt. Rückgängig stellt es wieder her.');
  }
  openContext(key) {
    if(!CONTEXTS[key])return;
    this.openView(key);
  }
  withViews(config) {
    if(!Array.isArray(config.views))config.views=Object.entries(CONTEXTS).map(([id,name])=>({id,name,scene:clone(config.scenes[id])}));
    config.library_version=4;delete config.assignments;
    if(!Array.isArray(config.themes))config.themes=this.catalog.presets.map(p=>({id:p.id,name:p.name,style:themeStyle(p.layout.scenes.dashboard)}));
    config.active_theme=config.active_theme || '';
    const theme=config.themes.find(t=>t.id===config.active_theme);
    for(const view of config.views){view.theme_override=view.theme_override===true;if(theme&&!view.theme_override)applyThemeStyle(view.scene,theme.style,view.id==='startup');}
    const base=this.catalog.presets[0].layout.scenes;
    config.scenes={signal:clone(config.scenes.signal || base.signal),no_signal:clone(config.scenes.no_signal || base.no_signal)};
    for(const view of config.views)config.scenes[view.id]=clone(view.scene);
    return config;
  }
  compileViews() {if(this.themeEditing && this.theme)for(const key of THEME_FIELDS)this.theme.style[key]=clone(this.themeScene[key]);this.withViews(this.config);}
  ensureView() {if(this.themeEditing){if(!this.config.themes.some(t=>t.id===this.themeId))this.page='overview';else this.refreshThemePreview();}if(!this.config.views.some(v=>v.id===this.viewId))this.viewId=this.config.views[0]?.id;if(!this.viewId)this.page='overview';this.showPage();}
  usage(id) {if(id==='startup')return 'Feste Startansicht · offlinefähig';if(id==='hdmi_full')return 'Feste Ansicht · HDMI 1 / 2 / 3';return CONTEXTS[id] ? (SOURCE_CONTEXTS.includes(id)?'Feste Ansicht · Quelle':'Feste Mitteilungsansicht') : 'Eigene Ansicht · Quelle';}
  showPage() {const overview=this.page==='overview';this.shadowRoot.querySelector('.overview').hidden=!overview;this.shadowRoot.querySelector('.workspace').hidden=overview;this.shadowRoot.querySelector('.editor-navigation').hidden=overview;if(overview)this.renderer?.clear();else this.refreshScene();}
  openView(id) {this.widgetEditor?.close();if(!this.config.views.some(v=>v.id===id))return;this.viewId=id;this.sceneKey=CONTEXTS[id]?id:'dashboard';this.selected=null;this.page='editor';this.showPage();this.updateStatus();this.scrollTop=0;}
  transitionSelect(label) {return `<select class="display-transition" aria-label="${escapeHTML(label)}" title="HDMI zwischen den gespeicherten Positionen und Größen bewegen">${options({none:'Direkt',smooth:'Animiert'},this.transitionMode)}</select>`;}
  bindTransitions() {
    this.shadowRoot.querySelectorAll('.display-transition').forEach(select=>{
      select.value=this.transitionMode;
      select.onchange=event=>{this.transitionMode=event.target.value;this.bindTransitions();};
    });
  }
  renderOverview() {
    const root=this.shadowRoot, gallery=root.querySelector('.primary-gallery');if(!gallery)return;
    const card=view=>`<article class="view-card"><button class="view-preview" data-open-view="${escapeHTML(view.id)}" aria-label="${escapeHTML(view.name)} bearbeiten"><div class="view-thumbnail" data-preview="${escapeHTML(view.id)}"></div></button><div class="view-card-body"><h3>${escapeHTML(view.name)}</h3><p>${escapeHTML(this.usage(view.id))}</p><div class="view-actions"><button class="small" data-open-view="${escapeHTML(view.id)}">Bearbeiten</button>${SOURCE_CONTEXTS.includes(view.id)||!CONTEXTS[view.id]?`<span class="display-control"><button class="small" data-display-view="${escapeHTML(view.id)}">Anzeigen</button>${this.transitionSelect("Übergang für "+view.name)}</span>`:''}<button class="small" data-copy-view="${escapeHTML(view.id)}" aria-label="${escapeHTML(view.name)} duplizieren">Duplizieren</button>${CONTEXTS[view.id]?`<button class="small" data-reset-view="${view.id}" aria-label="${view.name} Standard wiederherstellen">Standard wiederherstellen</button>`:`<button class="small delete" data-delete-view="${escapeHTML(view.id)}" aria-label="${escapeHTML(view.name)} löschen">Löschen</button>`}</div></div></article>`;
    gallery.innerHTML=this.config.views.filter(view=>!NOTIFICATION_CONTEXTS.includes(view.id)).map(card).join('');
    root.querySelector('.notification-gallery').innerHTML=this.config.views.filter(view=>NOTIFICATION_CONTEXTS.includes(view.id)).map(card).join('');
    root.querySelectorAll('[data-open-view]').forEach(b=>b.onclick=()=>this.openView(b.dataset.openView));
    root.querySelectorAll('[data-copy-view]').forEach(b=>b.onclick=()=>this.duplicateView(b.dataset.copyView));
    root.querySelectorAll('[data-delete-view]').forEach(b=>b.onclick=()=>this.deleteView(b.dataset.deleteView));
    root.querySelectorAll('[data-reset-view]').forEach(b=>b.onclick=()=>this.resetView(b.dataset.resetView));
    this.bindTransitions();
    root.querySelectorAll('[data-display-view]').forEach(b=>{b.disabled=this.busy;b.onclick=()=>this.activateView(b.dataset.displayView);});
    const active=this.config.themes.find(t=>t.id===this.config.active_theme);
    root.querySelector('.theme-manager-status').textContent=active?'Standard: '+active.name+' · '+this.config.views.filter(v=>!v.theme_override).length+' Ansichten folgen dem Theme':'Wähle ein Standard-Theme. Bis dahin bleiben die vorhandenen Gestaltungen erhalten.';
    root.querySelector('.template-options').innerHTML=this.config.themes.map(t=>`<article class="theme-card"><div class="mini" data-theme-preview="${escapeHTML(t.id)}" style="background:${window.LGLayoutBackground(t.style,{sun:this.sun(),imageUrl:id=>this.imageUrl(id)})}"></div><div class="view-card-body"><h3>${escapeHTML(t.name)}</h3><p>${t.id===this.config.active_theme?'Aktives Standard-Theme':t.style.media_background_enabled?'Mit Medienplayer-Hintergrund':'Farben & Hintergrund'} · <code>${escapeHTML(t.id)}</code></p><div class="view-actions"><button class="small" data-edit-theme="${escapeHTML(t.id)}" aria-label="${escapeHTML(t.name)} Theme bearbeiten">Bearbeiten</button><button class="small" data-use-theme="${escapeHTML(t.id)}" aria-label="${escapeHTML(t.name)} als Standard-Theme">Als Standard</button><button class="small" data-copy-theme="${escapeHTML(t.id)}" aria-label="${escapeHTML(t.name)} Theme duplizieren">Duplizieren</button>${this.catalog.presets.some(p=>p.id===t.id)?`<button class="small" data-reset-theme="${t.id}">Theme zurücksetzen</button>`:`<button class="small delete" data-delete-theme="${escapeHTML(t.id)}" aria-label="${escapeHTML(t.name)} Theme löschen">Löschen</button>`}</div></div></article>`).join('');
    for(const [key,method] of [['edit','openTheme'],['use','useTheme'],['copy','duplicateTheme'],['reset','resetTheme'],['delete','deleteTheme']])root.querySelectorAll('[data-'+key+'-theme]').forEach(b=>b.onclick=()=>this[method](b.getAttribute('data-'+key+'-theme')));
    this.paintGallery();
  }
  paintGallery() {
    for(const node of this.shadowRoot.querySelectorAll('[data-theme-preview]')){const theme=this.config.themes.find(t=>t.id===node.dataset.themePreview);if(theme)node.style.background=window.LGLayoutBackground(theme.style,{sun:this.sun(),imageUrl:id=>this.imageUrl(id)});}
    if(!this.config || !this.shadowRoot.querySelector('.view-gallery'))return;
    const sun=this.sun();this.shadowRoot.querySelectorAll('[data-preview]').forEach(node=>{const view=this.config.views.find(v=>v.id===node.dataset.preview);if(!view)return;node.style.background=window.LGLayoutBackground(view.scene,{sun,imageUrl:id=>this.imageUrl(id)});if(node.dataset.layout!==JSON.stringify(view.scene)){node.dataset.layout=JSON.stringify(view.scene);node.innerHTML=view.scene.elements.map(item=>`<div class="mini-widget" style="left:${item.x}%;top:${item.y}%;width:${item.width}%;height:${item.height}%;border-radius:${Math.min(item.radius,12)}px;background:${item.kind==='hdmi'?'#07131c':item.background};color:${item.color};opacity:${Math.max(.4,item.opacity)}">${escapeHTML(item.label || KINDS[item.kind])}</div>`).join('');}});
  }
  showCreator(template='morning') {
    if(this.config.views.length>=32){this.flash('Maximal 24 eigene Ansichten. Entferne zuerst eine Ansicht.',true);return;}
    const root=this.shadowRoot.querySelector('.view-creator');root.hidden=false;
    root.innerHTML=`<h2>Neue Ansicht</h2><div class="creator-fields"><label>Name<input id="new-view-name" maxlength="80" value="${escapeHTML(this.catalog.presets.find(p=>p.id===template)?.name || 'Meine Ansicht')}"></label><label>Vorlage<select id="new-view-template" aria-label="Vorlage">${options(Object.fromEntries(this.catalog.presets.map(p=>[p.id,p.name])),template)}</select></label><label>Aufbau<select id="new-view-context" aria-label="Aufbau">${options(CONTEXTS,'dashboard')}</select></label></div><p class="note">Inhalte und Aufbau bleiben unabhängig. Farben und Hintergrund folgen dem Standard-Theme. Nach dem Speichern erscheint die Ansicht als eigene Quelle.</p><div class="links"><button class="primary" data-create-view>Ansicht anlegen</button><button class="secondary" data-cancel-view>Abbrechen</button></div>`;
    root.querySelector('[data-cancel-view]').onclick=()=>root.hidden=true;
    root.querySelector('[data-create-view]').onclick=()=>{const name=root.querySelector('#new-view-name').value.trim();if(!name){this.flash('Bitte gib der Ansicht einen Namen.',true);return;}const preset=this.catalog.presets.find(p=>p.id===root.querySelector('#new-view-template').value),key=root.querySelector('#new-view-context').value;this.checkpoint();const id='view_'+(Date.now().toString(36)+Math.random().toString(36).slice(2,12));this.config.views.push({id,name,theme_override:false,scene:clone(preset.layout.scenes[key])});root.hidden=true;this.changed();this.openView(id);this.sceneKey=key;this.flash('Ansicht angelegt. Nach dem Speichern erscheint sie automatisch als eigene Quelle.');};
    root.scrollIntoView({block:'nearest'});root.querySelector('#new-view-name').focus();
  }
  duplicateView(id) {if(this.config.views.length>=32){this.flash('Maximal 24 eigene Ansichten.',true);return;}const view=this.config.views.find(v=>v.id===id);if(!view)return;this.checkpoint();const copy=clone(view);copy.id='view_'+(Date.now().toString(36)+Math.random().toString(36).slice(2,12));copy.name=(copy.name.slice(0,70)+' · Kopie');this.config.views.push(copy);this.changed();this.flash('Unabhängige Kopie angelegt. Speichern übernimmt sie dauerhaft.');}
  deleteView(id) {
    if(this.busy || CONTEXTS[id] || !this.config.views.some(v=>v.id===id))return;
    this.checkpoint();this.config.views=this.config.views.filter(v=>v.id!==id);this.ensureView();this.changed();
    this.flash('Eigene Ansicht entfernt. Speichern entfernt auch ihre Quelle. Eine aktive Ansicht wechselt zum Dashboard. Rückgängig ist möglich.');
  }
  resetView(id) {
    if(this.busy || !CONTEXTS[id])return;
    const view=this.config.views.find(v=>v.id===id);if(!view)return;
    this.checkpoint();view.theme_override=false;view.scene=clone(this.catalog.presets[0].layout.scenes[id]);this.selected=null;this.changed(true);
    this.flash(CONTEXTS[id]+' auf den Standard zurückgesetzt. Speichern übernimmt die Änderung; Rückgängig stellt deinen Entwurf wieder her.');
  }
  async activateView(id) {
    if(this.busy)return;if(this.dirty){this.flash('Speichere zuerst deine Ansichten.',true);return;}
    if(!this.config.views.some(v=>v.id===id))return;
    if(!this.config.enabled){this.checkpoint();this.config.enabled=true;this.changed();await this.save();if(this.dirty)return;}
    await this.selectSource(id);
  }
  async selectSource(id) {
    // Always select the saved stable ID; open drafts never change source routing.
    if(this.busy || this._sourceBusy || (CONTEXTS[id]&&!SOURCE_CONTEXTS.includes(id)))return;
    if(!this.saved.views.some(v=>v.id===id)){this.flash('Speichere die neue Ansicht zuerst.',true);return;}
    const transition=this.transitionMode;
    this._sourceBusy=true;
    try {
      const registry=await this.hass.callWS({type:'config/entity_registry/list'});
      const player=registry.find(e=>e.config_entry_id===this.entryId&&e.entity_id.startsWith('media_player.')&&!e.disabled_by);if(!player)throw Error();
      if(transition==='smooth'){
        await this.hass.callService('lg_rs232_ip','show_view',{entity_id:player.entity_id,view:id,transition});
        this.flash('Gespeicherte Ansicht animiert angezeigt.'+(this.dirty?' Deine Änderungen bleiben im Entwurf.':''));return;
      }
      const attrs=(id==='hdmi_full' ? (await this.hass.callApi('GET',`states/${player.entity_id}`))?.attributes : this.hass.states[player.entity_id]?.attributes) || {};
      const source=id==='hdmi_full' ? attrs.hdmi_source : attrs.view_sources?.[id] || attrs[{pip_view:'pip_source',media_view:'media_view_source',dashboard:'dashboard_source'}[id]] || CONTEXTS[id];
      if(id==='hdmi_full'&&!source){this.flash('Der aktuelle HDMI-Eingang ist noch nicht bekannt. Wähle zuerst einen HDMI-Eingang in der Fernbedienung.',true);return;}
      if(!source)throw Error();
      await this.hass.callService('media_player','select_source',{entity_id:player.entity_id,source});
      this.flash('Gespeicherte Quelle '+source+' angezeigt.'+(this.dirty?' Deine Änderungen bleiben im Entwurf.':''));
    }catch(_){this.flash('Quelle nicht erreichbar. Prüfe eigene Layouts, SI-Dauerbetrieb und Stromversorgung.',true);}finally{this._sourceBusy=false;}
  }
  flash(message,error=false) {for(const selector of ['.flash','.gallery-flash']){const node=this.shadowRoot.querySelector(selector);if(node){node.textContent=message;node.classList.toggle('error',error);}}}
}
if(!customElements.get('lg-display-studio'))customElements.define('lg-display-studio',LGDisplayStudio);

/* Browser-only editor; the LG receives just validated part overrides. */
class LGWidgetEditor {
  constructor(host,id) {
    this.host=host;this.id=id;this.viewId=host.viewId;this.partId=null;this.dragging=false;
    this.root=document.createElement('section');this.root.className='widget-dialog';this.root.setAttribute('role','dialog');this.root.setAttribute('aria-modal','true');this.root.setAttribute('aria-label','Widget bearbeiten');
    this.root.innerHTML=`<header class="widget-dialog-header"><div><h2></h2><p>Einzelne Inhalte gestalten · der Entwurf bleibt bis zum Speichern im Studio.</p></div><button class="secondary" data-undo title="Widget-Änderung rückgängig">↶</button><button class="secondary" data-redo title="Widget-Änderung wiederholen">↷</button><button class="secondary" data-reset>Inhalt-Layout zurücksetzen</button><button class="primary" data-close>Fertig</button></header><div class="widget-dialog-body"><main class="widget-workbench"><p class="widget-context"></p><div class="widget-frame"><div class="widget-preview"><div class="lg-hdmi-placeholder"></div></div><div class="widget-part-selection"></div></div><p class="note">Ein Element wählen und ziehen; die Ecke ändert seine Größe. Positionen beziehen sich auf die angegebene Gruppe. Entfernte Inhalte bleiben wiederherstellbar.</p><div class="widget-binding"></div></main><aside class="widget-inspector"><label>Inhaltselement<select aria-label="Inhaltselement" data-part></select></label><div class="widget-part-fields"></div></aside></div>`;
    host.shadowRoot.append(this.root);this.previousFocus=host.shadowRoot.activeElement;
    this.root.querySelector('[data-close]').onclick=()=>this.close();
    this.root.querySelector('[data-reset]').onclick=()=>this.reset();
    for(const action of ['undo','redo'])this.root.querySelector('[data-'+action+']').onclick=()=>{host.action(action);this.refresh();};
    this.root.querySelector('[data-part]').onchange=e=>{this.partId=e.target.value;this.refresh();};
    this.root.onkeydown=e=>{
      if(e.key==='Escape'){e.preventDefault();e.stopPropagation();this.close();}
      if(e.key==='Tab'){const items=[...this.root.querySelectorAll('button,input,select,textarea')].filter(n=>!n.disabled&&n.offsetParent!==null),first=items[0],last=items[items.length-1],active=host.shadowRoot.activeElement;if(e.shiftKey&&active===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&active===last){e.preventDefault();first.focus();}}
    };
    this.renderer=new window.LGLayoutRenderer(this.root.querySelector('.widget-preview'),this.root.querySelector('.lg-hdmi-placeholder'),true);
    this.root.querySelector('.widget-preview').onclick=e=>{const part=[...this.entries].reverse().find(p=>this.element(p)?.contains(e.target));if(part){this.partId=part.id;this.refresh();}};
    this.resize=new ResizeObserver(()=>{if(!this.dragging)this.paint();});this.resize.observe(this.root.querySelector('.widget-workbench'));
    this.refresh();this.root.querySelector('[data-close]').focus();
  }
  get item(){return this.host.viewId===this.viewId?this.host.scene.elements.find(i=>i.id===this.id):null;}
  get entries(){return window.LGWidgetParts.catalog(this.item);}
  get part(){return this.entries.find(p=>p.id===this.partId);}
  get config(){return this.item.parts?.[this.partId] || {};}
  enabled(part){const flag={label:'show_label',cover:'show_cover',progress:'show_progress',playback:'show_playback_icon',volume:'show_volume'}[part.id];return this.item.parts?.[part.id]?.visible!==false&&(!flag||(flag==='show_playback_icon'?this.item[flag]===true:this.item[flag]!==false));}
  get node(){return this.renderer.nodes[this.id];}
  element(part=this.part){return this.node&&part?window.LGWidgetParts.find(this.node,part):null;}
  parent(part=this.part){return part?.parent?this.element(this.entries.find(p=>p.id===part.parent)):this.node;}
  label(part){const parent=this.entries.find(p=>p.id===part.parent);return (parent?parent.name+' / ':'')+part.name;}
  close(){this.resize?.disconnect();this.renderer?.clear();this.root.remove();if(this.host.widgetEditor===this)this.host.widgetEditor=null;this.previousFocus?.focus();}
  changed(){this.host.changed();this.host.renderProperties();this.refresh();}
  update(key,value){
    const item=this.item;if(!item)return;this.host.checkpoint();item.parts ||= {};
    if(['x','y','width','height'].includes(key))this.arrange(this.part.parent);
    const conf=item.parts[this.partId] ||= {};
    if(value===null)delete conf[key];else conf[key]=value;
    if(key==='color')this.host.markThemeOverride();
    if(['x','y','width','height'].includes(key)){
      conf.x=Math.min(conf.x,100-conf.width);conf.y=Math.min(conf.y,100-conf.height);
      if(key==='width')conf.width=Math.min(value,100-conf.x);if(key==='height')conf.height=Math.min(value,100-conf.y);
    }
    if(key==='visible'&&value){const flag={label:'show_label',cover:'show_cover',progress:'show_progress',playback:'show_playback_icon',volume:'show_volume'}[this.partId];if(flag)item[flag]=true;}
    this.changed();
  }
  box(part=this.part){
    const conf=this.item.parts?.[part.id];if(conf?.x!==undefined)return {x:conf.x,y:conf.y,width:conf.width,height:conf.height};
    const el=this.element(part),parent=this.parent(part),bounds=parent?.getBoundingClientRect(),rect=el?.getBoundingClientRect();
    if(!bounds?.width||!bounds.height||!rect?.width||!rect.height)return {x:5,y:5,width:90,height:20};
    const x=Math.max(0,Math.min(99,(rect.left-bounds.left)/bounds.width*100)),y=Math.max(0,Math.min(99,(rect.top-bounds.top)/bounds.height*100));
    return {x,y,width:Math.max(1,Math.min(100-x,rect.width/bounds.width*100)),height:Math.max(1,Math.min(100-y,rect.height/bounds.height*100))};
  }
  arrange(parentId){
    const siblings=this.entries.filter(p=>p.parent===parentId),boxes=siblings.map(p=>[p,this.box(p)]);
    // Freeze siblings before removing any from normal flow, avoiding layout jumps.
    for(const [part,box] of boxes){const el=this.element(part);if(el?.getBoundingClientRect().width || part.id===this.partId){const conf=this.item.parts[part.id] ||= {};if(conf.x===undefined)Object.assign(conf,box);}}
  }
  reset(){
    this.host.checkpoint();delete this.item.parts;delete this.item.clock_time_format;delete this.item.clock_date_format;
    Object.assign(this.item,{show_label:true,show_cover:true,show_progress:true,show_volume:true,show_playback_icon:false});this.partId=null;this.changed();
  }
  refresh(){
    if(!this.item){this.close();return;}
    this.root.querySelector('h2').textContent=(this.item.label || KINDS[this.item.kind])+' · Widget bearbeiten';
    const entries=this.entries;
    if(!entries.some(p=>p.id===this.partId))this.partId=entries.find(p=>p.id!=='label')?.id || entries[0]?.id || null;
    this.root.querySelector('[data-part]').innerHTML=entries.map(p=>`<option value="${p.id}" ${p.id===this.partId?'selected':''}>${escapeHTML(this.label(p))}${this.item.parts?.[p.id]?.visible===false?' · entfernt':''}</option>`).join('');
    this.root.querySelector('[data-part]').disabled=!entries.length;
    this.root.querySelector('[data-undo]').disabled=!this.host.history.length;this.root.querySelector('[data-redo]').disabled=!this.host.future.length;
    this.paint();this.fields();this.binding();
  }
  paint(){
    if(!this.item||!this.renderer)return;
    const frame=this.root.querySelector('.widget-frame'),area=this.root.querySelector('.widget-workbench'),ratio=this.item.width/this.item.height*16/9;
    const width=Math.min(Math.max(120,area.clientWidth-40),Math.max(130,this.root.clientHeight-240)*ratio);
    frame.style.width=width+'px';frame.style.height=width/ratio+'px';
    const scene=clone(this.host.scene),item=clone(this.item);Object.assign(item,{x:0,y:0,width:100,height:100});scene.elements=[item];scene.media_background_enabled=false;
    this.renderer.render(scene,this.host.values(),{contentScale:100/this.item.height,timezone:this.host.timezone,sun:this.host.sun(),mediaUrl:(...args)=>this.host.mediaUrl(...args),imageUrl:id=>this.host.imageUrl(id),now:new Date(),message:{title:'Home Assistant',message:this.host.shadowRoot.querySelector('#test-message')?.value || 'Deine Mitteilung'}});
    if(!this.dragging)this.selection();
  }
  tick(now){this.renderer?.tick(now);}
  selection(){
    const layer=this.root.querySelector('.widget-part-selection');layer.innerHTML='';
    const part=this.part;if(!part)return;
    const el=this.element(),parent=this.parent(),frame=this.root.querySelector('.widget-frame').getBoundingClientRect();
    const rect=el?.getBoundingClientRect();const visible=rect?.width&&rect.height&&getComputedStyle(el).display!=='none';
    this.root.querySelector('.widget-context').textContent=this.label(part)+' · '+(part.parent?'Relativ zu '+this.entries.find(p=>p.id===part.parent).name:'Relativ zum Widget')+(visible?'':' · derzeit ohne sichtbaren Inhalt');
    if(!visible||!parent||this.config.visible===false)return;
    const target=document.createElement('div');target.className='part-outline';target.tabIndex=0;target.setAttribute('role','button');target.setAttribute('aria-label',part.name+' im Widget verschieben');
    Object.assign(target.style,{left:rect.left-frame.left+'px',top:rect.top-frame.top+'px',width:rect.width+'px',height:rect.height+'px'});
    target.innerHTML=`<span class="part-tag">${escapeHTML(part.name)}</span><span class="part-resize" title="Inhaltsgröße ändern"></span>`;
    target.onpointerdown=e=>this.pointer(e,target);target.onkeydown=e=>{
      if(['Delete','Backspace'].includes(e.key)){e.preventDefault();this.update('visible',false);return;}
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();const box=this.box(),step=e.shiftKey?.1:1;
      const key=['ArrowLeft','ArrowRight'].includes(e.key)?'x':'y',change=['ArrowLeft','ArrowUp'].includes(e.key)?-step:step;this.update(key,Math.max(0,Math.min(100-box[key==='x'?'width':'height'],box[key]+change)));
    };
    layer.append(target);
  }
  pointer(event,target){
    if(event.button!==0)return;event.preventDefault();event.stopPropagation();
    const resizing=event.target.classList.contains('part-resize'),startX=event.clientX,startY=event.clientY,parent=this.parent(),rect=parent.getBoundingClientRect();
    if(!rect.width||!rect.height)return;this.host.checkpoint();this.item.parts ||= {};this.arrange(this.part.parent);const original=clone(this.config);
    this.dragging=true;target.setPointerCapture(event.pointerId);
    target.onpointermove=e=>{
      const dx=(e.clientX-startX)/rect.width*100,dy=(e.clientY-startY)/rect.height*100,conf=this.config;
      if(resizing){conf.width=Math.max(1,Math.min(100-original.x,original.width+dx));conf.height=Math.max(1,Math.min(100-original.y,original.height+dy));}
      else{conf.x=Math.max(0,Math.min(100-original.width,original.x+dx));conf.y=Math.max(0,Math.min(100-original.height,original.y+dy));}
      this.paint();const box=this.element().getBoundingClientRect(),frame=this.root.querySelector('.widget-frame').getBoundingClientRect();Object.assign(target.style,{left:box.left-frame.left+'px',top:box.top-frame.top+'px',width:box.width+'px',height:box.height+'px'});
    };
    const end=()=>{target.onpointermove=target.onpointerup=target.onpointercancel=null;this.dragging=false;this.changed();};target.onpointerup=target.onpointercancel=end;
  }
  fields(){
    const root=this.root.querySelector('.widget-part-fields'),part=this.part;
    if(!part){root.innerHTML='<p>HDMI ist ein einzelnes Bildelement. Seine Position und Größe bearbeitest du im Ansichts-Editor.</p>';return;}
    const conf=this.config,box=this.box(),el=this.element(),style=el?getComputedStyle(el):null,parent=this.parent();
    const field=(key,label,value,min,max,step=.1)=>`<label>${label}<input data-field="${key}" type="number" value="${Math.round(value*100)/100}" min="${min}" max="${max}" step="${step}"></label>`;
    const size=conf.font_size ?? Math.max(1,Math.min(100,(parseFloat(style?.fontSize)||16)/(parent?.clientHeight||200)*100));
    root.innerHTML=`<div class="toggle"><label><input data-visible type="checkbox" ${this.enabled(part)?'checked':''}>Element anzeigen</label></div><h3>Position & Größe</h3><div class="form-grid">${field('x','Inhalt links (%)',box.x,0,99)}${field('y','Inhalt oben (%)',box.y,0,99)}${field('width','Inhalt Breite (%)',box.width,1,100)}${field('height','Inhalt Höhe (%)',box.height,1,100)}</div>${part.text?`<h3>Text & Schrift</h3><label class="field">Textquelle<select data-text-mode>${options({live:'Original / Live-Inhalt',custom:'Eigener Text'},conf.text===undefined?'live':'custom')}</select></label>${conf.text!==undefined?`<label class="field">Eigener Inhalt<textarea data-text maxlength="2000">${escapeHTML(conf.text)}</textarea></label>`:''}<div class="form-grid">${field('font_size','Inhalt Schriftgröße (%)',size,1,100)}<label>Schrift<select aria-label="Inhalt Schrift" data-choice="font">${options({'':'Vom Widget',sans:'Sans Serif',serif:'Serif',mono:'Monospace'},conf.font || '')}</select></label><label>Schriftschnitt<select data-choice="font_weight">${options({'':'Vom Widget',400:'Normal',500:'Medium',600:'Halbfett',700:'Fett'},String(conf.font_weight || ''))}</select></label><label>Textausrichtung<select data-choice="align">${options({'':'Vom Widget',left:'Links',center:'Mittig',right:'Rechts'},conf.align || '')}</select></label><label>Inhalt Textfarbe<input data-color type="color" value="${conf.color || this.item.color}"></label><button class="small" data-theme-color>Widget-Farbe verwenden</button></div>`:''}<h3>Darstellung</h3><div class="form-grid">${field('opacity','Inhalt Deckkraft',conf.opacity ?? 1,0,1,.05)}${field('z_index','Inhalt Ebene',conf.z_index ?? 2,0,30,1)}${field('radius','Inhalt Rundung (%)',conf.radius ?? 0,0,50,1)}${['cover','picture'].includes(part.id)?`<label>Bild einpassen<select data-choice="fit">${options({'':'Vom Widget',contain:'Vollständig',cover:'Ausfüllen',fill:'Strecken'},conf.fit || '')}</select></label>`:''}</div><div class="links"><button class="small delete" data-delete-part>Inhalt entfernen</button><button class="small" data-reset-part>Element zurücksetzen</button></div>`;
    root.querySelector('[data-visible]').onchange=e=>this.update('visible',e.target.checked);
    root.querySelector('[data-delete-part]').onclick=()=>this.update('visible',false);
    root.querySelector('[data-reset-part]').onclick=()=>{this.host.checkpoint();if(this.item.parts)delete this.item.parts[this.partId];const flag={label:'show_label',cover:'show_cover',progress:'show_progress',playback:'show_playback_icon',volume:'show_volume'}[this.partId];if(flag)this.item[flag]=flag!=='show_playback_icon';this.changed();};
    root.querySelectorAll('[data-field]').forEach(input=>input.onchange=()=>this.update(input.dataset.field,Math.max(Number(input.min),Math.min(Number(input.max),Number(input.value)||Number(input.min)))));
    root.querySelectorAll('[data-choice]').forEach(input=>input.onchange=()=>this.update(input.dataset.choice,input.value===''?null:input.dataset.choice==='font_weight'?Number(input.value):input.value));
    if(part.text){root.querySelector('[data-text-mode]').onchange=e=>this.update('text',e.target.value==='custom'?(el?.textContent || ''):null);const text=root.querySelector('[data-text]');if(text)text.onchange=()=>this.update('text',text.value);root.querySelector('[data-color]').onchange=e=>this.update('color',e.target.value);root.querySelector('[data-theme-color]').onclick=()=>this.update('color',null);}
  }
  binding(){
    const root=this.root.querySelector('.widget-binding');
    if(this.item.kind==='clock'){
      root.innerHTML=`<div class="form-grid"><label>Uhr-Anzeige<select data-clock-view>${options({both:'Uhrzeit und Datum',time:'Nur Uhrzeit',date:'Nur Datum',none:'Beides ausgeblendet'},this.item.parts?.time?.visible===false?(this.item.parts?.date?.visible===false?'none':'date'):this.item.parts?.date?.visible===false?'time':'both')}</select></label><label>Zeitformat<select data-clock="clock_time_format">${options({'24h':'24 Stunden','12h':'12 Stunden'},this.item.clock_time_format || '24h')}</select></label><label>Datumsformat<select data-clock="clock_date_format">${options({long:'Dienstag, 6. Oktober',short:'06.10.2026',weekday:'Dienstag',iso:'2026-10-06'},this.item.clock_date_format || 'long')}</select></label></div>`;
      root.querySelector('[data-clock-view]').onchange=e=>{this.host.checkpoint();this.item.parts ||= {};for(const id of ['time','date']){this.item.parts[id] ||= {};this.item.parts[id].visible=e.target.value==='both'||e.target.value===id;}this.changed();};
      root.querySelectorAll('[data-clock]').forEach(input=>input.onchange=()=>{this.host.checkpoint();this.item[input.dataset.clock]=input.value;this.changed();});
    }else root.innerHTML=`<p class="note">${this.item.entity_id?'Verbunden mit '+escapeHTML(this.item.entity_id)+'. ':''}Die Entität und allgemeinen Widget-Einstellungen bleiben im Ansichts-Editor verfügbar. „Inhalt-Layout zurücksetzen“ stellt die Elemente des gewählten Widget-Stils wieder her; Entität, äußere Position und Größe bleiben erhalten.</p>`;
  }
}
