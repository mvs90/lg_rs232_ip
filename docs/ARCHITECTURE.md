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

## Display Studio and declarative scenes

The optional Studio uses an administrator-only HA custom panel and authenticated editor views. Layout JSON is validated and revision-checked, stored separately per entry, and contains no arbitrary HTML/CSS or HA service calls. A panel pairing token cannot use the editor API. The independent device/AV boundary remains unchanged.

DisplayLayouts tracks only configured entity IDs, coalesces state events and caches bounded calendar/forecast responses on HA. The ES5 renderer is shared by the modern editor's preview and the LG app; it retains one native HDMI plane, caches unchanged widget formatting and changes automatic signal scenes without hardware source commands. Notification scenes temporarily override the persistent scene, then return to it. Saving a layout does not grant app/SI enablement or a power lease. Explicit Dashboard source selection persists separately in the resident journal and is exposed as active presentation through the device API while the display is not confirmed off; this prevents AV idle/standby automation from cutting off an intentional dashboard. HDMI selection clears that flag. The native controller presentation flag stays independent, so explicit power/input control is not blocked. HA shutdown/unload cancels listeners, timers and outstanding data fetches.

Background images are admin-uploaded, bounded, decoded/reencoded on the HA executor, content-addressed and stored per entry. The paired app can only fetch images referenced by its saved scenes. Layout save and image deletion share a lock. Forecast requests are deduplicated by entity/type, with bounded daily/hourly arrays and HA-side solar calculations; only derived day/night flags and selected sun attributes reach the panel. The ES5 weather module uses local SVG and animates only current-condition icons.


### Media cards and area suggestions (2.8)

`layout_cards.py` whitelists media/status metadata and builds administrator-only suggestions from HA area, device and entity registries. Explicit entity areas override device areas; suggestions do not mutate saved layouts. `layout_media.py` fetches covers on demand through the live HA media entity, strips metadata/resizes in an executor, deduplicates per-player fetches and discards results for previous tracks. A per-entry HMAC identifies current artwork without exposing upstream paths, content IDs or credentials. The paired cover endpoint checks enabled layouts and saved media/cover bindings before reading; editor previews remain administrator-only. No player-control endpoints are added.

The ES5 `cards.js` renderer is shared by Studio and the LG app. State updates invalidate only changed widgets; artwork nodes persist, failed images back off, and the existing one-second timer updates progress locally. The LG requests no third-party artwork/icon URLs. Each display bounds cover fetch concurrency, timeout, cache entries and bytes; unselected/removed bindings cannot be fetched by the paired client.


### Fixed and custom view library (2.15)

`layout_library.py` validates library version 3: seven protected `{id, name, scene}` records (`hdmi_full`, `dashboard`, `pip_view`, `media_view`, `overlay`, `pip`, `fullscreen`) plus up to 24 independent `view_*` records. Fixed names/IDs cannot be deleted or renamed; assignments are rejected. The runtime config and library share one Store record/revision/save lock. Earlier libraries copy their assigned designs into the fixed slots and retain unused designs as custom sources. Storage changes only on save; import accepts older exports through the same conversion.

Every custom view compiles to a named scene. All usable scenes participate in the existing combined 32-entity bound, scoped image access, weather/calendar subscriptions and bounded payload. Legacy `signal`/`no_signal` keys remain for runtime compatibility but do not trigger automatic layouts. No per-view polling loop is added. Source names are collision-safe against HDMI and other views. A stable `custom_view` ID participates in the existing acknowledgement/OSD rollback transaction; renaming changes only the label. Deleting an active custom view selects Dashboard and persists the corrected selection.

Public API v1 additively exposes `view_sources`, `active_view` and `async_select_view(id)`. AV Companion 1.4 consumes these optionally, maintains unique labels against linked-player sources and includes custom views in standby protection and its combined source list. Physical input/signal getters return unknown while any persistent view is selected.

The Studio overview/editor share one draft/history. Reset replaces only the selected fixed scene with its Cinema default, and requires Save. Solar colour/position uses a 30-second HA-side cache for `sun.sun`, with no location coordinates sent to clients. Editor value refreshes use the smaller runtime endpoint rather than transferring the library. Custom sun entities retain event-driven updates.

### Explicit app sources and colour themes (introduced in 2.10)

HDMI source selection uses the editable `hdmi_full` scene on the same native video plane, with a full-screen default. Explicit persistent sources use their named scenes; physical HDMI inputs use `hdmi_full`. `pip_view` remains separate from the transient notification `pip` scene. Both choices are journalled in the existing acknowledged input/OSD transaction and roll back together on missing acknowledgement. Explicit HDMI clears both flags, even for an unchanged input. Legacy automatic scenes remain in the editor library but are omitted from panel payloads, subscriptions, forecasts and paired image access. Existing libraries assign their former HDMI composition to `pip_view` without changing content.

The optional public API v1 extension adds `pip_available`, `pip_active` and `async_select_pip`; `presentation_active` protects either persistent source until confirmed power-off. AV Companion 1.2 consumes the optional extension while retaining compatibility with older API v1 versions. The Studio editor applies only theme colour/background fields; context navigation selects the associated saved view. Since 2.15, HDMI is a protected editable view. Upgrading a version-2 library inserts only this default and preserves all existing records. Its entities participate in normal subscriptions and limits. The Studio overview separates persistent views from the three transient notification views.

## Persistent media view and resolution tiers (2.12)

Public API v1 adds `media_view_available`, `media_view_active` and `async_select_media_view()`. AV Companion treats the extension as optional. Active media views participate in `presentation_active`; signal/input getters do not report a physical HDMI source while a persistent view is selected. Selection shares the existing app acknowledgement, OSD guard and rollback journal with Dashboard/PiP.

`media_view` is now a fixed editable view and active runtime scene. Artwork requests accept only 640, 1280 and 2160; clients select the tier using image geometry × DPR. One shared upstream request produces variants on an executor; the LRU bounds compressed data to 32 MiB/32 entries. An oversized result is returned to its caller without a refetch loop even if immediately evicted. Display heartbeat rendering diagnostics accept only bounded dimensions/DPR, without arbitrary browser data.
