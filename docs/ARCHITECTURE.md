# Integration boundary and API v1

`lg_rs232_ip` owns the LG TCP transport, HTTPS/WebSocket session, credential/certificate pin, device settings, preview capture, native presentation queue and cleanup. `av_companion` owns optional HA entity references, remote/sound routing, standby evidence and socket policy. Neither integration imports the other's controller/entity internals. AV imports only `lg_rs232_ip.api`.

## Public adapter

`get_display_api(hass, lg_entry_id, version=1)` returns a reload-safe adapter resolving the active controller per call. An unsupported API version fails explicitly. The LG config-entry ID is persisted; changing the LG entity ID does not break the link. Only one AV config entry may claim each LG entry.

- `ready`, `is_available`, `is_intentionally_unpowered`, `presentation_active`, `model_name`, `software_version`, `osd_restore_error` are read-only status properties.
- `async_get_power_status(use_cache=False)` and `async_get_input(use_cache=False)` bypass cached state. Signal, volume and raw mute queries are provided. An unloaded LG returns unknown (`None`) to read queries; writes fail.
- Power, input, volume, mute and remote writes are serialized against the native presentation transition lock. Native queued/download/active content rejects conflicting AV writes.
- `async_present(action, **kwargs)` accepts the documented native presentation actions only; `async_clear_content()` cancels them with LG-owned restoration.
- `async_begin_external_presentation()` reserves the LG for a timed external presentation and returns an opaque lease token. `async_end_external_presentation(token)` releases only that lease. A native queue request is rejected while the lease exists. AV uses `finally` and unload cancellation to release it.
- `supply_guard()` holds the LG command lock while AV calls its socket service. It yields true only for a fresh confirmed-off display without any native presentation or external lease. Unknown/unloaded LG cannot authorize a cut. Queue insertion shares this lock.
- `set_power_supply_state(False)` suspends LG I/O for a confirmed externally unpowered display. `True` resumes querying; `None` forgets the hint when AV unloads. The LG never knows which socket is involved.
- Event `lg_rs232_ip_status` carries only `entry_id` and prompts subscribers to refresh. It is an invalidation notice, not power evidence.

AV performs normal foreign-device operations using HA services. Its LG commands use the adapter because they need the same transaction lock as fresh power/signal checks; firing uncoordinated LG entity services would lose that guard.

## Cancellation, reload and unavailable devices

Explicit LG power/input commands cancel native content before acting. Explicit AV off/input commands cancel external and native content. Automatic AV standby never cancels native content. Native restoration respects external source/app changes; within-app manual content replacement cannot always be detected. Power loss/crashes can leave owned uploads or OSD restoration pending; these limits are documented in FEATURES.

LG unload closes its own presentation/session and emits invalidation. AV becomes unavailable and cannot cut power. LG reload is resolved through the same adapter. AV unload cancels its tasks and forgets the external supply hint; standalone LG operation continues. Optional foreign entity renames update AV options; circular AV/LG targets are rejected.

Two repositories intentionally contain one `custom_components` domain each, following [HACS requirements](https://www.hacs.dev/docs/publish/integration/). HA [manifest dependencies](https://developers.home-assistant.io/docs/creating_integration_manifest/#dependencies) do not install another HACS repository or guarantee a configured LG entry; AV explicitly retries until its selected LG is ready. No prototype migration is supplied.

## Optional hosted display app

`display_app.py` owns per-entry token/assets/status and the persistent SI recovery journal. `NativePresentations` launches it through the same queue and transition lock as native media. SI provisioning and HDMI restoration are read back through `LGWebManager`; only the fixed SI launcher and HDMI app IDs are allowed. `show_display_app` is also available through the existing `async_present` adapter. The app receives only the currently authorized presentation and selected sensor values. See [Display app](DISPLAY-APP.md).

`resident_app.py` manages the optional persistent SI configuration separately from presentation leases. Fresh versioned visibility heartbeats enable the resident presentation path; HDMI signal readiness is diagnostic and cannot force a relaunch. Foreground and settings ownership are verified during maintenance. Physical source changes pause ownership; lost HA connectivity retains the loaded HDMI view. HA/AV source commands update the embedded source under the existing OSD guard and await a scoped acknowledgement. The selected input is persisted separately from the original restoration snapshot; idle never blocks standby.

Resident app requests coalesce to the latest content at each priority, and an event interrupts an active normal request without waiting for its duration or running a hardware refresh. Urgent content retains priority. Native media retain the existing FIFO/urgent queue and guarded transitions. Explicit cancellation and unload release presentation tasks and waiters.

One 25-second long poll wakes on content, input, allowed-sensor or capture changes; independent five-second heartbeats do not wake it. The ES5 client retains the HDMI element and patches only changed content. Camera capture uses one per-entry request ID and a bounded binary JPEG response, with web fallback and error backoff. Native bridge/upload lifetimes end on success, failure or page exit; frames never enter config storage. The app's per-entry token grants no generic command/service execution.
