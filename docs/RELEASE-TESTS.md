# Release acceptance — 2026-10-02

## LG 2.3.0: hosted SI app, HDMI overlay and PiP

**218 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 44 browser tests pass across Chromium and WebKit.** New coverage includes real token-scoped HTTP routes, fragmented/oversized/invalid event requests, URL and sensor validation, expiry, restored settings after ambiguous writes/restart/cancellation, foreign-SI/input ownership, no-wake recovery, website fallback, and the actual OSD guard with initially enabled and disabled OSD. Frontend tests exercise plain-text rendering, acknowledged paint, blanking private content after connection loss, HDMI readiness before acknowledgement and remote-card actions. Browser HDMI-plane properties are simulated; hardware results below are separate.

In the shared **HA 2026.9.4 Docker instance**, setup was completed through HA's ordinary options flow. The physical **75UH5F-HJ / 04.13.50 / webOS 4.0.1-136** loaded the HA-hosted app through its SI launcher and reported its platform bridge. Fullscreen, HDMI-overlay and HDMI-PiP actions each completed with a rendering acknowledgement, no presentation error, the original HDMI 1 foreground app, and byte-for-byte equal SI settings after return. The configured 12-second displays took roughly 22–24 seconds including setup, launch and restoration. This timing is not a guaranteed instant-overlay latency.

Private panel captures verified the full-screen message/selected sensor, a notification over the running HDMI picture, and a smaller HDMI picture beside the HA overview. A fresh multi-frame HA camera stream was used for PiP verification after a normal cached screenshot initially still showed the prior HDMI view. A separate 30-second PiP presentation was cancelled through `clear_content`; HDMI and SI settings were restored with no presentation error. Public documentation contains no captured programme imagery or private pairing URLs.

The OSD option stayed enabled throughout these app tests. Additional physical HA switch tests started with OSD **on** and **off**: the final state matched each initial state, and manually disabled OSD remained off during the app. The transition-only suppression code is covered by software command-sequence tests; a state query several seconds after launch is not evidence of the short suppression interval itself. The panel's original OSD-on state and the temporarily enabled OSD test entity's registry setting were restored.

The user authorized these display tests, including reversible SI changes and development restarts. No SuperSign/Crestron setting, installed third-party SI app, Sonos/Apple TV setting or socket state was changed. Resident app standby/CEC/audio, all HDMI ports, all protected-content providers and arbitrary privileged SCAP commands remain unverified. The app is hosted and timed; always-on HDMI replacement is not enabled.

## LG 2.2.1: Safari with Home Assistant's service worker

**184 Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 36 browser tests pass across Chromium and WebKit.** New browser cases run with an active service worker forwarding camera requests through `fetch()`. They verify decoded, changing frames in the LG camera component, both component registration orders, repeated module loading, stable connections across state updates, reconnects, detachment and restoration of the original renderer for other cameras.

The remaining macOS Safari failure was reproduced in the real browser against the shared **HA 2026.9.4 Docker instance**. Safari reported `FetchEvent.respondWith received an error: Load failed` for the native camera request. The 2.2.0 native-MJPEG browser fixture had no active service worker and therefore missed this condition. The 2.2.1 frontend now uses the remote's binary JPEG reader inside the LG camera view as well. The updated integration was installed in that container; the owner then **visually confirmed that the preview works in Safari**. No browser security setting or Home Assistant core/service-worker file was changed.

This is a scoped frontend compatibility hook for `ha-camera-stream`, not a new HA public API. Its component contract should be retested with future frontend versions. The preview remains demand-driven screenshots; full-motion capture is not claimed.

## LG 2.2.0: enlarged view and adaptive screenshot capture

**184 Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 30 browser tests pass across Chromium and WebKit.** The new regression cases cover strict multipart parsing, initial-empty recovery, binary frame delivery, shared captures, request cancellation, off/on generations, retry backoff, unloading, frame decoding, reconnects and releasing hidden/detached remote views. Both browser engines render successive images in a native MJPEG image element. WebKit's multipart Fetch rejection and retained image-loader connections are avoided in the remote with an abortable binary response through the same authenticated HA camera route.

On **HA 2026.9.4 in the shared Docker instance**, the physical 75UH5F-HJ supplied 1280×720 frames to two concurrent clients. Seven unique frames were shared between the clients; six consecutive fresh-capture intervals measured **0.968–1.045 seconds**. The existing normal interval was **10 seconds**: `active_viewers` changed from 0 to 2, effective interval to 1 second, then back to 0 viewers / 10 seconds after disconnect. The card rendered the real camera as decoded JPEGs; clicking its preview opened HA's enlarged camera dialog, where a real 1280×720 image decoded successfully. No physical power/input/media commands were needed for this test.

The original broken enlarged view was not consistently reproducible in Chromium. The release corrects the inherited multipart boundary mismatch and avoids terminating the image stream after an empty first capture. Chromium/WebKit browser fixtures plus the real HA enlarged-view check verify the corrected delivery; they do not establish a single exclusive cause for the original screenshot on every client.

## LG 2.1.0: bundled dashboard remote

**168 Python tests pass on both supported HA/Python combinations; ten Chromium tests pass.** Browser coverage includes entity-scoped service calls, power/state guards, custom input labels, volume/mute, presentation return, native text, preserved editor/input state, duplicate-submit suppression, errors, preview invalidation, keyboard controls and a 320-pixel-wide mobile layout.

In the shared **HA 2026.9.4 Docker instance**, the bundled module loaded automatically without a Lovelace resource entry. The card appeared in the card picker and opened its visual editor; title and visibility edits updated the preview. Actual browser clicks sent LG `mc` navigation/Home/Menu/Exit, `xb` source, `kf` volume, `ke` mute and `ka` power commands through registered HA services to the TCP simulator. Standby disabled navigation and volume; explicit wake restored controls.

After the simulator test, the separate **LG Fernbedienung** dashboard was configured with the existing physical LG and its already-enabled preview camera. The disposable simulator entry was removed. Existing dashboard contents and integration options were not changed. Real display captures appeared in the editor preview; no new physical power/source/navigation acceptance is claimed for this card release. The corrected Home/Menu and new Exit key codes are verified against LG's webOS 4.0 manual, pages 67–68, and tested against the simulator.

## LG 2.0.1: setup and HTTPS certificate handling

**161 LG tests pass on both HA 2025.3.4 / Python 3.13 and HA 2026.9.4 / Python 3.14.** Coverage includes the initial settings step, option validation, automatic SHA-256 enrollment, preserved saved passwords/pins, explicit verification opt-out, sanitized discovery errors and no insecure retry after a certificate mismatch.

The HA **2026.9.4 Docker instance** was exercised through its actual config/options flow API with an LG TCP simulator and a temporary self-signed TLS endpoint:

- Connection details lead to the complete settings form before an entry is created or area assignment can start.
- Invalid preview settings keep the settings form open.
- An empty fingerprint is read over TLS and stored in entry options with verification enabled; the password is not returned as a form default.
- Explicitly disabling verification accepts an empty fingerprint and preserves a saved password.
- The new entry loads successfully. The user's existing display options and UniFi entry are preserved; the disposable test entry is removed afterward.

A read-only enrollment against the physical LG returned the same fingerprint as the previously checked device certificate. No display command or web password was sent during that check. The container showed no new errors or blocking-call warnings. The updated integration is installed in the shared container.

## Split release: LG 2.0.0 / AV Companion 1.0.0

Versions: **LG Professional Display 2.0.0**, **AV Companion 1.0.0**. Fresh configuration; no migration. The shared Docker test installation was updated from HA 2026.8.1 to **2026.9.4** after backing up its stopped configuration, components and Compose file. Existing UniFi Air Quality remained loaded and its data was preserved.

## Automated coverage

**144 LG tests + 86 AV tests = 230 tests**, on HA 2025.3.4 / Python 3.13 and HA 2026.9.4 / Python 3.14. Includes actual HA entity-service registration, a real HA event bus, local TCP framing and an HTTP stream view. Tests cover native uploads, cancellation/cleanup, OSD state preservation, URL recovery, camera throttling, boot-image generation, staged standby, volume/remote routing, unavailable devices, fresh confirmed-off power guards, queue/download ownership, external presentation leases, independent controller operation and reload-safe adapter access.

The split uncovered and fixed a forgotten-supply hint that could leave the base marked unpowered, a native-download gap in presentation ownership, a source-select path bypassing cancellation, and a status callback that HA would dispatch to a worker thread. The event-loop regression is tested with the actual HA event bus.

## HA 2026.9.4 container acceptance

The actual config/options flows and registered entity services were exercised with an LG TCP simulator plus separate registered source, sound and socket fixture entities. No physical socket or Apple TV was used for the destructive-transition scenarios.

- Independent LG setup and AV selection; optional device options; duplicate AV ownership rejected.
- Volume/mute/night-mode routing to sound without changing LG volume; play/pause/stop forwarding.
- HomeKit event target filtering and LG remote command delivery.
- Idle plus valid HDMI signal beyond the configured idle timeout leaves LG on.
- Sustained signal loss while the source says idle powers LG off before cutting the socket.
- Repeated stale idle cannot wake it; explicit AV wake restores socket, display and source.
- Another physical HDMI input blocks linked-player standby shutdown.
- LG unload makes AV unavailable without cutting supply; LG reload reconnects the existing adapter.
- AV unload forgets its supply hint; standalone LG power control still works.
- Optional player entity rename updates AV options; playback continues after reload.
- Full container restart reloads both integrations and UniFi successfully.

The simulator and fixture instructions are provided in the AV repository's `dev/` directory. Polling, timer waits and actual socket services are used; HTTP state injection alone is not the test mechanism.

## Physical LG acceptance after the split

On the **75UH5F-HJ / 04.13.50 / webOS 4.0.1-136**, the separate LG integration was configured in the same Docker HA instance. Through its registered HA services:

- The native toast was acknowledged over the authenticated pinned LG connection.
- A PNG was uploaded, shown for five seconds, restored to the original HDMI input and cleaned up without a presentation error.
- The camera API returned an actual 640×360 JPEG capture.

This validates service execution, device responses, state restoration and a captured image. The user had previously visually confirmed overlays, fullscreen return and OSD suppression; this run does not claim a new user visual confirmation. Earlier video/HLS/website hardware evidence remains in NATIVE-MEDIA and the device reference.

## Remaining device-dependent limits

A real Apple Home/iPhone pairing, actual tvOS/Sonos service behavior, USB boot-image import and a physical boot with that image were not repeated by these tests. The AX310 standby behavior is the owner's observed wiring behavior; no new mains-loss experiment was performed. Other LG models/firmware require their own acceptance. HDMI signal retained by an extractor plus false player idle is inherently ambiguous; the default policy does not force off a valid signal. Native live video capture and network installation of a custom boot logo are not claimed.
