# Native schedules, clock region and audio/calibration

Added in **2.30.0**. Hardware reference: **75UH5F-HJ, firmware 04.13.50, webOS 4.0.1-136**. These functions do not need the optional SI display app. The schedule and region actions require **native LG web access** with the Mobile URL password; the RGB/audio entities use RS232/IP.

## Controls on the device page

| Control | Values | Reference-device result |
|---|---|---|
| White balance, red/green/blue gain | 0–254, whole steps | All six RGB controls read, changed by one step and restored through HA |
| White balance, red/green/blue offset | 0–127, whole steps | These are LG's direct calibration registers, not six-axis colour management or multipoint Expert calibration |
| Sound mode | Standard, Music, Cinema, Sports, Game, News / Clear Voice III | All six selections verified; previous uppercase automation IDs retained (`STANDARD`, `NEWS`, etc.) |
| LG audio output level | Off, Variable, Fixed | All values verified; Variable follows LG volume |
| LG audio input | Digital (HDMI/DP/OPS), Analog | Both values verified |
| LG balance | 0–100, 50 centred | Conditional: the UH5F rejects the query in this installation; entity remains unavailable |
| Manual daylight saving | On/off; rules in attributes | Available for editing with automatic time disabled |
| Power-on / power-off / brightness schedule sensors | Entry count and `entries` attribute | Actual active device lists, not legacy shadow timer fields |

RGB values are raw LG calibration levels. Do not interpret gain as percent or offset as Kelvin. The sound controls affect the **LG**, not Sonos. The FeinTech AX310 extracts the soundbar signal upstream of this display; changing an LG sound preset does not configure Sonos or provide eARC on the panel. Native sound database fields mentioning ARC are not sufficient proof of a working ARC output.

One shared 60-second poll handles audio/RGB and another reads all three native schedule lists. Existing protocol rejection backoff avoids repeatedly querying unsupported controls. Changes require confirmed power and a valid current read; they do not wake the display. A successful write is accepted only after matching fresh readback. An uncertain write is not automatically replayed.

## Stored power schedules

Use **Developer tools → Actions** or an automation with `lg_rs232_ip.add_power_schedule`, targeting the display's `media_player` entity. These schedules run in the LG itself even when HA is unavailable. They use the **display's local clock and timezone**, not HA's timezone.

```yaml
action: lg_rs232_ip.add_power_schedule
target:
  entity_id: media_player.lg_display_display
data:
  kind: power_on
  time: "07:00"
  repeat: weekdays
```

`kind`: `power_on` or `power_off`. Repeat: `daily`, `weekdays` (Monday–Friday), `monday_saturday`, `weekends`, or `sun`, `mon`, `tue`, `wed`, `thu`, `fri`, `sat`. Maximum **seven entries per list**. Exact duplicates are a no-op; overlapping entries at the same time are rejected. Arbitrary combinations created in LG's menu remain intact, but removing a combination outside these protocol encodings must be done in that menu.

The action programs the timer only. It does not cut a smart plug, command Apple TV/Sonos, select a Studio view, or change the on-timer input/holiday policy. A timer cannot turn on a display disconnected from mains. PM mode and other LG timer policies still apply. Choose HA/AV Companion automations when the whole AV chain should follow a coordinated sequence.

## Stored brightness schedules

Enable the **Brightness scheduling** switch first. LG rejects list operations while this mode is off; the integration does not silently enable it. Enabling a pre-existing schedule can immediately affect backlight. Entries repeat daily, maximum **six**.

```yaml
action: lg_rs232_ip.add_brightness_schedule
target:
  entity_id: media_player.lg_display_display
data:
  time: "07:00"
  backlight: 75
```

Read the schedule sensor's `entries` attribute to see saved times and levels. It remains readable while the function is off. Disabling the function preserves its entries. Manual backlight adjustment remains subject to the existing brightness-scheduling/energy-mode dependencies.

## Removing or changing one entry

Copy `id` from the appropriate schedule sensor. Brightness IDs are times such as `07:00`; power IDs combine days and time, such as `mon@07:00` or `fri+mon+thu+tue+wed@07:00`. Treat the displayed ID as opaque and copy it exactly.

```yaml
action: lg_rs232_ip.remove_native_schedule
target:
  entity_id: media_player.lg_display_display
data:
  kind: power_on
  schedule_id: "mon@07:00"
```

To change an entry, remove that entry and add its replacement. These are two explicit actions, not an atomic edit. The integration provides no blanket delete-all operation. Before deleting it freshly reads the active list, finds the matching serial slot and checks the list again. Afterward it verifies that every other entry is preserved. Concurrent external changes or uncertain responses are reported, not silently overwritten.

UH5F regenerates **all internal `_id` values** on each serial schedule mutation, even for unchanged rows. They are unsuitable for HA identifiers. The integration uses content-based identifiers and compares actual settings instead. It also explicitly classifies `e1…e7 ff ff` as writes: the trailing `ff` bytes are not a read query and must never lead to caching a deletion.

Power schedules: `fd` / `fe`, read slots `f1…f7`. Brightness: `ss`, read slots `f1…f6`. Only the selected slot is removed. Native `onOffTimeSchedule` is authoritative for power timers; `onTimerCount`, `onTimerSchedule` and similar older fields remained empty during confirmed writes on this firmware. Brightness entries are stored in the JSON string `easyBrightnessSchedule`.

## Timezone and manual daylight saving

Read the device's own catalog first:

```yaml
action: lg_rs232_ip.get_timezones
target:
  entity_id: media_player.lg_display_display
data:
  country: DE
response_variable: lg_timezones
```

`get_timezones` returns the available `ZoneID`, city, country, standard UTC offset in minutes and DST-support flag. Then, with automatic time enabled:

```yaml
action: lg_rs232_ip.set_timezone
target:
  entity_id: media_player.lg_display_display
data:
  continent: Europe
  country: DE
  timezone: Europe/Berlin
```

The integration passes the selected **device-provided timezone object** back to LG. It verifies continent, country and actual timezone separately. If a step fails, the preceding step may already be applied; the action reports the failure and refreshes the current clock instead of replaying setters. Existing schedules immediately follow the new local clock.

For a manually maintained clock, `configure_dst` controls LG's recurring summer-time rules. `week: 5` means **last**, not fifth occurrence; weekdays are **0 Sunday … 6 Saturday**; hours are **0–23**. Supply all eight rule fields together, or omit all to change only on/off. Identical start/end rules cannot be enabled. Example European-style manual rules:

```yaml
action: lg_rs232_ip.configure_dst
target:
  entity_id: media_player.lg_display_display
data:
  enabled: true
  start_month: 3
  start_week: 5
  start_weekday: 0
  start_hour: 2
  end_month: 10
  end_week: 5
  end_weekday: 0
  end_hour: 3
```

Turn automatic time off before enabling manual DST. Rule changes temporarily turn manual DST off, verify both rules and only then re-enable it. Re-enabling automatic time also disables active manual DST, following LG's own UI dependency. Rules can be prepared with `enabled: false` while automatic time is on. The clock sensor exposes `display_timezone`, `automatic` and `manual_dst`; it continues to interpret LG's actual GMT offset rather than assuming HA's timezone.

## Remaining gaps

Holiday calendars, on-timer source/volume policies, EQ, AV sync and sound-reset are not exposed through unverified generic database writes. TruMotion, Real Cinema, multipoint/CMS calibration, automatic input failover and rotation retain the limits listed in [the settings audit](SETTINGS-AUDIT.md). This release confirms configuration and restoration; it does not claim an actual seasonal DST transition, every scheduled power event, or operation on another Signage family.

Protocol reference: [LG webOS 4 guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA). The public repository contains integration logic and observed schemas, not LG's proprietary frontend files, device passwords or private snapshots.
