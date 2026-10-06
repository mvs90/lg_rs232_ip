# Picture controls and power modes

LG Professional Display **2.10.1**, display app **1.7.2**. Verified on **75UH5F-HJ / firmware 04.13.50 / webOS 4.0.1-136**. Other models can reject controls depending on their input and mode; an unavailable value is not a zero reading.

## Aspect ratio

Use the **Aspect Ratio** select:

- **Full Screen** (`kc 02`) fills the available image area. In the resident app this stretches HDMI to the complete video rectangle.
- **Original** (`kc 06`) retains the image proportions. In the app the picture is fitted inside the video rectangle with unused space when needed.

The setting is read back after writing. The paired app receives changes through its existing long poll and adjusts the same video element in HDMI full-screen, PiP and notifications; it does not switch inputs or reload the decoder. If a read fails, HA reports the control unavailable; the app retains its last confirmed fitting mode.

The older **Aspect Ratio Code** number remains for existing automations, restricted to **2** and **6** (step 4). Arbitrary 0–255 values were incorrect: **255 is a query**, not an aspect-ratio setting. No guessed 4:3/zoom modes are offered. These codes are not the separate `xd` commands for LG's native Multi Screen feature.

A 16:9 signal inside a 16:9 rectangle can look identical in both modes. Black bars encoded inside a video remain part of that video; this control does not crop them away. Studio still determines the video rectangle's position and size, including whether a video widget exists at all.

## Backlight

**Backlight** (`mg`, 0–100%) adjusts panel illumination. **Brightness** (`kh`) adjusts the picture's tonal brightness and is a separate control.

| Condition | Manual Backlight |
|---|---|
| Energy Saving OFF, MINIMUM or MEDIUM; panel on; scheduling off | Available when the panel confirms a valid value |
| Energy Saving MAXIMUM | Unavailable: maximum energy saving controls illumination |
| Energy Saving AUTO | Unavailable: automatic energy saving controls illumination |
| LG Brightness Scheduling enabled | Unavailable: the display's schedule controls illumination |
| Panel off / PM standby / unknown power | Unavailable |
| DPM configured, but panel still on | DPM alone does not lock the slider |
| Picture mode changed | Read the new mode's backlight; do not retain an old mode's number |

The **Backlight Control** diagnostic sensor explains the current restriction, including energy-saving mode, scheduling and actual panel state. It remains readable while the number is unavailable. Home Assistant itself omits custom attributes on unavailable number entities, so relying only on the slider's attributes would hide the reason.

For manual control, choose **Energy Saving → OFF, MINIMUM or MEDIUM**. If scheduling is active, turn off **Display → Advanced Setting → Energy Saving → Brightness Scheduling** on the LG. The integration never disables an energy policy or schedule automatically when moving the slider.

Writes require an exact acknowledgement **and a fresh matching readback**. Failed or blocked reads clear the displayed number. Relevant setting changes invalidate temporary rejection caches and refresh the controls; an earlier `NG` must not lock a now-valid control for another five minutes. Unrelated commands, such as volume changes, retain the optional-command backoff to avoid excessive device traffic.

Picture presets may have different stored backlight values. In the acceptance test General used 75 and Auto Power Save used 100 with energy saving off. APS alone was **not** treated as an unconditional manual-control lock; the actual energy, schedule, panel and readback determine availability. Smart Energy Saving, dynamic contrast and the programme itself can also affect perceived brightness. A configured backlight percentage is not a measured luminance or power-consumption value.

## DPM versus PM mode

**DPM Delay** is the no-input timeout. **PM Mode** determines what the monitor does when going off. The actual panel state is a third, separate value.

- PM **Sustain Aspect Ratio** preserves EDID for the attached computer. It is not the image-scaling select above.
- PM **Screen Off & Backlight On** can keep partial illumination for temperature management while the screen is off. It is not ordinary manual backlight control.
- PM **Network Ready** keeps power control reachable while the monitor is off.

In the verified installation, DPM stayed at **1 minute** and PM stayed at **Network Ready** throughout manual backlight changes. AUTO energy saving, not the configured DPM timeout, explained the unavailable backlight control. Tests did not deliberately trigger DPM standby or alter the Apple TV/extractor power topology.

## Evidence and limits

The [official LG webOS 4.0 guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA) documents power modes on pages 16–17, picture controls on pages 29–34, `kc` and `jq` on page 76, `mg` on page 81 and brightness scheduling on pages 87–88. The panel's authenticated Control Manager `/js/design/device.js`, `backlightCallback`, additionally gates its own slider on energy saving off/min/med, disabled `easyBrightnessMode`, and screen-on state. This internal implementation is firmware-specific and is not redistributed.

Physical acceptance used the existing HA 2026.9.4 container. OFF/MINIMUM/MEDIUM accepted 75 → 70 → 75 and the independent LG picture database confirmed 70. MAXIMUM/AUTO were correctly unavailable, and switching back recovered immediately. The APS preset and return were checked without changing its stored backlight. Both aspect codes were acknowledged/read back; captures showed contain/fill geometry on a deliberately narrow PiP rectangle while the SI app remained active. The HDMI image was black during those captures, so this verifies the video plane's geometry rather than active programme detail or HDCP behaviour. The original library, source, aspect, picture mode, backlight, energy saving, DPM and PM mode were preserved/restored.

Brightness-scheduling and panel-off blocking have automated coverage and were cross-checked against LG documentation; their activation was not forced on this installation. Native captures, firmware frontend copies, addresses and credentials remain private under ignored local storage.

## ISM: image-retention protection

**ISM-Modus (Nachbildschutz)** is a named, translated select. It controls LG's image-retention treatment, not input selection, backlight, DPM or the display app. For the identified indoor 75/86/98-inch UH5F-H family it offers:

| HA option | LG command data (hex) | Effect |
|---|---|---|
| Off / Aus – normale Bildanzeige | `08` | Normal picture without ISM treatment. **Off is not `00`.** |
| White wash / Weißbild | `04` | A full white pattern replaces the programme picture. |
| User image / Benutzerbild | `90` | Uses images imported through the LG ISM menu. |
| User video / Benutzervideo | `91` | Uses a video imported through the LG ISM menu. |

Import ISM media on the LG under **General → Safety Mode → ISM Method** from the USB `ISM` folder. This is separate from HA display-app media and the boot logo. Repeat, standby time and duration remain LG settings; selecting a method does not configure a schedule or upload media. A confirmed method value does not prove a scheduled wash is currently visible.

The [LG webOS 4.0 guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA), pages 22–23 and 85, also documents Orbiter (`02`, four-pixel shifts), but limits it to outdoor models and requires a signal. It is therefore **not offered for the known indoor UH5F-H profile**. The guide also excludes Orbiter while User Video is active.

For other model families, the generic selection additionally includes Inversion (`01`), Orbiter (`02`), Colour Wash (`20`) and Washing Bar (`80`), as documented in [LG's older Signage installation guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=wzyRhbm7yskyYDcjkjrg), page 22. These are model-dependent, not a claim of support on every LG. Inversion reverses colours; colour wash alternates white/colour patterns; washing bar moves a bar over the image. Older generations may require the ISM timer to be set to Immediately.

A write requires an exact acknowledgement and a fresh matching `jp ff` readback. Rejected/unknown readings never become a made-up mode. The old, disabled-by-default **ISM Method Code** number is retained for existing automations but only accepts the same documented profile values; arbitrary bytes, including `255` (a read request), cannot be written as modes. For normal use, choose the named select.
