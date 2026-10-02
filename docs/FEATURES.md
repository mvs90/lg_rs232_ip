# Extended controls (1.2.0)

The LG display remains the main device. Every link is optional. Existing entry IDs and entity IDs are preserved. Install the official integrations for your linked devices first. Configure links under **Settings → Devices & services → LG Display RS232/IP → Configure**. Do not select another entity belonging to this integration as a target; circular links are rejected.

## Remote and HomeKit

Select the Apple TV `remote` entity and choose **apple_tv** for remote power commands. Explicit TV on/off then uses `wakeup`/`suspend`. With a different remote, choose **generic** for `remote.turn_on`/`remote.turn_off`. Without a remote, the previous linked media-player power actions remain the fallback.

HomeKit `homekit_tv_remote_key_pressed` events are accepted only for this TV's entity ID. Arrows, select, back, exit and track/skip keys go to the linked remote when its HDMI input is active. On other inputs, supported navigation keys go to the LG panel. Playback controls follow the active media player. Unsupported controls are not advertised; next/previous track no longer masquerade as LG direction keys.

For automations:

```yaml
action: lg_rs232_ip.send_remote_command
target:
  entity_id: media_player.lg_display_media_player
data:
  command: home
```

The HomeKit setup remains accessory mode with only the combined TV selected. Device-specific remote commands and app behaviour still depend on the target device.

## Media, deep links and cameras

Standard `media_player.play_media` now forwards to the configured **content player**, or to the linked player if no separate content player is configured. Select the physical HDMI input for a separate content player. The display is powered on and its input selected before playback. HA media-source IDs are resolved and local HA URLs are processed for device access; application deep links are preserved.

```yaml
action: media_player.play_media
target:
  entity_id: media_player.lg_display_media_player
data:
  media_content_type: url
  media_content_id: youtube://watch/VIDEO_ID
```

This is normal playback, with no timed restoration. Seek, repeat and shuffle are passed through when the active player supports them. A separate content player supplies playback state and metadata while its input is active.

A URL alone does not make a player a web browser. Apple TV cannot display an arbitrary HA dashboard through `play_media`. Web pages require a browser-capable target; images, camera streams and videos require a target supporting their format. Camera media-source URLs can be resolved through HA, but the target must support the resulting stream. Use an explicit media URL or a media-source ID supported by your HA installation.

## Temporary content and queue

```yaml
action: lg_rs232_ip.show_content
target:
  entity_id: media_player.lg_display_media_player
data:
  media_id: media-source://media_source/local/doorbell.mp4
  media_type: video
  duration: 30
  priority: normal
```

- Requests are queued (maximum 10 pending). An `urgent` request goes next; it does not interrupt the current presentation.
- The current display input is captured before playback and restored after the duration. The duration starts once content submission completes.
- Display wake is **disabled by default** for temporary content and notifications. Enable it explicitly if required. Normal `play_media` is an explicit playback request and can wake the display.
- Quiet hours use HA's local timezone, support overnight intervals and are checked both when queued and when started. `urgent` bypasses quiet hours, but never the disabled-wake setting.
- While a temporary presentation is active, linked standby automation is suspended. Afterwards its evidence is reset.
- A manual command through the combined TV cancels the presentation before performing the new command. If the physical input changed externally, automatic restoration does not overwrite that input.
- Failures are reported through `presentation_error`; queued actions return when accepted, not when playback finishes.

```yaml
action: lg_rs232_ip.clear_content
target:
  entity_id: media_player.lg_display_media_player
```

This clears the queue and ends the current presentation. Restoration concerns the **display input and any display power enabled for that presentation**. It does not reconstruct a movie's playback position, DRM session or app state. Reusing Apple TV for temporary content can replace its previous playback. A separate content player is preferable when the original movie should continue independently. The integration does not alter Sonos volume for visual presentations. If a source was changed and changed back externally between observations, ownership of that change cannot be determined perfectly.

## Custom screen notifications: renderer interface

Configure **Notification renderer script** only when you have a working on-screen backend. The integration provides queuing, quiet hours, wake policy, duration, cleanup and `overlay`/`fullscreen` selection. It does **not** implement an undocumented UH5C overlay API, install an LG app or turn Apple TV into an arbitrary notification renderer. Without a renderer, `show_notification` returns an explicit error.

```yaml
action: lg_rs232_ip.show_notification
target:
  entity_id: media_player.lg_display_media_player
data:
  message: Someone is at the front door
  title: Doorbell
  mode: overlay
  duration: 15
  priority: normal
```

The selected script is called directly as `script.<your_script>` with these variables:

| Variable | Meaning |
| --- | --- |
| `action` | `show` or `clear` |
| `session_id` | Unique identifier, identical for both calls |
| `message`, `title` | Content to render |
| `mode` | `overlay` or `fullscreen` |
| `duration` | Requested duration in seconds |

The renderer must perform a short show/clear operation and return, not wait out the duration. Each call has a 15-second timeout. It must validate the requested mode, reject unsupported overlays and clear only the matching session. It must not override a newer user-selected view. A backend that supports neither clear nor session ownership should implement those semantics itself before use. For the verified LG-native actions below, no renderer script is needed.

The backend may manage its own content layout. When it changes HDMI input, the integration records the resulting input and restores the original one only if it still owns the selection. This script's overlay support depends on its backend. The separate `native_toast_configured` attribute reports whether native web access is configured; it is not a live connection check.

## Sonos / sound-system options

Select the separate volume player as before. Optionally choose existing Sonos **Night Sound** and **Speech Enhancement** switch entities. They remain Sonos-owned controls; this integration forwards actions instead of duplicating Sonos device discovery.

```yaml
action: lg_rs232_ip.set_sound_mode
target:
  entity_id: media_player.lg_display_media_player
data:
  mode: night  # or speech
  enabled: true
```

Enable **Select sound system TV input on explicit turn-on** only for a device whose source list contains the configured source name (default `TV`). No sound-system power-off or grouping is inferred. This keeps independently playing music separate from display standby.

```yaml
action: lg_rs232_ip.announce
target:
  entity_id: media_player.lg_display_media_player
data:
  media_id: media-source://media_source/local/chime.mp3
  media_type: music
  volume: 35
```

The target must advertise announcement support. This sends `announce: true` with a temporary announcement volume; persistent volume is not changed by this integration. Sonos mixing/restoration is delegated to the official integration. TTS can be sent using an appropriate HA-generated media-source URL. Announcement calls obey normal quiet hours and do not power the display on. Sonos groups, favourites, alarms and equalizer controls remain available through the official Sonos integration rather than being copied into the TV entity.

## Standby, power and reduced polling

Startup timeout and the wait after switching on the power socket are configurable. Off cancels a pending wake task. Socket actions must reach the requested on/off state before the integration treats them as confirmed. Socket shutdown requires a fresh physical display-off query. A socket manually switched off cancels a pending wake.

Optionally select a **display-only power sensor** reporting W or kW and configure a measured standby threshold. Idle plus low consumption can confirm standby over 120 seconds when HDMI signal status is unknown. A valid HDMI signal, active playback, invalid units/numbers and measurements older than 180 seconds prevent this evidence from being used. Do not use a sensor measuring the combined display/Apple TV/Sonos load. It is supplementary evidence, never a shutdown trigger on its own. A sensor whose HA `last_updated` does not advance for identical readings is treated conservatively as stale.

Repeated read queries share a short cache; fresh shutdown confirmations bypass it. Writes invalidate the cache. Optional queries rejected with `NG` are suppressed for five minutes; timeouts do not permanently mark features unsupported. Advanced settings/diagnostic entities are disabled by default on new installations to avoid polling every model-specific command. Existing registry choices are preserved. Enable only the controls your panel supports. Commands and value maps are not automatically certified for every LG model.

Download integration diagnostics for connection and decision information without device addresses, entity names, media URLs or message text. Runtime attributes include `presentation_active`, `presentation_queue_size`, `presentation_error`, and `notification_backend_configured`.


## Native LG text overlays and fullscreen images (v1.4)

Verified on **75UH5F-HJ, software 04.13.50, webOS 4.0.1-136**. These optional actions use the display's internal Content/Control Manager interface. Other Signage models or firmware versions need their own acceptance test; consumer webOS TV integrations are a different protocol.

In integration options, enable **native LG web access**, enter the **Mobile URL web password** (LG remote → Home → Mobile URL), and the **SHA-256 fingerprint of the LG HTTPS certificate**. This is separate from the settings administrator PIN. Leaving the password field empty preserves the saved password. HA stores the credential in its private config entry; it is not included in entity attributes or integration diagnostics. The web interfaces on ports 3737 and 3777 must be reachable and use the same certificate, as on the tested display.

Obtain the fingerprint from the browser's certificate details, or run `python3 tools/read_web_certificate.py DISPLAY_IP` on the trusted device network and compare it with the browser certificate. The helper only reads the certificate; it sends no credentials or display commands. The integration pins that certificate for every web request, including WebSocket control. A changed certificate requires deliberate reconfiguration. No router port forwarding is required.

Native text over the current HDMI picture:

```yaml
action: lg_rs232_ip.show_toast
target:
  entity_id: media_player.lg_display
data:
  message: "The washing machine is finished."
  priority: normal
```

The panel must already be awake. LG controls the toast layout and duration; there is no configurable duration or clear action. Use 1–1000 characters. This does not change the input or pause Apple TV. Quiet hours apply; `urgent` bypasses them.

Temporary fullscreen PNG/JPEG:

```yaml
action: lg_rs232_ip.show_native_image
target:
  entity_id: media_player.lg_display
data:
  media_id: media-source://media_source/local/doorbell.png
  duration: 15
  priority: normal
```

HTTP(S), `/local/...` and resolvable media-source IDs are accepted. Home Assistant downloads the image (maximum 5 MiB) without the LG login cookies, uploads a uniquely named temporary file, starts the built-in LG player, checks the foreground app, waits the requested duration, restores the previous external input, and deletes its own upload. The action queues the request; inspect `presentation_active`, `presentation_queue_size` and `presentation_error` for its outcome. `lg_rs232_ip.clear_content` cancels queued/current fullscreen content and triggers restoration and cleanup. It cannot clear a toast.

The normal queue limit (10), quiet hours, urgent ordering and optional display-wake setting apply. Standby synchronization is suspended during the presentation. A manual Home Assistant source/power command cancels it first. A physical source/app change is respected. Existing native LG app sessions are rejected because they cannot be reconstructed safely. Native playback is identified by the foreground app: the RS232 input read may still report HDMI during the transition and later return `e0`.

Restoration/cleanup also runs on cancellation and orderly integration unload. If restoration cannot be confirmed, the file is retained to avoid deleting the currently displayed image; `presentation_error` explains this. Network loss, an unknown upload outcome, a process crash or mains loss may leave a file beginning `ha_lg_` in Content Manager. Remove such files manually after leaving native playback. The integration never sweeps or deletes existing user media. Switching manually to another file within the same LG native-player app cannot be distinguished from this presentation and is not covered by source-change detection.

Direct image URL launch was accepted by LG but produced **“Wiedergabe nicht möglich”**. The upload-first path above was visually confirmed, including the return to Apple TV. WebSocket/app acknowledgements alone do not prove correct visual decoding. These actions do not add a native video player, arbitrary webpage/dashboard rendering, permanent URL/boot/schedule changes. Screenshot preview is available separately from v1.5. Continue using the optional content player or a custom renderer for those formats.


## Suppress OSD during switching

Enable **Suppress OSD during input/fullscreen switching** in options (default off). Before an integration-controlled source switch or native image launch, a fresh `kl ff` read determines the original OSD state. Only an enabled OSD is temporarily disabled. After a two-second settling period it is restored, including on failed/cancelled switching. An already disabled or unknown OSD is never enabled by this feature.

An explicit change through the integration's OSD switch takes precedence over the temporary restoration. Concurrent transitions are serialized. `osd_restore_error` indicates an unconfirmed restoration. Native image entry and return each use the guard; `show_toast` does not. Locking the OSD may also temporarily hide other LG menus/messages. Settings made through another controller or the physical remote cannot always be distinguished from the temporary lock. A network/power failure or hard HA crash can prevent restoration; inspect the OSD switch in that case.

On the tested UH5F-H, enabling OSD during native image playback is rejected. The guard remembers its own temporary lock and restores it after returning to HDMI; OSD can therefore remain suppressed for the full image duration. A pre-existing manual off state never gains this restore ownership.


## Active HDMI extractor and separate power domains

For the documented LG/Sonos setup, use the [FeinTech AX310 wiring reference](devices/FEINTECH-AX310.md). Apple TV feeds AX310; video goes to LG HDMI 1 and eARC audio to Sonos. The **display-only socket must leave AX310 powered**. The owner reports that Apple TV stays in standby in this arrangement when the display is disconnected from mains. This is a physical, installation-specific observation, not a new software command or universal CEC guarantee.

The normal linked standby, no-signal and stale-idle protections remain in force. A retained signal does not veto confirmed Apple TV standby; a powered extractor does not itself prove a signal or playback. Display-only power measurements exclude the extractor. The volume target controls Sonos through its existing HA integration, independently of display mains. Native LG content audio is not automatically returned to Sonos via an eARC connection that the LG does not have.

## Boot logo and custom boot image (v1.5)

The **Boot logo** switch controls the display's actual persistent boot-logo setting (`sn a3 00/01`), independently of native web access. It reads the setting back after changes, does not wake the panel and never reboots it. A panel that rejects the status query makes the entity unavailable rather than reporting a fabricated off state. On the tested 75UH5F-HJ, off/on acknowledgements and readbacks passed; a physical boot cycle was not performed.

For your own image, upload a source PNG/JPEG/BMP to Home Assistant Media and run:

```yaml
action: lg_rs232_ip.prepare_boot_image
target:
  entity_id: media_player.lg_display
data:
  media_id: media-source://media_source/local/my-logo.png
  media_directory: local
response_variable: boot_image
```

The action fits the image without cropping or distorting it onto a black **1920×1080** canvas and produces a baseline JPEG without source metadata. Limits: 5 MiB source file, 20 megapixels decoded. Its output is under **Media → My media → lg_rs232_ip → CONFIG_ENTRY_ID → LG_MONITOR → bootlogo.jpg**. Re-running the action replaces only this integration-generated file for that display. `media_directory` is a configured HA media-directory key; the default is `local`, which needs write access. No file is put in the publicly served `/local` directory by this action.

**This prepares the file; it does not install it remotely.** The action response explicitly includes `installed_on_display: false`, the generated media-source ID and `usb_path: LG_MONITOR/bootlogo.jpg`. Download the JPEG, copy it into an `LG_MONITOR` directory at the USB drive's root, connect it to the display, then import it under **General → Advanced Settings → Background Image → Booting Logo Image** (menu wording may vary with language). LG documents BMP/JPG and at most 1920×1080 for the UH5F UHD boot logo; the no-signal image has different limits. The boot-logo switch then controls whether the installed image is shown.

No verified network boot-image import was found in this panel's inspected Content/Control Manager frontend. Uploading a regular media file is not equivalent to installing a boot logo. This action does not replace an existing panel logo, alter boot configuration or reboot the panel. Other model families, especially stretched panels, need their own boot-image size limits checked before using the generated file. [LG webOS 4 guide, Background Image](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA).

## Periodic display preview (v1.5)

Enable **native LG web access** first, then **display preview through screenshots** in integration options. Set the **interval from 10 to 3600 seconds** (default 30) and **height 360/720/1080 pixels** (default 720). The interval runs between completion of one attempt and the next; network/capture time adds to it. The camera entity **Display preview** provides actual JPEG captures of the panel, including the HDMI content seen in the hardware test. It is a periodically refreshed screenshot view, **not a native video/RTSP stream**. The LG web interface itself offers a 10-second screenshot refresh; a native continuous-video endpoint was not established.

Use a standard picture-entity card, substituting your entity ID:

```yaml
type: picture-entity
entity: camera.lg_display_display_preview
camera_view: auto
show_name: true
show_state: true
```

`camera.turn_off` pauses image collection and clears the cached frame; `camera.turn_on` resumes it. These actions never change display power. Restart/reload restores the options' configured preview enablement. The collector never wakes an off display and skips capture when power cannot be confirmed. Concurrent dashboards share the same rate-limited, in-memory frame. The configured interval is the collection rate; dashboard rendering may introduce additional delay.

Attributes expose `last_capture`, `refresh_interval`, `capture_height` and `preview_error`. Failed captures discard the old frame instead of presenting it as current, and retry on the next scheduled interval. No screenshot is stored to disk or included in diagnostics by the camera. HA's own camera permissions and standard `camera.snapshot` action still apply. Screenshots may contain whatever is currently visible on the display; availability/black frames depend on firmware, source and content. There is no attempt to bypass content-protection restrictions.

## Native video, websites and streams (1.6)

MP4 uploads, Play via URL websites without reboot, and tokenized HA-hosted HTML video for HLS/HTTP streams extend the native presentation queue. Conditional input/URL restoration, persistent URL recovery and bounded owned-file cleanup are covered by tests. [Actions, examples and exact limits](NATIVE-MEDIA.md).
