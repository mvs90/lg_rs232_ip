# Test matrix and limits — 2026-10-08

This audit covers LG **2.30.2**, optional display app **1.20.0**, and AV Companion **1.4.0**. It maps supported combinations and failure paths to repeatable tests. It is not a claim that every possible device, firmware or timing combination has been certified.

## Results

| Check | Result |
| --- | --- |
| LG Python suite, HA 2025.3.4 / Python 3.13 | 904 passed |
| LG Python suite, HA 2026.9.4 / Python 3.14 | 904 passed |
| AV Companion suite against current LG, both HA versions | 103 passed per version |
| Studio, display app and remote card, Chromium + WebKit | 262 passed in total |
| Existing HA 2026.9.4 container, actual flows/services/TCP and simulated devices | 14 scenarios passed |
| Official Hassfest | 0 invalid integrations |
| Ruff and whitespace checks | Passed |

The LG suite grew from 746 to 904 cases. AV gained six tests that prevent the manual acceptance harness from selecting an unrelated installation; its integration code is unchanged. Browser coverage grew from 260 to 262 cases with a two-card isolation regression in each engine. Parametrized cases and separate browser runs are counted individually.

Coverage.py measured the whole LG Python component, with no file exclusions:

| Metric | Before | After |
| --- | ---: | ---: |
| Statements | 6,359 / 7,803 (81.5%) | 6,750 / 7,837 (86.1%) |
| Branches | 1,820 / 2,524 (72.1%) | 1,935 / 2,534 (76.4%) |
| Combined statement/branch score | 79.2% | 83.7% |

Coverage is collected on HA 2026.9.4 locally; CI reports it on both supported HA versions. This metric does not measure JavaScript, physical rendering or correctness by itself. Remaining uncovered Python paths include entity wrappers and less common error handling. No 100% coverage claim or artificial exclusions are used.

## Configuration and behaviour matrix

“Automated” means controlled devices/responses, including actual HA classes and local TCP/HTTP/WebSocket servers where stated. Physical evidence from earlier releases remains separately recorded in [release acceptance](RELEASE-TESTS.md).

| Area | Combinations and invariants | Repeatable evidence |
| --- | --- | --- |
| Setup and optional features | Serial only; native web with app off/on and preview off/on; settings shown during initial setup; invalid dependencies rejected | `test_entry_lifecycle.py`, `test_config_flow.py` |
| Platform composition | All ten platform factories, correct display attribution, unique IDs within each domain, feature-gated camera/clock/text/app controls | `test_entry_lifecycle.py` |
| Lifecycle and isolation | Two displays; unload/recreate one; reload-safe API; failed platform unload keeps the entry working; partial setup failure/cancellation; one failed/cancelled cleanup does not stop other cleanup | `test_entry_lifecycle.py`, `test_api.py` |
| Offline setup and recovery | Powered off/unreachable setup without waking; persisted Set ID including 1000, invalid storage fallback; recovery-only web client; user-disabled entity preserved | `test_entry_lifecycle.py`, `test_system_settings.py` |
| TCP protocol | Fragmented, malformed, wrong-command and extended-ID replies; EOF/cancellation; late reply on old socket; cache invalidation; optional-query backoff isolated per device and bypassed for writes | `test_protocol.py`, `test_system_settings.py` |
| Command scheduling | Foreground priority, FIFO within priority, bounded fairness, mutual exclusion, cancelled waiter/handoff, task-scoped priority; no duplicate mutation after lost confirmation | `test_command_queue.py`, `test_web_latency.py`, settings suites |
| Native transport | Actual cookie login and HTTP/WS exchanges; isolated/reused sessions; expired login, rejected/wrong/oversized/malformed/closed replies; redirects rejected; cancellation releases connection/lock; next explicit request can recover without replaying a write | `test_web_transport.py`, `test_web_manager.py` |
| Source wake | Off/on/unknown state; power or source ACK loss; source-only wake; superseded action; bounded deadline; physically disconnected supply; power-off during startup | `test_wake.py`, `test_display_app.py`, browser remote tests |
| App sources | Every directed pair among HDMI 1/2/3, Dashboard, Dashboard PiP, Mediaplayer and one custom view; success and timeout paths, including idempotent selection; rollback retains stored view and HDMI; no native source write/relaunch during an app-only change | **98 cases** in `test_display_app.py` (7 × 7 × 2) |
| Optional app and startup | Resident/app-disabled paths, readiness, reconnect, owned SI settings and recovery, offline design/cache, bounded notifications and view restoration | `test_display_app.py`, `test_startup_design.py`, browser display-app tests |
| OSD | Initially on/off/unknown, nested switching, failed restoration, newer manual choice wins | `test_osd.py`, presentation/app suites |
| Picture and backlight | Preset/aspect decoding, preset restrictions, energy saving/brightness schedule/panel state dependencies, verified reset/copy, slider/readback errors, input/mode revisions | `test_picture_controls.py`, `test_picture_settings.py`, `test_hardware_settings.py` |
| Poll/write races | Setting changes between scan steps; external context change during the final native read; supply-off and off/on cycle while awaiting read; cancelled write releases control locks; repeated unchanged supply hints do not starve scans | `test_picture_settings.py` |
| Power and system | PM/DPM/WoL/no-signal/no-IR, wake prerequisite warnings, Set ID and recovery, signage name, unsupported values and readback mismatch | `test_power_settings.py`, `test_system_settings.py`, `test_hardware_settings.py` |
| Clock, ISM, schedules and audio | Timezone/DST/NTP validation, mode-dependent ISM fields, bounded media export, timer capacity/duplicates/ownership, regenerated native IDs, malformed reads, partial failures and one-shot writes | `test_maintenance.py`, `test_clock_region.py`, `test_ism.py`, `test_ism_media.py`, `test_native_schedules.py` |
| Native images/video/URLs | Type/size/URL validation, owned uploads/deletion, launch failure, cancellation, manual source change, persistent recovery and quiet-hours/no-wake policy | `test_native_presentations.py`, `test_stream_page.py`, `test_boot_preview.py` |
| Preview camera | Active/idle intervals, shared viewers, no stale result after power/source change, valid image framing and MIME, bounded failed capture | `test_boot_preview.py`, camera and web tests |
| Studio and widgets | Fixed/custom views, rename/duplicate/delete/reset, stale-edit rejection, theme inheritance, widget/part editing, local startup restrictions, camera/media proxy, 4K geometry | `test_layout*.py`, `test_widget_parts.py`, all three browser suites |
| Media artwork and live content | Delayed/failed/superseded cover, old-cover buffering, edge/whole-cover palette, black border skipping, player change, forecast/calendar/sun updates and removed-widget cleanup | Browser Studio/display-app suites |
| Dashboard remote | Source-only wake, pending/error feedback and two simultaneously rendered cards with isolated device state and command targets | `tests/frontend/remote.spec.cjs` |
| Diagnostics and service contracts | Redacted credentials/URLs/private content, actual entity service dispatch, adapter writes fail while unloaded, old adapter follows a reloaded entry without leaking leases | `test_entry_lifecycle.py`, `test_services.py`, `test_api.py` |
| Optional AV links | Missing/base-unloaded display, volume-only setup, playback/volume/remote/Sonos switch routing, HomeKit event target isolation, renamed entities, optional app/custom sources | AV `test_split.py`, `test_controls.py`, `test_media_player.py` |
| Standby and extractor topology | Valid signal protects idle; stale idle plus sustained signal loss; interrupted evidence; unknown network state is not standby; supported/unsupported signal fallback; confirmed player standby even with retained extractor signal; display-only socket; no stale re-wake | AV `test_standby.py`, `test_media_player.py`, `test_controls.py` |

The app-source matrix uses simulated HDMI 2/3 signals and controlled app acknowledgements. It exercises the actual selection transaction and persistent state, but is not a dual-HDMI hardware test. Setup uses real HA registries/stores/coordinators with device transports and platform forwarding controlled; real HA service/lifecycle integration is additionally exercised in Docker.

## Existing-container acceptance

Used the existing **unifi-air-quality-ha-dev**, running **HA 2026.9.4**. No new HA instance was created. A temporary TCP LG simulator and fixture player, sound system and socket provided deterministic state and real standby time windows. The 14 checks were:

1. Independent LG/AV configuration and operation.
2. Sound-system volume, mute and night-mode routing without changing LG volume.
3. Playback through HA services.
4. HomeKit remote event routed to its targeted LG.
5. Duplicate AV ownership of the same display rejected.
6. Idle with valid HDMI signal remains on beyond the idle timeout.
7. False player idle plus sustained signal loss turns off LG before its socket.
8. Stale idle cannot wake the system after shutdown.
9. Explicit AV wake restores socket, LG and source.
10. Standby guard does not shut down another selected HDMI input.
11. LG unload makes AV unavailable without cutting supply; reload reconnects it.
12. AV unload releases its supply hint; standalone LG still operates.
13. Renaming the linked player updates the reference and playback continues.
14. The existing UniFi integration remains loaded.

Acceptance scripts must select uniquely named **LG Split Test** / **AV Split Test** entries, never the first entry of a domain. Missing or duplicate lab names must abort. Do not use these reserved names for real devices. The AV [harness instructions](https://github.com/mvs90/av_companion/blob/main/dev/README.md) describe setup and cleanup. The audit used these exact scopes before any config-entry unload operation.

All three temporary entries and the fixture component were removed; the simulator was stopped. After a final restart, the original HA entry inventory was intact. On the physical **75UH5F-HJ / 04.13.50**, native picture/sound/commercial dictionaries and Studio configuration/revision/backgrounds/startup design matched fresh pre-test snapshots. The display remained on **Mediaplayer**, with its app connected. All **76 installed component files** matched the release source. No physical power cycle or settings mutation was needed for this audit. Private snapshots, tokens and raw logs are excluded from Git.

## Findings fixed in 2.30.2

- A final native picture response could overwrite the current state after an external input/power/energy change. Recheck context and power after the await; a supply cycle invalidates the scan even if power is back on when it finishes.
- A failed or cancelled setup could leave created device/app/web resources behind. Partial setup now unloads platforms and closes those resources.
- An exception or cancellation in one close operation could prevent the remaining cleanup. Cleanup now attempts every remaining resource and preserves cancellation afterward.

## Still requiring device-specific acceptance

| Boundary | What remains necessary |
| --- | --- |
| Two independent HDMI pictures | A second active source and an on-panel simultaneous-rendering test; only HDMI 1 currently has a physical signal. |
| HDMI + camera/video | A compatible real camera/stream and long-duration decoder/rendering checks. Local test-stream evidence does not certify arbitrary codecs, DRM, providers or resolutions. |
| Continuous HDMI video capture | No supported continuous HDMI-to-HA stream is established; screenshots are not a video-capture guarantee. |
| Offline cold boot | Physical power removal and boot with HA/network unavailable on the actual installation; cached browser startup tests do not certify this. |
| Apple TV, Sonos, AX310 and HomeKit | Physical tvOS/CEC/extractor/mains sequences and actual Apple Home pairing after relevant firmware changes. Simulated events/services do not replace them. |
| USB boot/ISM media | Physical import and subsequent boot/ISM playback; preparation/export tests do not install media on the panel. |
| Scheduled transitions and calibration | Actual power/brightness timer expiry, seasonal DST boundaries and measured image/calibration quality. Readback confirms storage, not visual or timed efficacy. |
| Other LG models / legacy browser | Repeat model/firmware acceptance. Chromium/WebKit tests do not emulate every detail of webOS 4 hardware or the installed macOS Safari build. |

## Reproduce

In each supported Python/HA environment, install the pinned HA version plus `requirements-test.txt`, then run:

```sh
python -m coverage run -m pytest -q
python -m coverage report
ruff check custom_components tests
npm ci
npm test
git diff --check
```

Run AV's suite in its own repository with both repositories on `PYTHONPATH`; keep the minimum supported LG API check as well as a current-LG check. For real transport tests allow local loopback sockets. For Docker use the existing designated test instance and the scoped harness above. Re-run the targeted hardware checks when protocol, startup, ownership or rendering behaviour changes, recording fresh originals and restoration before declaring acceptance.
