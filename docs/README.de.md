# LG Professional Display – Home Assistant und HACS

Das LG-Display ist das Hauptgerät. Optional werden ein vorhandener Zuspieler (z. B. Apple TV) und ein Soundsystem zu einer gemeinsamen TV-Mediaplayer-Entität zusammengeführt. Die ursprünglichen Integrationen bleiben als Anbindung erforderlich; in Dashboard und HomeKit genügt die gemeinsame Entität.

## Installation

1. HACS → Menü → Benutzerdefinierte Repositories.
2. `https://github.com/mvs90/lg_rs232_ip` als **Integration** hinzufügen.
3. Herunterladen und Home Assistant neu starten.
4. Einstellungen → Geräte & Dienste → Integration hinzufügen → **LG Display RS232/IP**.
5. Display-Adresse und Port eingeben (Standard **9761**).

Ab Home Assistant 2025.3. Die Aufnahme in den allgemeinen HACS-Katalog ist noch nicht erfolgt. Bei einem Upgrade bleiben Domain und bestehende Entity-IDs erhalten. Vorher die bisherige Installation sichern und den vorhandenen Komponentenordner ersetzen.

## Optionale Kopplung

Unter **Konfigurieren** den Zuspieler und dessen HDMI-Eingang auswählen. Optional einen Lautstärke-Mediaplayer auswählen. Lautstärke und Stummschaltung können nur am gekoppelten Eingang, immer über das Soundsystem oder am Display gesteuert werden. HDMI-Namen und sichtbare Apps sind einstellbar. Pro Display sind ein Zuspieler und ein Lautstärkegerät vorgesehen. Das Ausschalten des Soundsystems wird nicht automatisch gekoppelt. Ab Version 1.2 kann dessen TV-Eingang beim ausdrücklichen Einschalten gewählt werden.

## Apple TV meldet trotz Standby „idle“

Die Erkennung vertraut nicht allein dem Apple TV:

- Echte Standby-/Aus-Meldungen werden bestätigt. Verpasste Meldungen werden durch wiederholte Abfragen aufgefangen.
- Das Display wird unabhängig nach einem HDMI-Signal gefragt. Nach **120 Sekunden bestätigtem Signalverlust** werden Stromzustand, Eingang und Signal erneut geprüft und das Display ausgeschaltet.
- Ist die Signalabfrage nicht unterstützt oder unbekannt, wird nach **900 Sekunden durchgehendem „idle“** abgeschaltet. Ein vorhandenes Signal sowie „playing“, „paused“ und „buffering“ verhindern diese Idle-Rückfallebene.
- Wiederholte Idle-Meldungen und alte abgefragte Zustände schalten das Display nicht erneut ein. Nach automatischer Abschaltung explizit den gemeinsamen TV einschalten oder Wiedergabe starten; eine reine Idle-Meldung reicht dann nicht.

Beide Zeiten sind konfigurierbar; **0 deaktiviert** die jeweilige Stufe. Die Idle-Rückfallebene kann bei fehlender Signalunterstützung auch ein 15 Minuten unbenutztes Apple-TV-Menü abschalten. Die tatsächliche Verzögerung hängt vom Abfrageintervall ab. Beim Start, Quellenwechsel und bei unterbrochener Bestätigung beginnt die Erkennung neu. Unbekannte Netzwerkantworten werden niemals als fehlendes Signal gewertet.

Optional bietet die LG-Einstellung **Auto Sleep / No Signal Power Off** eine zusätzliche hardwareseitige Absicherung (modellabhängig, häufig 15 Minuten). Sie wird nicht ungefragt aktiviert.

## HomeKit

In **HomeKit Bridge** den Modus **Einzelgerät / Accessory** verwenden und ausschließlich den gemeinsamen TV-Mediaplayer auswählen. Die einzelnen Geräte nicht zusätzlich exportieren. Die TV-Entität stellt Ein/Aus, Quellen, Lautstärke sowie unterstützte Wiedergabeaktionen des Zuspielers bereit. Ab Version 1.2 werden HomeKit-Navigationstasten über eine optional konfigurierte Remote-Entität weitergeleitet.

## Prüfstand

Automatisierte Tests prüfen insbesondere die fehlerhafte Idle-Meldung, Signalverlust, Signalrückkehr, Eingangswechsel und fragmentierte Netzwerkantworten. Ein Test am konkreten Display und eine echte HomeKit-Kopplung sind vor Ort noch erforderlich. Siehe [Prüfanleitung](TESTING.md) und [vollständige Dokumentation](../README.md).

## Erweiterungen ab Version 1.2.0

Die Optionen enthalten jetzt eine gekoppelte Fernbedienung, einen separaten Inhaltsplayer samt HDMI-Eingang, Sonos-Schalter für Nachtmodus/Sprachverbesserung und einen optionalen Leistungssensor des Displays. Bei einer Apple-TV-Fernbedienung den Strommodus **apple_tv** wählen: Ein/Aus verwendet dann `wakeup`/`suspend`.

HomeKit-Navigationstasten werden dem aktiven Eingang zugeordnet. Medien-URLs und Home-Assistant-Medienquellen lassen sich mit `media_player.play_media` an die gemeinsame TV-Entität senden. Unterstützte Wiedergabefunktionen werden vom aktiven Player übernommen.

Neue Aktionen:

| Aktion | Zweck |
| --- | --- |
| `lg_rs232_ip.send_remote_command` | Navigation am aktiven Gerät |
| `lg_rs232_ip.show_content` | Medien zeitweise anzeigen und zum vorherigen Eingang zurückkehren |
| `lg_rs232_ip.clear_content` | Anzeige abbrechen und Warteschlange leeren |
| `lg_rs232_ip.show_notification` | Meldung über ein konfiguriertes Anzeige-Skript ausgeben |
| `lg_rs232_ip.set_sound_mode` | Sonos-Nachtmodus oder Sprachverbesserung |
| `lg_rs232_ip.announce` | Audio-Durchsage auf einem unterstützten Soundsystem |

Temporäre Inhalte und Meldungen dürfen das ausgeschaltete Display standardmäßig **nicht einschalten**. Das lässt sich ausdrücklich erlauben. Ruhezeiten gelten in der Home-Assistant-Zeitzone; wichtige Meldungen mit `priority: urgent` umgehen die Ruhezeit, aber nicht diese Einschaltsperre. Die Warteschlange enthält höchstens zehn wartende Einträge. Wichtige Einträge werden als Nächstes abgespielt, sie unterbrechen die aktuelle Anzeige nicht.

Während der Anzeige greift die gekoppelte Standby-Automatik nicht. Bei Abbruch oder Ablauf wird der vorherige Eingang wiederhergestellt, sofern er nicht zwischenzeitlich extern geändert wurde. Eine zuvor laufende Apple-TV-Wiedergabe wird nicht rekonstruiert; für unterbrechungsarme Anzeigen ist ein separater Inhaltsplayer sinnvoll. Normales `play_media` bleibt eine ausdrückliche Wiedergabeanforderung und darf das Display einschalten.

**LG-Überblendungen sind weiterhin nicht nativ implementiert.** `show_notification` benötigt ein funktionsfähiges Anzeige-Skript, das `show` und `clear` samt Sitzungs-ID verarbeitet. Ohne dieses Skript wird die Aktion mit einer klaren Fehlermeldung abgelehnt. Die UH5C-Modell-/Firmware-spezifische Anbindung steht noch aus. Ein beliebiger Medienplayer kann außerdem nicht automatisch Webseiten/Dashboards anzeigen.

[Alle Optionen, Beispiele und die Schnittstelle für Anzeige-Skripte](FEATURES.md).
