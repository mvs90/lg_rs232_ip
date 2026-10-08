# Settings audit and picture configuration

Integration **2.31.0**; physical reference **75UH5F-HJ / 04.13.50 / webOS 4.0.1-136**. This audit combines the actual LG menu, authenticated firmware responses and the [official webOS 4 guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA). A menu item or protocol command does not establish support on every Signage model.

## Device-menu grouping and Local Dimming in 2.31

The native Home Assistant device configuration card now follows the LG menu order and groups, with the standard alphabetical card available as a fallback. See the [complete menu inventory and dependencies](DEVICE-MENU.md). The new **LED Local Dimming** on/off switch uses verified `sn c1` readback. The actual menu and `tconLocalDimming` confirm support; the previous claim that this item was absent was incorrect. This is separate from the unverified four-level `sn c6` control.

## Further settings added in 2.30

The [native schedule, clock-region and audio/calibration guide](NATIVE-SCHEDULES-AUDIO.md) covers six RGB gain/offset controls, the completed six-mode sound selector, LG audio output level and digital/analog input, stored power and brightness schedules, the device timezone catalog and manual DST rules. These were exercised through the existing HA container and the physical UH5F, with the original settings restored. Balance is conditionally implemented but rejected by this reference setup.

## Picture controls in Home Assistant

Open **Settings → Devices & services → LG Professional Display → device → Configuration**. Picture mode is enabled and attached to the display by default. An older installation's integration-disabled mode entity is enabled automatically; an explicit user disable is preserved. Existing entity IDs are retained, so the older mode entity can still be named `select.picture_mode`.

| Control | Values / scope | Connection |
|---|---|---|
| Picture mode | Mall/QSR, General, Government/corporate, Transportation, Education, Expert, Auto Power Save, Calibration, Hospital | RS232/IP |
| Reset current picture mode | Reset the active picture preset's adjustments | RS232/IP |
| Apply current picture mode to all inputs | Copy that preset's adjustments across LG inputs | RS232/IP |
| Gamma | 1.9, 2.2, 2.4, BT.1886 | RS232/IP |
| Black level | UH5F external HDMI: Low / High; Auto only for a device-reported automatic context (other families may offer all three) | RS232/IP |
| Brightness, contrast, colour, tint | 0–100; tint 50 is neutral | RS232/IP |
| Sharpness | 0–50 | RS232/IP |
| Colour temperature on UH5F-H | 3200–13000 K, 100 K steps | RS232/IP |
| Dynamic contrast, dynamic colour, Super Resolution | Off, Low, Medium, High | Native web |
| Noise reduction, MPEG noise reduction | Off, Low, Medium, High, Auto | Native web |
| Colour gamut | Auto, Extended | Native web |
| Preferred skin, sky and grass colours | −5 to +5 | Native web |
| HDMI IT content | Automatic preset selection from HDMI content metadata | RS232/IP |
| UHD Deep Color | Separate switches for HDMI 1–3, when the input supports the query | RS232/IP |
| Brightness scheduling | Enable/disable the display's existing brightness schedule | RS232/IP |
| LED Local Dimming | On / Off; requires a valid current device read | RS232/IP |
| Automatic backlight minimum/maximum | 0–100%, step 5, only when supported; minimum cannot exceed maximum | RS232/IP |
| HDR picture mode / dynamic tone mapping | Conditional HDR controls; unavailable without a supported current context | RS232/IP |

Native-web controls require the integration's native LG web option and Mobile URL password. They do **not** require the optional display app. They are limited to the verified UH5F family and its known picture schema. Gamma, black level, reset/copy and the other serial controls work without that login.

The native advanced controls honour LG's active-editing and limitation flags. Calibration and Hospital are not treated as ordinary editable presets. Expert omits dynamic colour and the three preferred-colour adjustments. An unavailable or unknown reading is never substituted with Off or zero. Changes require an awake display, a valid current setting and fresh matching readback; configuration does not wake it. One shared 60-second coordinator reads the advanced settings. Firmware rejections use the existing bounded query backoff. Background polling keeps usable controls available while a read is in progress.

### Reset and apply to all inputs

These are **buttons**, usable from the device page or `button.press` in an automation. Reset affects picture adjustments, not the network, SI app, Home Assistant configuration or a factory reset. Apply-to-all can replace the selected preset's adjustments on other LG inputs: use it when those inputs should share the same calibration.

The scope is the **currently active LG picture context**. Native HDMI and HDMI rendered inside the SI app can use different stored adjustments. Studio views such as Dashboard and Mediaplayer are layouts, not independent physical input picture memories. The integration does not cycle through inputs, overwrite every preset, or select a different Studio view to perform these actions. LG briefly suspends command handling afterward; the shared connection allows a three-second settling period. Missing acknowledgement is reported as uncertain and the action is never automatically repeated.

Example (replace IDs with your device's entities):

```yaml
# Select General, then reset that preset.
- action: select.select_option
  target:
    entity_id: select.picture_mode
  data:
    option: general
- action: button.press
  target:
    entity_id: button.lg_display_aktuellen_bildmodus_zurucksetzen
```

Apply separately when wanted:

```yaml
action: button.press
target:
  entity_id: button.lg_display_aktuellen_bildmodus_auf_alle_eingange_anwenden
```

### Automation changes in 2.29

The translated picture-mode select now uses stable option IDs: `mall`, `general`, `corporate`, `transportation`, `education`, `expert1`, `aps`, `calibration`, `hospital`. Update automations that supplied earlier uppercase labels such as `GENERAL` or `AUTO POWER SAVE`; the entity identity itself stays the same. The old generic consumer-TV preset codes were incorrect for Signage and have been replaced.

UH5F colour temperature now uses **Kelvin**, not the old protocol byte. For example, old value 180 (`0xB4`) becomes **10000**. Update number actions and templates accordingly. Other model families retain their unverified raw temperature scale. Sharpness now rejects values above 50. Tint retains its previous 0–100 scale and explicitly labels 50 as neutral.

## Remaining settings: implementation status

| Area | Already available / added | Remaining work or dependency |
|---|---|---|
| Picture and illumination | Presets, reset/copy, the table above, aspect ratio, backlight, energy saving, Smart Energy Saving | TruMotion's active mode was absent from the native read API despite appearing in the menu. Real Cinema was locked for the current 2160p60 signal. Neither is exposed as a guessed control. |
| Expert calibration | Expert preset, gamma, temperature, gamut, six RGB gain/offset registers | Multi-point white balance and six-axis colour management need verified ranges, context and readback. A calibration preset is not a replacement for a measurement workflow. |
| Model-dependent illumination | Conditional min/max and HDR entities | This display rejects automatic backlight bounds in both the tested OFF and AUTO energy modes. The on/off Local Dimming menu was found and verified in 2.31; the separate four-level variant is not verified. HDR changes need an actual HDR source before hardware acceptance can be claimed. |
| Sleep and wake | No Signal / No IR, DPM delay and wake condition, PM mode, AC power-on state, WoL | Real wake reliability still depends on PM/network topology. See [power settings](POWER-SETTINGS.md). |
| Clock and timers | Clock, automatic time, NTP, timezone/DST, complete supported ISM timing; add/remove native on/off and brightness entries | Holiday calendars and on-timer source/volume policies remain separate work. Native timers do not coordinate a smart plug or AV Companion. |
| Protection and identity | ISM mode/timing, Set ID, Signage name, power-on delay, temperature unit, no-signal image, OSD/remote lock | ISM and boot images can be prepared in HA; installing into LG's special storage still needs USB. See [clock/ISM](CLOCK-ISM.md) and [system settings](SYSTEM-SETTINGS.md). |
| Inputs and playback | Native/app sources, Studio views, media, URL, PiP, OSD-preserving switching | Native failover priorities, per-input PC labels and rotation require coordination with resident-app/source ownership. They are not silently enabled. Only one independent live HDMI image is confirmed. |
| Sound | LG volume/mute, all six sound modes, audio output level, digital/analog input and conditional balance; Sonos routing in AV Companion | Speaker routing, AV sync, EQ and sound reset still need active-schema/model verification. LG sound processing is not Sonos/eARC soundbar processing; this installation uses the FeinTech extractor. |
| Network and administration | Local verified connection, certificate setup, SI provisioning, diagnostics | IP/Wi-Fi changes, password changes, factory reset and locks that could remove control need dedicated recovery workflows. No arbitrary settings-database write action is exposed. |
| Fleet/hardware functions | Device diagnostics and existing app capabilities | Video-wall synchronisation, external sensors, fans and multi-display calibration are hardware-specific and cannot be established with this single panel. |

These are explicit coverage limits, not claims that the menu functions do not exist. The next useful additions are holiday/on-timer policies and motion settings once their active values/dependencies can be verified. Automatic failover should first gain a clear ownership rule with the existing app and AV standby logic.

## Protocol and device evidence

Picture reset is `fk 00`; factory reset `fk 02` is never used by this feature. Apply-to-all is `sn 52 01`. The parser checks exact acknowledgements, including the subcommand/input for multi-operand reads. Gamma uses `sn ad`, black level `sn ae`, Deep Color `sn af`, HDMI IT content `sn 99`, brightness schedule `sm`, HDR preset/tone mapping `sn c4/c5` and automatic backlight bounds `sn ab`.

The native picture API is `getPictureDBVal` → `pictureDB1`, with a nonempty allowlisted keys array. Changes use `setPictureDBVal`, an allowlisted single setting, the active preset's `pictureSettingModified` flag and the same `from` field as LG's own interface. This setter has no acknowledgement event on the reference firmware; the integration verifies it through a new read. Do not substitute unrelated shadow settings or redistribute the panel's proprietary frontend source.

For measured test results, restoration and unverified hardware cases see [release acceptance](RELEASE-TESTS.md). Private device snapshots and credentials are excluded from the repository.
