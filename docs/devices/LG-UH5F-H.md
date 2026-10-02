# LG UH5F-H: reusable integration reference

Research date: 2026-10-02. Based on read-only queries to an owner's panel and official LG documentation. This is a model-family reference, not a claim that every firmware implements every documented feature. Private addresses, serial numbers, credentials and session cookies are excluded.

## Identity and evidence

| Item | Result | Evidence |
|---|---|---|
| Exact model returned by panel | **75UH5F-HJ** | `fv`, decoded hexadecimal ASCII |
| Product family | 75UH5F-H, 75-inch UHD Signage | LG product page and returned model |
| Software | **04.13.50**, raw `041350` | `fz`; this is not the webOS platform version |
| Platform generation | webOS Signage 4.x | LG product sheet says 4.0; another regional sheet says 4.1. Exact installed platform version is not yet read from the panel. |
| Control protocol | LG RS232 commands over TCP, port **9761**, Set ID **01** | Successful matching acknowledgements |
| Web management | HTTPS **3737** redirects to **3777**, title “Content Manager / LG Signage” | Observed HTTP response and application HTML |
| Consumer TV endpoints | TCP 3000/3001 refused; 80/443 refused | One-time connection checks, not proof that these can never exist |

The initial UH5C identification was an estimate and is superseded by the panel's own model response. Do not apply a consumer webOS TV profile to this display.

## Sources, provenance and offline copies

- [LG 75UH5F-H product support](https://www.lg.com/lk/support/product/lg-75UH5F-H.ATC): associates the documents below with the model family.
- [LG webOS 4.0 User Guide, English, 100 pages](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA): linked by LG with publication date 2025-07-21. Relevant pages: 4 (Home/Mobile URL), 5–9 (content/server/URL), 47–60 (content management), 61 (Control Manager), 71–100 (command protocol).
- [LG UH5F-H Owner's Manual, English, 39 pages](https://gscs-b2c.lge.com/open/downloadFile?fileId=RRrpEksM0dmlHnErlN5tuQ): hardware installation and model specifications.
- [LG US UH5F-H specification sheet](https://www.lg.com/us/business/download/resources/CT00001837/LG_SPEC-SHEET_UH5F-H_Series_092059_LR%5B20201024_070213%5D.pdf): webOS 4.0, hardware and product capabilities.
- [LG regional UH5F-H specification sheet](https://www.lg.com/content/dam/channel/wcms/in/support/products/documents/UH5F-H-LG-UHD-Signage-Digital-Datasheet.pdf): webOS 4.1 label; do not treat it as a reading from this installation.
- [LG webOS Signage developer portal](https://webossignage.developer.lge.com/): SCAP/IDCAP documentation requires partner access. Consumer TV APIs are not evidence of Signage support.

Downloaded file SHA-256: user guide `45da5cd7a0169dafa5b26f9cb18fe102bb131fc7764cd754ed4ff6abee8fc493`; owner manual `690508f367e0298ecc7350c6bc5319871226d490ccd21abdb456cb7acdcc32c5`.

The research workspace keeps downloaded official manuals and exact per-installation recordings under ignored `local/`. Third-party projects should download the original manuals from LG; the repository does not redistribute them.

## Live read-only baseline

All entries below are point-in-time observations while HDMI 1 was active. Values can change. No power, source, picture, network, firmware or password setting was changed during inventory.

| Meaning | Query (Set ID 01) | Payload after OK | Interpretation |
|---|---|---|---|
| Power | `ka 01 ff` | `01` | On |
| Model | `fv 01 ff` | `3735554835462d484a` | ASCII `75UH5F-HJ` |
| Software | `fz 01 ff` | `041350` | Three version fields |
| Input | `xb 01 ff` | `90` | HDMI 1, DTV encoding |
| Temperature | `dn 01 ff` | `20` | 32 °C |
| Operating hours | `dl 01 ff` | `1c2a` | 7,210 h; hexadecimal, not decimal or guessed scaled seconds |
| No-signal power-off | `fg 01 ff` | `01` | 15-minute hardware fallback enabled |
| DPM | `fj 01 ff` | `00` | Disabled |
| Wired Wake on LAN | `fw 01 ff` | `01` | Enabled according to this generation's guide |
| Power after supply returns | `tr 01 ff` | `02` | Power On |
| Picture mode | `dx 01 ff` | `01` | General, not consumer-TV “Vivid” |
| Sound mode | `dy 01 ff` | `01` | Standard |
| Energy saving | `jq 01 ff` | `01` | Minimum |
| Backlight | `mg 01 ff` | `4b` | 75/100 |
| Brightness | `kh 01 ff` | `32` | 50/100 |
| OSD language | `fi 01 ff` | `02` | German |
| Screen mute | `kd 01 ff` | `00` | Off |
| Failover | `mi 01 ff` | `00` | Off |
| HDMI signal | `sv 01 02 ff` | `0201` | Signal present |
| Actual panel state | `sv 01 03 ff` | `0300` | Screen on |
| Configured PM mode | `sn 01 0c ff` | `0c05` | Network Ready |
| DPM wake criterion | `sn 01 0b ff` | `0b00` | Clock-based wake criterion |
| No Signal Image | `sn 01 a9 ff` | `a900` | Off; distinct from no-signal shutdown |

Rejected in this state: `dw` (fan status), `sv 07` (temperature-sensor bitmask), `sv 17` (illuminance). An `NG` means rejected/unsupported in the tested context; it does not establish a faulty fan or sensor. Do not expose invented zero measurements.

Serial number (`fy`) was recorded privately. It is not needed to select the product profile or publish compatibility results.

## Protocol rules for other projects

1. Use ASCII `command SetID data\r`. Replies end with `x`, not necessarily a newline. TCP can split a reply arbitrarily.
2. Match response command letter and Set ID. An initial `x` can be the command letter (for example `dx`), not the frame terminator. Close a timed-out connection rather than accepting its delayed frame for a later request.
3. `ff` is a read only where the individual command documents it. Never iterate a guessed command catalogue or send `mc ... ff`: `mc` sends a remote key.
4. For `sv` and `sn`, validate the echoed subcommand before interpreting the remaining payload: `OK0300` belongs to status `03`, not signal status `02`.
5. A plain integer parser cannot decode model names, serials, version strings or arbitrary multi-field replies. Preserve raw frames locally and use command-specific decoders.
6. Treat missing/NG replies as unknown; do not turn them into off, no-signal or hardware failure. Some commands need an active external input.
7. Software version is `fz`. `fw` is **Wake on LAN**. `fv` reads the model; the legacy `ng` mapping was wrong. Model support is not proven by a generic command dictionary.
8. DPM is a timeout value. This guide lists `00` off, `02` 10 s, `04` 1 min, `05` 3 min, `06` 5 min, `07` 10 min. The old boolean-on value `01` is not in this model's table.
9. Writes need a separate, deliberate acceptance test. A successful status read alone does not prove a setting can be changed in every mode.

Run a bounded, allowlisted inventory with Python's standard library:

```sh
python3 tools/read_display_inventory.py DISPLAY_IP --output local/inventory.json
```

Use `--include-serial` only for a private record. Outputs contain the installation address and must not be committed. No subnet scan, power cycle or authentication attempt is part of the tool.

## Standby design for this installation

The panel already has no-signal power-off enabled. Keep the integration's faster independently confirmed no-signal shutdown and continuous-idle fallback. The captured baseline contains a signal, so it is **not** a reproduction of the Apple TV standby fault.

DPM could provide another device-local response after signal loss; use the new optional DPM Delay selector to choose a timeout deliberately. Do not silently enable it: DPM, PM Mode, HDMI clock behaviour and wake control interact. An Apple TV may stop video without removing the clock. `sv 02` must be recorded during an actual faulty idle/standby event before deciding which combination works best.

`sn 0c` is the configured policy; `sv 03` is the current panel state. These are different concepts. “Screen off” may leave the computer/network alive and is not sufficient proof that it is safe to cut mains. The integration's existing confirmed-power-off requirement stays in effect.

With `tr=02`, restoring the smart plug makes the display turn on. This matters for startup sequencing and automatic-wake blocking. No supply interruption was tested.

## Direct content and notifications

| Approach | Evidence | Remaining work |
|---|---|---|
| Existing linked player | Implemented in v1.2.0 | Configure a player that supports the desired media formats |
| Native Content Manager | App reachable; LG documents files, playlists, templates and scheduling | Authenticate, inspect capabilities, test one temporary asset and restore input |
| Native Play via URL | LG-documented browser feature and Control Manager setting | Inspect authenticated interface; verify rendering and transient launch without changing boot behaviour |
| Saved internal media (`sn a8`) | Listed in LG command guide | Determine an existing asset's valid ID/name; never guess or start every item |
| Multi Screen / PIP (`xc`) | Documented, model-specific | Check input combinations and layout; PIP is not an arbitrary text overlay |
| Overlay over live HDMI | No verified public remote API yet | A Signage app/renderer with confirmed HDMI composition support or a suitable external compositor |

The public web UI's JavaScript shows session login, CAPTCHA and internal application/media routes. These are observed implementation details, **not a supported public API contract**. No authenticated media or control endpoint has yet been validated. Do not ship a backend that merely guesses those calls.

LG's URL feature can save an automatic launch URL and offers a reboot action. A notification must not rewrite boot configuration or reboot the panel for every message. Prefer a preconfigured renderer with transient show/clear sessions and input restoration. Web browser generation, codecs, TLS and authentication constrain which Home Assistant dashboards and media actually work.

## Web login

On the **LG remote**, press **Home**, choose **Mobile URL**, and read the web address and initial web password. The guide distinguishes this from the settings/admin default. The initial web password is no longer displayed after it has been changed. Do not reset credentials to collect an inventory.

The live web UI requests a CAPTCHA. An authorized attempt with the documented admin default was rejected; the separate web credential is still needed. Browser access also needs the owner to accept the panel's local certificate warning. For an eventual integration, provide explicit certificate trust/pinning rather than silently disabling TLS verification globally.

## Improvements implemented from these findings

- Correct `fv` model decoding and `fz` software/firmware reporting; real identity in HA device information and sanitized diagnostics.
- Documented DPM timeout selection and corrected legacy DPM switch semantics (on selects 1 minute).
- Optional signal, current panel-power and configured PM-mode sensors with subcommand validation and unknown-state handling.
- UH5F-specific picture-mode labels and color-temperature command range; corrected OSD language mapping and automatic energy-saving option.
- Fixed frame assembly for replies whose command letter is `x`, verified against the actual picture-mode reply.
- Removed the undocumented abnormal-state query, unused speculative command catalogues and heuristic operating-time parser.

These changes are covered by automated tests. Identity and status reads are checked on the actual panel; setting writes, power cycles, physical HomeKit interaction and native content playback have not been tested on it.

## Useful next extensions, in priority order

1. **Native fullscreen renderer:** authenticate once, inspect the built-in media/URL interfaces, validate a small temporary image, then reuse the presentation queue and restoration contract. Avoid modifying permanent schedules.
2. **Hardware standby acceptance sequence:** capture `ka`, `xb`, `sv 02`, `sv 03` during Apple TV playing, paused, normal standby and erroneous idle. Verify wake via remote after each relevant PM setting.
3. **Capability profiles:** identify model/firmware at setup, hide unavailable choices and distinguish explicit NG from transient no-response. Use recorded fixtures for each family.
4. **Blank-screen mode with retained audio/network:** expose verified screen mute as a deliberate action and restore it; do not confuse it with mains-safe standby.
5. **Thermal and operating-hours alerts:** build HA automations from the existing temperature/hour sensors. Thresholds must come from the exact model's operating limits, not an invented generic warning temperature.
6. **Multi-input mapping:** independently associate HDMI inputs with player/remote entities, retaining one HomeKit TV. Current integration supports one linked player plus one content target.
7. **Brightness automation:** prefer HA time/sun-based backlight control. The ambient-light status query was rejected, so do not rely on a claimed light sensor without further evidence.
8. **Native overlays:** a separate development track requiring verified Signage APIs and a panel-side app/composition test. A successful Content Manager login alone does not prove overlay support.
