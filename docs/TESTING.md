# Hardware acceptance checks

Record panel model/firmware, HA version and release version. Tests below deliberately change device power; run them when the display is not needed. Do not publish private addresses or raw diagnostic recordings.

1. Install through a HACS custom repository and verify reload/removal without dangling connections or tasks.
2. With no linked devices, verify power, all supported inputs, display volume and mute.
3. Link a player and a volume entity; verify source labels, app selection, playback and volume routing on each input.
4. While watching content, verify `signal_present: true`. Leave the Apple TV menu idle beyond 15 minutes: a present signal must prevent fallback shutdown.
5. Put Apple TV into standby. Verify normal shutdown; then simulate a stale `idle` player state with a test/template entity. With HDMI signal absent, verify a no-signal candidate, at least two observations across the configured delay, and `last_standby_reason: no_signal`.
6. Leave stale idle updates arriving after shutdown: the display must stay off. Start playback or use explicit turn-on: it must wake.
7. Restore signal or switch HDMI inputs during the countdown: shutdown must be cancelled. Repeat during display wake and immediately after HA restart.
8. Disable signal checking to simulate an unsupported panel. Continuous idle should trigger the fallback; paused/playing/unavailable states should not. Set idle delay to zero and verify it remains disabled.
9. Disconnect the network: do not interpret loss of communication as standby or turn off the power socket without confirmed off status.
10. Pair the combined entity with HomeKit in accessory mode. Verify one TV, on/off, source selection and sound-system volume. Do not export the underlying devices again.

Automated tests use synthetic state objects and a local TCP server. They cannot certify a physical LG panel, tvOS, HDMI handshake, or Apple Home pairing.

## Additional 1.2 checks

11. Configure the Apple TV remote and verify actual wake/suspend, HomeKit arrows/menu and isolation between two TVs.
12. Start a wake while the panel boots, then immediately turn off. No background task may wake it later.
13. Configure a separate content player. Play a compatible media-source item, then verify timed source restoration, queue ordering and manual cancellation.
14. Change the HDMI input using the physical remote during a presentation. The integration must not restore over this choice.
15. Verify default no-wake and overnight quiet hours. Urgent requests may bypass quiet hours but must not bypass no-wake.
16. With an actual renderer script, verify show/clear session ownership, error handling and both supported modes. Without it, notification actions must fail explicitly.
17. Verify Sonos TV source, night mode, speech enhancement and announcement volume through the optional links.
18. If using a power sensor, measure display-only standby consumption; verify stale/invalid measurements never count as evidence.

The automated suite runs against Home Assistant 2025.3.4 (Python 3.13) and 2026.9.4 (Python 3.14), including real HA entity-service routing and a local TCP server. This does not certify on-device rendering, tvOS behaviour or specific Sonos firmware.

## UH5F-H hardware readback (2026-10-02)

The updated integration read 75UH5F-HJ, software 04.13.50, picture mode 1, signal present, panel state 0, PM mode 5 and DPM disabled from the panel. This validates readback and decoding only. No setting writes, source changes or power cycles were performed. A repeated inventory exposed the leading-x response framing bug and the corrected picture-mode read was verified on the real device. See [device reference](devices/LG-UH5F-H.md) for the baseline and remaining acceptance sequence.


Native web acceptance (v1.4): tests cover certificate pin validation, login failure, fragmented/bounded responses, no automatic mutation retry, PNG/JPEG validation, owned asset paths, native toast policy, upload/launch cancellation, physical source changes, restoration failure and optional wake/standby restoration. On 75UH5F-HJ the owner confirmed text over HDMI and fullscreen/return; the production client was then checked with upload, foreground detection, source restoration and deletion. Direct HTTP image playback failed despite a positive launch acknowledgement.

For another model/firmware, opt in only after checking the certificate and normal login. Test one disposable image while watching the panel, then verify return and deletion. Test power/socket/Apple TV/HomeKit flows separately; the native presentation check does not validate those physical interactions. A manual change within the same native player app is an acknowledged ownership limitation.

OSD acceptance on the same panel: readback on → off during native image → on after HDMI return; the owner visually confirmed no OSD banner during the transition. Automated tests also preserve initially disabled/unknown OSD and a newer manual HA OSD change.
