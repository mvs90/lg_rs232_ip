# Release acceptance

## LG 2.20.0: view-specific startup screen and bounded fast recovery — 2026-10-06

**404 Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 98 display-app browser cases pass in Chromium/WebKit.** Additional 4K rendering checks cover the Mediaplayer start screen. Tests verify non-persistent, paired and uncached startup intents, cancellation by input/off/shutdown, five-second startup versus thirty-second normal backoff, stale bootstrap replies, target-render dismissal, local expiry and HDMI with a previously selected media view.

Installed LG 2.20.0 / app 1.16.0 in the existing HA 2026.9.4 container and tested the physical 75UH5F-HJ:

- Confirmed standby plus ten seconds, then only App-Mediaplayer: **51.8 seconds** to completed service/confirmed view. A second measured run took **53.8 seconds**. The previous 2.19.1 run took 53.2 seconds: these samples do **not** establish a substantial improvement in total startup time.
- Starting App-HDMI 1 with Mediaplayer previously selected completed in **50.8 seconds**. The client confirmed `hdmi_full`, and the final native capture showed the actual Apple TV HDMI picture without the loading screen. Browser tests additionally cover the entire pending-HDMI phase and late bootstrap responses.
- Timing-only probes showed the app requesting its startup hint and first state about **19–20 seconds** after power-on; native web-login connections still failed during the following phase and foreground/settings verification succeeded around 50 seconds. No launch loop or fallback to another input was introduced.
- A screenshot delivered through the real app-backed HA camera during the pending Mediaplayer request visibly shows **“Mediaplayer wird gestartet …”**. Later frames show the requested media layout. This verifies the loader on the physical panel, beyond mocked browser rendering. It does not establish an image during the earlier firmware phase.
- Fresh OSD readback and schema-normalized saved libraries match the original values after each cycle. The final source is App-Mediaplayer, with the app connected. Power modes, boot logo, saved views, Sonos, Apple TV and socket settings were not changed.

Temporary timing wrappers were removed and the source-tree production component was redeployed. Private captures, credentials, pairing URLs and test timing records remain outside Git. Standby-cycle results do not imply AC-loss or other-model boot-time guarantees.

## LG 2.19.1: select an app source directly from standby — 2026-10-06

**397 Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14.** Regression tests hold the app unavailable for a simulated 65 seconds, then verify the originally requested Mediaplayer view/App-HDMI is applied without a background HA poll. Further cases cover native web backoff, no relaunch of an already foreground SI app, takeover by another input/power-off/shutdown, bounded timeout and no replay of expired requests.

The user reported a black screen after selecting App-Mediaplayer from standby in 2.19.0. The HA log recorded the integration's 30-second view-connection timeout; the app connected later with `hdmi_full`, not the requested media view. The prior acceptance tests covered source switching on an already awake panel and did not catch this startup timing failure.

Installed 2.19.1 in the existing HA 2026.9.4 Docker container. On the physical 75UH5F-HJ, selected App-HDMI 1, switched off, waited for confirmed standby plus ten seconds, then issued **only Input → App-Mediaplayer**. The request succeeded after **53.2 seconds**. Input state and the client heartbeat confirmed `media_view`; an independent native foreground query and panel screenshot confirmed the SI app and visible media layout. Original OSD state and all saved Studio views were preserved. The display was left **on in the requested Mediaplayer view**. This is a standby-wake test, not a mains-disconnected cold boot or a promise of identical startup duration on every firmware.

## LG 2.19.0: named ISM modes and explicit app inputs — 2026-10-06

**390 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14.** New coverage verifies documented model-specific ISM codes, invalid-byte rejection, exact acknowledgement plus uncached readback, unknown/offline state, legacy-number validation, app/native routing, paused-app resumption, no native fallback on failure/timeout, superseded requests, Studio-source rename/removal and name collisions.

Installed in the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container and checked the German ISM dropdown and expanded Input list in its actual browser UI. The indoor **75UH5F-HJ** reported ISM `08` (Off); reselecting that unchanged mode confirmed both write and readback. White Wash, User Image and User Video were checked against LG documentation and protocol tests, **not activated on the physical panel**. Orbiter is omitted from this indoor profile because the webOS 4 guide restricts it to outdoor models.

Physical source tests through HA confirmed App-Dashboard, App-Dashboard PiP, App-Mediaplayer, App-HDMI 1, native HDMI 1 and resumption into App-HDMI 1. The saved custom view App-Ohne HDMI was also selected and returned. Switching from the media player immediately updated the Input entity. The native foreground query confirmed the resident SI app; all saved Studio views were retained. Only HDMI 1 has an active source; HDMI 2/3 routing is covered by automated tests, not a second physical signal. A fresh OSD query after the switches confirmed its original enabled state (the UI can briefly retain the temporary suppressed state until refreshed). The original display standby was restored. Private device credentials, captures and test records remain excluded from Git.

## LG 2.18.1: brief offline startup notice — 2026-10-06

Release app **1.15.1**. Targeted local checks: **94 Python app/backend tests** and **86 display-app browser cases across Chromium/WebKit** pass, including six new cases for the first failed request, a silent five-second timeout, five-second expiry, early recovery, no repetition, hidden-page cleanup and unchanged HDMI decoder identity. Ruff and diff checks pass.

In the existing HA 2026.9.4 container, a cached app reload was tested while its paired endpoints returned HTTP 503. Native LG captures showed the startup notice at approximately 1.6 seconds and its removal at approximately 8.2 seconds. There was no active HDMI picture during this acceptance run; continued decoder identity is verified by browser regression tests, not claimed as a new active-programme hardware test. The SI launcher remained foreground. The panel was initially in standby and was briefly awakened for cache update/testing, then returned to standby. The final app cache and installed source were checked after removing the temporary test hooks; saved views were retained.

The notice is local HTML above the existing app content and makes no native OSD or source-setting call. It appears only for a failed initial state request, lasts at most five seconds, and closes earlier when HA responds. Existing long-poll timeouts resume after that first request. Private native captures and installation data are excluded from Git.

## LG 2.18.0: offline HDMI startup, multicast and platform controls — 2026-10-06

**372 Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 170 browser cases pass across Chromium and WebKit.** New coverage includes opt-in/scoped offline manifests, cache updates, invalid/foreign HDMI records, restoration before HA connects, native diagnostic allowlists and reply tickets, CPU counter reset handling, unsupported sensor values, multicast URL validation, decoder reuse/release, Studio saving/overlap rejection and the video-wall transaction's exact native parameter wrapper, verification and rollback. The real HA service-registry test covers video-wall routing, range validation and OSD-guard entry/exit.

Installed **LG 2.18.0 / app 1.15.0** in the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container. AV Companion remains **1.4.0**; no new container or changes to unrelated integrations were made.

- **Offline startup:** enabled the option through the actual HA options flow. The LG reported a complete cache. A controlled native display reboot caused its web port to go down; during restart all paired app endpoints returned HTTP 503 while HA itself stayed running. A native capture showed full-screen HDMI in the foreground SI launcher while HA reported the app disconnected. Endpoints and initial OSD state were restored, the final uninstrumented app reconnected, and cache status returned to 1. This is an already-populated-cache reboot test, not physical mains removal or cache-eviction acceptance.
- **Multicast:** temporarily configured the existing camera demo through the real library API with a 239.x.x.x UDP source and a 90-second, TTL-1 local H.264/MPEG-TS sender. Two native captures three seconds apart showed changing test-video content beside HDMI. The extra decoder reported 640×360. Timed return restored HDMI 1, camera mode became inactive and the original library was restored. No multicast sender is left running.
- **Diagnostics:** actual native responses confirmed 2,080,919,552 bytes total RAM, temperature/backlight and tile geometry. A valid pair of CPU counter samples produced a load delta; samples with a changed CPU set deliberately omitted it. Illuminance, humidity, rotation, fan and screen-check were explicitly unsupported/error. No compatible external sensor was attached.
- **Video wall:** applied enabled 2×2/tile 1/natural mode off, verified readback and captured the resulting crop. Restored the exact previous disabled geometry (including its retained row/column/ID/natural-mode settings). The original enabled OSD was restored. Native errors from an exploratory incorrectly shaped request were resolved by the documented `tileInfo` wrapper; it is covered by regression tests.
- **Final preservation:** all nine saved views compare equal after schema normalization; SI settings equal their original values; source is HDMI 1, foreground is SI, camera widget is inactive and app 1.15.0 is connected with cache ready. Installed LG and AV files match their source trees. LG and UniFi entries remain loaded. Temporary reboot/outage hooks and flags are absent. No new LG error was logged after final deployment.

Studio's new source/URI controls were inspected in the actual HA browser; all draft and persisted user designs remain unchanged. Private native captures, pairing URLs, local recovery records and credentials stay excluded from Git. Remaining hardware limits are recorded in the [capability table](devices/LG-UH5F-H.md#additional-video-and-platform-capability-tests-2026-10-06): two independent active HDMI signals, multi-panel synchronization, external sensors and continuous HDMI video export.

## LG 2.17.0: camera widgets and timed event views — 2026-10-06

**356 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 156 browser cases pass across Chromium and WebKit.** Coverage includes camera binding authorization, recursive LG-camera exclusion, bounded image work/cache, cancellation, decoder reuse/release, stream failure/stall fallback, native-plane transparency, overlap validation and automatic snapshots for overlays. View tests cover timer replacement during an in-flight selection, preserved return targets, manual takeover, quiet hours, shutdown and blueprint installation without overwriting local edits. Reduced motion and unchanged-state animation behavior are covered.

Installed **LG 2.17.0 / app 1.14.2** in the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container. No new HA instance was created; AV Companion remains 1.4.0.

- Native captures on the physical **75UH5F-HJ** visibly confirmed HDMI 1 alongside the bundled H.264/MPEG-TS HLS clip for direct and animated entry. Captures three seconds apart show advancing video content. Early captures sometimes contained two black native video surfaces despite reported readiness; captures after eight additional seconds showed both images. This is not a guarantee of instantaneous visible startup. Replacing a timed view returned to the original HDMI 1 view; the camera became inactive and the SI launcher remained foreground.
- A temporary HA Generic Camera served alternating synthetic PNG frames. In automatic mode over full-screen HDMI, the app selected snapshots; a native capture confirmed the image visibly over HDMI. Image requests advanced while visible and stopped after leaving the view. The temporary camera and server were removed afterwards.
- The real HA blueprint API accepted the installed event-view blueprint. It is available to create an automation; no automation was enabled. The custom **Kamera · Teststream** demo remains saved as an additional source. All pre-existing views were retained; temporary changes to the demo were restored. The final display source is HDMI 1.

The second native video was hidden when overlapping full-screen HDMI, despite reporting a ready decoder. This firmware therefore uses separate rectangles for streams and snapshots for overlays. Only HDMI 1 has a connected source, so two independent HDMI signals remain unverified. HA-camera HLS using other containers/codecs, continuous HDMI export, offline cold start, multicast, video-wall synchronization and external panel sensors are not certified. See the [device capability record](devices/LG-UH5F-H.md#additional-video-and-platform-capability-tests-2026-10-06). Private captures, credentials and recovery records remain excluded from Git.

## LG 2.16.0: animated HDMI geometry transitions — 2026-10-05

**342 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 146 browser cases pass across Chromium and WebKit.** New tests inspect intermediate shrinking/growing geometry, bounded update counts, delayed acknowledgement, decoder identity/no reload, no animation replay on polling, direct interruption, hidden HDMI, input changes, reduced motion, Studio dropdown actions without saving drafts, service validation and timeout rollback with OSD protection.

Installed **LG 2.16.0 / app 1.13.0** in the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container. The physical **75UH5F-HJ** acknowledged animated full-screen → Dashboard PiP → full-screen transitions. Native captures during both moves show intermediate HDMI sizes with the programme continuing, followed by the exact saved target geometry. The HDMI input and SI foreground app remained unchanged. The saved library was compared before/after and preserved; the original HDMI 1 source was restored. Control images remain local and excluded from Git. AV Companion stays at 1.4.0.

## LG 2.15.1: show the current HDMI input from Studio — 2026-10-05

**340 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 138 browser cases pass across Chromium and WebKit.** Coverage verifies both display buttons, a fresh backend input despite stale frontend state, renamed/hidden HDMI inputs, all three HDMI targets behind persistent app views, unknown-input handling and preservation of unsaved drafts.

Installed **LG 2.15.1 / app 1.12.0** in the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container. The overview's Nur HDMI button returned the physical **75UH5F-HJ** from Dashboard PiP to HDMI 1. With HDMI 2 selected behind Mediaplayer, the editor button correctly returned to HDMI 2. Both actions were acknowledged as `hdmi_full`, with the resident app connected and no app error. The saved library was unchanged, the original HDMI 1 / Dashboard PiP selection was restored, and installed component bytes match the repository. AV Companion remains at 1.4.0.

## LG 2.15.0: editable HDMI and grouped notifications — 2026-10-05

**337 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 134 browser cases pass across Chromium and WebKit.** Coverage adds the version-2 to version-3 library conversion, protected HDMI identity, scoped HDMI-widget data and persistence, notification-section placement, custom copies remaining in the primary section, HDMI editing/reset/undo, and one video element through HDMI input changes and notification return.

Installed **LG 2.15.0 / app 1.12.0** in the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container. On the physical **75UH5F-HJ**, HDMI 1 used the full-screen default; an edited HDMI composition with smaller positioned video and a test label was acknowledged and confirmed in a native capture. HDMI 1 and HDMI 2 shared the composition while retaining their source identities. An overlay returned to the HDMI scene, and restoring the default restored full-screen video. The SI launcher remained foreground.

The existing saved views were compared with the upgraded library and preserved. Test modifications were removed and the original Dashboard PiP source restored. Browser inspection verified Nur HDMI as the first editable/resettable view and the three messages in a separate section below all persistent views. No additional container or AV update is needed; AV Companion 1.4 remains compatible. Private captures/backups stay excluded from Git.

## LG 2.14.0 / AV 1.4.0: fixed views and dynamic sources — 2026-10-05

**335 LG tests and 97 AV tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14. All 130 browser cases pass across Chromium and WebKit.** New coverage protects fixed names/IDs from deletion, tests per-view reset and undo, custom creation/duplication/rename/deletion, API revisions and conversion of existing designs, scoped data/image access and combined entity limits. Source tests cover collisions, stable IDs, acknowledgement timeout rollback, notification return, HDMI element identity, deletion fallback and AV standby/linked-source behavior. The final Studio fix canonicalizes scene order so undo correctly restores the saved indicator.

The existing **unifi-air-quality-ha-dev / HA 2026.9.4** container runs **LG 2.14.0 / app 1.11.0 / AV 1.4.0**. The physical **75UH5F-HJ** verified a temporary custom source, live renaming with unchanged ID, notification return, persistence across a restart of this same HA container, and deletion of the active source returning to Dashboard. A temporary AV entry selected the custom source and followed its rename/deletion live. Mediaplayer, Dashboard PiP and HDMI full-screen selection still work; native capture confirmed the custom composition and the SI app remained foreground. No Sonos playback command was sent.

All existing assigned designs were compared with the converted fixed views; unused Ohne HDMI remains a deletable custom source. The live API rejected deleting/renaming protected views without changing the library. Browser inspection verified fixed-view controls and reset/undo against the real HA frontend. Temporary view and AV entry were removed and the original source restored as **Dashboard PiP** (formerly PiP). Private backups and captures remain excluded from Git. HomeKit source exposure is through the combined entity; new Apple Home pairing was not tested.

## LG 2.13.0: cover colours and optional playback icon — 2026-10-05

**332 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; all 128 browser cases pass across Chromium and WebKit.** Coverage adds colour-only 4K backgrounds without a second visible cover, small sampling-image requests, one edge analysis per cover across fit/dimming changes, missing artwork and pause fallback, optional playing/paused SVGs across all three media styles, timeline alignment, paused progress, no repeated icon DOM mutations, removal of status text, strict config validation and saving the new Studio controls without changing source assignments.

The existing **unifi-air-quality-ha-dev / HA 2026.9.4** container runs LG 2.13.0 and the physical **75UH5F-HJ** reports connected app **1.10.0**. The saved Wohnzimmer media view uses colour-only background (35% dimming) and enables the state icon. All other views and source assignments were preserved. Native capture verified the media view without a textual playback badge; Mediaplayer → Dashboard → original HDMI 1 retained the SI app in the foreground. Installed files match the repository and the LG app reports no error.

The actual **Wohnzimmer Sonos** was playing its **TV** input with no artwork, duration or position. This verifies the fallback on the real panel: no invented cover, progress or icon. Cover gradients, artwork changes, playing/paused icons and 4K rendering were verified with browser fixtures, not claimed as observed on this live TV source. No playback/skip/pause command was sent to Sonos. Private configuration backups and captures remain outside Git.

## LG 2.12.1: source selection preserves view assignments — 2026-10-05

**38 Studio browser cases pass across Chromium and WebKit.** Regression checks select all three sources from an open music view with an unsaved draft, assert no library POST or assignment changes, preserve the draft through subsequent save, cover unavailable sources/unassigned defaults and require an explicit gallery action for assigning an unassigned view.

The existing HA 2026.9.4 container and physical LG reproduced the issue: Dashboard and Mediaplayer had been assigned to the same music view. The original Dashboard view was intact. Restoring only its assignment preserved every saved view. Repeated Mediaplayer ↔ Dashboard service selections then showed the two distinct compositions in native captures; app scene, entity source and selection flags matched, the SI app remained foreground, and assignments stayed unchanged. The fix changes Studio behavior; it does not rewrite existing assignments automatically.

## LG 2.12.0 / AV 1.3.0: full-screen media and UHD assets — 2026-10-05

**331 LG and 95 AV Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14.** **116 browser cases pass across Chromium and WebKit**, including 3840×2160 at density 1 and the physical LG's 1920×1080 CSS viewport at density 2. New checks exercise persistent media-source selection, same-HDMI exit, OSD rollback, restart state, standby/supply guards, name collisions, old saved views, artwork tiers/shared fetches/cache-byte limits, oversize-cache completion, strict resolution queries, 4K background retention, long-title geometry and gallery source assignment.

Using the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container and physical **75UH5F-HJ / webOS 4.0.1-136**, integration 2.12.0 and app 1.9.0 displayed the **actual Wohnzimmer Sonos** currently playing through AirPlay. No synthetic media integration was installed and no play/pause/skip command was sent to Sonos. The additional named music view was saved while preserving all six existing views and their assignments. Original Dashboard source was restored after testing.

- Native LG capture verified large cover, title, artist, album, playback state and progress. Studio showed the same live Sonos metadata and editable full-screen card controls. Naturally changing tracks updated the preview.
- Repeated Mediaplayer → PiP → Mediaplayer → HDMI → Mediaplayer selections retained the SI launcher as foreground. An overlay returned to the music view. The video element identity and hidden HDMI during music notifications are also asserted in both browsers.
- A temporary AV Companion entry exposed and selected Mediaplayer, returned to HDMI full-screen, and followed direct LG selection. It was removed after the test; source/library were preserved. Actual HomeKit discovery on an iPhone was not tested.
- Runtime diagnostics measured **1920×1080 CSS pixels, device pixel ratio 2, screen 1920×1080**. Resource selection therefore targets 3840×2160; internal GPU buffer format/resolution and panel bit depth are not independently verified. Native capture remains limited to Full HD.
- The real AirPlay artwork was **512×512** for all requested tiers (640/1280/2160), proving that small originals are not artificially upscaled. Separate image tests verify high-resolution variants and 3840×2160 backgrounds.

Private screenshots, player details and credentials remain excluded from Git. The new media view is configured for the user's room; it does not change playback or bind a sound system to the standalone LG integration.

## LG 2.11.0: media cover backgrounds — 2026-10-05

**322 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 108 browser cases pass across Chromium and WebKit.** New coverage includes background-only entity subscriptions/scoped image access, strict options and the combined entity limit, playback/track transitions, all three fit modes, dimming, actual red/blue border sampling, one analysis per unchanged cover, slow obsolete responses, image-failure backoff, theme/save/undo/duplicate preservation and HDMI element identity.

The existing **unifi-air-quality-ha-dev / HA 2026.9.4** container and physical **75UH5F-HJ / webOS 4.0.1-136** ran integration 2.11.0 with app **1.8.0**. A temporary media-player integration supplied synthetic artwork through HA's real media image API. Native LG captures visually verified proportional fitting, stretching, centered sizing, changed cover/edge colours, pause/off fallback and resumed playback. The SI launcher remained foreground. Studio preview and the real HA player selector were checked in the existing HA UI. No actual Sonos playback was started or interrupted. Original views/source were restored and the temporary fixture was removed after acceptance.

## LG 2.10.1: picture-control dependencies — 2026-10-05

**320 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 102 browser cases pass across Chromium and WebKit.** Coverage includes the energy/schedule/panel dependency matrix, stale-value removal, exact acknowledgements/readback, mode-triggered rejection-cache invalidation, HA state-context serialization, visible diagnostics for disabled controls and aspect changes on the same video element.

The existing HA 2026.9.4 container and LG 75UH5F-HJ verified manual backlight writes in Off/Minimum/Medium, lockout in Maximum/Auto, immediate recovery, APS preset readback and both aspect modes. Native captures confirmed video-plane geometry in PiP; the HDMI image was black, so no active-programme/HDCP claim is made. Picture settings, DPM/PM policies, original Dashboard source and saved library were restored. See [detailed evidence and limits](PICTURE-CONTROLS.md).

## LG 2.10.0: colour-only themes and explicit PiP source — 2026-10-04

**302 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 100 browser cases pass across Chromium and WebKit.** Ruff and whitespace checks pass. New coverage includes theme changes preserving every non-colour widget field, editable palettes, context navigation without changing the source, read-only HDMI preview, explicit PiP selection, source-label collisions, persistence, acknowledgement rollback, standby/supply protection, removal of the PiP HDMI widget, and omission of old automatic scenes from panel data/forecast/image access.

Using the existing **unifi-air-quality-ha-dev / HA 2026.9.4** container and physical **75UH5F-HJ / firmware 04.13.50 / webOS 4.0.1-136**: the initial source/restart/capture checks used display app 1.7.0; the final AV and payload checks verified **1.7.1** after its notification handling adjustment for views without an HDMI widget.

- Native captures verified HDMI 1 full-screen and the previously saved HDMI composition as the separate PiP view. The SI launcher stayed foreground. Selecting the same HDMI 1 after PiP restored full-screen video.
- A four-second overlay returned to persistent PiP. Restarting the same container restored the PiP selection and unchanged saved library. Unconnected HDMI 2 remained in the full-screen HDMI scene after the former signal-delay period instead of loading widgets. Dashboard still used its own saved composition.
- A temporary real AV Companion 1.2.0 config entry exposed PiP, selected it through the public LG API, returned to full-screen HDMI and reflected direct LG PiP selection. The temporary entry was removed afterwards. No linked player, sound system, socket or Apple Home pairing was added.
- The final paired payload contains only the five active custom contexts; legacy automatic scenes remain saved but are omitted. Installed LG 2.10.0 and AV Companion 1.2.0 files match repository sources.
- The real HA Studio UI showed left colour/background controls and top context buttons. Applying Paper & Sand retained exactly the same widget labels and geometry; undo restored the original draft. The actual remote offered HDMI 1/2/3, Dashboard and PiP.

The original library, bindings and HDMI 1 source were preserved/restored. Private native captures and credentials are excluded from Git. These checks do not certify total LG CPU/RAM, multi-day operation, every HDMI/HDCP provider or actual HomeKit input discovery on an iPhone.

## LG 2.9.0: saved views and live solar backgrounds — 2026-10-04

**297 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 96 browser cases pass across Chromium and WebKit.** Ruff and whitespace checks pass.

Coverage includes independent named copies, six-context assignments, old-layout adoption without overwriting the original store, delete/undo/default fallback, empty galleries, mobile sizing, optimistic conflicts, administrator-only HTTP access, inactive-image protection, preservation of unassigned/shared views through the older API, continued widget editing after save, live solar updates and cancellation of the solar timer. Only assigned scenes and their selected entities reach the display; the saved library stays in HA.

Using the existing **`unifi-air-quality-ha-dev` HA 2026.9.4 container**, without creating another instance, and the physical **75UH5F-HJ / firmware 04.13.50 / webOS 4.0.1-136 / app 1.6.0**:

- The six existing scenes became six saved views with their real weather/sensor bindings intact. Two independent test views were saved; while unassigned they did not alter the runtime layout.
- Assigning the test solar view to Dashboard displayed it. Restarting the same container preserved both views and the assignment; the resident app reconnected.
- The actual `sun.sun` position advanced after 35 seconds with an unchanged saved-layout revision, confirming the live calculation without an editor reload.
- A temporary, explicitly synthetic sun entity exercised day and night within a short test. Native LG screenshots visually confirmed both gradients after a state change alone, without another layout save or source switch. The SI launcher remained foreground.
- Deleting an assigned view restored its context's built-in default. The original six views, their entity bindings, configured solar entity and selected Dashboard source were restored afterwards, and the temporary sun entity was removed.
- Installed LG 2.9.0 and AV Companion 1.1.0 files match their respective repository sources. AV Companion was unchanged; private captures, configuration backups and authentication are excluded from Git.

These tests establish persistence and live rendering on this panel. They do not measure total LG CPU/RAM or multi-day operation. Solar position is calculated on HA every 30 seconds; the display receives only the resulting angles and uses the existing lightweight renderer.

## LG 2.8.0: media cards and room suggestions — 2026-10-04

**291 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 88 browser tests pass across Chromium and WebKit.** Ruff and whitespace checks pass. Coverage includes exact entity/device room inheritance, disabled/hidden/diagnostic exclusions, no automatic saves, media binding validation, bounded image conversion, coalesced concurrent fetches, cancellation isolation, stale-cover races, failed-cover backoff, plaintext metadata, selected-entity privacy, administrator-only previews, paired saved-binding checks, GET-only routes, compact/poster artwork, playing/paused progress, off/absent covers and removal/undo.

Using the existing **`unifi-air-quality-ha-dev` HA 2026.9.4 container**, without creating another HA instance, and the physical **75UH5F-HJ / firmware 04.13.50 / webOS 4.0.1-136 / app 1.5.0**:

- A temporary test integration supplied a real registered HA `MediaPlayerEntity` with a local owned cover image and temperature/door entities. A temporary device area produced exactly the expected media/status suggestions through HA's real registries. No real Sonos is configured in this test installation; these are explicitly synthetic media fixtures, not a Sonos-device compatibility claim.
- In the real Studio UI, selecting the room showed the proposed cards. Adding the media card displayed its cover, title, artist, album, progress and volume in the draft; its duplicate suggestion became disabled. Removing it restored the suggestion and the unchanged saved configuration. The preview used the authenticated HA media image API.
- The real HA media entity API returned a resized 640×640 JPEG. Native LG captures visually verified compact and large-cover layouts, selected state icons, playing → paused (1:21), changed title/cover, off-state cleanup and a completely empty scene after removing all cards. The SI launcher stayed foreground throughout.
- Old artwork keys returned HTTP 204 after the track changed. After cards were removed their entity no longer appeared in the display payload. No artwork URLs, media-content IDs or HA credentials are passed to the panel.
- The original user layout, real weather/sensor bindings and selected Dashboard source were restored. Temporary entities, the test integration and its room were removed. Existing AV Companion was unchanged. Private captures and local authentication are excluded from Git.

The tests validate the shared HA media contract and actual display rendering. Metadata completeness still depends on the installed media integration/source; these tests do not measure total LG CPU/RAM or multi-day operation.

## LG 2.7.0: Dashboard source, weather and own backgrounds — 2026-10-04

**284 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 82 browser tests pass across Chromium and WebKit.** Ruff and whitespace checks pass. Coverage includes persisted Dashboard selection, same-HDMI return, acknowledged rollback, AV standby/supply protection, source-label collisions, empty scenes, message removal/type changes, daily/hourly request deduplication and provider failure, astronomical night flags, unchanged DOM, animated/static icons, failed-weather cleanup, image bounds/metadata stripping, authenticated upload, per-entry paired reads, referenced-image deletion protection and editor undo/cleanup.

On the physical **75UH5F-HJ / 04.13.50 / webOS 4.0.1-136**, using the shared **HA 2026.9.4 Docker instance** and display app **1.4.0**:

- The LG media player offers **Dashboard** while HDMI 1 still has a signal. Selecting it renders the separate scene and keeps the SI launcher foreground. Returning to the same HDMI restores the signal scene.
- Temporary, explicitly synthetic HA weather/calendar/temperature and sun states rendered the current SVG weather icon, real widget geometry, morning/day/night gradients and calendar fallback. Native captures verified the actual LG rendering. Daily/hourly service responses and populated forecast rows were tested with HA fixtures and Chromium/WebKit; no external forecast provider is configured in this test instance. The hardware correctly showed the unsupported-forecast hint.
- Overlay messages on a Dashboard without HDMI stayed free of a TV video rectangle, then returned to Dashboard. A fully empty Dashboard rendered its background without errors.
- A generated PNG was uploaded through the real administrator API, converted and displayed as a background. Deletion while referenced returned HTTP 409. The disposable image was removed after restoring the configuration.
- A HA restart preserved **Dashboard** selection and reconnected the resident app. A separate physical standby/wake also restored Dashboard. HDMI 1 could then be selected normally.
- The real Studio panel exposed the sixth scene, weather controls and image library. Unauthorized editor requests returned HTTP 401. The test source was installed in the running container; private captures, credentials and transient test entities are excluded from Git.

Existing signal/no-signal/notification scenes were preserved. Only the new Dashboard scene is prepared with the Morgenlicht template; no private weather/calendar entities were auto-selected. The final output returns to HDMI 1. AV Companion 1.1.0 adds the same source to the combined player, using the optional public API extension; its separate acceptance is documented in that repository. No Apple Home/iPhone pairing is part of these tests. These tests do not establish total LG process RAM/CPU, multi-day stability, arbitrary weather-provider support or mains-loss behaviour.

## LG 2.6.0: Display Studio

**275 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14. All 74 browser cases passed across Chromium and WebKit** (72 in the full run, followed by the expanded 26-case app suite after the last widget-cache optimization). Coverage includes layout bounds, plain-text rendering, authenticated/admin-only real HTTP routes, optimistic-save conflicts, persistence, removed bindings during in-flight fetches, bounded service results, HA timezone/all-day fallback, editor drag/resize/undo, responsive editing, safe text and preservation of the HDMI element through scene changes. Unchanged calendar widgets perform no repeated date formatting during capture-style polls.

On the physical **75UH5F-HJ / 04.13.50 / webOS 4.0.1-136**, with **HA 2026.9.4**:

- The automatically registered sidebar editor opened in the real HA frontend. No manual dashboard or resource creation was required.
- Cinema, Aurora, Morgenlicht and Paper & Sand all rendered on the LG. Temporary HA test states supplied explicitly labelled synthetic weather, calendar and temperature values; these entities were removed afterwards. Calendar/forecast service responses were tested with HA service fixtures, not live external weather/calendar providers.
- Aurora retained HDMI in its positioned/resized video rectangle. Native screen captures showed the backgrounds, widget geometry and typography.
- Custom overlay, PiP and fullscreen messages each reported the expected scene and returned to the configured persistent scene after expiry. The SI launcher remained foreground throughout.
- Switching the embedded input to unconnected HDMI 2 produced the automatic no-signal scene after the configured delay. Returning to HDMI 1 restored the signal scene without replacing the SI app.
- A HA restart preserved the saved layout and reconnected app **1.3.2**. Final test configuration is Cinema, automatic mode, HDMI 1, with no test-entity bindings. Installed integration files match the repository source. Unauthenticated access to the real editor endpoint returned HTTP 401.

The scene heartbeat is a five-second diagnostic, not a message-latency measurement. Only one native HDMI plane is used. These checks do not measure total LG RAM/CPU, multi-day stability, all protected-content sources or every panel model. Portrait layouts, uploaded background images and arbitrary Lovelace/HTML execution are outside this release. Private HDMI screenshots and credentials are excluded from Git.


## LG 2.5.0: persistent HDMI and responsive app controls — 2026-10-03

**253 Python tests pass on HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 56 browser tests pass across Chromium and WebKit.** These cover same-element HDMI selection and scoped acknowledgements, missing signal, connection loss without relaunch, cancellation, original SI preservation, manually enabled/disabled OSD, latest-message replacement, urgent priority, sensor-driven updates, unchanged DOM, expired-message replay prevention and repeated screenshot bridge cleanup. The historical 2.4 checks below describe that release, including its now-replaced pause-on-HA-source-selection behavior.

On the **physical 75UH5F-HJ, firmware 04.13.50, webOS 4.0.1-136**, using the shared **HA 2026.9.4 Docker installation**:

- Resident app 1.2.0 resumed through the HA device button and retained SI foreground. Six successive 30-second overlay/PiP/fullscreen requests replaced one another and were acknowledged after **87, 75, 40, 43, 38 and 38 ms**; median **42 ms**. This measures service request to app paint acknowledgement on this LAN, not photodiode/display latency.
- Twelve additional rapidly submitted messages left only the newest visible; clearing content returned directly to the embedded fullscreen HDMI view.
- HA source selection changed HDMI 1 → HDMI 2 → HDMI 1 while the native foreground remained the SI launcher. Each completed in approximately **2.9 seconds**, including the configured OSD guard and its settling delay. HDMI 2 had no signal: after 35 seconds the app remained connected, `hdmi_signal_ready` was false, and an overlay was acknowledged without waiting for HDMI frames. SI settings were unchanged.
- The preview returned eight valid JPEG stream parts after returning to HDMI 1; the final 1280×720 capture visually showed HDMI with no app message. Buffered/repeated parts are not counted as independent captures or an FPS benchmark.
- HA was stopped during an overlay. After 17 seconds, a direct capture showed fullscreen HDMI without the private message and the SI launcher remained foreground. Restarting HA reconnected the resident app. Confirmed standby and subsequent wake reconnected it again with no app error.
- The final installation keeps the optional app and resident autostart enabled, with HDMI 1 selected. Native Web/API access, camera intervals and manually selected certificate policy are preserved.

The app uses bounded request/capture lifetimes and patches existing DOM nodes; browser stress checks release all 30 successive screenshot bridges with a maximum of one live bridge and preserve the HDMI element. This is not a measurement of the LG process's total RAM/CPU or multi-day stability. Native image/video/website playback still uses its documented guarded app transition; only resident app messages/layouts and HA HDMI selection avoid that transition. The existing hosted cold-start requirement (HA must be reachable) remains.

## LG 2.4.0: optional resident app and automatic camera routing

**240 Python tests pass on both HA 2025.3.4/Python 3.13 and HA 2026.9.4/Python 3.14; 48 browser tests pass across Chromium and WebKit.**

Resident mode is an explicit opt-in, separate from temporary SI presentations. Fresh app version/visibility/HDMI heartbeats select the existing-app path; a stopped or disabled app cannot receive requests. New tests cover idle without a presentation lease, no-launch overlay/PiP routing, standby/wake, transient web failures, source-change pause/resume, AV source mapping/leases, originally enabled and manually disabled OSD, SI restoration, requested-frame authentication/validation, long-poll wakeup, capture backoff, camera fallback and HA stop cleanup. Browser tests cover unchanged HDMI elements through layouts, expiry/offline cleanup and binary JPEG upload/error handling.

On the physical **75UH5F-HJ / 04.13.50 / webOS 4.0.1-136**, using **HA 2026.9.4**:

- Enabled resident mode through the real HA options flow; the app connected as version 1.1.0 with HDMI ready.
- Repeated 4-second overlay, PiP and full-screen messages stayed in `commercial.signage.signageapplauncher` and completed without presentation errors. The full checks, including camera/foreground reads, took approximately 5.3–5.6 seconds. Fresh camera frames used backend `app` and showed the actual composed screen; HDMI source and signal remained correct in HA.
- `show_toast` automatically used the app queue; cancellation cleared the message and kept the resident HDMI app.
- Disabling the app restored ordinary HDMI1 and byte-for-byte equal original SI settings. The same camera entity switched to backend `web`. Re-enabling reconnected the app.
- Stopped HA while a message was active. A direct panel screenshot after 17 seconds confirmed HDMI remained visible and private notification content was gone. The app reconnected after HA restarted.
- A physical standby/wake sequence confirmed power off and subsequent resident reconnection. The initial three-second state check was too early for the panel/HA poll; the corrected acceptance waits for confirmed standby. Transient Control Manager availability during wake and stale error reporting were fixed and covered by regression tests.

- With the active interval set to 0.5 seconds, seven consecutive fresh 1280×720 frame intervals measured **0.793–0.941 seconds** through the actual HA camera stream; backend was `app`. This is about 1.1–1.3 new screenshots per second in that short sample, not full-motion video.
- A controlled display reboot reconnected the resident app after **72.5 seconds**, with the SI launcher in foreground and unchanged owned SI configuration. HA stayed available during this test; no mains interruption was used.
- Native website playback returned to the resident SI app without a presentation error. Explicit HA HDMI selection paused resident mode, and the device-page Resume button reconnected it.

The app remains hosted: loading after a cold start needs reachable HA. This is screenshot capture, not a native video encoder. These tests do not certify all CEC/HDCP/audio providers or mains-loss behaviour. Private programme captures, credentials and pairing URLs are excluded from the repository.

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
