# Home Assistant display app

LG 2.6 includes an optional app hosted by Home Assistant and launched by the panel's existing **SI app launcher**. No SuperSign server, Crestron controller, developer-mode login, IPK packaging or extra HACS repository is required. It remains part of the independent LG integration; AV Companion retains player/sound/socket orchestration.

The separately installed **[Display Studio](DISPLAY-STUDIO.md)** extension sidebar groups persistent views above a separate notification section and manages seven fixed editable views: Nur HDMI, Dashboard, Dashboard PiP, Mediaplayer, Mitteilung, Mitteilung PiP and Mitteilung Vollbild. Each has independent default restoration and cannot be deleted. Every additional saved view becomes a named source automatically; no assignment is needed. HDMI selection uses the shared editable Nur HDMI scene in the same app, with full-screen video as its default. Persistent sources keep the last HDMI input for any included video element, survive normal standby/HA restart and resume after notifications. Selecting any HDMI source returns to the saved Nur HDMI scene. Source transactions retain the OSD guard; deleting an active custom view returns to Dashboard. Themes alter colours/backgrounds only. Editor navigation never changes the display source.

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

The app uses local assets and ES5-compatible JavaScript for the tested Chromium 53 platform. During an HA/integration outage, it shows a brief warning once and retains the current custom, Dashboard, PiP or Mediaplayer view for **30 seconds by default**. Configure **HDMI fallback on HA outage (seconds)** in the LG integration options (0–600; 0 means immediate). The timer starts when the outage is detected, not on each retry. Unresponsive requests can take their existing response timeout before an outage is detected. Values shown while disconnected are no longer live; notifications still respect their own expiry.

After the delay, the app clears widgets, cameras and overlays and expands its last HDMI video plane to fullscreen. It reuses the decoder and does **not** switch the LG input or leave the app. An existing plain HDMI view stays fullscreen. Reconnection before the deadline retains the view; later reconnection restores the current server view. This uses the configured/last known HDMI input, not a guessed port. If none is known, the app remains in its local empty state.

An obsolete AppCache manifest (404/410 during integration unload) never triggers navigation. Updates verify the paired HTML document, version markers and essential assets before reloading; failed or stalled checks retain the running app. A bounded acknowledgement retry handles lost responses independently of HDMI signal readiness. App assets are included in HACS updates. The resident app pauses polling, local timers, camera work and capture when hidden, then resumes the same HDMI element when visible. A transient webOS visibility change never closes the app; an actual page unload still releases its resources. The LG adapter assigns the loaded Studio provider version to the renderer bundle, and update checks verify that renderer as well as the main app. This is a hosted app with an optional device-side startup cache on compatible LG browsers; no local ZIP/IPK application slot is replaced. These safeguards protect an already loaded app. They do not turn a hosted URL into an installable offline app or guarantee a cold start after its cache was removed.

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

**Startup:** without the offline option, HA must be reachable to load the hosted app after restart. Version 2.18 adds the opt-in cache described below and verifies HDMI after a display reboot with its app endpoints unavailable. A first launch, cleared/evicted cache or changed pairing still needs HA. No hardware video encoder or HDMI audio/video stream is exposed.

The camera chooses its backend automatically without changing its entity ID or dashboard configuration. Active intervals may be **0.5–10 seconds** (0 disables acceleration); the normal background interval remains 1–3600 seconds. Requests are shared across viewers, never run as parallel captures, and slow panels determine the achievable rate. Closing viewers restores the slower interval; disabling the camera stops collection. Screenshots include the composed screen (HDMI and overlays) and remain in memory.

On the 75UH5F-HJ, direct `captureScreen` returned 1280×720 JPEGs in 573–605 ms before upload, versus 754–836 ms for three existing web capture/download requests. These are short feasibility measurements, not sustained frame-rate guarantees. The [device reference](devices/LG-UH5F-H.md#direct-app-screenshots--hardware-investigation-2026-10-02) documents the calls and limits; [release tests](RELEASE-TESTS.md) record the production integration checks.

## Runtime efficiency (app 1.2.0)

- A single external HDMI video element is reused through overlays, PiP, fullscreen content and input changes. Layout changes do not reload its source. An explicit HDMI change reloads only that element's source.
- One HTTP long poll waits up to 25 seconds and wakes immediately for content, selected-input, allowed-sensor or capture changes. Five-second version/visibility heartbeats run independently. Foreground and SI ownership checks remain in regular maintenance, not on every message's critical path.
- Text/card nodes update only when values change. Idle HDMI causes no clock/countdown DOM updates. No frontend framework, remote asset bundle or background animation runs on the panel.
- Only one requested screenshot is captured/uploaded at a time. The native bridge, upload callbacks, timeout and temporary base64 references are released afterwards, including on errors or page exit. Content is rendered before capture begins. Existing HA camera intervals and shared-viewer backpressure remain effective.
- Private content expires locally even while HA is unavailable and cannot reappear from a repeated stale response. Already loaded HDMI continues; the hosted cold-start limitation above still applies.

On the physical 75UH5F-HJ, six consecutive connected layout/message requests were acknowledged after **38–87 ms** (median **42 ms**) in a short LAN test, including replacement of active 30-second messages. A burst of twelve requests left only the newest visible. These measurements exclude initial app startup and do not promise the same latency on other networks or devices. HDMI input changes include the OSD guard's settling period and are slower than layout changes. Process-wide RAM/CPU and multi-day stability were not measured; bounded DOM, request and capture lifetimes are verified by regression tests.

### Camera widgets and event views (2.17)

Studio can place one additional camera/test-stream widget beside its existing HDMI plane. Playback is demand-driven and muted; leaving the view releases the decoder. A paired route resolves only saved camera bindings, using HA's camera API and scoped HLS endpoint. It never exposes camera login credentials or a generic URL proxy. Automatic mode falls back to bounded snapshots when streaming fails. The bundled 640×360, 15 fps synthetic H.264/MPEG-TS clip demonstrates the hardware path without a real camera. See [Studio setup and automation instructions](DISPLAY-STUDIO.md#kamera-und-teststream-neben-hdmi).

Timed `show_view` actions use one replaceable timer and explicit ownership checks, not a queue of old events. Native OSD suppression still wraps view changes and the return transition. The additional camera is excluded from CSS entrance animation. Ordinary widgets use a 280 ms entrance on smooth view changes; there is no permanent animation loop for this feature.


### Offline HDMI startup (2.18)

In the integration's **Configure** form, enable resident SI mode and **Offline HDMI startup using device cache**. This is optional and disabled by default. Load the app once with HA online. The **Display app** sensor's `offline_start` attribute must report `enabled: true`, `supported: true`, `cache_status: 1` before relying on the cached start. Status 2/3 indicates checking/downloading; 4 means an update is ready. Modern browsers may report unsupported; the tested webOS 4 Chromium 53 supports its legacy Application Cache.

Since 2.18.1 / app 1.15.1, an unsuccessful first state request displays a small local notice: **“Home Assistant ist nicht erreichbar. Die Verbindung wird erneut versucht.”** The initial request times out after five seconds. The notice disappears after five seconds or immediately when HA responds, whichever comes first. It appears only once per app start, preserves HDMI and OSD, and needs no downloaded notification layout. Later outages in the same running app do not repeat this startup notice.

The Application Cache contains the paired app's HTML, scripts, styles and small grain texture. It excludes HA state, background uploads, artwork, camera images and test-video segments. Since 2.21, a separate bounded localStorage record holds only the offline Startanzeige design and its selected image; see below. A separate scoped local record stores only the last valid HDMI input and fit. During offline startup that input opens full-screen immediately; HA layouts, widgets and notifications resume after reconnection. App version plus an asset-content digest invalidates old assets. Disabling the option obsoletes the manifest after the app contacts HA and removes its HDMI record. Removing pairing prevents network access, although already cached static code/HDMI can remain on the device until its cache is cleared.

Hardware evidence: the native reboot was issued, the LG web port became unreachable, and a subsequent capture showed HDMI in the SI launcher while all paired app endpoints returned 503 and HA reported the app disconnected. Endpoints and original OSD state were then restored. This verifies restart from an already populated cache, **not** a mains-loss test, cache durability after factory reset, or offline boot on every LG model. The local ZIP installation slot was left untouched.

### Platform diagnostics and video-wall configuration (2.18)

Press **Refresh platform diagnostics** / **Plattformdiagnose aktualisieren** on the LG device. Three read-only native calls run once; there is no extra background poll. The **Display app** sensor exposes `platform_diagnostics` with `sampled_at`, availability flags, `memory_bytes`, supported sensor values and `video_wall` geometry. CPU percentage requires two valid samples and uses cumulative counter differences; counter resets or changes in online CPU count omit the percentage. It describes the device's CPU activity, not only this app. RAM fields are native categories and should not be assumed to sum to total. Unsupported sensors are listed explicitly instead of reporting zero.

The resident app must be connected to configure a tile through **Developer tools → Actions → LG Professional Display: Configure video wall tile**:

```yaml
action: lg_rs232_ip.configure_video_wall
target:
  entity_id: media_player.lg_display_display
data:
  enabled: true
  rows: 2
  columns: 2
  tile_id: 1
  natural_mode: false
```

Rows/columns are 1–15, tile ID is 1–rows×columns, and natural mode compensates for bezels. Unspecified settings are preserved. The action reads the complete original settings, checks the requested geometry, applies it and verifies readback. On failure it attempts to restore and verify the original settings. It shares the normal control lock and OSD-suppression option; initially disabled OSD stays disabled. A device/network failure can prevent verified restoration and is reported as an error. Save the prior geometry before deliberate changes. Disabling tile mode does not imply resetting its row/column settings.

On the tested panel, 2×2 tile 1 was applied and captured, then the exact prior disabled geometry was restored. This configures **one display's crop**; it does not provide frame synchronization or discover/link multiple panels. No arbitrary native-service passthrough is exposed.

## Input select: direct HDMI and explicit app sources (2.19)

The display's **Input** select now exposes both routes:

- **HDMI 1 / HDMI 2 / HDMI 3**: select the native LG input and pause the resident app. This explicitly leaves the app, with the existing OSD-preserving switch guard.
- **App-HDMI 1 / App-HDMI 2 / App-HDMI 3**: show that HDMI input full-screen inside the resident SI app. If necessary, wake the display and resume the configured app. A failed app connection reports an error instead of silently changing to native HDMI.
- **App-Dashboard / App-Dashboard PiP / App-Mediaplayer** and **App-&lt;saved view name&gt;**: select the corresponding Studio view. Custom views appear, rename and disappear with the Studio library. Name collisions receive an `(App)` suffix so no HDMI option is overwritten.

App HDMI options require resident SI mode; Studio view options also require enabled custom layouts. They remain selectable while the app is paused so that selecting one can resume it. Notifications are temporary content and do not become permanent input sources. The current option follows the acknowledged app view or embedded HDMI, even when LG's native `xb` response still refers to the underlying HDMI input. Controller/app events update the entity immediately without adding TCP requests.

The media player, remote card and AV Companion keep their existing automatic routing: choosing HDMI there uses the connected resident app when available. Explicit native/app routing is provided by the **Input** select; existing media-player source names and the AV API remain unchanged.

### Reliable source-only wake (2.25.1)

Selecting a source through the media player, remote card or Input select explicitly wakes the display before applying the source. The remote card enables its input selector in confirmed standby. Native **Input → HDMI 1/2/3** keeps native HDMI; the media player's HDMI sources use the configured resident app, waiting for it to connect. **App-HDMI** and saved app views retain their explicit app routing. This also works after the app was paused by a native source selection.

The configured **Display startup timeout** now covers the initial TCP query, power command and confirmation together. Temporary connection loss or a missing power-on reply is retried within this budget; it is not reported as a rejected command. Readback precedes each retry, power writes are at least five seconds apart, and a confirmed ACK is not sent repeatedly while the panel boots. Native HDMI selection additionally tolerates up to 15 seconds of service readiness delay and verifies readback after a missing ACK. Each source write retains the existing OSD guard. A native source selected during this wake remains paused from the app’s perspective; a delayed maintenance poll cannot mistake the same startup for a new wake cycle and resume the app over it. Unanswered follow-up input queries retain the last confirmed source.

Power-off during startup uses the same bounded retries; an exact standby ACK or fresh off readback confirms shutdown. A newer source, power-off or HA shutdown supersedes the pending request, including while power readiness is being checked. A real timeout produces a bounded error without replaying the old source later. An intentionally disconnected external supply is still reported explicitly; use AV Companion to restore that supply. Network availability remains a prerequisite, and this does not add Wake-on-LAN or promise a shorter firmware boot.

### Starting an app source from standby (2.19.1)

LG can acknowledge power-on before its web services and resident app are ready. Selecting an app view or App-HDMI therefore retains the requested source while startup completes. The integration checks resident maintenance every five seconds during this bounded startup phase, honours the existing backoff after web errors and does not relaunch an SI app already in the foreground. It no longer relies solely on the normal polling schedule and a passive 30-second wait.

The app-readiness budget after power-on is 90 seconds, or the configured Display wake timeout if that is longer. The separate power-on timeout still applies. A new source, power-off or HA shutdown supersedes the waiting request. An expired request reports failure and is not replayed later; there is no automatic native-HDMI fallback. HDMI may remain black while the attached player is asleep, which must not be mistaken for the requested Mediaplayer view. Source application still needs the app's matching acknowledgement and uses the existing OSD guard.


### Faster startup and view-specific start screen (2.20)

When an explicit app-source request has to wait for connection, the integration retries failed web readiness checks after **five seconds** instead of the normal thirty. Each read-only foreground probe is limited to four seconds during this phase. Input/settings writes retain their existing transaction and timeout handling. The existing overall startup limit still applies, and an already foreground SI app is preserved. Outside an explicit start, normal thirty-second failure backoff avoids continuous load on an unavailable display.

Dashboard, Dashboard PiP, Mediaplayer and custom views receive a static, resolution-independent start screen. Since 2.21, the fixed Studio Startanzeige controls its content; the emergency fallback names the requested view. A small paired, uncached request starts before the full renderer loads. It contains only the current transient request; no intent or target label is embedded in cached HTML or saved to the panel. Since 2.21 only the separately configured offline design is saved locally. The screen disappears as soon as the target layout is rendered, or when the request is withdrawn, connection fails or its local deadline expires (at most ninety seconds). Warm view changes have no start screen.

**Full-screen HDMI is exempt.** The initial shell is transparent, cached HDMI can start immediately, and an explicit HDMI startup ignores a previously saved media/dashboard scene until source confirmation. A late response from the early startup request cannot overwrite the newer regular state. The separate brief “Home Assistant ist nicht erreichbar” notice retains its earlier behavior; it reports an actual connection problem, rather than covering HDMI with a loading screen.

The display firmware must first wake its panel, web services and SI browser. The app cannot draw during the firmware phase before its HTML executes. This feature reduces avoidable recovery waits and covers the application-loading phase; it does **not** install a model-dependent boot image, guarantee a zero-black-screen power-on, or keep the processor awake during standby. Boot-logo settings remain independent.

### Editable offline startup design (2.21)

Studio includes the protected **Startanzeige** view with local text/clock widgets, static backgrounds and one optional uploaded image. It is independent of normal layout enablement and is not a selectable source. Existing libraries gain this view without changing other designs. Import and save handlers reject connected widgets, entity bindings, media backgrounds and solar backgrounds in the fixed startup slot.

The paired early response and normal state expose only a content-version digest. The app requests `startup-design` once for a new digest; that bundle includes the scene, timezone and optional JPEG data URI (maximum 768 KiB raw image). Image preparation runs outside HA's event loop, retains 4K where possible and caches the result. The app atomically replaces one scoped localStorage record, validates it again before use and renders it with the shared layout engine. A visible local clock ticks once a minute. No extra decoder, live entity requests or animation loop is created. Main-state updates and unrelated Studio edits do not re-download an unchanged design.

The app sensor's `startup_design` attribute reports `version`, `cached` and `image_cached`. Studio compares the connected app's reported version with the current design before confirming local storage. Quota failures leave the in-memory design usable but do not claim persistence. Cache clearing, browser eviction and a changed pairing can require another online synchronization. The ordinary Application Cache option remains necessary to load the hosted code without HA.

Only design content is cached, never the transient startup request. When HA is completely unavailable at boot, the existing cached-HDMI path and short connection notice run; a previous non-HDMI source is not replayed. The firmware's earlier boot phase remains outside the app's control. See [Studio configuration](DISPLAY-STUDIO.md#startanzeige-ohne-live-daten).
