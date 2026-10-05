# Changelog

## 2.17.0

- Add one configurable camera widget per Studio view: local H.264/HLS test stream, HA HLS, automatic snapshot fallback, 1–30 s snapshot interval and contain/cover fit. Release app 1.14.2.
- Respect the tested native plane ordering: video streams must sit beside HDMI; overlapping HA cameras in automatic mode use snapshots. Keep video surfaces transparent.
- Keep the existing HDMI decoder; mute and release the additional video when hidden. Share only saved camera bindings through the paired route, block recursive LG preview cameras, and expose bounded camera readiness diagnostics.
- Add short widget entrances alongside smooth HDMI transitions, respecting reduced motion and avoiding video texture animations.
- Add bounded `show_view.duration` and an optional, automatically installed HA automation blueprint. Repeated events replace the timer; manual controls take over.
- Document physical HDMI + MP4/HLS evidence and the remaining dual-HDMI, HDMI-stream-export and offline-cold-start limits.

## 2.16.0

- Add a Direct/Animated dropdown beside Studio display actions and a `show_view` action for automations. Keep transition choice separate from saved designs and unsaved drafts.
- Animate the existing HDMI plane between saved positions and sizes in 700 ms, with at most 30 geometry updates per second. Keep one decoder, skip unchanged/hidden/new-input cases, respect reduced motion, and cancel superseded moves.
- Acknowledge the source only after the final geometry, preserving the OSD guard and timeout rollback. Release app 1.13.0.

## 2.15.1

- Add an Anzeigen action for Nur HDMI in the Studio overview and editor. Return from Dashboard, PiP, Mediaplayer or custom views to the currently selected HDMI input, including renamed or hidden inputs.
- Read the current HDMI target from Home Assistant on each click. If the input is unknown, show a helpful message instead of guessing an input. Preserve unsaved drafts and the existing OSD restoration.

## 2.15.0

- Move the three notification views into a separate section below fixed and custom views.
- Add Nur HDMI as the first protected, editable and individually resettable view. All HDMI inputs use its saved composition; the default is full-screen video. Keep one video element through edits, source selection and notification return.
- Add only the HDMI default when upgrading existing libraries, preserving every saved design and custom source. Keep 24 custom views and the shared entity/resource bounds. Release app 1.12.0.

## 2.14.0

- Replace view assignments with six protected, editable views: Dashboard, Dashboard PiP, Mediaplayer, Mitteilung, Mitteilung PiP and Mitteilung Vollbild. Add per-view default restoration with undo and explicit save; remove the assignment section.
- Make every added or duplicated view an independent source. Preserve stable IDs across renames; deleting the active view returns to Dashboard. Keep existing user designs, bindings and backgrounds during conversion.
- Extend public API v1 for dynamic sources, consumed by AV Companion 1.4.0. Preserve OSD restoration, acknowledgement rollback, notification return, restart state and standby protection.
- Release app 1.11.0 with dynamic scene selection on the existing HDMI decoder. Retain the 32-entity bound and shared data/image caches across six fixed plus up to 24 custom views.

## 2.13.0

- Add a colour-only cover background: sample the cover edges for a full-screen gradient without displaying the cover twice. Make this the default background mode for new Mediaplayer views; retain the existing image modes for other designs. Decode only the small artwork tier for colour sampling, including at 4K.
- Remove textual playback-state badges from every media-card style. Add an optional SVG play/pause state indicator beside the progress timeline, configurable per card in Studio and enabled in new full-screen media templates. Hide it when no usable timeline exists.
- Release display app 1.10.0 with cached artwork analysis and no repeated state-icon DOM updates. Preserve source assignments, the HDMI decoder and the existing OSD restoration.

## 2.12.1

- Fix Studio source buttons silently assigning the currently edited view to Dashboard, PiP or Mediaplayer. Source selection now shows the saved source without changing views, assignments or unsaved drafts.
- Label the gallery action for unassigned views explicitly as “Als Dashboard verwenden”; already assigned views retain their source. Existing assignments are never automatically rewritten by the update.

## 2.12.0

- Add the persistent Mediaplayer source and configurable full-screen media view in Display Studio, with artwork, metadata, playback state and progress. Keep independent named views, colour themes and optional cover backgrounds.
- Keep HDMI full-screen selection, notification return, OSD restoration, restart persistence and AV standby protection consistent across Dashboard, PiP and Mediaplayer. Extend public API v1 additively for AV Companion 1.3.0.
- Select bounded 640/1280/2160 artwork tiers using viewport area and pixel density. Share one upstream fetch, preserve originals without upscaling, cap the JPEG cache at 32 MiB and retain 4K background uploads. Add static gradient dithering and bounded renderer diagnostics.
- Release display app 1.9.0. Verify on the existing HA container and physical LG using the actual Wohnzimmer Sonos, including source transitions and notification return without interrupting AirPlay.

## 2.11.0

- Add an optional per-view media-player cover background to Display Studio, independent of media cards. Show it only while the selected player is playing; restore the regular theme on pause, stop, unavailable/missing artwork or load errors.
- Offer stretch, proportional fit and centered-size modes, adjustable dimming and a live gradient sampled from all four cover edges. Preserve these settings across colour themes, saved views, duplication and export/import.
- Reuse scoped artwork caching and HA state subscriptions. Display app 1.8.0 samples only 32×32 pixels per new cover, reuses the background for unchanged data, rejects stale loads and retains the HDMI decoder.
- Keep background-only players inside the existing 32-entity bound; disabled/unassigned/legacy views grant no new panel image access. Improve Studio preview request cleanup after track changes, saves and navigation.

## 2.10.1

- Replace arbitrary aspect-ratio values with a named Full Screen/Original select; retain the legacy number with validated codes. Verify native acknowledgement/readback and mirror fitting to the resident HDMI plane without a decoder/input switch (app 1.7.2).
- Honour backlight locks from Auto/Maximum energy saving, brightness scheduling and actual panel-off state; configured DPM alone does not lock manual control. Add a Backlight Control diagnostic sensor and clear stale numeric values.
- Require matching readback for backlight and picture/energy mode changes, refresh dependent controls and invalidate mode-dependent rejection caches. Correct the energy-saving sensor's AUTO decoding.
- Document and physically test the mode dependencies, preserving the installation's original settings.

## 2.10.0

- Separate editor colour themes from content templates. Left-hand themes/palette/background controls preserve widgets, entities, text, geometry and typography; top context buttons navigate saved views and a read-only HDMI-fullscreen preview.
- Keep physical HDMI selections full-screen in the resident app regardless of signal status or legacy automatic layouts. Add the persistent PiP source and independently assigned `pip_view` scene, retaining the last HDMI input and returning after notifications.
- Persist Dashboard/PiP selections in the acknowledged source transaction with OSD-state preservation, rollback and AV standby protection. Add optional API v1 PiP capabilities for AV Companion 1.2.0.
- Preserve old HDMI compositions for the explicit PiP view; keep legacy drafts while excluding inactive automatic scenes from panel payloads and data/forecast subscriptions. Release display app 1.7.1.

## 2.9.0

- Start Studio with a gallery of named views. Create from templates, edit, rename, independently duplicate or delete views; assign them to Dashboard, HDMI signal/no-signal and notification contexts. Preserve existing layouts, bindings and backgrounds as six named views.
- Save the bounded library and assignments atomically with revision checks. Retain undo/redo, protect backgrounds referenced by inactive views and send only assigned scenes/data to the paired display. Add administrator-only library editing alongside the existing runtime layout endpoint.
- Keep widget controls bound to the current draft after saving, so continued edits to the selected widget are retained.
- Rename the Morgenlicht template to Sonnenstand and use a solar background in every template variant. Calculate live solar elevation/azimuth on HA every 30 seconds and update the open editor and display without reload. Keep coordinates on HA and stop timers when layouts are disabled/unloaded.
- Release display app 1.6.0; existing dashboard-source, OSD and AV behavior is retained.

## 2.8.0

- Add compact and large-cover media cards for Sonos and other HA media players: artwork, title, artist, album, playback state and optional progress/volume. Use the existing HA media entity API for artwork, with bounded conversion/cache and no upstream media credentials in the panel payload.
- Suggest cards using actual HA entity/device area assignments. Offer styled status cards with local SVG icons for room climate, lights, doors, locks and other selected states; skip hidden/disabled/diagnostic entities and never add or publish suggestions automatically.
- Add per-card removal directly in the layer list, retain undo/redo, and place new cards in available space when possible. Release the shared display renderer as app 1.5.0.
- Cover playback transitions, missing/changed artwork, concurrent requests, privacy boundaries, exact room inheritance and editor removal in backend/browser regression tests.

## 2.7.0

- Add Dashboard as a persistent LG media-player source with an independent sixth scene, retained across HA restart/standby and acknowledged in the resident app without leaving SI. Explicit HDMI selection exits it and retains the existing OSD guard.
- Protect an intentionally selected dashboard from AV Companion's automatic standby/supply decisions through the device API; explicit power/source control remains available.
- Allow removal and type changes for every widget, including messages and HDMI; support empty scenes, undo/redo and existing 2.6 layouts.
- Add daily/hourly forecasts (1–8 periods), locally animated current weather symbols, provider/HA-derived night icons, configurable weather styles and sun-position backgrounds. Fetch only selected data, deduplicate requests and keep forecast symbols static.
- Add configurable gradient angles and private JPEG/PNG uploads, bounded and resized on HA; per-display image libraries support referenced-image protection and unused-image cleanup.
- Release display app 1.4.0 with the shared Studio renderer; no separate HACS frontend package is required.

## 2.6.0

- Automatically register the administrator-only LG Display Studio sidebar panel, with a shared editor/display renderer and four editable templates.
- Add independent signal/no-signal and overlay/PiP/fullscreen scenes, freely positioned HDMI and widgets, backgrounds, typography, colours, layer order, undo/redo and validated JSON import/export.
- Show selected HA states, weather forecasts, calendar events and timezone-aware clocks with bounded HA-side caches and per-entry persistent, revision-checked configuration.
- Keep the existing HDMI element through layout changes and debounce loss of signal; retain optional app operation and existing OSD/notification/standby policies. Report the actual app scene and revision in diagnostics.
- Validate on both supported HA generations, Chromium/WebKit and the physical webOS 4 panel. See docs/DISPLAY-STUDIO.md and docs/RELEASE-TESTS.md.

## 2.3.0

- Add an optional HA-hosted display app with per-device pairing, automatic temporary SI configuration, rendering acknowledgement, sensor allowlist and HA setup options. No external CMS or developer-mode installation is needed.
- Add fullscreen, HDMI overlay and HDMI picture-in-picture layouts; expose the action, device test/overview/recovery buttons, status sensor and remote-card controls.
- Reuse the presentation queue, AV ownership, wake/quiet-hour policy and OSD transition guard. Preserve disabled OSD and user input changes, journal settings before writes, restore HDMI/SI on completion or cancellation, and retry owned recovery after reconnect.
- Keep arbitrary HA service access and unrestricted entity data out of the panel endpoint. Bound requests, expire withdrawn/offline content, render messages as text, and use local ES5 assets compatible with the tested webOS 4 platform.
- Document the verified SI launcher and external-video path, server/Crestron distinctions, and limitations of permanent app operation, HDCP/audio and model compatibility.

## 2.2.1

- Fix the enlarged LG camera view in macOS Safari when Home Assistant's service worker is active. Share the remote card's abortable binary JPEG reader with the LG view instead of sending multipart MJPEG through Safari's Fetch implementation.
- Scope the frontend compatibility renderer to this integration's screenshot cameras. Preserve Home Assistant's camera dialog, settings and snapshot download; other cameras retain their original renderer.
- Cover active service-worker delivery, both component registration orders, successive decoded frames, duplicate module loading, reconnects and connection cleanup in Chromium and WebKit.

## 2.2.0

- Use correctly framed MJPEG for the enlarged camera view, with recovery after empty or failed first captures and neutral frames instead of stale content.
- Capture faster while preview streams are open: default 1 second, configurable 0–10 seconds (0 disables acceleration). Restore the normal interval after the last viewer closes; normal interval now accepts 1–3600 seconds.
- Share captures across all viewers, isolate capture cancellation from disconnected requests, discard results from before camera-off, and back off on failures.
- Remote preview opens the enlarged camera dialog, retains one stream across state updates, and closes it when hidden, offscreen or removed.
- Add strict multipart HTTP regression tests and Chromium/WebKit preview decoding and connection lifecycle coverage.

## 2.1.0

- Bundle the LG Display Remote dashboard card and load it automatically with the integration. Include a visual editor, card picker entry, German/English labels, theme support and mobile layout.
- Control display power, HDMI source, navigation, volume/mute and presentation return. Optionally show existing screenshot captures and send native text overlays.
- Guard commands during standby, unavailable/unknown states and in-flight requests; show failures without assuming a successful state change. Preserve typed messages during HA updates.
- Correct LG Home/Menu key codes to the webOS 4 guide and add Exit. Align the action selector with supported LG commands.
- Add browser regression tests and frontend CI. Document setup and YAML configuration.

## 2.0.1

- Show the full LG settings form during initial setup, after connection details and before device/area assignment. Save selected settings as config-entry options.
- Share fields and validation with the later Configure dialog, including web credentials and preview requirements. Restore the screenshot-interval validation translation.
- Automatically enroll and store an empty SHA-256 certificate fingerprint during setup/configuration; existing pins stay unchanged. Add explicit certificate-verification opt-out, with verification enabled by default.
- Existing entries and options are unchanged.

## 2.0.0

- Standalone LG controller, pure display entity and display-only configuration.
- Native overlays/media, OSD, preview and boot-image features retained in LG.
- Optional player, sound, socket, standby and combined HomeKit features moved to the separate AV Companion repository.
- Documented API v1 with reload-safe access, presentation ownership and fresh confirmed-off supply guard.
- New split/lifecycle/concurrency coverage and Home Assistant 2026.9.4 Docker acceptance tests.
- Fresh configuration only; no migration from the combined prototype.


## 1.6.0

- Native MP4 video presentations: bounded 50 MiB upload, foreground verification, timed restoration and owned-file cleanup.
- Website presentations through verified Play via URL input E3, without reboot. Preserve prior URL configuration, respect user changes and journal recovery across HA restarts.
- HTTP(S) HLS/browser-video streams through short-lived tokenized HA-hosted HTML video pages; muted autoplay by default. No transcoding, DRM or native RTSP support.
- Shared queue, quiet hours, wake policy, cancellation and OSD handling for images, videos, websites and streams. New actions documented with HA examples and LG/Sonos compatibility limits.
- Hardware checks confirmed MP4, HTML and HLS rendering; direct network video through DSMP was acknowledged but did not play, so is not used.

## 1.5.0

- Real LG boot-logo switch (`sn a3`) with exact acknowledgement validation and fresh readback; no automatic reboot or wake.
- Optional display-preview camera using native JPEG captures, with 10–3600 second intervals and 360p/720p/1080p resolution. Captures come from HTTPS 3737; the earlier 3777 download returned 404.
- Preview on/off controls collection only. Concurrent viewers share one throttled request; failed captures clear stale images; off/unknown panel power does not trigger a capture or wake.
- `prepare_boot_image` generates a metadata-free 1920×1080 baseline JPEG in HA Media and returns USB import instructions. Direct remote boot-logo installation is **not verified or claimed**; the documented LG USB import remains necessary.
- Expanded device reference and hardware acceptance results. Screenshot bytes and original installation details remain private.

## 1.4.0

- Optional OSD suppression during input/native-image transitions, preserving an initially disabled OSD and giving explicit HA OSD changes precedence. Fresh state reads, cancellation cleanup and restoration diagnostics.

- Optional native LG web access with per-device TLS certificate pinning, private session cookies and sanitized failures.
- `show_toast`: native text over the current picture, confirmed on 75UH5F-HJ / webOS 4.0.1. LG controls duration; no renderer script needed.
- `show_native_image`: bounded PNG/JPEG download, unique internal-storage upload, foreground verification, timed display, external input restoration and owned-file cleanup. Uses the existing queue/quiet-hours/wake policies.
- Cancellation waits for bounded upload/launch writes so their results can be cleaned up. Source changes are respected; uncertain restoration retains the image with an error instead of deleting visible media.
- Document authenticated platform information, observed web protocol and acceptance results for reuse. Direct URL image playback is not used because the panel rejected rendering despite acknowledging launch.


## 1.3.0

- Read-only hardware verification of 75UH5F-HJ / 04.13.50, official LG source inventory and reusable device reference.
- Correct model and software decoding; firmware no longer incorrectly reads Wake on LAN.
- Optional DPM timeout selector, signal and panel-power/PM-mode sensors; documented DPM switch value and validated subcommand echoes.
- UH5F picture labels and color-temperature range, corrected language mapping and Auto energy saving.
- Fixed framing of replies beginning with command letter x (including picture mode), verified against the panel.
- Removed the undocumented abnormal-state query, unused speculative command catalogues and heuristic elapsed-time parser.
- Added an allowlisted, read-only inventory tool; per-installation data stays private.
- Native content/overlay backend remains pending authenticated validation; no panel settings were changed.

## 1.2.0

- Capability-aware playback controls, seek/repeat/shuffle and media-source/deep-link forwarding.
- Optional remote entity with Apple TV wakeup/suspend and scoped HomeKit navigation.
- Separate content-player input, temporary presentations, bounded queue, quiet hours, cancellation and conditional input restoration.
- Notification renderer script interface with show/clear session contract; native LG overlays remain unsupported pending model/firmware verification.
- Optional Sonos TV source, night/speech controls and audio announcements.
- Configurable display startup, confirmed socket state and cancellation of competing wake tasks.
- Optional fresh power-measurement evidence; idle fallback survives intermittent signal-query failures.
- Shared short query cache, fresh confirmation reads, rejected-command cooldown and connection cleanup on cancellation.
- Advanced entities opt-in on new installations, corrected zero-value ACK handling and privacy-conscious diagnostics.


## 1.1.0

First public HACS release, based on the existing private 1.0.0 integration.

- Standard custom-component repository layout, MIT license, English/German documentation and automated checks.
- Independent HDMI signal status, confirmed no-signal shutdown and configurable idle fallback for stale Apple TV states.
- No automatic wake from repeated idle updates or polled stale player states.
- Confirmed linked standby applies only to the linked HDMI input; polling can recover missed standby events.
- Fragmented TCP responses are assembled and matched to command/device. Timed-out connections are discarded to prevent delayed replies contaminating subsequent queries.
- Invalid power responses remain unknown. An unknown display state no longer authorizes power-socket shutdown.
- Playback actions and state are delegated to the linked player; sound-system volume remains optional.
- Configurable TV polling, self-link validation and standby diagnostics.

Live panel compatibility and HomeKit pairing must still be verified on the target installation. Install through a HACS custom repository; default catalogue listing is not included.
