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
6. **Multi-input mapping:** independently associate HDMI inputs with player/remote entities, retaining one HomeKit TV. Current integration supports one linked player plus one content target.
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
