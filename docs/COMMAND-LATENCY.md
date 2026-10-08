# Command latency and background polling

Version 2.30.1 prioritizes settings actions over queued status reads. No extra
configuration is required. The optional display app is not required for this
change; it remains at version 1.20.0.

## What caused the delay

On the 75UH5F-HJ (firmware 04.13.50), background queries for HDR picture mode
(`sn C4`), HDR tone mapping (`sn C5`) and both automatic-backlight bounds
(`sn AB 00/01`) received no response in the tested context. Each consumed the
existing two-second command deadline, followed by reconnecting. A full picture
scan held the settings lock across all these reads. Mode changes and individual
picture adjustments also triggered unnecessary complete rescans. Measured HA
actions could consequently take almost 14 seconds.

Silence does not establish permanent lack of support. Availability remains based
on actual responses, and silent optional background queries are retried after
60 seconds. Explicit setting checks bypass this pause.

## How command processing works

- User and automation setting actions, including prerequisite reads and verified
  readback, take priority over queued polling. Actions remain FIFO within their
  priority. After eight priority handoffs a waiting background operation gets a
  turn, so polling is not starved.
- Already-sent requests finish normally. A real timeout or cancellation discards
  the serial connection before another request can use it. Responses cannot be
  reassigned to a different command, and writes are not replayed automatically.
- Background picture scans release their settings lock between queries. If a
  setting or picture context changes mid-scan, the partial old scan is discarded
  instead of overwriting the newly confirmed state.
- A picture-mode action completes after its own device confirmation. Dependent
  controls refresh asynchronously. Individual picture-number and native colour
  changes update their own state without clearing every optional capability.
- Ordinary native-web system changes leave the independent serial transport
  available. A Set ID change still reserves it until the real address has been
  reconciled, including lost acknowledgements and cancellation.
- WebSocket closing after a native reply is bounded to 250 ms; the existing
  request deadline and certificate verification stay unchanged. The former
  library default could wait 10 seconds for a close reply. A deliberately
  unresponsive local server verifies this bound; the physical LG's measured
  close replies were prompt, so this was not established as the hardware delay's
  main cause. See the official [aiohttp timeout reference](https://docs.aiohttp.org/en/stable/client_reference.html#aiohttp.ClientWSTimeout).

## Physical measurements, 2026-10-08

Existing `unifi-air-quality-ha-dev`, HA 2026.9.4; physical 75UH5F-HJ, app connected
in the Mediaplayer view. Timing covers an authenticated HA WebSocket service
request through actual service completion, not the REST API's early return or
human-observed panel rendering. Each action uses device confirmation; the longer
sequence also independently reads native picture values after every change.

| Action | Before: range, 3 changes | After: range, 3 changes | Longer sequence: median / maximum, 6 changes |
| --- | --- | --- | --- |
| Picture mode | 0.638–12.787 s | 0.631–1.164 s | 0.649 / 0.670 s |
| Contrast | 0.801–0.939 s | 0.276–0.397 s | 0.363 / 4.739 s |
| Dynamic contrast | 0.761–13.656 s | 0.377–0.441 s | 0.330 / 1.195 s |

The longer run spans periodic background polling, with 18 confirmed changes.
There is no guaranteed sub-second response: an in-flight silent device query,
HA's own entity updates, a reconnect or an unavailable native web service can
still delay completion. The contrast outlier is retained in the results. The
existing three-second settling period after picture reset/apply-all is also
preserved deliberately.

Testing restored the original active picture profile, all picture values and
profile-modified flags, Smart Energy Saving and brightness scheduling. Native
picture, sound and commercial dictionaries match the fresh pre-test snapshots.
Studio configuration, revision, saved backgrounds and startup design are
unchanged; the Mediaplayer app view remains connected. Other presets, network
conditions and LG models can have different timing.
