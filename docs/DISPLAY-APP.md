# Home Assistant display app

LG 2.3 adds an optional app hosted by Home Assistant and launched by the panel's existing **SI app launcher**. No SuperSign server, Crestron controller, developer-mode login, IPK packaging or extra HACS repository is required. It remains part of the independent LG integration; AV Companion retains player/sound/socket orchestration.

## Setup in Home Assistant

1. Open **Settings → Devices & services → LG Professional Display → Configure**. Enable native LG web access with the Mobile URL password, then **Enable display app**.
2. Choose **SI app (temporary)**. Leave the Home Assistant URL empty to use HA's configured network URL. If that URL is not reachable from the panel, enter the HA server's LAN base URL, for example `http://homeassistant.local:8123`. A Docker installation may require the Docker host's LAN address. `localhost` and loopback addresses are rejected. HTTPS needs a certificate the panel trusts; the LG certificate-verification option controls the other direction (HA → LG), not this connection.
3. Optionally select up to 12 sensor/binary-sensor entities for the overview. Only their names, states and units are shared while an overview is active.
4. On the LG device page press **Test display app**. The panel must be awake on an HDMI input. Home Assistant saves the current SI settings, configures its paired app URL, launches the app, waits for its rendering acknowledgement, then returns to HDMI and restores the settings. No URL or access token has to be copied manually.
5. **Show sensor overview** displays the selected sensors for 60 seconds. The bundled remote card adds a Display app section with a layout selector, message field and overview button. Reload the browser after updating the integration.

The alternative **Website (Play via URL)** launcher supports the full-screen view on devices where the SI launcher is unavailable. HDMI overlay and PiP require SI mode and firmware support. The integration refuses to replace any existing enabled SI application; it never deletes installed panel apps.

## Automation action

```yaml
action: lg_rs232_ip.show_display_app
target:
  entity_id: media_player.lg_display_display
data:
  title: Home Assistant
  message: The washing machine has finished.
  duration: 30
  layout: overlay
  dashboard: false
  priority: normal
```

| Field | Meaning |
|---|---|
| `title` | Up to 160 characters; default Home Assistant |
| `message` | Plain text, up to 2000 characters; no arbitrary HTML/script execution |
| `duration` | 1–3600 seconds after rendering is acknowledged |
| `layout: fullscreen` | Full-screen message / selected sensor overview |
| `layout: overlay` | HDMI fills the background, notification panel appears in the lower right |
| `layout: pip` | HDMI appears in a smaller window alongside the message / selected sensors |
| `dashboard` | Include only sensors explicitly selected in integration options |
| `priority` | `normal` respects quiet hours; `urgent` bypasses quiet hours but never the no-wake policy |

Use `lg_rs232_ip.clear_content` or the remote card's return button to cancel. Presentations use the existing queue, wake policy, AV ownership guard and **OSD suppression option**. An OSD that was manually disabled is never enabled by the transition guard. Layout changes inside a running app do not issue an input command.

## Status, recovery and privacy

The **Display app** sensor reports disabled, ready, connected, SI active or error, plus app version, presence of a webOS platform bridge, and pending SI restoration. Bridge presence alone does not establish permission to use every SCAP API. Presentation errors also appear on the LG media-player entity.

Original SI settings are saved to a private HA `.storage` journal **before** changing the panel. Normal completion, cancellation and integration unload restore owned settings. After an interrupted HA run, recovery restores the saved HDMI app and SI settings when the panel is awake; polling retries after loss of connectivity. Recovery does not wake an off display or overwrite SI settings changed outside HA. **Restore SI settings** on the device page retries explicitly. After a crash, source/settings recovery does not imply that the panel's earlier power/OSD state can always be reconstructed.

Each config entry has its own random pairing token. The panel receives no HA login or long-lived HA access token. Its narrow endpoint serves only bundled files, current presentation data and four bounded status-event types. The endpoint cannot call HA services or read arbitrary entities. Disabling the app immediately revokes this endpoint. Do not share its private URL or expose the panel's management ports to the internet. A browser connected through plain HTTP shares the same transport limitations as that LAN connection.

The app uses local assets and ES5-compatible JavaScript for the tested Chromium 53 platform. It clears private content after expiration or 15 seconds without a successful HA response. Repeated polls retry a lost rendering acknowledgement. App assets are included in HACS updates; version changes trigger a reload, and the app requests closing when it leaves the foreground. This is a hosted app, not an offline-installed package.

## Confirmed capabilities and limits

Tested on **75UH5F-HJ, firmware 04.13.50, webOS 4.0.1-136**, with HA 2026.9.4. HDMI is embedded locally through LG's `service/webos-external` video source (`ext://hdmi:1` etc.). It is not captured and streamed through HA. Only one HDMI source is embedded; PiP means HDMI plus app content, not two independently decoded HDMI inputs.

The initial SI launch can briefly interrupt the picture while the HDMI video plane initializes. This release uses timed presentations and restores the ordinary HDMI app afterwards. It does **not** enable an always-running replacement HDMI app. Such a resident mode could avoid repeated launches, but needs separate long-running tests for standby, CEC, HDCP, sound, power recovery and physical input changes. It is not a fix for Apple TV falsely reporting idle. Existing native `show_toast` remains the least intrusive simple text overlay.

The FeinTech AX310 still extracts the Apple TV's audio upstream for Sonos. Display-app content does not create a new eARC return path. Audio continuity, lip sync, every protected-content provider, every HDMI port and long-term standby behaviour are not certified by a successful picture test. No SuperSign or Crestron endpoint has been repurposed for unsupported commands.

See [release evidence](RELEASE-TESTS.md) and the reusable [device/API reference](devices/LG-UH5F-H.md).
