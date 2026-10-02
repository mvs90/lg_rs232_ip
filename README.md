# LG Professional Display RS232/IP

Control an LG professional signage display locally from Home Assistant.

**Version 1.5 adds a boot-logo switch, a periodic screenshot camera and custom boot-image preparation for USB import. Native text/fullscreen actions remain available. Verified on 75UH5F-HJ / webOS 4.0.1. [Setup and examples](docs/FEATURES.md#boot-logo-and-custom-boot-image-v15).**

 Optionally combine the display, an existing media player (such as Apple TV), and a sound system into **one TV media-player entity** for dashboards and Apple Home.

[Deutsche Anleitung](docs/README.de.md) · [Report a problem](https://github.com/mvs90/lg_rs232_ip/issues) · [MIT license](LICENSE)

## Installation with HACS

1. In HACS, open **Custom repositories** from the menu.
2. Add `https://github.com/mvs90/lg_rs232_ip` with category **Integration**.
3. Download **LG Professional Display RS232/IP**, then restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → LG Display RS232/IP**.
5. Enter the display host and TCP port (default **9761**).

This repository is installable as a HACS custom repository. It is not yet part of the default HACS catalogue. Requires Home Assistant 2025.3 or newer.

Manual installation: copy `custom_components/lg_rs232_ip` into Home Assistant's `custom_components` directory, then restart. When replacing an existing installation, retain the integration domain and existing configuration; entity unique IDs are unchanged. Back up your existing component first. Do not install a second copy under a different domain.

## Display first, optional device linking

Without linked devices, the integration controls display power, HDMI input, volume and supported display settings. Communication is local TCP carrying LG RS232 commands; this is **not** the LG webOS consumer TV integration. Configure network control on your panel or serial-to-IP adapter. The current input map is HDMI 1/2/3 = `90`/`91`/`92` (hex); command and setting support varies by model.

Under the integration's **Configure** options:

- **Linked media player**: an already configured Home Assistant Apple TV or other media player. Choose its physical HDMI input. The integration forwards supported playback actions and exposes app sources and media metadata on that input.
- **Linked volume media player**: an existing soundbar/receiver entity. Volume and mute can follow the linked HDMI input, apply to every input, or stay on the display. With no separate sound entity, the existing linked-player volume fallback remains available.
- **Source names and visibility**: rename or hide HDMI inputs and choose which linked apps to expose.
- **Power supply switch**: optionally control an external socket. It is switched off only after confirmed display standby. Keep the display powered for normal network wake unless you configure this socket.

The linked integrations remain installed as device drivers. Expose only the combined TV to dashboards/HomeKit if you want one visible device. One playback entity and one volume entity can be linked per display; multiple independently mapped players are not supported yet. Sound-system TV input selection is optional; power-off and grouping are not automatic.

## eARC soundbar with an active HDMI extractor

The documented Sonos installation uses **Apple TV → FeinTech AX310 → LG HDMI 1**, with the AX310's eARC output connected to Sonos. The LG does not provide the required eARC connection. **Only the LG is on the switched socket; AX310 remains permanently powered.** The owner reports that this arrangement keeps Apple TV in standby when the display loses mains power, whereas display disconnection can otherwise wake it. This is installation-specific, not a general extractor guarantee.

Keep display power, HDMI signal and player state separate. A confirmed Apple TV standby state may shut down the LG even if a signal remains present. Do not use the extractor's power consumption as LG standby evidence. [Wiring, behaviour and acceptance checks](docs/devices/FEINTECH-AX310.md).

## Multi-stage standby protection

Apple TV can incorrectly remain `idle` after going to sleep. This integration does not treat a repeated `idle` update or a polled active state as a reason to wake the display.

1. A genuine linked `off`/`standby` transition is briefly confirmed before display shutdown, on the linked HDMI input only. Polling recovers missed standby events with repeated observations.
2. The display's independent **HDMI signal query** (`sv <set-id> 02 ff`) is checked. Continuous no-signal observations for **120 seconds**, followed by a fresh power/input/signal confirmation, trigger shutdown even if the player incorrectly says `idle` or `playing`.
3. If signal status is unsupported or unknown, **900 seconds of continuous `idle`** is a configurable fallback. An optional, fresh display power measurement can provide an additional 120-second idle/low-consumption confirmation. A detected signal blocks this fallback; `playing`, `paused`, `buffering`, `unknown` and `unavailable` do not count as idle.
4. Automatic shutdown cannot be reversed by polling stale Apple TV state. Explicit turn-on or a genuine active state transition can wake again. After an automatic shutdown, an `idle` transition alone stays blocked; start playback or use the combined TV's turn-on command.

Signal checking and both timeouts are configurable. Set a timeout to **0** to disable that layer. The idle fallback is a heuristic: on a panel without signal-status support it can also shut down an Apple TV menu after 15 minutes. Increase or disable it if that is undesirable. Delays start at the first valid observation and can overshoot by a polling interval. Startup, source changes, power transitions and interrupted evidence reset the check. Restarting Home Assistant starts a new confirmation period.

The TV's attributes expose `signal_present`, `standby_candidate`, `standby_samples`, `last_standby_reason` and `automatic_wake_blocked`. Unknown/unsupported responses never mean “no signal.” LG's built-in No Signal Power Off (`fg`, often 15 minutes) can provide an additional hardware fallback on supported panels; enable it deliberately in the panel settings or the integration's Auto Sleep control.

## Apple Home / HomeKit

Create a **HomeKit Bridge** entry in **accessory mode**, selecting only the combined `media_player` entity. It has the TV device class, power, sources and volume controls. Playback support follows the linked player. Remove/exclude separately exported display, player and sound-system entities to avoid duplicates.

Example YAML (replace the entity ID):

```yaml
homekit:
  - name: LG Display
    mode: accessory
    port: 21064
    filter:
      include_entities:
        - media_player.lg_display_media_player
```

Do not configure the same accessory through both YAML and the UI. This does not turn the TV into a native Apple TV Home hub. HomeKit navigation is forwarded when a linked remote is configured; see [extended controls](docs/FEATURES.md).

## Compatibility and verification

The initial implementation comes from an existing private LG display setup. The public release adds automated regression tests; a model-by-model compatibility matrix and a live HomeKit/hardware acceptance test are still needed. Please report the exact panel model, firmware, HA version and sanitized observations when contributing compatibility results. Some inherited advanced controls are model-specific; an `NG` response indicates unsupported or rejected commands.

Developer setup (Python 3.13):

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests
```

See [hardware acceptance checks](docs/TESTING.md) and [contributing](CONTRIBUTING.md). No device addresses, recordings or credentials are required for automated tests.

Protocol reference: [LG RS232 command guide, Status check](https://www.lg.com/us/support/products/documents/English%28US%29.pdf). Packaging follows [HACS integration requirements](https://www.hacs.dev/docs/publish/integration/); Apple Home setup follows [Home Assistant HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/).

## Verified device research

The hardware inventory and authenticated playback tests identify **75UH5F-HJ**, software **04.13.50**. See the [reusable model reference](docs/devices/LG-UH5F-H.md) for official LG sources, confirmed commands, energy settings, content/notification options and remaining acceptance tests. Private installation details are not published.

## Native videos, streams and websites

From v1.6.0, use `lg_rs232_ip.show_native_video` for MP4 files up to 50 MiB, `lg_rs232_ip.show_stream` for HTTP(S) HLS/browser-compatible video, and `lg_rs232_ip.show_website` for websites. All require optional native LG web access. Presentations return after the configured duration; `clear_content` cancels them. Website settings are restored conditionally, with recovery after HA restart. [Setup, examples and compatibility limits](docs/NATIVE-MEDIA.md).
