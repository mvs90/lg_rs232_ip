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

## Sonos-Anschluss über FeinTech AX310

In der dokumentierten Installation ist ein **FeinTech AX310 HDMI 2.1 Audio Extractor für eARC-Soundbars** nötig, da das LG-Display den erforderlichen eARC-Anschluss nicht bietet:

**Apple TV → AX310 → LG HDMI 1**, zusätzlich **AX310 → eARC → Sonos**.

Der AX310 ist ein aktives HDMI-Gerät mit **dauerhafter Stromversorgung**. Die schaltbare Steckdose versorgt ausschließlich das Display. Apple TV und Sonos werden getrennt verwaltet. In dieser Installation bleibt Apple TV dank des dauerhaft versorgten AX310 im Standby, wenn das Display vom Strom getrennt wird; ohne diese Wirkung kann die Display-Stromtrennung das Apple TV aufwecken. Das ist eine Beobachtung des Besitzers und keine allgemeine Garantie für andere Anlagen.

Die Logik unterscheidet deshalb Display-Stromzustand, HDMI-Signal und Apple-TV-Zustand. Ein bestätigtes Apple-TV-Standby darf das Display auch bei vorhandenem Signal ausschalten. Umgekehrt beweist ein eingeschalteter Extractor keine laufende Wiedergabe. Bei einer falschen Idle-Meldung **und** gültigem HDMI-Signal bleibt die Lage mehrdeutig; die Integration unterstellt hier keinen Standby. Ein optionaler Leistungssensor muss allein das Display messen.

Beim Abschalten der Display-Steckdose sendet die Integration keine Einschalt- oder Ausschaltbefehle an die anderen Geräte. Eine Software-Steuerung des AX310 ist nicht implementiert. Ton nativer LG-Inhalte gelangt über diese Anordnung nicht automatisch zurück zu Sonos; Sonos-Durchsagen aus HA sind davon unabhängig. [Anschluss- und Funktionsreferenz](devices/FEINTECH-AX310.md).

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
| `lg_rs232_ip.show_toast` | Native Textmeldung über dem aktuellen LG-Bild |
| `lg_rs232_ip.show_native_image` | PNG/JPEG temporär im Vollbild mit Rückkehr zum vorherigen Eingang |
| `lg_rs232_ip.set_sound_mode` | Sonos-Nachtmodus oder Sprachverbesserung |
| `lg_rs232_ip.announce` | Audio-Durchsage auf einem unterstützten Soundsystem |

Temporäre Inhalte und Meldungen dürfen das ausgeschaltete Display standardmäßig **nicht einschalten**. Das lässt sich ausdrücklich erlauben. Ruhezeiten gelten in der Home-Assistant-Zeitzone; wichtige Meldungen mit `priority: urgent` umgehen die Ruhezeit, aber nicht diese Einschaltsperre. Die Warteschlange enthält höchstens zehn wartende Einträge. Wichtige Einträge werden als Nächstes abgespielt, sie unterbrechen die aktuelle Anzeige nicht.

Während der Anzeige greift die gekoppelte Standby-Automatik nicht. Bei Abbruch oder Ablauf wird der vorherige Eingang wiederhergestellt, sofern er nicht zwischenzeitlich extern geändert wurde. Eine zuvor laufende Apple-TV-Wiedergabe wird nicht rekonstruiert; für unterbrechungsarme Anzeigen ist ein separater Inhaltsplayer sinnvoll. Normales `play_media` bleibt eine ausdrückliche Wiedergabeanforderung und darf das Display einschalten.

**Seit v1.4 sind native Textüberblendungen und Vollbilder am 75UH5F-HJ bestätigt.** In den Integrationsoptionen den nativen Webzugriff aktivieren, das separate LG-Mobile-URL-Passwort und den SHA-256-Fingerabdruck des Display-Zertifikats eintragen. Das Passwort ist über die LG-Fernbedienung unter **Home → Mobile URL** abrufbar; ein leeres Passwortfeld behält das gespeicherte Passwort bei.

`show_toast` blendet Text über dem laufenden Bild ein. Das Display muss eingeschaltet sein; Dauer und Layout bestimmt LG. `show_native_image` lädt PNG/JPEG (maximal 5 MiB) zuerst in den internen LG-Speicher, zeigt es für die gewünschte Dauer, kehrt zum vorherigen Eingang zurück und löscht die eigene temporäre Datei. Direktes Starten einer Bild-URL führte am Testgerät zu „Wiedergabe nicht möglich“. Ruhezeiten, Warteschlange und die standardmäßig deaktivierte Aufweckoption gelten auch hier. `clear_content` beendet Vollbilder; LG-Toasts können damit nicht vorzeitig gelöscht werden.

Die Wiedergabeaktion bestätigt zunächst die Aufnahme in die Warteschlange. Fehler stehen im Attribut `presentation_error`. Bei unklarer Wiederherstellung bleibt die Datei vorsichtshalber erhalten; verwaiste Dateien mit `ha_lg_` im Content Manager nach Verlassen der Wiedergabe entfernen. Nach einem Absturz oder Netzwerkverlust ist automatische Bereinigung nicht garantiert. Ein manueller Wechsel zu einem anderen Inhalt innerhalb derselben LG-Wiedergabe-App ist nicht erkennbar.

`show_notification` bleibt für eigene Anzeige-Skripte mit `show`/`clear` und Sitzungs-ID verfügbar. Webseiten, Videos und Dashboards benötigen weiterhin einen passenden Medienplayer oder Renderer. Die native Schnittstelle ist eine interne LG-Webschnittstelle und auf anderen Firmware-/Modellversionen separat zu prüfen. [Konfiguration und Beispiele](FEATURES.md#native-lg-text-overlays-and-fullscreen-images-v14).

[Alle Optionen, Beispiele und die Schnittstelle für Anzeige-Skripte](FEATURES.md).

## Geräteprüfung und Wissensbasis

Das geprüfte Display identifiziert sich als **75UH5F-HJ**, Software **04.13.50**. Die [Gerätereferenz](devices/LG-UH5F-H.md) enthält LG-Quellen, bestätigte Abfragen, Energiezustände und die bestätigten nativen Anzeigewege. Neu sind optionale Sensoren für HDMI-Signal, tatsächlichen Bildschirmzustand und PM-Modus sowie eine DPM-Zeitauswahl. Der ältere DPM-Schalter aktiviert nun eine Minute. Es werden keine Einstellungen automatisch geändert. Firmware- und Modellsensoren sowie Bildmodus-/Sprachzuordnungen wurden korrigiert. Das bisherige, nicht dokumentierte Abnormal-State-Signal wird nicht mehr angelegt.


## OSD bei Umschaltung unterdrücken

Die Option **„OSD während Quellen-/Vollbildumschaltung unterdrücken“** ist standardmäßig aus. Aktiviert liest sie vor jeder Quellenumschaltung den aktuellen OSD-Zustand frisch vom Display. Nur ein zuvor eingeschaltetes OSD wird vorübergehend ausgeschaltet und nach einer zweisekündigen Beruhigungszeit wieder eingeschaltet. Ein schon manuell ausgeschaltetes oder nicht lesbares OSD wird nicht verändert.

Das gilt für Quellenwechsel über diese Integration sowie Start und Rückkehr nativer Vollbilder. Bei Abbruch oder fehlgeschlagener Umschaltung läuft die Wiederherstellung ebenfalls. Eine zwischenzeitliche Bedienung des OSD-Schalters in Home Assistant hat Vorrang. Schlägt die Wiederherstellung fehl, zeigt `osd_restore_error` das an. Während der Unterdrückung wirken gegebenenfalls auch andere LG-Menüs/Einblendungen nicht; native Toasts werden selbst nicht mit dieser Option unterdrückt.

Direkte Änderungen durch andere Programme oder die Fernbedienung lassen sich nicht immer von der temporären Deaktivierung unterscheiden. Netzwerk-/Stromausfall oder ein harter HA-Absturz können die Wiederherstellung verhindern; dann den OSD-Schalter gezielt prüfen. Die Option ändert keine dauerhafte Benutzerpräferenz bei normal abgeschlossener Umschaltung.

Beim geprüften UH5F-H lässt sich das OSD während der nativen Bildanzeige nicht wieder einschalten. Die Integration merkt sich deshalb ihre eigene temporäre Sperre und stellt das OSD nach der Rückkehr zu HDMI wieder her. Es kann während des gesamten Vollbilds unterdrückt bleiben. Ein bereits vorher manuell ausgeschaltetes OSD erhält diese Wiederherstellungsmarkierung nicht.


## Bootlogo und Vorschau ab Version 1.5

**Bootlogo:** Der neue Schalter „Boot logo“ schaltet das echte LG-Startlogo ein oder aus. Der Zustand wird nach dem Schreiben erneut gelesen. Das Display wird dabei weder eingeschaltet noch neu gestartet. Ausschalten und Wiederherstellen wurden am Gerät bestätigt.

**Eigenes Startbild:** Die Aktion `lg_rs232_ip.prepare_boot_image` nimmt eine Bild-URL oder eine Datei aus HA-Medien entgegen und erstellt eine passende 1920×1080-JPEG-Datei. PNG/JPEG/BMP bis 5 MiB und 20 Megapixel sind erlaubt; das Seitenverhältnis bleibt erhalten, freie Flächen werden schwarz gefüllt. Die Datei liegt danach unter „Medien → Meine Medien → lg_rs232_ip → Eintrags-ID → LG_MONITOR → bootlogo.jpg“.

Ein direkter Fernimport als Bootlogo ist bei diesem Gerät nicht bestätigt. Die vorbereitete Datei muss noch auf einen USB-Stick in den Ordner `LG_MONITOR` kopiert und am LG unter „Allgemein → Erweiterte Einstellungen → Hintergrundbild → Startlogo“ importiert werden. Die Aktion meldet ausdrücklich `installed_on_display: false`; ein normaler Content-Manager-Upload würde das Startlogo nicht ersetzen.

**Display-Vorschau:** In den Integrationsoptionen den nativen Webzugriff und die Screenshot-Vorschau aktivieren. Intervall: **10–3600 Sekunden**, standardmäßig 30; Auflösung: **360p, 720p oder 1080p**. Alle drei Auflösungen wurden mit echtem HDMI-Inhalt getestet. Die neue Kamera „Display preview“ lässt sich als Bildkarte ins Dashboard aufnehmen. Es handelt sich um regelmäßig aktualisierte Screenshots, nicht um einen flüssigen Videostream.

Die Kamera kann unabhängig vom Display ein- oder ausgeschaltet werden. Sie weckt das Display nicht; bei Aufnahmefehlern wird das alte Bild verworfen. Der Zeitstempel `last_capture` zeigt das Alter der Aufnahme. Die Vorschau speichert Bilder nur im Arbeitsspeicher. [Aktionen und Dashboard-Beispiel](FEATURES.md#boot-logo-and-custom-boot-image-v15).

## Videos, Streams und Webseiten direkt auf dem LG

Ab **1.6.0** stehen mit aktiviertem nativem LG-Webzugriff drei Aktionen bereit:

- `lg_rs232_ip.show_native_video`: MP4-Datei aus HA-Medien oder von einer URL, maximal 50 MiB. Die Datei wird vorübergehend auf das Display geladen und anschließend gelöscht.
- `lg_rs232_ip.show_stream`: direkte HTTP(S)-HLS- oder browsergeeignete Video-URL. HA stellt dafür eine kurzlebige Videoseite bereit; der LG muss HA und die Medienquelle erreichen können. Standardmäßig stummgeschaltet (`muted: true`).
- `lg_rs232_ip.show_website`: Webseite über den LG-Eingang „Play via URL“, ohne Neustart.

Mit `duration` (1–3600 Sekunden) wird die Anzeigedauer festgelegt. Danach erfolgt die Rückkehr zum vorherigen Eingang; `lg_rs232_ip.clear_content` bricht vorzeitig ab. Die bisherige URL-Loader-Einstellung wird gesichert und wiederhergestellt, sofern sie zwischenzeitlich niemand geändert hat. Eine Wiederherstellung nach einem HA-Neustart ist ebenfalls vorgesehen. Warteschlange, Ruhezeiten, Aufweckoption und OSD-Unterdrückung gelten wie für native Bilder.

```yaml
action: lg_rs232_ip.show_website
target:
  entity_id: media_player.lg_display
data:
  url: http://dashboard.example.local/display
  duration: 120
```

MP4, eine einfache Webseite und ein HLS-Teststream wurden am vorhandenen Display dargestellt. Nicht jede moderne Webseite funktioniert im älteren LG-Browser. DRM-Anbieter, RTSP/RTMP und automatische Transkodierung werden nicht unterstützt; Streams benötigen direkte Medienlinks. Die Wiedergabe endet für die Integration nach der eingestellten Dauer, nicht automatisch mit dem letzten Videobild. Native LG-Tonausgabe läuft über die bestehende AX310-Verkabelung nicht automatisch zu Sonos.

[Vollständige Anleitung mit Video-/Stream-Beispielen und Grenzen](NATIVE-MEDIA.md).
