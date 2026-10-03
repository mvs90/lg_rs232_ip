# Changelog

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
