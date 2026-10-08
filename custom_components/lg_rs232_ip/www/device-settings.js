/* LG menu order on Home Assistant's device page. No HA source files are changed.
 * Reuse HA's own entity cards, including disabled entities and service controls.
 * Unknown frontend contracts fall back to the unchanged HA configuration card.
 */
(() => {
  const installed = Symbol.for("lg_rs232_ip.device-settings.installed");
  const nested = Symbol.for("lg_rs232_ip.device-settings.nested");
  const currentView = Symbol.for("lg_rs232_ip.device-settings.view");
  const tag = "lg-display-device-settings";
  const nativeTag = "ha-device-entities-card";
  let catalog;

  function context(card) {
    const entries = card.entities;
    if (card[nested] || !card.hass || !Array.isArray(entries) || !entries.length)
      return null;
    const first = entries[0];
    if (!first.device_id || !first.config_entry_id) return null;
    // Never infer ownership from a friendly name, entity_id, or LG manufacturer.
    if (!entries.every((e) => e.platform === "lg_rs232_ip" &&
        e.entity_category === "config" && e.device_id === first.device_id &&
        e.config_entry_id === first.config_entry_id && typeof e.unique_id === "string"))
      return null;
    return `${first.device_id}:${first.config_entry_id}`;
  }
  function entityKey(entry) {
    const prefix = `${entry.config_entry_id}_`;
    return entry.unique_id.startsWith(prefix)
      ? `${entry.entity_id.split(".")[0]}:${entry.unique_id.slice(prefix.length)}`
      : null;
  }

  class LGDeviceSettings extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._cards = new Map();
      this._groups = new Map();
      this.shadowRoot.innerHTML = `<style>
        :host { display:block; color:var(--primary-text-color); }
        .toolbar { display:flex; align-items:center; justify-content:space-between;
          gap:12px; padding:20px 16px 12px; }
        h2 { margin:0; font-size:var(--ha-font-size-xl,24px); font-weight:400; }
        button { background:none; border:0; color:var(--primary-color); cursor:pointer;
          font:inherit; padding:10px 4px; border-radius:6px; }
        button:focus-visible, summary:focus-visible { outline:2px solid var(--primary-color); outline-offset:-2px; }
        details { border-top:1px solid var(--divider-color); }
        summary { cursor:pointer; padding:18px 20px; font-size:16px; font-weight:500; }
        .sections { padding:0 8px 12px; }
        ha-device-entities-card { margin:0 0 8px; }
        .count { color:var(--secondary-text-color); font-size:12px; margin-inline-start:8px; }
        [hidden] { display:none !important; }
      </style><ha-card outlined><div class="toolbar"><h2></h2><button type="button"></button></div>
        <div class="menu"></div><div class="standard" hidden></div></ha-card>`;
      this._menu = this.shadowRoot.querySelector(".menu");
      this._standard = this.shadowRoot.querySelector(".standard");
      this._toggle = this.shadowRoot.querySelector("button");
      this._toggle.addEventListener("click", () => {
        this._plain = !this._plain;
        this._updateMode();
        this._sync();
      });
    }
    update(owner) {
      this._owner = owner;
      this._de = (owner.hass.language || owner.hass.locale?.language || "en").startsWith("de");
      this.shadowRoot.querySelector("h2").textContent = owner.header;
      this._updateMode();
      this._sync();
    }
    _updateMode() {
      this._toggle.textContent = this._plain
        ? (this._de ? "LG-Menü" : "LG menu")
        : (this._de ? "Alphabetische Liste" : "Alphabetical list");
      this._toggle.setAttribute("aria-label", this._de
        ? "Darstellung der Geräteeinstellungen wechseln" : "Change device settings presentation");
      this._menu.hidden = !!this._plain;
      this._standard.hidden = !this._plain;
    }
    _title(item) { return item.title[this._de ? "de" : "en"]; }
    _nativeCard(id, entries, title, parent) {
      let record = this._cards.get(id);
      if (!record) {
        const card = document.createElement(nativeTag);
        card[nested] = true;
        record = { card };
        this._cards.set(id, record);
        parent.append(card);
      }
      const { card } = record, owner = this._owner;
      card.hass = owner.hass;
      card.deviceName = owner.deviceName;
      card.header = title;
      // Retain HA row elements/focus across ordinary hass state updates.
      if (!record.entries || entries.length !== record.entries.length ||
          entries.some((entry, i) => entry !== record.entries[i])) {
        card.entities = entries;
        record.entries = entries;
      }
      // Preserve a user's per-section "show disabled entities" choice.
      if (record.showHidden !== owner.showHidden) {
        card.showHidden = !!owner.showHidden;
        record.showHidden = owner.showHidden;
      }
      return card;
    }
    _sync() {
      if (!this._owner) return;
      const owner = this._owner;
      if (this._plain) {
        this._nativeCard("standard", owner.entities, owner.header, this._standard);
        return;
      }
      const remaining = new Set(owner.entities);
      const byKey = new Map();
      for (const entry of owner.entities) {
        const key = entityKey(entry);
        if (!byKey.has(key)) byKey.set(key, []);
        byKey.get(key).push(entry);
      }
      const usedGroups = new Set(), usedCards = new Set();
      const groups = catalog.groups.map((group) => ({ ...group,
        sections: group.sections.map((section) => ({ ...section,
          entries: section.entities.flatMap((key) => byKey.get(key) || []),
        })),
      }));
      for (const group of groups) for (const section of group.sections)
        for (const entry of section.entries) remaining.delete(entry);
      // New/unknown entities are always accessible, never silently filtered out.
      if (remaining.size) groups.push({ id:"other", title:{de:"Weitere Einstellungen",en:"Other settings"},
        sections:[{id:"other",title:{de:"Weitere Einstellungen",en:"Other settings"},entries:[...remaining]}] });
      for (const group of groups) {
        const sections = group.sections.filter((section) => section.entries.length);
        if (!sections.length) continue;
        usedGroups.add(group.id);
        let block = this._groups.get(group.id);
        if (!block) {
          const details = document.createElement("details");
          details.dataset.group = group.id;
          const summary = document.createElement("summary");
          const label = document.createElement("span"), count = document.createElement("span");
          count.className = "count";
          summary.append(label, count);
          const content = document.createElement("div");
          content.className = "sections";
          details.append(summary, content);
          block = { details, label, count, content };
          this._groups.set(group.id, block);
          this._menu.append(details);
        }
        block.label.textContent = this._title(group);
        block.count.textContent = String(sections.reduce((n,s) => n+s.entries.length,0));
        for (const [index, section] of sections.entries()) {
          const id = `${group.id}/${section.id}`;
          usedCards.add(id);
          const card = this._nativeCard(id, section.entries, this._title(section), block.content);
          if (block.content.children[index] !== card)
            block.content.insertBefore(card, block.content.children[index] || null);
        }
        // insertBefore below preserves existing elements, open state and focus.
      }
      const desired = groups.filter((g) => usedGroups.has(g.id)).map((g) => this._groups.get(g.id).details);
      desired.forEach((node, i) => {
        if (this._menu.children[i] !== node) this._menu.insertBefore(node, this._menu.children[i] || null);
      });
      for (const [id, block] of this._groups) if (!usedGroups.has(id)) {
        block.details.remove(); this._groups.delete(id);
      }
      for (const [id, record] of this._cards) if (id !== "standard" && !usedCards.has(id)) {
        record.card.remove(); this._cards.delete(id);
      }
    }
  }

  async function install() {
    const response = await fetch("/lg_rs232_ip/device-menu.json", {
      cache:"no-cache", signal:AbortSignal.timeout(5000),
    });
    if (!response.ok) return;
    const data = await response.json();
    if (data.version !== 1 || !Array.isArray(data.groups)) return;
    // Validate the whole catalog before replacing any native rendering.
    const ids = new Set(), keys = new Set();
    for (const group of data.groups) {
      if (!group.id || ids.has(group.id) || !group.title?.de || !group.title?.en || !Array.isArray(group.sections)) return;
      ids.add(group.id);
      for (const section of group.sections) {
        const id = `${group.id}/${section.id}`;
        if (!section.id || ids.has(id) || !section.title?.de || !section.title?.en || !Array.isArray(section.entities)) return;
        ids.add(id);
        for (const key of section.entities) {
          if (typeof key !== "string" || !/^[a-z_]+:[a-z0-9_]+$/.test(key) || keys.has(key)) return;
          keys.add(key);
        }
      }
    }
    catalog = data;
    await customElements.whenDefined(nativeTag);
    const prototype = customElements.get(nativeTag).prototype;
    if (prototype[installed] || typeof prototype.render !== "function") return;
    if (!customElements.get(tag)) customElements.define(tag, LGDeviceSettings);
    const original = prototype.render;
    const shouldUpdate = prototype.shouldUpdate;
    Object.defineProperty(prototype, installed, {value:true});
    prototype.render = function (...args) {
      const key = context(this);
      if (!key) {
        this[currentView] = null;
        return original.apply(this, args);
      }
      try {
        let view = this[currentView];
        if (!view || view.contextKey !== key) {
          view = document.createElement(tag);
          view.contextKey = key;
          this[currentView] = view;
        }
        view.update(this);
        return view;
      } catch (_) {
        this[currentView] = null;
        return original.apply(this, args);
      }
    };
    // HA 2025.x forwards hass-only updates directly to its own row list and
    // skips render(). Forward those updates to our nested native cards too.
    if (typeof shouldUpdate === "function") prototype.shouldUpdate = function (...args) {
      try {
        if (this[currentView] && context(this) === this[currentView].contextKey)
          this[currentView].update(this);
      } catch (_) { this[currentView] = null; return true; }
      return shouldUpdate.apply(this, args);
    };
    // Handle a device page already mounted before this optional module loads.
    function refresh(root) {
      for (const node of root.querySelectorAll("*")) {
        if (node.localName === nativeTag && context(node)) node.requestUpdate?.();
        if (node.shadowRoot) refresh(node.shadowRoot);
      }
    }
    refresh(document);
  }
  install().catch(() => { /* Offline catalog / changed HA: retain native view. */ });
})();
