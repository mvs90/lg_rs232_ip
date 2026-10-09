# LG Professional Display

Local Home Assistant integration for LG professional signage displays using RS232 over TCP, with optional native LG web access. **Version 2.32.1 is the independent LG device integration.** Apple TV, Sonos, socket coordination and combined HomeKit control are provided by the separate [AV Companion](https://github.com/mvs90/av_companion) integration.

**Device settings follow the LG menu order** directly on the Home Assistant device page, with collapsible groups and a standard alphabetical fallback. LED Local Dimming is now available as a verified on/off switch. [Menu inventory, dependencies and remaining limits](docs/DEVICE-MENU.md).

Picture presets, **reset current preset / apply to all inputs**, gamma, black level and verified advanced picture controls are available on the device page. See the [settings audit](docs/SETTINGS-AUDIT.md), including model limits and the Kelvin/option-ID changes for existing automations.

Date/time, automatic NTP, custom NTP servers and mode-dependent ISM settings are available through native web access. Prepare ISM images/videos in HA Media for the documented USB import. [Clock and ISM guide](docs/CLOCK-ISM.md).

Power and wake configuration: **Auto Sleep No Signal / No IR, PM mode, power-on status, wired/wireless WoL and DPM wake-up control**, with confirmed readback and a Home Assistant warning for restricted network power-on. See [power settings](docs/POWER-SETTINGS.md).

[Deutsche Anleitung](docs/README.de.md) · [Display Studio](docs/DISPLAY-STUDIO.md) · [Dashboard remote](docs/DASHBOARD-CARD.md) · [System settings](docs/SYSTEM-SETTINGS.md) · [Features and actions](docs/FEATURES.md) · [Device reference](docs/devices/LG-UH5F-H.md) · [MIT license](LICENSE)

## Install with HACS

1. HACS → Custom repositories: add `https://github.com/mvs90/lg_rs232_ip`, category **Integration**.
2. Download, then restart Home Assistant.
3. Settings → Devices & services → Add integration → **LG Professional Display**.
4. Enter the display host, TCP port (normally **9761**) and its current Set ID (normally **1**).
5. Confirm the full display settings form, including optional native web access and screenshot preview. Home Assistant asks for an area only after this step.
6. Reload the frontend, edit a dashboard and add **LG Display Remote**. Its visual editor lets you select the display and optional preview camera; the card is bundled and registered automatically.

Requires Home Assistant 2025.3 or later; tested on 2025.3.4 and 2026.9.4. Available as a HACS custom repository, not in its default catalogue. Manual install: copy `custom_components/lg_rs232_ip` into HA's `custom_components` directory and restart. This release is designed for a fresh setup; no migration from the earlier combined prototype is included.

## Design your display

[Display Studio](https://github.com/mvs90/display_studio) is now an **independent optional HACS integration**. Install it separately and add a Studio entry linked to this LG display to use saved dashboards, themes, media/weather/calendar widgets, custom notification designs and Studio sources. Existing LG Studio designs/backgrounds are copied once without overwriting originals. The Studio sidebar is registered by the extension. See the [setup and split guide](docs/DISPLAY-STUDIO.md).

LG retains hardware control, OSD suppression, resident SI app startup, native HDMI/video planes and screenshots. The app accepts Studio's renderer through a public, owner-checked adapter API and rebinds after LG reload. Without Studio, the LG device integration and basic resident HDMI/notifications remain usable. Studio also offers a browser/kiosk output for other displays.

## What belongs to this integration

- LG power, HDMI sources, display volume/mute, navigation and model-supported picture, audio and energy settings.
- HDMI signal, device information, temperature and diagnostic sensors. Optional advanced entities are disabled by default; enable those supported by your model.
- Native text overlays, temporary fullscreen images and MP4 videos, HTTP(S) streams and websites, with input restoration and owned-file cleanup.
- OSD suppression during switching that preserves a manually disabled OSD.
- Boot-logo on/off and preparation of a custom boot image for **USB import**.
- A screenshot camera with 1–3600 second background refresh, automatic faster capture while the remote or enlarged preview is open (default 1 second), and 360/720/1080p resolution. From 2.2.1, the LG frontend uses Safari-compatible binary JPEG delivery, including the enlarged camera dialog. Standard MJPEG remains available to external clients; this is not a native video endpoint.

An optional [Home Assistant display app](docs/DISPLAY-APP.md) adds automatic SI provisioning, fullscreen messages, selected sensor overviews, HDMI overlays and HDMI picture-in-picture. Optional resident mode keeps HDMI in the app between messages. HA HDMI selection changes the embedded input; new app messages replace outdated ones immediately. Notifications and screenshot capture automatically use the connected app with native fallback. Configure it in HA; no separate display-app package is required.

LG device control works without any Apple TV, soundbar or socket. Native web features require the separate Mobile URL password. An empty SHA-256 field is filled automatically on save and used for subsequent certificate checks. Verification is enabled by default and can be explicitly disabled; basic RS232/IP control requires no web login. [Setup, limits and examples](docs/FEATURES.md), [videos/streams/websites](docs/NATIVE-MEDIA.md).

```yaml
action: lg_rs232_ip.show_toast
target:
  entity_id: media_player.lg_display
data:
  message: "The washing machine is finished."
```

Use `media_player.play_media` on the LG entity for native image/video/website/HLS media; `extra.duration` controls the temporary duration. The dedicated native actions expose priority and other options. Actions queue fullscreen playback; inspect `presentation_active` and `presentation_error` for completion/error information.

## Optional AV system

Install [AV Companion](https://github.com/mvs90/av_companion) in addition, select this LG entity, then optionally link existing HA entities for a player, sound system and display-only socket. Its combined TV is the normal dashboard/HomeKit target. Only LG Professional Display opens device connections or owns web credentials. The [API contract](docs/ARCHITECTURE.md) documents coordination and failure behavior.

For the documented Sonos setup, **Apple TV → permanently powered FeinTech AX310 → LG HDMI 1**, with AX310 eARC to Sonos. The switched socket supplies **only the LG**. [Wiring and observed standby behavior](docs/devices/FEINTECH-AX310.md).

## Compatibility and development

Verified hardware: **75UH5F-HJ**, software **04.13.50**, webOS **4.0.1-136**. Other professional models may support different commands; this is not the consumer webOS TV protocol. Device acknowledgements alone do not establish successful visual decoding. Known firmware limits and official LG references are preserved in the [device reference](docs/devices/LG-UH5F-H.md).

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check custom_components tests
```

See the [current test matrix and remaining hardware checks](docs/TEST-MATRIX.md), [test instructions](docs/TESTING.md), [split acceptance report](docs/RELEASE-TESTS.md) and [contributing](CONTRIBUTING.md).

Picture controls: [aspect-ratio options, backlight locks and DPM/PM dependencies](docs/PICTURE-CONTROLS.md).

### Full-screen music view and 4K assets

Select **Mediaplayer** in Display Studio to configure a full-screen cover, title, artist, playback state and progress view. Bind any existing HA media player, customize widgets and backgrounds, then select the new source on the LG or AV Companion 1.4.0. Artwork tiers honor display pixel density; uploaded backgrounds retain up to 3840×2160 pixels. See [configuration, resource limits and measured LG rendering](docs/DISPLAY-STUDIO.md#mediaplayer-im-vollbild).

Version 2.18 adds optional cached HDMI startup during HA outages, UDP multicast beside HDMI, on-demand platform diagnostics and verified video-wall tile configuration. Camera widgets, short transitions and timed event views remain included. See [Display Studio](docs/DISPLAY-STUDIO.md) and the [hardware capability report](docs/devices/LG-UH5F-H.md#additional-video-and-platform-capability-tests-2026-10-06).

Version 2.21 adds a fixed editable **Startanzeige** in Studio, with local text, clock/date and cached static backgrounds only. Studio confirms when the display has stored the design; full-screen HDMI remains exempt. See [offline startup design](docs/DISPLAY-STUDIO.md#startanzeige-ohne-live-daten).

### Additional device settings (2.30)

RGB white balance, complete sound presets and LG audio input/output controls now accompany native on/off and brightness schedule actions, timezone selection and manual DST rules. See [configuration and examples](docs/NATIVE-SCHEDULES-AUDIO.md) for supported hardware, dependencies and the remaining settings audit.
