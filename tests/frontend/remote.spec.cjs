const { test, expect } = require("@playwright/test");
const path = require("node:path");
const { startPreviewServer } = require("./preview-server.cjs");
let previewServer;
test.beforeAll(async () => {
  previewServer = await startPreviewServer();
});
test.afterAll(async () => {
  await previewServer.close();
});
const script = path.resolve(
  "custom_components/lg_rs232_ip/www/lg-display-remote.js",
);
const initial = {
  entity_id: "media_player.display",
  state: "on",
  attributes: {
    integration_domain: "lg_rs232_ip",
    friendly_name: "Wohnzimmer",
    source: "HDMI 1",
    source_list: ["HDMI 1", "Apple TV", "HDMI 3"],
    volume_level: 0.3,
    is_volume_muted: false,
    signal_present: true,
    native_web_enabled: true,
  },
};
async function mount(page, config = {}) {
  await page.goto(previewServer.url);
  await page.addScriptTag({ path: script });
  await page.evaluate(
    ({ state, config }) => {
      window.calls = [];
      window.hass = {
        language: "de",
        states: { "media_player.display": state },
        entities: {
          "media_player.display": { platform: "lg_rs232_ip", device_id: "lg" },
        },
        callService: async (...args) => {
          window.calls.push(args);
          if (window.fail) throw Error("test failure");
          if (window.pending) await window.pending;
        },
      };
      window.card = document.createElement("lg-display-remote");
      card.setConfig({ entity: "media_player.display", ...config });
      card.hass = hass;
      document.body.append(card);
    },
    { state: initial, config },
  );
}
async function update(page, patch) {
  await page.evaluate((patch) => {
    hass.states["media_player.display"] = {
      ...hass.states["media_player.display"],
      ...patch,
    };
    card.hass = { ...hass };
  }, patch);
}
const calls = (page) => page.evaluate(() => window.calls);

test("power, navigation and custom input names target only selected LG", async ({
  page,
}) => {
  await mount(page);
  await page.getByRole("button", { name: "Ausschalten", exact: true }).click();
  await expect
    .poll(() => calls(page))
    .toEqual([
      ["media_player", "turn_off", { entity_id: "media_player.display" }],
    ]);
  await page.getByRole("button", { name: "Oben", exact: true }).click();
  await page.getByRole("button", { name: "OK", exact: true }).click();
  await page.getByRole("button", { name: "Zurück", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Eingang", exact: true })
    .selectOption("Apple TV");
  expect((await calls(page)).slice(1)).toEqual([
    [
      "lg_rs232_ip",
      "send_remote_command",
      { command: "up", entity_id: "media_player.display" },
    ],
    [
      "lg_rs232_ip",
      "send_remote_command",
      { command: "select", entity_id: "media_player.display" },
    ],
    [
      "lg_rs232_ip",
      "send_remote_command",
      { command: "back", entity_id: "media_player.display" },
    ],
    [
      "media_player",
      "select_source",
      { source: "Apple TV", entity_id: "media_player.display" },
    ],
  ]);
});

test("standby, missing, foreign and unavailable entities never send navigation", async ({
  page,
}) => {
  await mount(page);
  await update(page, { state: "off" });
  await expect(
    page.getByRole("button", { name: "Oben", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Einschalten", exact: true }).click();
  expect(await calls(page)).toEqual([
    ["media_player", "turn_on", { entity_id: "media_player.display" }],
  ]);
  for (const state of ["unavailable", "unknown"]) {
    await update(page, { state });
    await expect(page.locator("#power")).toBeDisabled();
  }
  await page.evaluate(() => {
    delete hass.entities["media_player.display"];
    hass.states["media_player.display"] = { state: "on", attributes: {} };
    card.hass = { ...hass };
  });
  await expect(page.locator("#power")).toBeDisabled();
  await page.evaluate(() => {
    delete hass.states["media_player.display"];
    card.hass = { ...hass };
  });
  await expect(page.locator("#status")).toContainText("LG-Display auswählen");
  expect((await calls(page)).length).toBe(1);
});

test("volume, mute and clearing a presentation use correct services", async ({
  page,
}) => {
  await mount(page);
  await page.getByRole("slider").fill("65");
  await page
    .getByRole("button", { name: "Stummschalten", exact: true })
    .click();
  await page.getByRole("button", { name: "Lauter", exact: true }).click();
  await page.getByRole("button", { name: "Leiser", exact: true }).click();
  await update(page, {
    attributes: {
      ...initial.attributes,
      presentation_active: true,
      presentation_queue_size: 2,
    },
  });
  await page.getByRole("button", { name: "Zum Eingang zurück" }).click();
  expect(await calls(page)).toEqual([
    [
      "media_player",
      "volume_set",
      { volume_level: 0.65, entity_id: "media_player.display" },
    ],
    [
      "media_player",
      "volume_mute",
      { is_volume_muted: true, entity_id: "media_player.display" },
    ],
    ["media_player", "volume_up", { entity_id: "media_player.display" }],
    ["media_player", "volume_down", { entity_id: "media_player.display" }],
    ["lg_rs232_ip", "clear_content", { entity_id: "media_player.display" }],
  ]);
});

test("message survives state updates and input is rendered as text", async ({
  page,
}) => {
  await mount(page, { name: "<img src=x onerror=alert(1)>" });
  await expect(page.locator("h2")).toHaveText("<img src=x onerror=alert(1)>");
  expect(await page.locator("h2 img").count()).toBe(0);
  await page.locator("#message-panel summary").click();
  await page
    .getByRole("textbox", { name: "Nachricht auf dem Display" })
    .fill("Hallo <b>LG</b>");
  await update(page, {
    attributes: { ...initial.attributes, volume_level: 0.4 },
  });
  await expect(page.getByRole("textbox")).toHaveValue("Hallo <b>LG</b>");
  await page.getByRole("button", { name: "Senden", exact: true }).click();
  expect(await calls(page)).toEqual([
    [
      "lg_rs232_ip",
      "show_toast",
      { message: "Hallo <b>LG</b>", entity_id: "media_player.display" },
    ],
  ]);
  await update(page, {
    attributes: { ...initial.attributes, native_web_enabled: false },
  });
  await expect(page.locator("#message-panel")).toBeHidden();
});

test("pending request blocks repeats and failures are visible without optimistic state", async ({
  page,
}) => {
  await mount(page);
  await page.evaluate(() => {
    window.pending = new Promise((resolve) => (window.finish = resolve));
  });
  await page.getByRole("button", { name: "Oben", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Oben", exact: true }),
  ).toBeDisabled();
  await page.evaluate(() => {
    card._remote("up");
    window.finish();
    window.pending = null;
  });
  await expect(
    page.getByRole("button", { name: "Oben", exact: true }),
  ).toBeEnabled();
  expect((await calls(page)).length).toBe(1);
  await page.evaluate(() => (window.fail = true));
  await page.getByRole("button", { name: "Ausschalten", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Befehl fehlgeschlagen");
  await expect(page.locator("#status")).toHaveText("Ein");
});

async function preview(page) {
  await mount(page, { camera_entity: "camera.display" });
  await page.evaluate(() => {
    hass.states["camera.display"] = {
      state: "idle",
      attributes: {
        entity_picture: "/api/camera_proxy/camera.display?token=test",
        last_capture: "2026-10-02T12:00:00Z",
        collection_enabled: true,
      },
    };
    card.hass = { ...hass };
  });
  await expect(page.locator("#image")).toHaveAttribute("src", /^blob:/);
  await expect
    .poll(() => page.locator("#image").evaluate((el) => el.naturalWidth))
    .toBe(64);
}

test("preview decodes changing multipart frames and keeps one stream through state updates", async ({
  page,
}) => {
  await preview(page);
  const connected = previewServer.stats.connections;
  // WebKit's canvas API can expose only the initial MJPEG frame. Inspect rendered pixels.
  const pixels = async () =>
    (await page.locator("#image").screenshot()).toString("base64");
  const first = await pixels();
  await expect.poll(pixels).not.toBe(first);
  await update(page, {
    attributes: { ...initial.attributes, volume_level: 0.6 },
  });
  await page.evaluate(() => {
    hass.states["camera.display"].attributes.last_capture =
      "2026-10-02T12:00:01Z";
    card.hass = { ...hass };
  });
  expect(previewServer.stats.connections).toBe(connected);
  await page.evaluate(() => {
    hass.states["camera.display"].attributes.preview_error = "capture_failed";
    card.hass = { ...hass };
  });
  await expect(page.locator("#image")).toBeHidden();
  await expect(page.locator("#image")).toHaveAttribute("src");
  await page.evaluate(() => {
    delete hass.states["camera.display"].attributes.preview_error;
    card.hass = { ...hass };
  });
  await expect(page.locator("#image")).toBeVisible();
  expect(previewServer.stats.connections).toBe(connected);
  await update(page, { state: "off" });
  await expect(page.locator("#image")).not.toHaveAttribute(
    "src",
    /camera_proxy_stream/,
  );
  await expect.poll(() => previewServer.stats.active).toBe(0);
});

test("preview opens selected camera and stops capture offscreen, hidden or detached", async ({
  page,
}) => {
  await preview(page);
  await page.evaluate(() =>
    card.addEventListener(
      "hass-more-info",
      (event) => (window.moreInfo = event.detail),
    ),
  );
  await page.getByRole("button", { name: "Vorschau vergrößern" }).click();
  expect(await page.evaluate(() => window.moreInfo)).toEqual({
    entityId: "camera.display",
  });
  await page.evaluate(() => (card.style.display = "none"));
  await expect.poll(() => previewServer.stats.active).toBe(0);
  await page.evaluate(() => (card.style.display = "block"));
  await expect.poll(() => previewServer.stats.active).toBe(1);
  // Emulate the browser visibility event; the actual stream must be released.
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => previewServer.stats.active).toBe(0);
  await page.evaluate(() => {
    delete document.visibilityState;
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => previewServer.stats.active).toBe(1);
  await page.evaluate(() => card.remove());
  await expect.poll(() => previewServer.stats.active).toBe(0);
});

test("camera collection off prevents streams and configuration rebuild releases old stream", async ({
  page,
}) => {
  await preview(page);
  await page.evaluate(() => {
    hass.states["camera.display"].attributes.collection_enabled = false;
    card.hass = { ...hass };
  });
  await expect.poll(() => previewServer.stats.active).toBe(0);
  await page.evaluate(() => {
    hass.states["camera.display"].attributes.collection_enabled = true;
    card.hass = { ...hass };
  });
  await expect.poll(() => previewServer.stats.active).toBe(1);
  await page.evaluate(() =>
    card.setConfig({ ...card._config, name: "New title" }),
  );
  await expect.poll(() => previewServer.stats.active).toBe(1);
  await page.evaluate(() =>
    card.setConfig({ ...card._config, show_preview: false }),
  );
  await expect.poll(() => previewServer.stats.active).toBe(0);
});

test("editor picks LG only, supports optional camera and preserves config after updates", async ({
  page,
}) => {
  await mount(page);
  await page.evaluate(() => {
    hass.states["media_player.sonos"] = {
      state: "on",
      attributes: { friendly_name: "Sonos" },
    };
    hass.states["camera.display"] = {
      state: "idle",
      attributes: {
        preview_mode: "periodic_screenshot",
        friendly_name: "LG Preview",
      },
    };
    hass.entities["camera.display"] = { device_id: "lg" };
    window.editor = document.createElement("lg-display-remote-editor");
    editor.setConfig({
      type: "custom:lg-display-remote",
      entity: "media_player.display",
    });
    editor.hass = hass;
    editor.addEventListener(
      "config-changed",
      (e) => (window.newConfig = e.detail.config),
    );
    document.body.replaceChildren(editor);
  });
  await expect(
    page
      .getByRole("combobox", { name: "LG-Display", exact: true })
      .locator("option"),
  ).toHaveCount(2);
  await page
    .getByRole("combobox", { name: "Vorschaukamera (optional)", exact: true })
    .selectOption("camera.display");
  await page
    .getByRole("textbox", { name: "Titel (optional)", exact: true })
    .fill("Mein Display");
  await page
    .getByRole("checkbox", { name: "Display-Lautstärke anzeigen" })
    .uncheck();
  await page.evaluate(() => (editor.hass = { ...hass }));
  await expect(page.getByRole("textbox")).toHaveValue("Mein Display");
  const config = await page.evaluate(() => window.newConfig);
  expect(config).toMatchObject({
    entity: "media_player.display",
    camera_entity: "camera.display",
    name: "Mein Display",
    show_volume: false,
  });
  await page.evaluate(() =>
    editor.setConfig({
      ...editor._config,
      name: "Extern geändert",
      show_volume: true,
    }),
  );
  await expect(page.getByRole("textbox")).toHaveValue("Extern geändert");
  await expect(
    page.getByRole("checkbox", { name: "Display-Lautstärke anzeigen" }),
  ).toBeChecked();
});

test("keyboard navigation stays scoped and layout fits a small phone", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 1100 });
  await mount(page);
  await page.getByRole("button", { name: "OK", exact: true }).focus();
  await page.keyboard.press("ArrowLeft");
  expect(await calls(page)).toEqual([
    [
      "lg_rs232_ip",
      "send_remote_command",
      { command: "left", entity_id: "media_player.display" },
    ],
  ]);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(320);
  await page.screenshot({
    path: "test-results/lg-remote-mobile.png",
    fullPage: true,
  });
});

test("card picker registration is unique and changing language rebuilds inputs correctly", async ({
  page,
}) => {
  await mount(page);
  await page.addScriptTag({ path: script, type: "module" });
  expect(
    await page.evaluate(
      () =>
        window.customCards.filter((c) => c.type === "lg-display-remote").length,
    ),
  ).toBe(1);
  await page.evaluate(() => (card.hass = { ...hass, language: "en" }));
  await expect(
    page.getByRole("combobox", { name: "Input", exact: true }),
  ).toHaveValue("HDMI 1");
  await expect(
    page.getByRole("button", { name: "Turn off", exact: true }),
  ).toBeVisible();
});

test("failed volume and source changes restore the last confirmed HA values", async ({
  page,
}) => {
  await mount(page);
  await page.evaluate(() => {
    window.fail = true;
  });
  await page.getByRole("slider").fill("70");
  await expect(page.getByRole("status")).toContainText("Befehl fehlgeschlagen");
  await expect(page.getByRole("slider")).toHaveValue("30");
  await page
    .getByRole("combobox", { name: "Eingang", exact: true })
    .selectOption("HDMI 3");
  await expect(page.getByRole("status")).toContainText("Befehl fehlgeschlagen");
  await expect(
    page.getByRole("combobox", { name: "Eingang", exact: true }),
  ).toHaveValue("HDMI 1");
});

test("preview reconnects after interrupted response", async ({ page }) => {
  await preview(page);
  const count = previewServer.stats.connections;
  previewServer.disconnect();
  await expect
    .poll(() => previewServer.stats.connections)
    .toBeGreaterThan(count);
  await expect(page.locator("#image")).toBeVisible();
  await expect
    .poll(() => page.locator("#image").evaluate((el) => el.naturalWidth))
    .toBe(64);
  await page.evaluate(() => card.remove());
  await expect.poll(() => previewServer.stats.active).toBe(0);
});

test("native enlarged image decodes successive standard MJPEG frames", async ({
  page,
}) => {
  await page.goto(previewServer.url);
  await page.evaluate(() => {
    const img = document.createElement("img");
    img.id = "native";
    img.src = "/api/camera_proxy_stream/camera.display";
    document.body.append(img);
  });
  await expect
    .poll(() => page.locator("#native").evaluate((el) => el.naturalWidth))
    .toBe(64);
  const pixels = async () =>
    (await page.locator("#native").screenshot()).toString("base64");
  const first = await pixels();
  await expect.poll(pixels).not.toBe(first);
});

test("frame reader handles split headers and payloads and rejects oversized frames", async ({
  page,
}) => {
  await mount(page);
  const result = await page.evaluate(async () => {
    function response(text) {
      const bytes = new TextEncoder().encode(text);
      let offset = 0;
      return new Response(
        new ReadableStream({
          pull(controller) {
            if (offset < bytes.length)
              controller.enqueue(bytes.slice(offset, ++offset));
            else controller.close();
          },
        }),
        { headers: { "Content-Type": "application/octet-stream" } },
      );
    }
    const frames = jpegFrames(
      response(
        "--test\r\nContent-Type: image/jpeg\r\nContent-Length: 3\r\n\r\nabc\r\n--test\r\nContent-Type: image/jpeg\r\nContent-Length: 4\r\n\r\ndefg",
      ),
    );
    const decoded = [
      (await frames.next()).value,
      (await frames.next()).value,
    ].map((bytes) => new TextDecoder().decode(bytes));
    await frames.return();
    let rejected = false;
    try {
      await jpegFrames(
        response(
          "--test\r\nContent-Type: image/jpeg\r\nContent-Length: 999999999\r\n\r\n",
        ),
      ).next();
    } catch {
      rejected = true;
    }
    return { decoded, rejected };
  });
  expect(result).toEqual({ decoded: ["abc", "defg"], rejected: true });
});

for (const definedFirst of [true, false]) {
  test(`LG native camera view works through service worker, registration first: ${definedFirst}`, async ({
    page,
  }) => {
    await page.goto(previewServer.url);
    await page.evaluate(async () => {
      await navigator.serviceWorker.register("/service-worker.js");
      await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller) {
        await new Promise((resolve) =>
          navigator.serviceWorker.addEventListener(
            "controllerchange",
            resolve,
            { once: true },
          ),
        );
      }
    });
    const registerCamera = async () =>
      page.evaluate(() => {
        class NativeCamera extends HTMLElement {
          constructor() {
            super();
            this.attachShadow({ mode: "open" });
          }
          set stateObj(state) {
            this._state = state;
            if (this.isConnected) this.paint();
          }
          get stateObj() {
            return this._state;
          }
          connectedCallback() {
            this.paint();
          }
          render() {
            return `Native camera: ${this.stateObj?.entity_id || "none"}`;
          }
          paint() {
            const rendered = this.render();
            if (
              rendered instanceof Node &&
              this.shadowRoot.firstChild === rendered
            )
              return;
            this.shadowRoot.replaceChildren(rendered);
          }
        }
        customElements.define("ha-camera-stream", NativeCamera);
      });
    if (definedFirst) await registerCamera();
    await page.addScriptTag({ path: script });
    if (!definedFirst) await registerCamera();
    await page.evaluate(() => {
      window.camera = document.createElement("ha-camera-stream");
      camera.stateObj = {
        entity_id: "camera.display",
        state: "idle",
        attributes: {
          integration_domain: "lg_rs232_ip",
          preview_mode: "periodic_screenshot",
          entity_picture: "/api/camera_proxy/camera.display?token=test",
          collection_enabled: true,
          last_capture: "2026-10-02T12:00:00Z",
          friendly_name: "LG Display preview",
        },
      };
      window.loadedFrames = 0;
      camera.addEventListener("load", () => loadedFrames++);
      document.body.append(camera);
    });
    await expect(page.locator("#image")).toHaveAttribute("src", /^blob:/);
    await expect
      .poll(() => page.locator("#image").evaluate((el) => el.naturalWidth))
      .toBe(64);
    await expect
      .poll(() => page.evaluate(() => loadedFrames))
      .toBeGreaterThan(2);
    const pixels = async () =>
      (await page.locator("#image").screenshot()).toString("base64");
    const first = await pixels();
    await expect.poll(pixels).not.toBe(first);
    const connections = previewServer.stats.connections;
    await page.evaluate(() => {
      camera.stateObj = {
        ...camera.stateObj,
        attributes: {
          ...camera.stateObj.attributes,
          last_capture: "2026-10-02T12:00:01Z",
        },
      };
    });
    expect(previewServer.stats.connections).toBe(connections);
    await page.evaluate(() => {
      window.renderBefore =
        customElements.get("ha-camera-stream").prototype.render;
    });
    await page.addScriptTag({ path: script, type: "module" });
    expect(
      await page.evaluate(
        () =>
          renderBefore ===
          customElements.get("ha-camera-stream").prototype.render,
      ),
    ).toBe(true);
    await page.evaluate(() => {
      camera.stateObj = {
        entity_id: "camera.front_door",
        state: "idle",
        attributes: {},
      };
    });
    await expect(page.locator("ha-camera-stream")).toContainText(
      "Native camera: camera.front_door",
    );
    await expect.poll(() => previewServer.stats.active).toBe(0);
  });
}

test("native LG preview releases streams on detach and retries through service worker", async ({
  page,
}) => {
  await mount(page);
  await page.evaluate(async () => {
    await navigator.serviceWorker.register("/service-worker.js");
    await navigator.serviceWorker.ready;
    if (!navigator.serviceWorker.controller)
      await new Promise((resolve) =>
        navigator.serviceWorker.addEventListener("controllerchange", resolve, {
          once: true,
        }),
      );
    window.nativePreview = document.createElement("lg-display-camera-preview");
    nativePreview.stateObj = {
      entity_id: "camera.display",
      state: "idle",
      attributes: {
        entity_picture: "/api/camera_proxy/camera.display?token=test",
        last_capture: "2026-10-02T12:00:00Z",
        collection_enabled: true,
      },
    };
    document.body.replaceChildren(nativePreview);
  });
  await expect
    .poll(() => page.locator("#image").evaluate((el) => el.naturalWidth))
    .toBe(64);
  const count = previewServer.stats.connections;
  previewServer.disconnect();
  await expect
    .poll(() => previewServer.stats.connections)
    .toBeGreaterThan(count);
  await expect(page.locator("#image")).toBeVisible();
  await page.evaluate(() => nativePreview.remove());
  await expect.poll(() => previewServer.stats.active).toBe(0);
});

test('display app controls respect opt-in and send only selected display', async ({page}) => {
  await mount(page);
  await expect(page.locator('#app-panel')).toBeHidden();
  await update(page, {attributes: {...initial.attributes, display_app_enabled: true}});
  await page.locator('#app-panel summary').click();
  await page.locator('#app-message').fill('Test notification');
  await page.locator('#app-layout').selectOption('pip');
  await page.locator('#app-send').click();
  await page.locator('#app-dashboard').click();
  const sent = await calls(page);
  expect(sent[0][0]).toBe('lg_rs232_ip');
  expect(sent[0][1]).toBe('show_display_app');
  expect(sent[0][2].message).toBe('Test notification');
  expect(sent[0][2].layout).toBe('pip');
  expect(sent[1][2].dashboard).toBe(true);
  expect(sent[1][2].entity_id).toBe('media_player.display');
});

test('source selection wakes from standby, including the previously selected input', async ({page}) => {
  await mount(page);
  await update(page, {state:'off'});
  const input=page.getByRole('combobox',{name:'Eingang',exact:true});
  await expect(input).toBeEnabled();
  await expect(input).toHaveValue('');
  await page.evaluate(()=>{window.pending=new Promise(resolve=>window.finishWake=resolve);});
  await input.selectOption('HDMI 1');
  await expect(input).toBeDisabled();
  await expect(page.locator('#feedback')).toHaveText('Display wird gestartet …');
  await expect(page.getByRole('button',{name:'Oben',exact:true})).toBeDisabled();
  expect(await calls(page)).toEqual([['media_player','select_source',{source:'HDMI 1',entity_id:'media_player.display'}]]);
  await update(page,{state:'on'});
  await page.evaluate(()=>window.finishWake());
  await expect(input).toBeEnabled();
  await expect(input).toHaveValue('HDMI 1');
  for (const state of ['unavailable','unknown']) {
    await update(page,{state});
    await expect(input).toBeDisabled();
  }
});

test('failed source wake leaves the selector available for a new explicit retry', async ({page}) => {
  await mount(page);
  await update(page,{state:'off'});
  await page.evaluate(()=>{window.fail=true;});
  const input=page.getByRole('combobox',{name:'Eingang',exact:true});
  await input.selectOption('Apple TV');
  await expect(page.locator('#feedback')).toContainText('fehlgeschlagen');
  await expect(input).toBeEnabled();
  await expect(input).toHaveValue('');
  await page.evaluate(()=>{window.fail=false;});
  await input.selectOption('Apple TV');
  expect((await calls(page)).length).toBe(2);
  await expect(page.locator('#feedback')).toHaveText('Befehl gesendet');
});
