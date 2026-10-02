# Native LG videos, streams and websites

Available from **1.6.0** with **native LG web access** enabled in the integration options (Mobile URL password and pinned SHA-256 certificate). These actions run on the LG itself and do not need Apple TV as a renderer. From LG 2.0, external-player `media_player.play_media` and `show_content` routing belongs to the separate [AV Companion](https://github.com/mvs90/av_companion) entity. On the LG entity, `play_media` uses native LG playback.

| Action | Source | Method |
| --- | --- | --- |
| `lg_rs232_ip.show_native_video` | MP4 URL or HA media-source ID; maximum 50 MiB | HA downloads the bounded file, uploads a uniquely named temporary MP4 to LG storage, then opens the native player |
| `lg_rs232_ip.show_stream` | HTTP(S) HLS playlist or browser-compatible video URL; HA media-source IDs can also be resolved | LG opens a temporary HTML video page served by HA; the browser fetches media directly |
| `lg_rs232_ip.show_website` | HTTP(S) website URL | Temporarily configure Play via URL, then select LG input `E3` without rebooting |
| `lg_rs232_ip.clear_content` | No source | Cancel the current presentation, empty its queue and perform conditional restoration |

## Home Assistant examples

Replace the example entity and URLs with your installation values. In Developer Tools → Actions, use:

```yaml
action: lg_rs232_ip.show_native_video
target:
  entity_id: media_player.lg_display
data:
  media_id: media-source://media_source/local/demo.mp4
  duration: 60
```

```yaml
action: lg_rs232_ip.show_stream
target:
  entity_id: media_player.lg_display
data:
  media_id: https://media.example.com/live/index.m3u8
  duration: 300
  muted: true
```

```yaml
action: lg_rs232_ip.show_website
target:
  entity_id: media_player.lg_display
data:
  url: http://dashboard.example.local/display
  duration: 120
```

```yaml
action: lg_rs232_ip.clear_content
target:
  entity_id: media_player.lg_display
```

`duration` is the time to remain on screen, **1–3600 seconds**, measured after launch confirmation. There is no reliable playback-ended event: a short clip does not automatically return to HDMI at its final frame. A stream also ends when the configured display duration expires. Repeated actions queue (maximum ten waiting requests). `clear_content` interrupts immediately, then waits for bounded operations and restoration to finish. The usual quiet hours, urgent priority, optional notification wake and OSD suppression policies apply. Native presentations protect the display from the linked Apple TV's standby automation while active.

## Compatibility and networking

- **Verified hardware:** 75UH5F-HJ, firmware 04.13.50, webOS 4.0.1-136. A locally generated H.264 MP4 and a segmented HLS test playlist rendered successfully; a plain HTML page rendered as well. Input and URL configuration returned to their previous values. This does not establish compatibility with every live provider, codec or newer LG model.
- Use MP4/H.264 with `yuv420p` as a conservative video starting point. The MP4 container check and launch acknowledgement cannot prove decoder compatibility. There is no transcoding and no automatic detection of a player error page.
- Streams must be **direct media URLs**, not YouTube/video-provider watch pages. DRM, arbitrary authenticated providers, RTSP/RTMP, DASH and WebRTC are not implemented. Convert camera RTSP to an LG-compatible HTTP HLS feed externally (for example through an appropriate HA camera/stream setup).
- For `show_stream`, the LG must reach **both Home Assistant's configured URL and the media source**. Set a reachable internal HA URL in Settings → System → Network. HTTPS certificates and mixed-content restrictions apply. The stream page uses a random, short-lived bearer token, sends no LG credentials and is removed at presentation completion. A media-source URL may expire independently, so signed-link lifetime can limit playback.
- The generated stream page uses the browser's native HTML video support, without an external player library. `muted: true` is the default for reliable autoplay; unmuted autoplay depends on the firmware/browser. Browser controls are available, but HA does not expose native video seek/pause or playback position through these presentation actions.
- Websites use the display's older browser. Modern HA dashboards, complex JavaScript, login flows or TLS requirements may be incompatible. No website credentials or HA login tokens are automatically supplied. A simple dedicated display page is the most predictable target. Do not embed username/password in URLs.
- Native LG audio **does not automatically reach Sonos** through the Apple TV → AX310 → LG/eARC soundbar topology. Use the external player route when audio must follow that HDMI source, or a separate HA Sonos announcement.

## Restoration and persistent settings

A presentation starts only from a known external HDMI app, so an existing native application session is not silently replaced. It records display power and input. On completion/cancellation it restores those only while it still owns the screen; an intervening source change takes precedence. Temporary uploaded videos are deleted only after playback has been left or display standby has been confirmed. Failed restoration leaves the owned file and reports `presentation_error` rather than deleting a file that may still be playing.

Websites and streams temporarily change **Play via URL**, which is a persistent device setting. The previous mode and URL are saved in HA storage before changing them, restored after the presentation if the setting still matches the temporary value, and recovered after a HA restart/reload. A failed recovery retains the record for retry before the next website/stream presentation. A user-modified URL setting is not overwritten. Abrupt HA/device/network failure can leave the temporary page or setting active until recovery; the stream page itself expires. Recovery concerns the URL setting, not restoration of an arbitrary browser session.

Normal OSD suppression preserves an originally disabled OSD. Browser-owned messages such as a fullscreen hint may still be firmware-dependent; suppression is not a general filter for website/browser content.

## LG interface evidence

The [official webOS 4.0 guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA) documents Play via URL (p. 8) and input `E3` (p. 76). On the tested firmware:

- Content Manager's own frontend launches internal videos through PUT `/content/play/dsmp`, with `params.type = "video"` and the uploaded internal path. The request is accepted before playback actually appears; verify foreground separately.
- A direct HTTP video URL through that endpoint was acknowledged but did not fetch the media or enter the player. It is **not** used for streams.
- Control Manager provides `getPlayViaUrl` and `setPlayViaUrl` with `playViaUrlMode` and `playViaUrl`. The setter does not send the callback expected by a normal request. Send once, then confirm the exact setting with readback; do not replay a timed-out mutation.
- Setting the URL alone does not open it. Selecting `xb E3` enters `com.webos.app.browser`, requests the page and starts supported HTML video, without a reboot.

These are an observed internal Signage interface, not the consumer TV SSAP API. See the [LG device reference](devices/LG-UH5F-H.md) for the underlying device inventory and [AX310 reference](devices/FEINTECH-AX310.md) for the audio path.
