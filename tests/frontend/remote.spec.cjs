const { test, expect } = require("@playwright/test");
const path = require("node:path");
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
  await page.setContent(
    '<body style="margin:16px;background:#f4f5f8;font-family:Arial;color:#172b3a"></body>',
  );
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
  await page.locator("summary").click();
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

test("preview requests only new captures and removes stale image on failure or standby", async ({
  page,
}) => {
  await mount(page, { camera_entity: "camera.display" });
  await page.evaluate(() => {
    hass.states["camera.display"] = {
      state: "idle",
      attributes: {
        entity_picture: "/api/camera_proxy/camera.display?token=test",
        last_capture: "2026-10-02T12:00:00Z",
      },
    };
    card.hass = { ...hass };
  });
  const src = await page.locator("#image").getAttribute("src");
  expect(src).toContain("capture=2026-10-02");
  await update(page, {
    attributes: { ...initial.attributes, volume_level: 0.6 },
  });
  expect(await page.locator("#image").getAttribute("src")).toBe(src);
  await page.evaluate(() => {
    hass.states["camera.display"].attributes.preview_error = "capture_failed";
    card.hass = { ...hass };
  });
  await expect(page.locator("#image")).not.toHaveAttribute("src");
  await page.evaluate(() => {
    delete hass.states["camera.display"].attributes.preview_error;
    card.hass = { ...hass };
  });
  await update(page, { state: "off" });
  await expect(page.locator("#image")).not.toHaveAttribute("src");
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
