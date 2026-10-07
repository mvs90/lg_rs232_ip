# LG UH5F-H: reusable integration reference

Research date: 2026-10-02. Based on read-only inventory, authorized reversible presentation tests and official LG documentation. This is a model-family reference, not a claim that every firmware implements every documented feature. Private addresses, serial numbers, credentials and session cookies are excluded.

## Identity and evidence

| Item | Result | Evidence |
|---|---|---|
| Exact model returned by panel | **75UH5F-HJ** | `fv`, decoded hexadecimal ASCII |
| Product family | 75UH5F-H, 75-inch UHD Signage | LG product page and returned model |
| Software | **04.13.50**, raw `041350` | `fz`; this is not the webOS platform version |
| Installed platform | **webOS 4.0.1-136**, goldilocks-genepi | Authenticated platform info; regional product sheets use varying generation labels |
| Control protocol | LG RS232 commands over TCP, port **9761**, Set ID **01** | Successful matching acknowledgements |
| Web management | HTTPS **3737** redirects to **3777**, title “Content Manager / LG Signage” | Observed HTTP response and application HTML |
| Consumer TV endpoints | TCP 3000/3001 refused; 80/443 refused | One-time connection checks, not proof that these can never exist |

The initial UH5C identification was an estimate and is superseded by the panel's own model response. Do not apply a consumer webOS TV profile to this display.

## Sources, provenance and offline copies

- [LG 75UH5F-H product support](https://www.lg.com/lk/support/product/lg-75UH5F-H.ATC): associates the documents below with the model family.
- [LG webOS 4.0 User Guide, English, 100 pages](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA): linked by LG with publication date 2025-07-21. Relevant pages: 4 (Home/Mobile URL), 5–9 (content/server/URL), 47–60 (content management), 61 (Control Manager), 71–100 (command protocol).
- [LG UH5F-H Owner's Manual, English, 39 pages](https://gscs-b2c.lge.com/open/downloadFile?fileId=RRrpEksM0dmlHnErlN5tuQ): hardware installation and model specifications.
- [LG US UH5F-H specification sheet](https://www.lg.com/us/business/download/resources/CT00001837/LG_SPEC-SHEET_UH5F-H_Series_092059_LR%5B20201024_070213%5D.pdf): webOS 4.0, hardware and product capabilities.
- [LG regional UH5F-H specification sheet](https://www.lg.com/content/dam/channel/wcms/in/support/products/documents/UH5F-H-LG-UHD-Signage-Digital-Datasheet.pdf): webOS 4.1 label; do not treat it as a reading from this installation.
- [LG webOS Signage developer portal](https://webossignage.developer.lge.com/): SCAP/IDCAP documentation requires partner access. Consumer TV APIs are not evidence of Signage support.

Downloaded file SHA-256: user guide `45da5cd7a0169dafa5b26f9cb18fe102bb131fc7764cd754ed4ff6abee8fc493`; owner manual `690508f367e0298ecc7350c6bc5319871226d490ccd21abdb456cb7acdcc32c5`.

The research workspace keeps downloaded official manuals and exact per-installation recordings under ignored `local/`. Third-party projects should download the original manuals from LG; the repository does not redistribute them.

## Live read-only baseline

All entries below are point-in-time observations while HDMI 1 was active. Values can change. No power, source, picture, network, firmware or password setting was changed during inventory.

| Meaning | Query (Set ID 01) | Payload after OK | Interpretation |
|---|---|---|---|
| Power | `ka 01 ff` | `01` | On |
| Model | `fv 01 ff` | `3735554835462d484a` | ASCII `75UH5F-HJ` |
| Software | `fz 01 ff` | `041350` | Three version fields |
| Input | `xb 01 ff` | `90` | HDMI 1, DTV encoding |
| Temperature | `dn 01 ff` | `20` | 32 °C |
| Operating hours | `dl 01 ff` | `1c2a` | 7,210 h; hexadecimal, not decimal or guessed scaled seconds |
| No-signal power-off | `fg 01 ff` | `01` | 15-minute hardware fallback enabled |
| DPM | `fj 01 ff` | `00` | Disabled |
| Wired Wake on LAN | `fw 01 ff` | `01` | Enabled according to this generation's guide |
| Power after supply returns | `tr 01 ff` | `02` | Power On |
| Picture mode | `dx 01 ff` | `01` | General, not consumer-TV “Vivid” |
| Sound mode | `dy 01 ff` | `01` | Standard |
| Energy saving | `jq 01 ff` | `01` | Minimum |
| Backlight | `mg 01 ff` | `4b` | 75/100 |
| Brightness | `kh 01 ff` | `32` | 50/100 |
| OSD language | `fi 01 ff` | `02` | German |
| Screen mute | `kd 01 ff` | `00` | Off |
| Failover | `mi 01 ff` | `00` | Off |
| HDMI signal | `sv 01 02 ff` | `0201` | Signal present |
| Actual panel state | `sv 01 03 ff` | `0300` | Screen on |
| Configured PM mode | `sn 01 0c ff` | `0c05` | Network Ready |
| DPM wake criterion | `sn 01 0b ff` | `0b00` | Clock-based wake criterion |
| No Signal Image | `sn 01 a9 ff` | `a900` | Off; distinct from no-signal shutdown |

Rejected in this state: `dw` (fan status), `sv 07` (temperature-sensor bitmask), `sv 17` (illuminance). An `NG` means rejected/unsupported in the tested context; it does not establish a faulty fan or sensor. Do not expose invented zero measurements.

Serial number (`fy`) was recorded privately. It is not needed to select the product profile or publish compatibility results.

## Protocol rules for other projects

1. Use ASCII `command SetID data\r`. Replies end with `x`, not necessarily a newline. TCP can split a reply arbitrarily.
2. Match response command letter and Set ID. An initial `x` can be the command letter (for example `dx`), not the frame terminator. Close a timed-out connection rather than accepting its delayed frame for a later request.
3. `ff` is a read only where the individual command documents it. Never iterate a guessed command catalogue or send `mc ... ff`: `mc` sends a remote key.
4. For `sv` and `sn`, validate the echoed subcommand before interpreting the remaining payload: `OK0300` belongs to status `03`, not signal status `02`.
5. A plain integer parser cannot decode model names, serials, version strings or arbitrary multi-field replies. Preserve raw frames locally and use command-specific decoders.
6. Treat missing/NG replies as unknown; do not turn them into off, no-signal or hardware failure. Some commands need an active external input.
7. Software version is `fz`. `fw` is **Wake on LAN**. `fv` reads the model; the legacy `ng` mapping was wrong. Model support is not proven by a generic command dictionary.
8. DPM is a timeout value. This guide lists `00` off, `02` 10 s, `04` 1 min, `05` 3 min, `06` 5 min, `07` 10 min. The old boolean-on value `01` is not in this model's table.
9. Writes need a separate, deliberate acceptance test. A successful status read alone does not prove a setting can be changed in every mode.

Run a bounded, allowlisted inventory with Python's standard library:

```sh
python3 tools/read_display_inventory.py DISPLAY_IP --output local/inventory.json
```

Use `--include-serial` only for a private record. Outputs contain the installation address and must not be committed. No subnet scan, power cycle or authentication attempt is part of the tool.

## HDMI/audio topology and power domains

Owner clarification on 2026-10-02: **Apple TV → FeinTech AX310 HDMI 2.1 eARC audio extractor → LG HDMI 1**, plus the AX310 eARC output to Sonos. The LG lacks the required eARC connection. The extractor is **permanently powered and excluded from the display's switched socket**. In this installation it keeps Apple TV in standby when the LG loses mains power; the owner reports that display disconnection can otherwise wake Apple TV. No new mains interruption/A/B test was performed to verify the physical cause. See [AX310 reference](FEINTECH-AX310.md) for wiring, implications and remaining acceptance checks.

The existing HDMI1 signal/video inventory was therefore observed through an active extractor, not a direct Apple TV-to-LG cable. Do not infer source activity or a complete HDMI-chain power-down from the LG's supply state. The exact Sonos model and extractor EDID/CEC settings remain unrecorded.

## Standby design for this installation

The panel already has no-signal power-off enabled. Keep the integration's faster independently confirmed no-signal shutdown and continuous-idle fallback. The captured baseline contains a signal, so it is **not** a reproduction of the Apple TV standby fault.

DPM could provide another device-local response after signal loss; use the new optional DPM Delay selector to choose a timeout deliberately. Do not silently enable it: DPM, PM Mode, HDMI clock behaviour and wake control interact. An Apple TV may stop video without removing the clock. `sv 02` must be recorded during an actual faulty idle/standby event before deciding which combination works best.

`sn 0c` is the configured policy; `sv 03` is the current panel state. These are different concepts. “Screen off” may leave the computer/network alive and is not sufficient proof that it is safe to cut mains. The integration's existing confirmed-power-off requirement stays in effect.

With `tr=02`, restoring the smart plug makes the display turn on. This matters for startup sequencing and automatic-wake blocking. No supply interruption was tested.

## Authenticated platform inventory

The owner's authorized Mobile URL login succeeded. The separate settings administrator default did not authenticate this web interface. No password was changed or reset.

- webOS **4.0.1-136**, codename **goldilocks-genepi**; software **04.13.50**, MICOM **V1.02.0**, bootloader **4.03.67**.
- HTTPS **3777**: Content Manager; HTTPS **3737**: Control Manager. Both presented the same device certificate. Before login, Control Manager redirects to the login page.
- Input apps: `com.webos.app.hdmi1` = HDMI1, `hdmi2` = HDMI2, `hdmi3` = HDMI3/OPS/DVI, `hdmi4` = DisplayPort. These are app identifiers, not additional physical HDMI sockets.
- Observed HDMI1 video: 3840×2160, 60 Hz, progressive, 16:9, SDR. This describes the captured session, not all supported signal formats.
- Web capability flags include photo, transition, ratio, Control Manager, virtual controller and Play via URL; no fan control/check-screen capability. Such flags alone are not a functional acceptance test.
- Play via URL was off with an empty URL. No persistent URL, schedule, reboot, boot mode or password setting was changed.

## Direct content and notifications: confirmed results

| Feature | Hardware evidence | Integration |
|---|---|---|
| Native text overlay over HDMI | `sendToast` accepted; owner saw the text over Apple TV, HDMI stayed active | `show_toast`; LG controls duration |
| Native fullscreen PNG from internal storage | Owner confirmed image and return to Apple TV; unique test file deleted successfully | `show_native_image`; upload, timed display, foreground check, restore, delete |
| Native image with HTTP URL as `src` | Launch acknowledged, but panel showed “Wiedergabe nicht möglich” | Not used; upload first |
| Foreground detection | `getForegroundAppInfo` identifies `com.webos.app.dsmp`; `xb` can still report HDMI during transition, then `e0` | Never infer native player ownership from `xb` alone |
| Screenshot | Capture JPEG path downloads on **3737**, not 3777. Valid images confirmed at 640×360, 1280×720, 1920×1080 with HDMI content | v1.5 periodic preview camera |
| Play via URL / browser / dashboards | Setting visible; transient safe rendering not verified | Not changed; use external player/custom renderer |
| Multi Screen / PIP | LG-documented, input/layout dependent; not hardware-tested | Not exposed as arbitrary text composition |

### Observed internal web protocol

This is derived from the panel's own frontend and authenticated bounded tests. It is **not a supported public API contract**, not the consumer webOS SSAP API, and may change with firmware. v1.4 keeps it optional with certificate pinning and dedicated device cookies.

1. On 3777, check `/login/checkLoginStatus`, get `/login/captcha`, then the web UI's accessible representation at `/login/captchaText`. POST `/login/login` JSON with `passwd` and `captcha`. Authentication returns `data.result`; retain session cookies. A rejected login must not cause credential guessing or reset.
2. On 3737, open `/socket.io/?EIO=3&transport=websocket` with the same session. Engine.IO 3 / Socket.IO 2 sends `0{...}` then `40`; answer ping `2` with pong `3`. Send `42["api",{"command":"getForegroundAppInfo","eventID":1}]`; callback is `getForegroundAppInfo1` with `appId` and `returnValue`.
3. Text: command `sendToast` plus `message`; success arrives as `42["return",{"result":true,"from":"toast"}]`. No duration/clear contract was established. Alert/scroll commands exist in frontend code but are not yet verified for safe cleanup.
4. Image upload: POST multipart field `file` to `/file/contentManager` on 3777. Confirm `data.result` and the exact generated path under `/mnt/lg/appstore/signage/`. The integration only generates PNG/JPEG UUID names prefixed `ha_lg_`.
5. Play: PUT `/content/play/dsmp` with query parameter `reqParam` containing JSON `{"id":"com.webos.app.dsmp","params":{"type":"image","src":"/mnt/lg/appstore/signage/OWNED.png"}}`. Success is `data.payload.returnValue`. Read the whole HTTP body: a single stream read may return only a fragment. Wait for the native player to enter foreground; launch can be delayed.
6. Restore the saved external input using RS232/IP `xb`, then verify an external input app is in foreground. Only remove the owned asset once leaving playback is confirmed. Respect a user's different foreground app.
7. Delete: DELETE `/content` with `reqParam` JSON `{"path":[{"deviceId":"INTERNAL_STORAGE_SIGNAGE","subDeviceId":"","itemPath":"/mnt/lg/appstore/signage/OWNED.png","type":"image"}]}`. Verify `data.payload.returnValue`. Do not enumerate/delete unrelated media.

`/content/list` can list MEDIA records (including `fileName`, `fullPath`, `mediaType`, `udn`). Filtering on `fileName` was rejected because no matching database index exists; the integration avoids that dependency. Private inventory results, serial numbers, passwords, cookies and certificate fingerprints are excluded from this repository.

## Web login and trust

On the **LG remote**, press **Home → Mobile URL** and read the web address and initial web password. LG distinguishes it from the settings/admin default. The initial web password is no longer displayed after it has been changed. Do not reset credentials to collect an inventory.

The production client pins the SHA-256 device certificate on both web ports. Obtain its fingerprint from browser certificate details or `tools/read_web_certificate.py`, then configure it with the web password. Browser certificate trust is separate from integration certificate pinning. The login CAPTCHA flow was explicitly authorized by the owner and exercised through the UI's own accessible challenge representation. No authentication checks are bypassed.

## Improvements implemented from these findings

- Correct `fv` model decoding and `fz` software/firmware reporting; real identity in HA device information and sanitized diagnostics.
- Documented DPM timeout selection and corrected legacy DPM switch semantics (on selects 1 minute).
- Optional signal, current panel-power and configured PM-mode sensors with subcommand validation and unknown-state handling.
- UH5F-specific picture-mode labels and color-temperature command range; corrected OSD language mapping and automatic energy-saving option.
- Fixed frame assembly for replies whose command letter is `x`, verified against the actual picture-mode reply.
- Removed the undocumented abnormal-state query, unused speculative command catalogues and heuristic operating-time parser.

These changes are covered by automated tests. Identity and status reads are checked on the actual panel; power cycles and physical HomeKit interaction have not been tested on it. Native text overlays and fullscreen image/return were visually confirmed; the production client also passed upload/play/foreground/restore/delete checks.

## Useful next extensions, in priority order

1. **Additional native media formats:** test a bounded local video with documented codec constraints and restoration. Keep arbitrary URLs, dashboards and persistent schedules separate from notifications.
2. **Hardware standby acceptance sequence:** capture `ka`, `xb`, `sv 02`, `sv 03` during Apple TV playing, paused, normal standby and erroneous idle. Verify wake via remote after each relevant PM setting.
3. **Capability profiles:** identify model/firmware at setup, hide unavailable choices and distinguish explicit NG from transient no-response. Use recorded fixtures for each family.
4. **Blank-screen mode with retained audio/network:** expose verified screen mute as a deliberate action and restore it; do not confuse it with mains-safe standby.
5. **Thermal and operating-hours alerts:** build HA automations from the existing temperature/hour sensors. Thresholds must come from the exact model's operating limits, not an invented generic warning temperature.
6. **Multi-input mapping:** independently associate HDMI inputs with player/remote entities, retaining one HomeKit TV. AV Companion supports one linked player plus one content target; the LG base has no foreign entity links.
7. **Brightness automation:** prefer HA time/sun-based backlight control. The ambient-light status query was rejected, so do not rely on a claimed light sensor without further evidence.
8. **Richer overlays:** basic native text is confirmed. Scrolling text, modal alerts and layout control need individual duration/clear/ownership tests before exposure.


## OSD suppression during transitions

The LG webOS 4 guide calls `kl` **OSD Lock**: `00` locks/hides OSD; `01` unlocks/enables it. This is separate from remote/key lock (`km`). The existing OSD Select entity's enabled state therefore corresponds to `kl=01`.

The optional transition guard reads `kl ff` without cache, suppresses only a confirmed enabled OSD, and restores only its own temporary change after a two-second settling interval. It covers RS232 input switches and native-player launch. Initially disabled/unknown OSD is untouched. Explicit HA OSD-switch intent supersedes the temporary restore. See the feature guide for concurrent-controller and hard-crash limits.

Live OSD test: `kl ff` initially returned `01`, disabling returned `00`, and a read during the native image confirmed `00`. The panel rejected restoring `kl 01` during DSMP playback. Therefore the integration retains ownership of its temporary lock until returning to an external input and retries there. It must not mistake that owned temporary off state for the user's pre-existing off preference. A newer explicit HA OSD-switch request clears this ownership.

The final guarded hardware test confirmed **OSD 01 → 00 during native playback → 01 after HDMI return**, with the temporary image deleted and no pending restore error. The owner also confirmed that no OSD information appeared during that switch.


## Boot logo and capture follow-up (v1.5)

- `sn 01 a3 ff` returned `n 01 OKa301x`. A reversible setting test confirmed `sn 01 a3 00`, readback off, restore `sn 01 a3 01`, readback on. Original state restored; no reboot/power cycle was performed.
- LG's guide page 26 documents USB `LG_MONITOR`/`lg_monitor`, BMP/JPG, and **1920×1080 maximum boot-logo image** for UHD panels. A UH5F no-signal image can be 3840×2160; do not confuse these limits.
- Inspected Content Manager and Control Manager frontend code exposed no verified boot-image import route. The integration prepares a USB-ready JPEG in HA Media rather than claiming that an ordinary content upload installs a boot logo.
- Capture command: `42["api",{"command":"capture","height":720,"eventID":1}]`. The callback `capture1` contains a **string**, e.g. `/tmp/captureTIMESTAMP.jpg`, rather than the usual result dictionary.
- Download that exact validated path immediately from authenticated **HTTPS 3737**, using the same pinned device certificate and cookies. Port 3777 returns HTTP 404, explaining the earlier unsuccessful probe. Do not treat returned paths as arbitrary URLs or filesystem paths.
- The client returned valid JPEGs at requested heights 360/720/1080. Visual inspection confirmed real HDMI pixels. The frontend's `captureRefresh` interval is 10 seconds. No continuous-video stream was established; v1.5 offers rate-limited screenshots instead.
- Screenshot captures only remain in RAM in the integration. Private development captures are excluded from version control. Boot logo preparation and camera collection do not modify input, OSD or panel power.

## Native video / website / HLS verification (2026-10-02)

- A generated 640×360 H.264/yuv420p MP4 was uploaded to owned internal storage, played by DSMP and confirmed through a captured frame. HDMI1 restoration and temporary-file deletion succeeded.
- Passing an HTTP MP4 URL directly to `/content/play/dsmp` returned a launch acknowledgement but made no source fetch and left HDMI1 active. No remote-video capability is inferred from that acknowledgement.
- `getPlayViaUrl` initially reported mode off and an empty URL. `setPlayViaUrl` writes successfully but gives no setter callback on this firmware; subsequent getter readback confirmed the setting.
- Setting a local test URL and selecting documented input `E3` opened `com.webos.app.browser`, requested the HTML page and rendered it. No reboot was needed. A generic browser launch through the DSMP endpoint had not opened it.
- A native HTML `video` element with muted autoplay fetched a local HLS playlist and its MPEG-TS segments; a captured frame confirmed rendered video. This test used a short HLS playlist, not a commercial live/DRM provider.
- Both browser probes restored the initial URL setting and HDMI1. Captures stay private. The production implementation preserves original URL settings and journals pending recovery in HA storage.

See [native media actions](../NATIVE-MEDIA.md) for user-facing examples and compatibility limits. A browser fullscreen hint appeared in an exploratory capture; do not promise suppression of every browser-owned message merely from the input OSD option.

Final controller round-trip checks also ran both website/HLS and native MP4 with `suppress_osd_during_switch` enabled. Both completed without `presentation_error`, returned to HDMI1, and restored the originally enabled OSD; URL mode was off with its original empty value afterward.

## SI application and external HDMI plane — 2.3 investigation

The publicly distributed [LG webOS CLI](https://github.com/webos-tools/cli), npm `@webos-tools/cli` 3.2.6, includes Signage SDK templates. Its `files/templates/signage-sdk-templates/scap_api/1.5.0/js/cordova-cd/configuration.js` documents the following `commercial` settings through `getServerProperty` / `setServerProperty`; `inputSource.js` creates the external-video element. No third-party SDK code is bundled by this integration.

| Native field | Observed / supported values |
|---|---|
| `appLaunchMode` | `none`, `local`, `remote`, `usb`; hosted prototype uses `remote` temporarily |
| `appType` | `zip` / `ipk`; hosted launcher tested with `zip` |
| `fqdnMode`, `secureConnection` | Native strings `on` / `off` |
| `fqdnAddr` | URL of hosted app entry point |
| `siServerIp`, `serverIpPort` | Native strings, preserved from the previous configuration |

Control Manager's authenticated Socket.IO `_api` methods `getSystemSettings` / `setSystemSettings`, category `commercial`, read and write these seven fields. The getter returns a flat dictionary; the setter uses `shouldCallback: true`. Each mutation was verified with a fresh readback, and the original settings were restored. The launcher is **`commercial.signage.signageapplauncher`**, started by the Control Manager's exact method spelling **`setInputSouce`**. `com.lg.app.signage` is the conventional separately installed app ID and was not installed on this panel; treating it as the hosted launcher was rejected. SI-to-HDMI return was verified with the same web method and the original `com.webos.app.hdmi1` ID.

Within the hosted SI app, `PalmSystem` and `PalmServiceBridge` are present; the browser reports Chromium **53.0.2785.34**. A `<video autoplay><source type="service/webos-external" src="ext://hdmi:1"></video>` produced the running 3840×2160 HDMI source. Metadata arrived before dimensions were nonzero, so the app waits for actual video dimensions before confirming an HDMI layout. CSS places the native HDMI plane under the notification or in a smaller PiP rectangle. Both results were captured on the real panel; see release evidence for complete HA tests.

webOS can retain a launched SI page in memory after returning to HDMI. Changing `fqdnAddr` alone did not refresh that cached prototype. The production app closes on leaving the foreground and refreshes when its version changes; its stable paired endpoint serves current state without relaunching for every sensor update. Two deliberate display restarts were used during development to remove earlier disposable pages. Routine production notifications require no display restart.

The public SDK also describes privileged functions such as `changeLogoImage` and `restartApplication`; presence in the SDK or presence of `PalmServiceBridge` is **not** proof that every call is permitted in this hosted app. They have not been added as unrestricted Luna command passthrough. Existing USB boot-image workflow remains unchanged.

SI settings enable this app path. SuperSign server settings configure LG's separate management products; Crestron settings target Crestron control systems. Neither was changed. HDMI-in-app is a useful basis for a future resident app but this release does not claim continuous standby/CEC/HDCP/audio acceptance.

## Direct app screenshots — hardware investigation, 2026-10-02

This feasibility probe preceded the optional resident mode and automatically selected app camera backend in 2.4. The measurements below isolate the platform calls; production acceptance is recorded separately in RELEASE-TESTS. Version 2.3.0 used only Control Manager capture/download and timed app presentations.

The public LG CLI's SCAP `Signage.captureScreen` implementation calls the platform bridge with:

```javascript
var bridge = new PalmServiceBridge();
bridge.onservicecallback = function (raw) {
  var result = JSON.parse(raw);
  // Validate returnValue, encoding, size and JPEG bytes before accepting data.
};
bridge.call(
  "luna://com.webos.service.commercial.signage.storageservice/captureScreen",
  JSON.stringify({save: false, width: 1280, height: 720})
);
```

On this panel, an ordinary hosted SI app successfully received `returnValue: true`, `encoding: "base64"`, `size` and `data`. The reported size matched the Base64 string length, not the decoded JPEG size. Three decoded 1280×720 images measured approximately 46–52 kB. Visual inspection confirmed the **HDMI programme and the app overlay together**, not just HTML or a black video plane. `save: false` avoids requesting a saved capture file. A 128×72 thumbnail also succeeded. The newer wrapper route `luna://com.webos.service.commercial.scapadapter/captureScreen` succeeded as well.

| Path | Samples | Observed duration |
|---|---|---|
| Existing authenticated Control Manager capture plus JPEG download, 1280×720 | 3 | 754–836 ms |
| Direct app `storageservice/captureScreen`, 1280×720 | 3 | 573–605 ms |
| Direct app capture, 128×72 | 1 | 368 ms |
| Direct app `scapadapter/captureScreen`, 1280×720 | 1 | 647 ms |

These are short sequential measurements with no competing HA camera requests. The existing-path timing includes the network download; app timing measures invocation to platform callback and **excludes the subsequent upload to HA**. The different programme frames and small sample count do not establish a sustained frame rate, a fixed percentage improvement or lower CPU use. They do establish that the app can obtain real HDMI pixels without the separate authenticated temporary-file download. An efficient implementation can send bounded binary JPEGs into the existing shared camera cache and capture only as quickly as viewers and the panel need, with the existing web path as fallback.

The runtime exposes `MediaRecorder` and canvas `captureStream`, but the external HDMI video element has **no `captureStream` method**. API presence on a canvas does not demonstrate access to the native HDMI video plane or a hardware encoder. No native HDMI H.264/WebRTC/RTSP capture route was found in the inspected SCAP wrappers or verified on the device. Feeding periodic screenshots into a video container would not increase the underlying capture rate. This test does not establish capture compatibility with all protected-content providers.

The local HA test container was stopped during the short probe to release the shared RS232 connection and prevent competing capture requests. The same production OSD transition guard covered both app launch and return. Final readback confirmed original HDMI1, identical original SI settings and original OSD enabled. HA 2026.9.4 was restarted and the LG and UniFi integrations returned to loaded state. No display reboot or permanent autostart change was made; screenshots and pairing URLs remain private.


### Resident source switching and latency — 2026-10-03

With app 1.2.0 / integration 2.5.0, changing the existing `service/webos-external` source and calling `video.load()`/`video.play()` changed HDMI 1 → HDMI 2 → HDMI 1 without leaving `commercial.signage.signageapplauncher`. The video DOM element is retained. HDMI 2 had no signal; zero video dimensions must be treated as signal absence, not loss of the app. Message/layout acknowledgements must not wait for those dimensions.

Removing repeated Control Manager foreground/settings reads from each notification and allowing content replacement reduced six measured request-to-render-acknowledgement times to 38–87 ms on this installation. Periodic ownership checks remain enabled. A lost heartbeat no longer triggers a native HDMI/SI relaunch cycle: the already loaded video plane remains and its long poll reconnects. See the 2.5 [acceptance record](../RELEASE-TESTS.md) for hardware, methods and limits. HDMI source changes retain the OSD guard, including its settling delay; layout changes require no OSD command.


## Picture-control verification — 2026-10-05

The live configuration used AUTO energy saving, General picture mode, DPM 1 minute, PM Network Ready and Original aspect ratio. Manual backlight 75 → 70 → 75 succeeded with energy saving Off, Minimum and Medium; Auto/Maximum prevented manual control. The panel's Control Manager also locks its slider during brightness scheduling or screen-off. DPM remained enabled during successful manual writes. APS with energy saving Off exposed its own backlight value (100), so do not infer an unconditional lock from the preset name.

`kc 02` and `kc 06` were acknowledged and read back in the SI app. App 1.7.2 mirrors the choice to the same HDMI element's fill/contain geometry; screenshots verified a deliberately non-16:9 rectangle. Original source, library and picture/power policies were restored. No DPM power-off test or active-programme scaling claim is made. [Full implementation and reusable dependency reference](../PICTURE-CONTROLS.md).

## SI rendering density (2026-10-05)

The hosted SI app on 75UH5F-HJ / firmware 04.13.50 / webOS 4.0.1-136 reports `innerWidth=1920`, `innerHeight=1080`, `screen.width=1920`, `screen.height=1080`, `devicePixelRatio=2`. Use logical CSS geometry and DPR-aware images; do not force a 3840-pixel CSS viewport or assume DPR=1. LG integration 2.12 exposes these bounded values in the Display app sensor's `rendering` attribute. This measurement guides UHD asset selection but does not independently establish GPU framebuffer precision. Native capture remains at most 1920×1080. Real Sonos AirPlay artwork during this test was 512×512, which remains a source-quality limitation.

## Additional video and platform capability tests (2026-10-06)

Tested unit: **75UH5F-HJ**, firmware **04.13.50**, webOS **4.0.1-136**, Chromium **53**. Only HDMI 1 carried an active signal; the owner confirmed HDMI 2/3 had no source attached. Tests used a local synthetic H.264 clip, not a door-camera feed.

| Capability | Evidence on this unit | Integration decision |
|---|---|---|
| HDMI plus MP4 | Native capture showed the running 3840×2160 HDMI picture beside a playing 640×360 MP4. Both video elements reported readiness without error. | One additional muted camera/video widget alongside the retained HDMI plane. |
| HDMI plus HLS | Native capture showed both pictures for direct and animated entry. Local H.264/MPEG-TS HLS decoded at 640×360 and playback time advanced. Some early captures showed black video planes despite readiness; captures after eight further seconds showed both pictures. | Bundled local HLS test stream; HA-camera HLS is attempted with optional still-image fallback. This does not establish instantaneous visible startup or every HLS codec/container variant. |
| Live-video overlap | A ready second decoder was hidden by full-screen HDMI despite HTML ordering. Separate rectangles rendered both pictures. Opaque widget surfaces also covered the native plane. | Keep stream rectangles separate and transparent; use HA-camera snapshots for overlays. Decoder readiness alone is insufficient. |
| HA-camera snapshot overlay | A temporary HA Generic Camera served alternating synthetic PNG frames. Native capture showed its image above full-screen HDMI; image requests stopped after removing the widget. | Automatic mode uses snapshots for overlap; 1–30 s interval with bounded requests. |
| Two independent HDMI sources | A second `service/webos-external` tag with `ext://hdmi:2` was accepted but reported 0×0 and rendered black; HDMI 1 remained visible. | **Not proven** without a second active input. Keep one HDMI element per scene. |
| Export HDMI video to HA | External video `captureStream` was undefined. Canvas readback after drawing HDMI raised a cross-origin `SecurityError`. A follow-up `enumerateDevices()` returned only an audio output, no video input. `MediaRecorder`/canvas capture existing globally did not provide HDMI access. | No continuous HDMI stream advertised. Continue bounded native JPEG capture. |
| Offline app startup after reboot | With the optional app cache populated, the display rebooted, its web port went down, and a native capture after boot showed HDMI while paired HA endpoints returned 503. | Opt-in cached startup in 2.18. Not a mains-loss/cache-eviction guarantee. Unknown local ZIP slot left untouched. |
| UDP multicast | H.264/MPEG-TS sent to a 239.x.x.x group rendered visibly beside HDMI; timed return released the extra decoder. | Configurable Studio multicast source in 2.18, one additional muted stream. |
| Video-wall geometry | Native 2×2/tile 1 settings applied and read back; capture showed the cropped image; exact disabled original restored. | Verified per-panel action with OSD protection and rollback attempt. Multi-panel synchronization remains untested. |
| Platform sensors | Native temperature and backlight returned valid numbers. Illuminance, humidity, rotation, fan and screen-check returned `Unsupported or Error`. | On-demand native diagnostics; unsupported values are absent, never synthetic zero. No external sensor hardware was connected. |

Official [75UH5F-H specifications](https://www.lg.com/au/business/information-display/digital-signage/uhd-digital-signage/75uh5f-h/) list four video tags and PiP/PBP. The [large-panel LG data sheet](https://www.lg.com/us/business/download/resources/CT00001837/LG_SPEC-SHEET_UH5F-H_Series_092059_LR%5B20201024_070213%5D.pdf) and [Signage developer portal](https://webossignage.developer.lge.com/) provide platform context, not a guarantee that all combinations work on this firmware. The official [LG CLI source](https://github.com/webos-tools/cli) includes public Signage templates and SCAP wrappers; detailed current platform documentation remains partner-restricted.

Private captures and exact device records stay in ignored local storage. Test tooling unloads only the LG config entry when it needs the exclusive TCP channel. The common HA container must remain running during such probes. Restore the configured SI endpoint **after it is available again**: loading a temporarily absent endpoint can leave a 404 document without the app's reconnection logic. A foreground launcher ID alone is not proof of a live app; require a versioned heartbeat and a visible capture.


### Reusable SCAP and offline findings — 2.18 (2026-10-06)

The following calls ran inside the paired foreground SI app through `PalmServiceBridge`. Their availability is a finding for this exact model/firmware, not a cross-model promise. Implementations use a fixed allowlist and bounded replies; no SDK source is bundled.

| Luna URI suffix under `luna://com.webos.service.commercial.scapadapter` | Parameters / result |
|---|---|
| `/getSystemUsageInfo` | `{cpus: true, memory: true}` → `memory.total/used/free/buffer/cached` in bytes, `cpus[].times.user/nice/sys/idle/irq` counters. Total observed RAM: 2,080,919,552 bytes. |
| `/deviceInfo/getSensorValues` | `{}` → temperature 36 °C and backlight string `75` in the sample; other listed fields unsupported. Values are measurements, not operating limits. |
| `/signage/getTileInfo` | `{}` → `enabled`, `row`, `column`, `tileId`, `naturalMode`. Disabled mode can retain non-default geometry; preserve it exactly. |
| `/signage/setTileInfo` | **`{tileInfo: {enabled, row, column, tileId, naturalMode}}`**. The outer `tileInfo` is mandatory. A flat object in an exploratory test caused `Message status unknown` and a temporarily unavailable SCAP service. The correctly nested call passed apply/readback/restore. Tests now assert the wrapper shape. |
| `/power/executePowerCommand` | `{powerCommand: "reboot"}` worked for the controlled cache acceptance test. No generic reboot/native-command action was added. |

The legacy `commercial.signage.storageservice/getSystemUsageInfo` also responded. Public SDK documentation for `Signage#setTileInfo` in the official [LG CLI templates](https://github.com/webos-tools/cli) specifies the nested parameters. The installed template set used for this investigation includes SCAP 1.7.6 and the detailed 1.5.0 API reference.

App inventory: `applicationManager/dev/listApps` returned unknown method. `getApplicationList` listed SuperSign and Screen Share, while `getAppInfo` for the SI ID describes the built-in launcher under `/usr/palm/applications`. Neither reliably identifies or backs up the separate local ZIP application slot. Local installation was therefore not attempted. Storage `spaceInfo` returned numeric strings whose units were not established; these are not exposed as invented byte counts.

Offline support: `applicationCache` exists on Chromium 53. The page is not a secure context, so a modern service-worker fallback is not assumed from API presence. The optional manifest caches static, token-scoped app assets only, uses version and asset digest for updates, and permits network requests separately. A scoped local HDMI record restores the native external-video plane before state polling succeeds. The production-code test used a bounded one-shot reboot hook, explicitly verified the port outage, captured HDMI with app endpoints disabled, then removed all test hooks and confirmed normal reconnection. A native capture proves visible HDMI after boot; it does not prove persistence after physical AC removal.

Multicast acceptance used a bounded H.264/yuv420p MPEG-TS sender with TTL 1 and an explicit LAN interface. Two captures three seconds apart confirmed changing test-video content alongside HDMI. The production Studio view, timed return and decoder teardown were exercised, then the original view library was restored. Network routing/IGMP settings were not changed. Continue testing other codec/resolution combinations individually.

Still requiring additional equipment or interfaces: two active HDMI inputs, synchronized video across multiple panels, compatible external sensors, and native continuous HDMI encoding/export. HA entity widgets already provide an independent path for room/environment data without relying on unsupported LG sensors.


## Startup timing and display indication (2.20, 2026-10-06)

On the tested 75UH5F-HJ, a confirmed standby followed by an explicit app-source selection gives a power ACK quickly, then starts the cached SI app's requests after roughly 19–20 seconds. The native LG web login can still fail with connection errors until approximately 50 seconds. Thus browser readiness and native web-control readiness are separate phases; shortening reconnect backoff alone does not guarantee a faster overall start. Measured Mediaplayer completion was 51.8/53.8 seconds and App-HDMI 1 was 50.8 seconds.

The static start screen is confirmed in a capture returned by the physical app during the Mediaplayer wait. It uses a fresh HA request rather than a remembered boot target. Full-screen HDMI bypasses it; a pending HDMI start also ignores a previously saved non-HDMI scene until normal acknowledgement. The web API's earlier unavailability is not evidence that the app cannot render local HTML. Conversely, the app cannot draw before the LG SI browser runs. The existing USB boot-logo workflow and power modes remain independent.

## General/system settings verification (2026-10-07)

Six settings were exposed and reversibly tested through the existing HA 2026.9.4 container: Smart Energy Saving, Signage name, Set ID, power-on delay, no-signal image and on-display temperature unit. All original values, selected App source and stored Studio configuration were restored/preserved. Live sun/entity values naturally change over time and are not part of the saved library comparison.

The Control Manager's public name endpoint returns a string: `getSignageName` → `signageName1`; writing uses `setSignageName` with a `signageName` argument and subsequent readback. The native form limits names to 32 UTF-16 code units. **Do not use `commercial.signageName` as the actual name:** its value differed from the public API and changing it did not rename the device. The preliminary test restored that shadow value.

The active Set ID is read through `getSetID` → `getSetID1` (`setId` integer). Writing `setSystemSettings`, category `option`, setting `setId` changes the actual RS232 address. **`commercial.signageSetId` is a separate shadow value:** modifying it did not change the public Set ID. That preliminary test was rejected by the integration's readback and its shadow value restored.

Confirmed actual IDs **1 → 2 → 1000 → 1** with fresh RS232 power queries at each address and persistent HA address storage. An entry reload while at ID 2 retained working control. Parse hexadecimal IDs numerically, accepting 2–4 digit representations; do not restrict responses to two digits or send broadcast address 0. The firmware also set `commercial.powerOnDelay` to **249 seconds** on selecting ID 1000. This dependent change is returned to HA and remembered for the wake deadline. It was separately restored to the original 0 seconds. Do not infer a general ID-to-delay formula from this one observation.

`commercial.smartEnergy`, `powerOnDelay`, `noSignalImage` and `temperatureUnit` accepted individual writes and fresh readback. With Energy Saving OFF, manual Backlight **75** remained writable with Smart Energy Saving both off and on; DPM and PM were unchanged. Switching the on-display temperature unit to Fahrenheit left the fresh RS232-backed HA sensor at **35 °C**, as before; Celsius was restored. This does not measure luminance or energy reduction, and toggling the no-signal image did not deliberately interrupt HDMI to test its visual artwork.

The feature uses three bounded native requests per minute for all six entities, without depending on the resident app or adding a display rendering loop. See [system settings](../SYSTEM-SETTINGS.md) for setup, automation, unavailable-state and address-recovery behavior. Downloaded device HTML/JavaScript, response inventories, names, credentials and captures remain private and excluded from Git.


## Power configuration acceptance (2.27.0, 2026-10-07)

The physical 75UH5F-HJ accepted and freshly read back `fg` and `mn` on/off, wired `fw` and wireless `sn 90` on/off, PM `sn 0c` values 00–05, AC power-on `tr` values 00–02, and DPM wake `sn 0b` values 00–01 through the existing HA control connection. Native `getPmMode` independently confirmed all six PM names, including `screenOffBacklight`. No IR also maps to `commercial.noActivityOff=4hours`, wired WoL to `commercial.wolEnable=1`, and DPM wake to `commercial.dpmWakeUpControl`. Do not substitute similarly named shadow database keys such as `wolMagicPacket`, `wolWireless` or `acOn` for these documented control commands.

The current restored DPM wake value is Clock + DATA; the earlier read-only baseline above recorded Clock on a different date. Tests preserve the setting found immediately before a run. Configuration confirmation does not prove actual WLAN wake, timer expiry or thermal behaviour. All power settings, the displayed app source and Studio data were restored/preserved. See [power settings](../POWER-SETTINGS.md) and [release tests](../RELEASE-TESTS.md).

## Clock and ISM configuration acceptance (2.28.0, 2026-10-07)

The native Control Manager exposes `getNTPStatus`/`setNTPStatus`, `getCurrentTime`/`setCurrentTime` and `getTimeZone`. The NTP setter returns boolean `true`; the time setter has no ACK event on this firmware and needs an independent fresh clock read. Despite its `utc` parameter name, its calendar fields are local display time. Parse the GMT offset in `getCurrentTime.current` rather than assuming HA's timezone. The clock has minute precision; manual editing is disabled while network time is on.

Commercial NTP settings use `ntpServerMode: auto/manual`, `ntpServerType: ipv4/ipv6/url` and the matching `ntpServerIpv4`, `ntpServerIpv6` or `ntpServerUrl`. Real HA actions confirmed all address types and restoration to the original defaults. This verifies stored settings, not NTP reachability. Timezone and manual daylight-saving rules remain in the LG menu.

`ismTimer` accepts `immediately`, `repeat` and `scheduling`. With an active method, repeat exposes `ismPeriod` (1–24 hours) and `ismTime` (1–10, 20, 30, 60, 90, 120, 180, 240 minutes); scheduling exposes `ismDays` and distinct `ismStartTime`/`ismEndTime` (minutes since midnight). Day codes are uppercase `MON` through `SUN`; a Tuesday selection saved in the physical menu independently confirmed `TUE`. Start/end can be returned as either integers or decimal strings. All seven weekday switches and supported modes were changed and restored through HA.

LG documents ISM image/video import from a USB root folder named `ISM`. Content Manager uploads are separate from this special storage. No direct network import into ISM storage was confirmed. HA can prepare and serve fitted images or bounded MP4 files; a USB import at the panel is still required. USB import and timed ISM playback were not exercised. See [clock/ISM reference](../CLOCK-ISM.md) for exact controls, limits and the official manual.

## Picture configuration acceptance (2.29.0, 2026-10-07)

The real HDMI 1 menu and HA actions confirmed all nine Signage `dx` modes: Mall/QSR, General, Government/corporate, Transportation, Education, Expert, APS, Calibration and Hospital. The previously hidden mode entity is now attached to the LG device and translated. The generic consumer-TV mapping was removed. For supported ranges, automation IDs, transport frames and the wider menu audit see [settings coverage](../SETTINGS-AUDIT.md).

Authenticated `getPictureDBVal` reads the active native picture context. The reference firmware returns `pictureModeSettingsActive` and `pictureControlLimitation` as strings. Its setters use `pictureSettingModified` indexed by the native preset (`normal`, `expert1`, etc.). All offered dynamic contrast/colour, Super Resolution, noise/MPEG reduction and gamut values were changed and independently read back; preferred skin/sky/grass tones accepted −2 and +2. `colorGamut=wide` is not an offered value: this firmware uses `auto` / `extended`. Expert/Calibration/Hospital have different editing constraints.

Gamma accepted all four protocol values. Black level accepted Low and High, but rejected Auto in the current external HDMI context. UH5F therefore offers Low/High, or only Auto if the device reports an automatic context. Sharpness uses 0–50. UH5F `xu` temperature codes `70`–`d2` correspond to 3200–13000 K; a 6500 K write and return to the original 10000 K were independently confirmed. The active input and stored preset matter: the app and native HDMI can expose different picture memories.

A reset was tested on the previously unmodified Expert preset: contrast 80 → 79 through HA, then `fk 00` restored all fields of the saved active picture database, including its unmodified flag. Returning to General reproduced the pre-test picture database without differences. `fk 02` was never sent. Apply-to-all `sn 52 01` is implemented and has exact-frame/ACK/settling tests, but was not physically executed because it can overwrite unbacked picture memories on other inputs. The web API ignored explicit dimension arguments (including an invalid dimension) and returned the active context, so it cannot be treated as a backup of all input profiles.

The observed picture database lists seven basic values for preset copying: backlight, contrast, brightness, sharpness, colour, tint and colour temperature. Its copy-target list also includes internal movie/photo/default contexts, not just the three physical HDMI sockets. The integration delegates the action's actual copy scope to firmware. It does not claim to export or restore every picture memory.

The native schema exposes motion options, but the active TruMotion mode is absent from the verified read response. Real Cinema is greyed out for the current 2160p60 signal. No guessed motion-setting writer was added. HDR and automatic-backlight range controls require valid model/context readback; see the release acceptance for the actual unavailable cases. Device firmware frontend copies, schema captures and programme screenshots remain private.
