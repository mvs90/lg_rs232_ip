# LG display features

All actions here belong to the standalone LG integration. Configure these under **LG Professional Display → Configure**. Apple TV, Sonos, external sockets and combined HomeKit control are documented in [AV Companion](https://github.com/mvs90/av_companion).

## Native LG text overlays and fullscreen images (v1.4)

Verified on **75UH5F-HJ, software 04.13.50, webOS 4.0.1-136**. These optional actions use the display's internal Content/Control Manager interface. Other Signage models or firmware versions need their own acceptance test; consumer webOS TV integrations are a different protocol.

In integration options, enable **native LG web access**, enter the **Mobile URL web password** (LG remote → Home → Mobile URL), and leave the **SHA-256 fingerprint** field empty to detect and store the certificate automatically (from 2.0.1). An explicit fingerprint can still be entered. This is separate from the settings administrator PIN. Leaving the password field empty preserves the saved password. HA stores the credential in its private config entry; it is not included in entity attributes or integration diagnostics. The web interfaces on ports 3737 and 3777 must be reachable and use the same certificate, as on the tested display.

Automatic detection trusts the certificate presented by the configured display during setup; it does not independently establish its identity. A saved fingerprint is never silently replaced after a mismatch. To enroll a replacement certificate deliberately, clear the fingerprint field and save again.

**Verify LG HTTPS certificate** is enabled by default. Disabling it explicitly retains HTTPS encryption but disables certificate identity verification for LG login, controls, uploads and screenshots. No automatic fallback disables this check.

For independent comparison, obtain the fingerprint from the browser's certificate details, or run `python3 tools/read_web_certificate.py DISPLAY_IP` on the trusted device network and compare it with the browser certificate. The helper only reads the certificate; it sends no credentials or display commands. With certificate verification enabled, the integration pins that certificate for every web request, including WebSocket control. A changed certificate requires deliberate reconfiguration. No router port forwarding is required.

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

Direct image URL launch was accepted by LG but produced **“Wiedergabe nicht möglich”**. The upload-first path above was visually confirmed, including the return to Apple TV. WebSocket/app acknowledgements alone do not prove correct visual decoding. Native videos, streams and websites use the separate actions documented below; arbitrary modern websites and DRM playback are not guaranteed.


## Suppress OSD during switching

Enable **Suppress OSD during input/fullscreen switching** in options (default off). Before an integration-controlled source switch or native image launch, a fresh `kl ff` read determines the original OSD state. Only an enabled OSD is temporarily disabled. After a two-second settling period it is restored, including on failed/cancelled switching. An already disabled or unknown OSD is never enabled by this feature.

An explicit change through the integration's OSD switch takes precedence over the temporary restoration. Concurrent transitions are serialized. `osd_restore_error` indicates an unconfirmed restoration. Native image entry and return each use the guard; `show_toast` does not. Locking the OSD may also temporarily hide other LG menus/messages. Settings made through another controller or the physical remote cannot always be distinguished from the temporary lock. A network/power failure or hard HA crash can prevent restoration; inspect the OSD switch in that case.

On the tested UH5F-H, enabling OSD during native image playback is rejected. The guard remembers its own temporary lock and restores it after returning to HDMI; OSD can therefore remain suppressed for the full image duration. A pre-existing manual off state never gains this restore ownership.


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

## Display preview and adaptive refresh (v2.2)

Enable **native LG web access** first, then **display preview through screenshots** in integration options. **Normal screenshot interval** accepts 1–3600 seconds (default 30). **Open preview interval** accepts 0–10 seconds (default 1); 0 disables acceleration. Choose **height 360/720/1080 pixels** (default 720). Existing installations retain their normal interval and automatically use the 1-second active default unless changed.

While the bundled remote preview is visible or HA's enlarged camera view is open, the shared collector uses the shorter of the normal and active intervals. Closing the last stream restores the normal interval. The remote also closes its stream when it leaves the viewport, the browser tab becomes hidden, or the card is removed. A click on the remote preview opens the standard enlarged camera dialog. Other cards that open the camera's MJPEG endpoint also activate faster collection; a thumbnail/still-image request alone does not. The native HA dialog controls its own stream lifecycle.

All viewers share one in-memory capture; two dashboards do not double the LG capture rate. Intervals are measured between capture starts. Captures never overlap; if an attempt takes longer, the next waits until at least 100 ms after completion. Errors use a growing retry delay (up to 30 seconds) to avoid continuously hammering an unavailable device. In the hardware check on a 75UH5F-HJ, 360p captures took about 0.6 seconds and 720p captures about 0.8 seconds, so approximately one new frame per second is realistic. Firmware, network and image resolution affect the result. This is a succession of real JPEG screenshots delivered as a browser-compatible MJPEG stream, **not a native video/RTSP/HLS feed**.

Use the bundled remote or a standard picture-entity card, substituting your entity ID:

```yaml
type: picture-entity
entity: camera.lg_display_display_preview
camera_view: auto
show_name: true
show_state: true
```

`camera.turn_off` pauses image collection and clears the cached frame; `camera.turn_on` resumes it. These actions never change display power. Restart/reload restores the options' configured preview enablement. The collector never wakes an off display and skips capture when power cannot be confirmed. Failed captures discard old pixels; an open stream shows a neutral blank frame and recovers when captures succeed again, even if its first capture was unavailable.

Attributes expose `collection_enabled`, `last_capture`, `refresh_interval`, `active_refresh_interval`, `effective_refresh_interval`, `active_viewers`, `capture_height` and `preview_error`. `active_viewers` counts MJPEG connections, not individual people. The frequently changing `last_capture` timestamp is excluded from recorder history. No screenshot is stored to disk or included in diagnostics by the camera. HA's camera permissions and standard `camera.snapshot` action still apply. Screenshots can include HDMI content, depending on firmware, source and content; there is no attempt to bypass content protection.

## Native video, websites and streams (1.6)

MP4 uploads, Play via URL websites without reboot, and tokenized HA-hosted HTML video for HLS/HTTP streams extend the native presentation queue. Conditional input/URL restoration, persistent URL recovery and bounded owned-file cleanup are covered by tests. [Actions, examples and exact limits](NATIVE-MEDIA.md).
