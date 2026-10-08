# LG menu on the Home Assistant device page

Since **2.31.0**, open **Settings → Devices & services → LG Professional Display → device → Configuration**. The configuration card follows the reference display's menu: **Ez Setting, General, Display, Sound, Admin**, followed by Home Assistant controls. Expand a group to use normal HA switches, selectors, sliders and action buttons. No Studio view is needed or created for these settings. Reload the browser after updating the integration.

The reference is **75UH5F-HJ / firmware 04.13.50 / webOS 4.0.1-136**, inspected on **2026-10-08**. Other model families can have different menu items. Only entities actually registered for this display appear. Empty sections are omitted; integration-only controls are in the final Home Assistant group. Settings appearing twice in LG's menu, such as Smart Energy Saving, have one HA row at their first menu location. Raw RGB calibration is grouped with Video Wall white balance, not presented as multipoint picture-preset calibration. Temperature-unit selection is under additional HA device settings because no corresponding menu row was observed in this walkthrough.

**Alphabetical list** switches back to the standard device configuration card. Disabled entities retain HA's per-section enable/edit flow. Entity IDs, user names, disabled/hidden choices, automation targets, backend availability and state updates are preserved. Grouping never makes an unavailable hardware option writable. It does not change the integration's setup/options dialog or the control, camera and diagnostic cards.

## Implementation and compatibility

HA supplies fixed entity categories rather than arbitrary integration-defined menu groups. The bundled frontend module narrowly wraps the native `ha-device-entities-card` configuration renderer for entries whose registry **platform, device ID and config entry ID all match LG**. It embeds the original native entity cards and does not modify HA files or import another copy of Lit. The 2025 frontend's state-update optimization is handled separately from newer rendering. Other integrations, mixed-ownership cards, controls and diagnostics keep their original renderer. Unknown new settings remain visible in an additional section. Missing/malformed catalogs or an incompatible rendering contract retain the native view.

The ordered, translated inventory lives in [`device-menu.json`](../custom_components/lg_rs232_ip/www/device-menu.json). Tests compare it against configuration entities from all supported setup combinations, so a future control cannot silently be forgotten. The grouping adds one small catalog request on browser load and no display polling, resident-app work or persistent settings writes. Native frontend internals are not a public extension API; future HA frontend changes still require compatibility testing. Use the alphabetical view as an immediate fallback.

## Physical menu audit

This is an inventory and dependency audit, **not a claim that every item is remotely implemented or every nested option was exercised**. All five top-level menus were inspected. Detailed captures covered system information, Set ID, clock, power, ISM, general advanced settings, picture controls/options, illumination, rotation, sound and video-wall overview. Existing acceptance evidence and tests supplement the walkthrough. Network/account changes, factory reset, fleet modes and external-hardware modes were not activated to inspect their effects. Private screenshots and native snapshots are excluded from the public repository.

| Actual LG menu / order | Implemented mapping and audit result |
|---|---|
| Ez → Video Wall | Six verified RGB gain/offset entities; tile mode, rows/columns, tile ID, natural mode and fleet calibration are not implemented. The overview exposes dependent controls while tile mode is off; no wall was activated. |
| Ez → On/Off Scheduler | Native schedule actions and count/list sensors exist. Holiday and timer input/volume policies remain open. |
| Ez → SI Server Setting | Optional resident-app provisioning, diagnostics and restoration are implemented. |
| Ez → Server Setting | Read-only platform/server inventory; no general SuperSign server configuration UI. |
| Ez → Failover | Not implemented; requires ownership rules with the resident app and AV standby behavior. |
| Ez → Status Mailing | No SMTP/account editor; use HA notification automations. No emails sent by the audit. |
| Ez → Play via URL | Existing website/URL actions with source restoration. |
| Ez → Data Cloning | No blanket display configuration import/export; Studio library backup has a different scope. |
| Ez → Sync Mode | Fleet synchronization not implemented or verified with this one panel. |
| Ez → Multi Screen | Resident-app layouts/PiP exist independently of this native menu. Two simultaneous independent HDMI sources remain unverified. |
| Ez → LG ConnectedCare, Office Meeting Mode | Present in this firmware's overview; not implemented as HA settings. No LG Business Cloud item was observed in this menu. |
| General → Language | OSD language select. |
| General → System Information | Signage name, Smart Energy Saving; model/software/serial and runtime information remain in HA device information/diagnostics. |
| General → Set ID | Set ID with stored-address adoption and tested extended addressing. Automatic fleet ID assignment/reset is not implemented. |
| General → Time & Date | Automatic time, manual date/time, manual DST and NTP; timezone/catalog and DST-rule actions. Automatic/manual dependencies are tested. |
| General → Power | No Signal, No IR, DPM, DPM wake condition, PM mode, power-on delay, AC power-on state, WoL. Native power history is not imported. |
| General → Network | Integration connection settings do not rewrite LG network configuration. Wired/Wi-Fi network editing and connectivity recovery remain open. |
| General → Safety Mode → ISM | Method and conditional repeat/wait/duration/weekly timing; image/video preparation for USB import. Actual timed execution and USB installation are not certified by this walkthrough. |
| General → Advanced → Beacon, PC/OPS Control | Not implemented; require BLE/OPS hardware and verified active APIs. |
| General → Advanced → Background Image | Boot-logo and no-signal-image switches. Boot/ISM USB preparation is documented; general no-signal artwork replacement remains open. |
| General → Advanced → Input Manager, SIMPLINK | Per-input PC/DTV labels and CEC policy editor remain open. Their effects overlap source/power ownership. |
| General → Advanced → Crestron, LG promota | Platform inventory exists; no Crestron controller or promota provisioning is claimed. |
| Display → Picture Mode | Presets, backlight, contrast, brightness, sharpness, colour, tint, temperature, apply/reset. Native HDMI and SI app contexts may retain different values. |
| Picture Mode → Advanced Control | Dynamic contrast/colour, preferred skin/sky/grass, gamut, Super Resolution, gamma. Expert and locked presets have separate dependency checks. |
| Picture Mode → Picture Options | Noise/MPEG reduction and conditional black level. Real Cinema was greyed out; TruMotion was visible, but its active API mode remains unverified. |
| Display → Aspect Ratio | Model-aware Full Screen / Original selector; legacy raw-code entity retained. |
| Display → Rotation | OSD/content rotation, external-input rotation and mirror mode were visible; not added as writes without app-layout and input-context validation. |
| Display → Advanced → UHD Deep Color | Conditional input switches. Hardware availability/readback, not the presence of a generic menu, determines writability. |
| Display → Advanced → Energy Saving | Energy mode, Smart Energy Saving and brightness schedules. Manual backlight is blocked by the applicable energy/schedule/power conditions. Conditional auto-backlight bounds remain unsupported on this tested device. |
| Display → Advanced → HDMI IT Content | Existing metadata-driven picture-mode switch. |
| Display → Advanced → LED Local Dimming | **New verified on/off switch in 2.31.0.** Corrects the previous audit's statement that this menu item was absent. |
| Sound → Sound Mode | Six stored LG presets and conditional balance. With SIMPLINK external speaker selected, this OSD row was greyed out; serial preset storage still responds. A stored preset is not proof that processing is applied to external audio. |
| Sound → Sound Out | Speaker routing remains open; the visible SIMPLINK setting does not establish physical eARC support. This installation uses the external FeinTech AX310. |
| Sound → Audio Out | Off / Variable / Fixed selector; the actual menu choices match the implemented codes. |
| Sound → AV Sync Adjust | Greyed out in the observed external-speaker context; no write interface exposed. EQ, AV sync and sound reset still need verification. |
| Sound → Digital Audio Input | Existing Digital / Analog selector. |
| Admin → Lock Mode | Existing remote lock and OSD visibility; other lock combinations/recovery not implemented. |
| Admin → Change Password, Enterprise Setting, Factory Reset | Present; no arbitrary writes or destructive test actions. No HDCP dynamic-output item was observed in this reference menu. |

## LED Local Dimming evidence

The observed menu is **Display → Advanced Setting → LED Local Dimming**. The on/off command is **`sn c1`**, data `00` / `01`, queried with `ff`. It is **not** the separate four-level `sn c6` setting described for other contexts in the [official LG webOS 4 guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA). No four-level select is inferred from the generic picture database's `localDimming: medium` value.

Real HA switch actions changed On → Off → On. The serial confirmation and fresh native **`commercial.tconLocalDimming`** agreed. A similarly named **`commercialLocalDimming`** field stayed unchanged and is not used as the active control. The final complete commercial dictionary matched its baseline. One off action plus independent web read completed in 0.566 s; this is an observation, not a latency guarantee or luminance measurement. The feature requires confirmed awake power and a valid current read; a missing/invalid response does not become Off. Writes are not replayed after an uncertain acknowledgement.

## Regression coverage

- Menu catalog completeness across five setup compositions, unique qualified keys, LG top-level order, stable registry identity and all translated section names.
- Both frontend contracts in Chromium/WebKit: disabled entries, changing states, changing language, adding/removing rows, two displays, renamed IDs, module loaded twice, existing mounted pages, unknown settings, missing identity/catalog, invalid duplicate entries and native fallback.
- Existing picture/backlight/energy/PM/source-context and ISM/clock/schedule dependency tests; unsupported queries, partial native failure, late replies, physical supply changes and no-wake behavior.
- New Local Dimming exact frames, valid/invalid reads, powered-off/unknown power, unsupported queries, lost-ACK reconciliation and no write replay.

See [release acceptance](RELEASE-TESTS.md), the [settings feature audit](SETTINGS-AUDIT.md) and the [test matrix](TEST-MATRIX.md) for the distinction between automated tests, physical setting verification and remaining hardware scenarios.
