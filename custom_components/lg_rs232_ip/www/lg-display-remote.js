/* LG Professional Display remote. Bundled locally; no runtime dependencies. MIT. */
const TEXT = {
  en: {
    title: "LG remote",
    on: "On",
    off: "Standby",
    unknown: "State unknown",
    unavailable: "Unavailable",
    missing: "Choose an LG display in the card settings.",
    powerOn: "Turn on",
    powerOff: "Turn off",
    source: "Input",
    selectSource: "Choose input",
    up: "Up",
    down: "Down",
    left: "Left",
    right: "Right",
    select: "OK",
    home: "Home",
    back: "Back",
    menu: "Menu",
    exit: "Exit",
    navigation: "Navigation",
    volume: "Display volume",
    louder: "Volume up",
    quieter: "Volume down",
    mute: "Mute",
    unmute: "Unmute",
    noSignal: "No HDMI signal",
    signal: "HDMI signal present",
    content: "Temporary content active",
    clear: "Return to input",
    message: "Text overlay",
    messageHint: "Message on the display",
    send: "Send",
    sent: "Command sent",
    failed: "Command failed. Check the display connection.",
    preview: "Display preview",
    enlarge: "Enlarge preview",
    previewMissing: "Preview unavailable",
    screenshot: "Screenshot",
    display: "LG display",
    name: "Title (optional)",
    camera: "Preview camera (optional)",
    none: "None",
    showSources: "Show inputs",
    showVolume: "Show display volume",
    showPreview: "Show preview",
    showMessage: "Show text overlay controls",
    editorHint:
      "Select the LG integration's display entity. These keys control the display itself.",
    more: "Entity details",
    queued: "queued",
  },
  de: {
    title: "LG-Fernbedienung",
    on: "Ein",
    off: "Standby",
    unknown: "Status unbekannt",
    unavailable: "Nicht erreichbar",
    missing: "In den Karteneinstellungen ein LG-Display auswählen.",
    powerOn: "Einschalten",
    powerOff: "Ausschalten",
    source: "Eingang",
    selectSource: "Eingang wählen",
    up: "Oben",
    down: "Unten",
    left: "Links",
    right: "Rechts",
    select: "OK",
    home: "Home",
    back: "Zurück",
    menu: "Menü",
    exit: "Beenden",
    navigation: "Navigation",
    volume: "Display-Lautstärke",
    louder: "Lauter",
    quieter: "Leiser",
    mute: "Stummschalten",
    unmute: "Ton einschalten",
    noSignal: "Kein HDMI-Signal",
    signal: "HDMI-Signal vorhanden",
    content: "Temporärer Inhalt aktiv",
    clear: "Zum Eingang zurück",
    message: "Text einblenden",
    messageHint: "Nachricht auf dem Display",
    send: "Senden",
    sent: "Befehl gesendet",
    failed: "Befehl fehlgeschlagen. Verbindung zum Display prüfen.",
    preview: "Display-Vorschau",
    enlarge: "Vorschau vergrößern",
    previewMissing: "Vorschau nicht verfügbar",
    screenshot: "Screenshot",
    display: "LG-Display",
    name: "Titel (optional)",
    camera: "Vorschaukamera (optional)",
    none: "Keine",
    showSources: "Eingänge anzeigen",
    showVolume: "Display-Lautstärke anzeigen",
    showPreview: "Vorschau anzeigen",
    showMessage: "Textmeldungen anbieten",
    editorHint:
      "Die Display-Entität der LG-Integration auswählen. Die Tasten bedienen das Display selbst.",
    more: "Entitätsdetails",
    queued: "in Warteschlange",
  },
};
const language = (hass) =>
  (hass?.locale?.language || hass?.language || "en").startsWith("de")
    ? "de"
    : "en";
const isLG = (hass, id) =>
  id.startsWith("media_player.") &&
  (hass.entities?.[id]?.platform === "lg_rs232_ip" ||
    hass.states[id]?.attributes.integration_domain === "lg_rs232_ip");
const displays = (hass) =>
  Object.keys(hass?.states || {}).filter((id) => isLG(hass, id));
const cameraFor = (hass, id) => {
  const device = hass?.entities?.[id]?.device_id;
  return device
    ? Object.keys(hass.states).find(
        (key) =>
          key.startsWith("camera.") &&
          hass.entities?.[key]?.device_id === device &&
          hass.states[key].attributes.preview_mode === "periodic_screenshot",
      )
    : undefined;
};
const fire = (node, name, detail) =>
  node.dispatchEvent(
    new CustomEvent(name, { detail, bubbles: true, composed: true }),
  );
const icon = (name) =>
  `<ha-icon icon="mdi:${name}" aria-hidden="true"></ha-icon>`;
const STYLE = `
  :host { display:block; color:var(--primary-text-color); }
  * { box-sizing:border-box; }
  [hidden] { display:none !important; }
  ha-card { display:block; overflow:hidden; padding:20px; height:100%; }
  header { display:flex; align-items:center; gap:12px; margin-bottom:18px; }
  .heading { flex:1; min-width:0; }
  h2 { margin:0; font-size:19px; font-weight:600; line-height:1.4; overflow-wrap:anywhere; }
  .status, .caption, .hint { color:var(--secondary-text-color); font-size:13px; line-height:1.5; }
  .status { display:flex; align-items:center; gap:6px; margin-top:3px; }
  .dot { width:7px; height:7px; border-radius:50%; background:var(--disabled-text-color,#888); }
  .dot.on { background:var(--success-color,#43a047); }
  button, select, input, textarea { font:inherit; color:inherit; }
  button { min-width:44px; min-height:44px; border:0; border-radius:12px; cursor:pointer;
    background:var(--secondary-background-color,#f2f3f5); display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:10px; }
  button:hover:enabled { background:var(--divider-color,#ddd); }
  button:active:enabled { transform:scale(.97); }
  button:focus-visible, select:focus-visible, input:focus-visible, textarea:focus-visible, summary:focus-visible {
    outline:2px solid var(--primary-color,#03a9f4); outline-offset:3px; }
  button:disabled, select:disabled, input:disabled, textarea:disabled { opacity:.4; cursor:default; }
  button.power { border-radius:50%; width:48px; height:48px; }
  button.power.active, button.primary { background:var(--primary-color,#03a9f4); color:var(--text-primary-color,#fff); }
  ha-icon { width:24px; height:24px; --mdc-icon-size:24px; flex-shrink:0; }
  .source { display:flex; align-items:center; gap:12px; margin-bottom:20px; }
  select { flex:1; width:100%; min-width:0; border:1px solid var(--divider-color,#ddd); background:var(--card-background-color,#fff); border-radius:10px; padding:12px; }
  .navigation { max-width:300px; margin:0 auto; }
  .shortcuts { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:14px; }
  .shortcuts button { flex-direction:column; font-size:11px; gap:4px; }
  .pad { display:grid; grid-template-columns:repeat(3,1fr); gap:6px; padding:12px; border-radius:50%;
    background:var(--secondary-background-color,#f2f3f5); width:216px; height:216px; margin:auto; }
  .pad button { border-radius:50%; background:transparent; }
  .pad .ok { background:var(--card-background-color,#fff); font-weight:600; box-shadow:0 1px 5px #0002; }
  .up {grid-area:1/2} .left {grid-area:2/1} .ok {grid-area:2/2} .right {grid-area:2/3} .down {grid-area:3/2}
  .volume { border-top:1px solid var(--divider-color,#ddd); margin-top:20px; padding-top:16px; }
  .volume-title {display:flex; justify-content:space-between; font-size:13px; margin-bottom:8px;}
  .volume-controls {display:flex; align-items:center; gap:8px;}
  input[type=range] { min-width:0; flex:1; width:100%; accent-color:var(--primary-color,#03a9f4); height:44px; margin:0; }
  .presentation { margin-top:16px; display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
  .presentation span {flex:1; font-size:13px;}
  details {border-top:1px solid var(--divider-color,#ddd); margin-top:16px; padding-top:12px;}
  summary {cursor:pointer; font-size:14px; padding:8px 0;}
  textarea {width:100%; min-height:80px; resize:vertical; background:var(--card-background-color,#fff); border:1px solid var(--divider-color,#ddd); border-radius:10px; padding:12px; margin:8px 0;}
  .send-row {display:flex; justify-content:flex-end;}
  .feedback {font-size:13px; line-height:1.5; overflow-wrap:anywhere; margin-top:12px;}
  .error {color:var(--error-color,#db4437);}
  .preview {margin:0 0 20px; border-radius:12px; overflow:hidden; background:var(--secondary-background-color,#f2f3f5);}
  .preview img {display:block; width:100%; aspect-ratio:16/9; object-fit:contain; background:#111;}
  .preview-open {display:block; width:100%; padding:0; border-radius:0; background:transparent;}
  figcaption {padding:8px 12px;}
  .preview-placeholder {padding:24px 12px; text-align:center; font-size:13px; color:var(--secondary-text-color);}
`;

// Read length-delimited JPEG parts from our authenticated HA camera endpoint.
// Explicit fetch cancellation also releases connections reliably in WebKit.
async function* jpegFrames(response) {
  if (
    !response.ok ||
    !response.headers
      .get("Content-Type")
      ?.startsWith("application/octet-stream") ||
    !response.body
  )
    throw new Error("Preview stream unavailable");
  const reader = response.body.getReader();
  let buffer = new Uint8Array(),
    length = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) throw new Error("Preview stream ended");
      if (buffer.length + value.length > 6 * 1024 * 1024)
        throw new Error("Preview frame too large");
      const joined = new Uint8Array(buffer.length + value.length);
      joined.set(buffer);
      joined.set(value, buffer.length);
      buffer = joined;
      while (true) {
        if (length === null) {
          let end = -1;
          for (let i = 0; i + 3 < buffer.length; i++) {
            if (
              buffer[i] === 13 &&
              buffer[i + 1] === 10 &&
              buffer[i + 2] === 13 &&
              buffer[i + 3] === 10
            ) {
              end = i;
              break;
            }
          }
          if (end < 0) {
            if (buffer.length > 8192)
              throw new Error("Invalid preview headers");
            break;
          }
          const headers = new TextDecoder().decode(buffer.subarray(0, end));
          const match = /Content-Length:\s*(\d+)/i.exec(headers);
          length = match ? Number(match[1]) : 0;
          if (
            !/Content-Type:\s*image\/jpeg/i.test(headers) ||
            length < 1 ||
            length > 5 * 1024 * 1024
          )
            throw new Error("Invalid preview frame");
          buffer = buffer.subarray(end + 4);
        }
        if (buffer.length < length) break;
        yield buffer.slice(0, length);
        buffer = buffer.subarray(length);
        length = null;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
}

class LGDisplayRemote extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._busy = false;
    this._previewVisible = false;
    this._visibilityChanged = () => this._update();
  }
  connectedCallback() {
    document.addEventListener("visibilitychange", this._visibilityChanged);
    this._observePreview();
  }
  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._visibilityChanged);
    this._previewObserver?.disconnect();
    this._previewObserver = undefined;
    this._previewVisible = false;
    this._stopPreview();
  }
  _observePreview() {
    this._previewObserver?.disconnect();
    if (!this.isConnected || !this._get("preview")) return;
    this._previewObserver = new IntersectionObserver((entries) => {
      this._previewVisible = entries.some((entry) => entry.isIntersecting);
      this._update();
    });
    this._previewObserver.observe(this._get("preview"));
  }
  _stopPreview() {
    this._previewAbort?.abort();
    this._previewAbort = undefined;
    this._get("image")?.removeAttribute("src");
    if (this._previewBlob) URL.revokeObjectURL(this._previewBlob);
    this._previewBlob = undefined;
    this._previewKey = undefined;
    clearTimeout(this._previewRetryTimer);
    this._previewRetryTimer = undefined;
    this._previewFailed = false;
  }
  async _startPreview(url) {
    const controller = new AbortController();
    this._previewAbort = controller;
    try {
      const response = await fetch(
        `${url}${url.includes("?") ? "&" : "?"}lg_preview=frames`,
        {
          signal: controller.signal,
          cache: "no-store",
          credentials: "same-origin",
        },
      );
      for await (const bytes of jpegFrames(response)) {
        if (controller.signal.aborted) break;
        const previous = this._previewBlob;
        this._previewBlob = URL.createObjectURL(
          new Blob([bytes], { type: "image/jpeg" }),
        );
        this._get("image").src = this._previewBlob;
        if (previous) URL.revokeObjectURL(previous);
        this._previewFailed = false;
        this._update();
      }
    } catch (error) {
      if (!controller.signal.aborted) this._previewError();
    }
  }
  _previewError() {
    this._previewFailed = true;
    this._get("image").hidden = true;
    this._get("preview-placeholder").hidden = false;
    if (
      !this._previewRetryTimer &&
      this.isConnected &&
      this._previewVisible &&
      document.visibilityState === "visible"
    ) {
      this._previewRetryTimer = setTimeout(() => {
        this._stopPreview();
        this._update();
      }, 2000);
    }
  }
  static getConfigElement() {
    return document.createElement("lg-display-remote-editor");
  }
  static getStubConfig(hass) {
    const entity = displays(hass)[0] || "";
    const camera = cameraFor(hass, entity);
    return { entity, ...(camera ? { camera_entity: camera } : {}) };
  }
  getCardSize() {
    return this._config?.camera_entity && this._config.show_preview !== false
      ? 13
      : 10;
  }
  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }
  setConfig(config) {
    if (
      !config ||
      typeof config.entity !== "string" ||
      !/^media_player\.[\w]+$/.test(config.entity)
    ) {
      throw new Error(
        "Choose an LG media_player entity / LG-Display auswählen",
      );
    }
    if (config.camera_entity && !/^camera\.[\w]+$/.test(config.camera_entity))
      throw new Error("Invalid camera entity");
    for (const key of [
      "show_sources",
      "show_volume",
      "show_preview",
      "show_message",
    ]) {
      if (config[key] !== undefined && typeof config[key] !== "boolean")
        throw new Error(`${key} must be true or false`);
    }
    if (config.name !== undefined && typeof config.name !== "string")
      throw new Error("name must be a string");
    if (this._config?.entity !== config.entity) this._feedback = "";
    this._config = { ...config };
    this._built = false;
    this._update();
  }
  set hass(hass) {
    this._hass = hass;
    this._update();
  }
  get hass() {
    return this._hass;
  }
  _get(id) {
    return this.shadowRoot.getElementById(id);
  }
  _build() {
    this._stopPreview();
    const t = TEXT[language(this._hass)];
    this._language = language(this._hass);
    const key = (command, image, cls = "", label = false) =>
      `<button class="${cls}" data-remote="${command}" title="${t[command]}" aria-label="${t[command]}">${image ? icon(image) : t[command]}${label ? `<span>${t[command]}</span>` : ""}</button>`;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>
      <header><div class="heading"><h2 id="title"></h2><div class="status"><span id="dot" class="dot"></span><span id="status"></span></div></div>
        <button id="more" title="${t.more}" aria-label="${t.more}">${icon("dots-horizontal")}</button><button class="power" id="power">${icon("power")}</button></header>
      <figure class="preview" id="preview" hidden><button class="preview-open" id="preview-open" aria-label="${t.enlarge}" title="${t.enlarge}"><img id="image" alt="${t.preview}" hidden><div id="preview-placeholder" class="preview-placeholder">${t.previewMissing}</div></button><figcaption class="caption" id="capture"></figcaption></figure>
      <div class="source" id="sources"><label for="source">${t.source}</label><select id="source" aria-label="${t.source}"></select></div>
      <div class="navigation" role="group" aria-label="${t.navigation}"><div class="pad">
        ${key("up", "chevron-up", "up")}${key("left", "chevron-left", "left")}${key("select", null, "ok")}${key("right", "chevron-right", "right")}${key("down", "chevron-down", "down")}
      </div><div class="shortcuts">${key("back", "arrow-u-left-top", "", true)}${key("home", "home-outline", "", true)}${key("menu", "menu", "", true)}${key("exit", "close", "", true)}</div></div>
      <div class="volume" id="volume"><div class="volume-title"><label for="level">${t.volume}</label><span id="volume-value"></span></div><div class="volume-controls">
        <button id="quieter" title="${t.quieter}" aria-label="${t.quieter}">${icon("minus")}</button><input id="level" type="range" min="0" max="100" step="1" aria-label="${t.volume}">
        <button id="louder" title="${t.louder}" aria-label="${t.louder}">${icon("plus")}</button><button id="mute"></button></div></div>
      <div id="presentation" class="presentation" hidden><span id="presentation-status"></span><button id="clear">${icon("exit-to-app")} ${t.clear}</button></div>
      <details id="message-panel" hidden><summary>${t.message}</summary><textarea id="message" maxlength="1000" aria-label="${t.messageHint}" placeholder="${t.messageHint}"></textarea><div class="send-row"><button id="send" class="primary">${icon("send")} ${t.send}</button></div></details>
      <div id="feedback" class="feedback" role="status" aria-live="polite" hidden></div>
    </ha-card>`;
    this.shadowRoot.querySelectorAll("[data-remote]").forEach((button) => {
      button.addEventListener("click", () =>
        this._remote(button.dataset.remote),
      );
      button.addEventListener("keydown", (event) => {
        const command = {
          ArrowUp: "up",
          ArrowDown: "down",
          ArrowLeft: "left",
          ArrowRight: "right",
        }[event.key];
        if (command) {
          event.preventDefault();
          if (!event.repeat) this._remote(command);
        }
      });
    });
    this._get("power").onclick = () =>
      this._call(
        "media_player",
        this._state().state === "off" ? "turn_on" : "turn_off",
        {},
        true,
      );
    this._get("more").onclick = () =>
      fire(this, "hass-more-info", { entityId: this._config.entity });
    this._get("source").onchange = (event) =>
      this._call("media_player", "select_source", {
        source: event.target.value,
      });
    this._get("quieter").onclick = () =>
      this._call("media_player", "volume_down");
    this._get("louder").onclick = () => this._call("media_player", "volume_up");
    this._get("mute").onclick = () =>
      this._call("media_player", "volume_mute", {
        is_volume_muted: !this._state().attributes.is_volume_muted,
      });
    this._get("level").oninput = (event) => {
      this._volumeEditing = true;
      this._get("volume-value").textContent = `${event.target.value}%`;
    };
    this._get("level").onchange = (event) => {
      this._volumeEditing = false;
      this._call("media_player", "volume_set", {
        volume_level: Number(event.target.value) / 100,
      });
    };
    this._get("clear").onclick = () =>
      this._call("lg_rs232_ip", "clear_content");
    this._get("message").oninput = () => this._update();
    this._get("send").onclick = async () => {
      const message = this._get("message").value.trim();
      if (message && this._state().attributes.native_web_enabled)
        await this._call("lg_rs232_ip", "show_toast", { message });
    };
    this._get("image").onerror = () => this._previewError();
    this._get("preview-open").onclick = () =>
      fire(this, "hass-more-info", { entityId: this._config.camera_entity });
    this._previewKey = undefined;
    this._sourceSignature = undefined;
    this._volumeEditing = false;
    this._built = true;
    this._observePreview();
  }
  _state() {
    return this._hass?.states[this._config?.entity];
  }
  _ready(allowOff = false) {
    const state = this._state();
    return (
      !!state &&
      isLG(this._hass, this._config.entity) &&
      !this._busy &&
      (state.state === "on" || (allowOff && state.state === "off"))
    );
  }
  _remote(command) {
    return this._call("lg_rs232_ip", "send_remote_command", { command });
  }
  async _call(domain, service, data = {}, allowOff = false) {
    if (!this._ready(allowOff)) return;
    this._busy = true;
    const entity = this._config.entity;
    this._feedback = "";
    this._update();
    try {
      await this._hass.callService(domain, service, {
        ...data,
        entity_id: entity,
      });
      if (this._config.entity === entity) {
        this._feedback = TEXT[language(this._hass)].sent;
        this._error = false;
      }
    } catch (error) {
      if (this._config.entity === entity) {
        this._feedback = TEXT[language(this._hass)].failed;
        this._error = true;
      }
    } finally {
      this._busy = false;
      this._update();
    }
  }
  _update() {
    if (!this._config || !this._hass) return;
    if (!this._built || this._language !== language(this._hass)) this._build();
    const t = TEXT[this._language],
      s = this._state(),
      a = s?.attributes || {};
    const on = s?.state === "on",
      valid = !!s && isLG(this._hass, this._config.entity);
    this._get("title").textContent =
      this._config.name || a.friendly_name || t.title;
    let status = !valid
      ? t.missing
      : on
        ? t.on
        : s.state === "off"
          ? t.off
          : s.state === "unknown"
            ? t.unknown
            : t.unavailable;
    if (on && a.signal_present === false) status += ` · ${t.noSignal}`;
    this._get("status").textContent = status;
    this._get("dot").classList.toggle("on", on);
    const power = this._get("power");
    power.title = power.ariaLabel = on ? t.powerOff : t.powerOn;
    power.classList.toggle("active", on);
    power.disabled = !this._ready(true);
    this._get("more").disabled = !s;
    this.shadowRoot
      .querySelectorAll(
        "[data-remote], #source, #quieter, #louder, #mute, #clear, #message",
      )
      .forEach((e) => {
        e.disabled = !this._ready();
      });
    this._get("sources").hidden = this._config.show_sources === false;
    const sources = Array.isArray(a.source_list) ? a.source_list : [];
    const source = this._get("source"),
      signature = JSON.stringify([sources, a.source]);
    if (this._sourceSignature !== signature) {
      source.replaceChildren();
      if (!sources.includes(a.source))
        source.add(new Option(a.source || t.selectSource, ""));
      sources.forEach((value) => source.add(new Option(value, value)));
      this._sourceSignature = signature;
    }
    source.value = sources.includes(a.source) ? a.source : "";
    source.disabled ||= sources.length === 0;
    this._get("volume").hidden = this._config.show_volume === false;
    const level = this._get("level"),
      volume =
        typeof a.volume_level === "number" && Number.isFinite(a.volume_level)
          ? Math.round(a.volume_level * 100)
          : null;
    if (!this._volumeEditing) level.value = volume ?? 0;
    level.disabled = !this._ready() || volume === null;
    if (!this._volumeEditing)
      this._get("volume-value").textContent =
        volume === null ? "—" : `${volume}%`;
    const mute = this._get("mute"),
      muted = a.is_volume_muted === true;
    mute.title = mute.ariaLabel = muted ? t.unmute : t.mute;
    mute.setAttribute("aria-pressed", String(muted));
    mute.innerHTML = icon(muted ? "volume-off" : "volume-high");
    this._get("presentation").hidden =
      !a.presentation_active && !(a.presentation_queue_size > 0);
    this._get("presentation-status").textContent =
      `${t.content}${a.presentation_queue_size ? ` · ${a.presentation_queue_size} ${t.queued}` : ""}`;
    this._get("message-panel").hidden =
      !a.native_web_enabled || this._config.show_message === false;
    this._get("send").disabled =
      !this._ready() || !this._get("message").value.trim();
    const feedback = this._get("feedback");
    feedback.hidden = !this._feedback;
    feedback.textContent = this._feedback || "";
    feedback.classList.toggle("error", !!this._error);
    this._updatePreview(on);
  }
  _updatePreview(on) {
    const container = this._get("preview"),
      img = this._get("image"),
      t = TEXT[this._language];
    container.hidden =
      this._config.show_preview === false || !this._config.camera_entity;
    const camera = this._hass.states[this._config.camera_entity],
      a = camera?.attributes || {};
    const usable =
      !container.hidden &&
      on &&
      this.isConnected &&
      this._previewVisible &&
      document.visibilityState === "visible" &&
      camera &&
      a.collection_enabled !== false &&
      typeof a.entity_picture === "string" &&
      a.entity_picture.startsWith("/api/camera_proxy/");
    if (!usable) {
      this._stopPreview();
      img.hidden = true;
      this._previewKey = undefined;
      this._get("preview-placeholder").hidden = false;
      this._get("capture").textContent = t.screenshot;
      return;
    }
    // One persistent stream activates shared fast capture. Frame/state updates
    // must not reconnect it; hiding/unmounting the card closes it immediately.
    const key = a.entity_picture.replace(
      "/api/camera_proxy/",
      "/api/camera_proxy_stream/",
    );
    if (this._previewKey !== key) {
      this._stopPreview();
      this._previewKey = key;
      this._startPreview(key);
    }
    img.hidden = this._previewFailed || !!a.preview_error || !a.last_capture;
    this._get("preview-placeholder").hidden = !img.hidden;
    const captured = new Date(a.last_capture);
    this._get("capture").textContent =
      `${t.screenshot}${Number.isNaN(captured.getTime()) ? "" : ` · ${captured.toLocaleTimeString(this._language)}`}`;
  }
}

class LGDisplayRemoteEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  setConfig(config) {
    if (JSON.stringify(config) !== JSON.stringify(this._config))
      this._signature = undefined;
    this._config = { ...config };
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    this._render();
  }
  _render() {
    if (!this._config || !this._hass) return;
    const lang = language(this._hass),
      t = TEXT[lang];
    const signature = JSON.stringify([
      lang,
      displays(this._hass),
      Object.keys(this._hass.states).filter((id) => id.startsWith("camera.")),
    ]);
    // HA sends state updates frequently; leave focused text fields intact.
    if (this._signature === signature && this.shadowRoot.childElementCount)
      return;
    this._signature = signature;
    this.shadowRoot.innerHTML = `<style>${STYLE}label.field{display:grid;gap:6px;margin:16px 0}input[type=text]{width:100%;padding:12px;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:10px}.check{display:flex;align-items:center;gap:10px;margin:14px 0}input[type=checkbox]{width:20px;height:20px;accent-color:var(--primary-color,#03a9f4)}</style>
      <p class="hint">${t.editorHint}</p>
      <label class="field">${t.display}<select id="entity" aria-label="${t.display}"></select></label>
      <label class="field">${t.name}<input id="name" type="text" aria-label="${t.name}"></label>
      <label class="field">${t.camera}<select id="camera_entity" aria-label="${t.camera}"></select></label>
      ${[
        ["show_sources", "showSources"],
        ["show_volume", "showVolume"],
        ["show_preview", "showPreview"],
        ["show_message", "showMessage"],
      ]
        .map(
          ([id, label]) =>
            `<label class="check"><input id="${id}" type="checkbox">${t[label]}</label>`,
        )
        .join("")}`;
    for (const [key, ids] of [
      ["entity", displays(this._hass)],
      [
        "camera_entity",
        Object.keys(this._hass.states).filter(
          (id) =>
            id.startsWith("camera.") &&
            this._hass.states[id].attributes.preview_mode ===
              "periodic_screenshot",
        ),
      ],
    ]) {
      const select = this.shadowRoot.getElementById(key);
      select.add(new Option(key === "entity" ? t.display : t.none, ""));
      if (this._config[key] && !ids.includes(this._config[key]))
        ids.push(this._config[key]);
      ids
        .sort()
        .forEach((id) =>
          select.add(
            new Option(
              this._hass.states[id]?.attributes.friendly_name || id,
              id,
            ),
          ),
        );
      select.value = this._config[key] || "";
      select.onchange = () => {
        this._config[key] = select.value;
        if (!select.value) delete this._config[key];
        if (key === "entity") {
          const camera = cameraFor(this._hass, select.value);
          if (camera) this._config.camera_entity = camera;
          else delete this._config.camera_entity;
          this.shadowRoot.getElementById("camera_entity").value = camera || "";
        }
        this._changed();
      };
    }
    const name = this.shadowRoot.getElementById("name");
    name.value = this._config.name || "";
    name.oninput = () => {
      this._config.name = name.value;
      this._changed();
    };
    for (const key of [
      "show_sources",
      "show_volume",
      "show_preview",
      "show_message",
    ]) {
      const input = this.shadowRoot.getElementById(key);
      input.checked = this._config[key] !== false;
      input.onchange = () => {
        this._config[key] = input.checked;
        this._changed();
      };
    }
  }
  _changed() {
    fire(this, "config-changed", { config: { ...this._config } });
  }
}

if (!customElements.get("lg-display-remote"))
  customElements.define("lg-display-remote", LGDisplayRemote);
if (!customElements.get("lg-display-remote-editor"))
  customElements.define("lg-display-remote-editor", LGDisplayRemoteEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "lg-display-remote"))
  window.customCards.push({
    type: "lg-display-remote",
    name: "LG Display Remote",
    preview: true,
    description:
      "LG-Fernbedienung · Power, inputs, navigation, volume and optional preview.",
    documentationURL:
      "https://github.com/mvs90/lg_rs232_ip/blob/main/docs/DASHBOARD-CARD.md",
  });
