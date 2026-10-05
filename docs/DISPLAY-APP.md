# Home Assistant display app

LG 2.6 includes an optional app hosted by Home Assistant and launched by the panel's existing **SI app launcher**. No SuperSign server, Crestron controller, developer-mode login, IPK packaging or extra HACS repository is required. It remains part of the independent LG integration; AV Companion retains player/sound/socket orchestration.

The automatically registered **[LG Display Studio](DISPLAY-STUDIO.md)** sidebar groups persistent views above a separate notification section and manages seven fixed editable views: Nur HDMI, Dashboard, Dashboard PiP, Mediaplayer, Mitteilung, Mitteilung PiP and Mitteilung Vollbild. Each has independent default restoration and cannot be deleted. Every additional saved view becomes a named source automatically; no assignment is needed. HDMI selection uses the shared editable Nur HDMI scene in the same app, with full-screen video as its default. Persistent sources keep the last HDMI input for any included video element, survive normal standby/HA restart and resume after notifications. Selecting any HDMI source returns to the saved Nur HDMI scene. Source transactions retain the OSD guard; deleting an active custom view returns to Dashboard. Themes alter colours/backgrounds only. Editor navigation never changes the display source.

## Setup in Home Assistant

1. Open **Settings → Devices & services → LG Professional Display → Configure**. Enable native LG web access with the Mobile URL password, then **Enable display app**.
2. Choose **SI app**. For continuous HDMI with automatic startup, also enable **Keep SI app running with automatic startup**. Leave that separate option off for temporary presentations. Leave the Home Assistant URL empty to use HA's configured network URL. If that URL is not reachable from the panel, enter the HA server's LAN base URL, for example `http://homeassistant.local:8123`. A Docker installation may require the Docker host's LAN address. `localhost` and loopback addresses are rejected. HTTPS needs a certificate the panel trusts; the LG certificate-verification option controls the other direction (HA → LG), not this connection.
3. Optionally select up to 12 sensor/binary-sensor entities for the overview. Only their names, states and units are shared while an overview is active.
4. On the LG device page press **Test display app**. The panel must be awake on an HDMI input. Home Assistant saves the current SI settings, configures its paired app URL, launches the app, waits for its rendering acknowledgement, then returns to HDMI and restores the settings in temporary mode. In resident mode the same app stays open and returns to its embedded HDMI view. No URL or access token has to be copied manually.
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

Use `lg_rs232_ip.clear_content` or the remote card's return button to cancel. Temporary app launches and native media use the existing queue. In connected resident mode, a new normal app message replaces the current normal message immediately, including one still awaiting acknowledgement. Urgent messages replace older app requests and are not interrupted by normal ones; only the newest normal request waits behind an active urgent message. Native media requests retain their queue order. Wake policy, quiet hours, the AV ownership guard and **OSD suppression option** remain effective. An OSD that was manually disabled is never enabled by the transition guard. Layout changes inside a running app do not issue an input command.

## Status, recovery and privacy

The **Display app** sensor reports disabled, ready, connected, SI active or error, plus app version, presence of a webOS platform bridge, and pending SI restoration. Bridge presence alone does not establish permission to use every SCAP API. Presentation errors also appear on the LG media-player entity.

Original SI settings are saved to a private HA `.storage` journal **before** changing the panel. In temporary mode, normal completion, cancellation and integration unload restore owned settings. Resident mode retains its owned SI configuration across HA reloads/restarts; disabling the app or resident mode restores the previous configuration when the panel is awake. If native web access is disabled simultaneously, a recovery-only client keeps retrying that restoration; it does not enable ordinary native web services. After an interrupted HA run, recovery restores the saved HDMI app and SI settings when the panel is awake; polling retries after loss of connectivity. Recovery does not wake an off display or overwrite SI settings changed outside HA. **Restore SI settings** on the device page restores explicitly and pauses resident mode. **Resume display app** resumes it. After a crash, source/settings recovery does not imply that the panel's earlier power/OSD state can always be reconstructed.

Each config entry has its own random pairing token. The panel receives no HA login or long-lived HA access token. Its narrow endpoint serves only bundled files, current presentation data and bounded status events and individually requested JPEG uploads (maximum 5 MiB; no unsolicited frames). The endpoint cannot call HA services or read arbitrary entities. Disabling the app immediately revokes this endpoint. Do not share its private URL or expose the panel's management ports to the internet. A browser connected through plain HTTP shares the same transport limitations as that LAN connection.

The app uses local assets and ES5-compatible JavaScript for the tested Chromium 53 platform. It clears transient notification content after expiration or 15 seconds without a successful HA response. An enabled Studio dashboard retains its last received values during a connection outage; those values are no longer live. A loaded resident app keeps its HDMI view visible during that outage. A bounded acknowledgement retry handles lost responses independently of HDMI signal readiness. App assets are included in HACS updates; version changes trigger a reload, and the app requests closing when it leaves the foreground. This is a hosted app, not an offline-installed package.

## Confirmed capabilities and limits

Tested on **75UH5F-HJ, firmware 04.13.50, webOS 4.0.1-136**, with HA 2026.9.4. HDMI is embedded locally through LG's `service/webos-external` video source (`ext://hdmi:1` etc.). It is not captured and streamed through HA. Only one HDMI source is embedded; PiP means HDMI plus app content, not two independently decoded HDMI inputs.

The initial SI launch can briefly interrupt the picture while the HDMI video plane initializes. Resident mode avoids repeated launches for messages and PiP while connected; it is optional and disabled by default. It does not solve an Apple TV falsely reporting idle. The resident HDMI view is not an active presentation lease, and the public AV adapter exposes its actual embedded HDMI input. Standby policy remains in AV Companion. Long-term CEC/audio acceptance, mains recovery and every protected-content provider remain device-dependent.

The FeinTech AX310 still extracts the Apple TV's audio upstream for Sonos. Display-app content does not create a new eARC return path. Audio continuity, lip sync, every protected-content provider, every HDMI port and long-term standby behaviour are not certified by a successful picture test. No SuperSign or Crestron endpoint has been repurposed for unsupported commands.

See [release evidence](RELEASE-TESTS.md) and the reusable [device/API reference](devices/LG-UH5F-H.md).

## Automatic routing and resident lifecycle

| State | Messages / HDMI PiP | Preview camera |
|---|---|---|
| App disabled | Existing native text overlay, image/video/website actions remain available; app-specific PiP requires enabling the app | Existing authenticated LG web capture |
| App enabled, temporary mode | Existing timed app launch, guarded return and SI restoration | App capture while connected/capable, otherwise web capture |
| Resident app connected, with or without an HDMI signal | `show_toast` uses an 8-second app overlay; `show_display_app` changes the current layout without launching or selecting an input | Demand-driven binary JPEG upload into the same HA camera cache |
| Resident app unavailable | Native toast fallback; app-specific layouts report that the resident app is unavailable, without triggering a temporary launch/source round trip. Resume or wait for reconnection | Immediate web capture when disconnected; timeout/error fallback with a 30-second app retry backoff |

The app stays **in the foreground with HDMI embedded full-screen**, including between messages. HA source selection (also through the AV adapter) selects HDMI inside the app and persists it separately from the original SI recovery snapshot. The same selection is a no-op. A changed source uses the existing OSD guard and a scoped app acknowledgement; the acknowledgement confirms source application, not that a cable supplies a signal. Overlay and PiP change that same video element's layout. A hidden background app is not the overlay mechanism. Native image/video/website playback uses its existing path, temporarily leaving resident mode with OSD suppression and then resuming it when ownership permits.

SI configuration is applied automatically from HA; existing third-party SI settings are never overwritten. Resident mode does not wake a sleeping display by itself. A confirmed off/on cycle or **Resume display app** can start it again. A physical source change pauses it, preventing the controller from repeatedly taking the screen back. A missing HDMI signal is a diagnostic state (`hdmi_signal_ready`), not an app disconnection. Missing heartbeats report a connection error while retaining the loaded HDMI view; they never trigger recurring HDMI/SI relaunches. The app retries its HA connection itself. An explicit Resume after a physical source change adopts that source inside the app. Required transitions retain the OSD guard; a manually disabled OSD stays disabled.

**Cold-start limit:** this remains a hosted SI app. The panel must reach HA to load its HTML/JavaScript after a cold start. An already loaded app retains HDMI during an HA outage, but this is not an offline-installed package and does not guarantee HDMI during a cold boot while HA is unavailable. No hardware video encoder or audio/video stream is exposed.

The camera chooses its backend automatically without changing its entity ID or dashboard configuration. Active intervals may be **0.5–10 seconds** (0 disables acceleration); the normal background interval remains 1–3600 seconds. Requests are shared across viewers, never run as parallel captures, and slow panels determine the achievable rate. Closing viewers restores the slower interval; disabling the camera stops collection. Screenshots include the composed screen (HDMI and overlays) and remain in memory.

On the 75UH5F-HJ, direct `captureScreen` returned 1280×720 JPEGs in 573–605 ms before upload, versus 754–836 ms for three existing web capture/download requests. These are short feasibility measurements, not sustained frame-rate guarantees. The [device reference](devices/LG-UH5F-H.md#direct-app-screenshots--hardware-investigation-2026-10-02) documents the calls and limits; [release tests](RELEASE-TESTS.md) record the production integration checks.

## Runtime efficiency (app 1.2.0)

- A single external HDMI video element is reused through overlays, PiP, fullscreen content and input changes. Layout changes do not reload its source. An explicit HDMI change reloads only that element's source.
- One HTTP long poll waits up to 25 seconds and wakes immediately for content, selected-input, allowed-sensor or capture changes. Five-second version/visibility heartbeats run independently. Foreground and SI ownership checks remain in regular maintenance, not on every message's critical path.
- Text/card nodes update only when values change. Idle HDMI causes no clock/countdown DOM updates. No frontend framework, remote asset bundle or background animation runs on the panel.
- Only one requested screenshot is captured/uploaded at a time. The native bridge, upload callbacks, timeout and temporary base64 references are released afterwards, including on errors or page exit. Content is rendered before capture begins. Existing HA camera intervals and shared-viewer backpressure remain effective.
- Private content expires locally even while HA is unavailable and cannot reappear from a repeated stale response. Already loaded HDMI continues; the hosted cold-start limitation above still applies.

On the physical 75UH5F-HJ, six consecutive connected layout/message requests were acknowledged after **38–87 ms** (median **42 ms**) in a short LAN test, including replacement of active 30-second messages. A burst of twelve requests left only the newest visible. These measurements exclude initial app startup and do not promise the same latency on other networks or devices. HDMI input changes include the OSD guard's settling period and are slower than layout changes. Process-wide RAM/CPU and multi-day stability were not measured; bounded DOM, request and capture lifetimes are verified by regression tests.
