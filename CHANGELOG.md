# Changelog

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
