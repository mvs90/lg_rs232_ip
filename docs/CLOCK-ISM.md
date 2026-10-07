# Datum, Uhrzeit und ISM-Nachbildschutz

Ab v2.28 sind die erweiterten Einstellungen über den optionalen **nativen LG-Webzugang** verfügbar. Die vorhandene ISM-Modusauswahl arbeitet weiterhin über RS232/IP. Geprüft wird am 75UH5F-HJ mit Software 04.13.50; andere Modelle können einzelne Parameter ablehnen. Nicht bestätigte Werte erscheinen nicht als vermeintlich gültige Einstellungen.

## Uhrzeit

- **Display-Datum und -Uhrzeit** zeigt die am Gerät gelesene Zeit und als Attribute dessen Zeitzone und Automatikstatus. Abfrage einmal pro Minute, Genauigkeit eine Minute.
- **Datum und Uhrzeit automatisch (NTP)** schaltet die tatsächliche Netzwerkzeitsynchronisierung des LG um.
- **Datum und Uhrzeit einstellen** ist nur bei ausgeschalteter Automatik verfügbar. HA zeigt Zeitwerte in seiner eigenen Zeitzone an; beim Schreiben wird der aktuelle UTC-Versatz der Display-Uhr berücksichtigt. Sekunden werden auf Minutenpräzision reduziert. Unterstützter Eingabebereich: 2010–2099.
- **NTP-Server (leer = Standard)** akzeptiert einen Hostnamen, eine IPv4- oder IPv6-Adresse. Ein leeres Feld wählt wieder den LG-Standardserver. Keine URL, Portnummer oder Zugangsdaten eintragen. Die Serverwahl aktiviert die Uhrzeitautomatik nicht eigenständig.

Die Zeitzone und gegebenenfalls manuelle Sommerzeitregeln bleiben im LG-Menü **Allgemein → Zeit & Datum** konfigurierbar. Der Uhrsensor zeigt die Zeitzone zusätzlich an; die Integration ersetzt sie nicht stillschweigend durch die HA-Zeitzone. Ein gespeicherter NTP-Server ist keine Zusage, dass dieser Server erreichbar ist oder bereits erfolgreich synchronisiert hat.

## ISM-Einstellungen

Die zusätzlichen Entitäten passen ihre Verfügbarkeit dem gelesenen Modus an:

| Auswahl | Zusätzliche Einstellungen |
|---|---|
| Aus | Wiederholung kann für die nächste Aktivierung vorbereitet werden |
| Einmal ausführen | Keine Wartezeit-/Zeitplanparameter |
| Nach Standbild wiederholen | Wartezeit 1–24 Stunden; Dauer 1–10, 20, 30, 60, 90, 120, 180 oder 240 Minuten |
| Wochenzeitplan | Wochentage und Start-/Endzeit in der lokalen Display-Zeit |

Die sieben Schalter **ISM Montag** bis **ISM Sonntag** wählen die aktiven Zeitplantage. Start und Ende müssen verschieden sein. Der gewählte ISM-Modus muss eine auf diesem Modell verfügbare Methode sein. UH5F bietet Aus, White Wash, Benutzerbild und Benutzervideo; Orbiter ist auf diesem getesteten Modell nicht verfügbar. Ohne importierte Benutzermedien kann der LG stattdessen eine weiße Fläche zeigen. Die Auswahl einer ISM-Methode kann die aktuelle Anzeige unterbrechen; ISM ist keine App-Benachrichtigung.

Die Modusauswahl aktualisiert die abhängigen Einstellungen unmittelbar. Änderungen am Gerät werden spätestens beim nächsten gemeinsamen Abruf übernommen. Bei ausgeschaltetem Display werden die Einstellungen nicht verändert und das Display wird dafür nicht aufgeweckt. Schreibbefehle werden bei verlorener Antwort nicht blind wiederholt; ein frischer Rücklesewert entscheidet über Erfolg.

## Bilder und Videos aus Home Assistant bereitstellen

Bilder/Videos zuerst über **Medien → Meine Medien → Medien hochladen** in HA ablegen. Anschließend unter **Entwicklerwerkzeuge → Aktionen** die Aktion **LG Professional Display: Prepare ISM media for USB import** aufrufen.

```yaml
action: lg_rs232_ip.prepare_ism_media
target:
  entity_id: media_player.lg_display_display
data:
  media_type: image
  media_ids:
    - media-source://media_source/local/ism-bild.jpg
  media_directory: local
response_variable: ism_export
```

Für ein Video `media_type: video` und genau eine MP4-Datei verwenden. Die Aktion erlaubt 1–4 Bilder (JPEG/PNG/BMP, je höchstens 5 MiB und 20 Megapixel) oder ein MP4 bis 50 MiB. Bilder werden ohne Verzerrung auf eine schwarze 1920×1080-Fläche eingepasst und als JPEG ohne Quelldaten-Metadaten gespeichert. Videos werden nicht umkodiert; der MP4-Container wird geprüft, nicht die Eignung sämtlicher Codecs für das jeweilige Display.

Die fertigen Dateien liegen im HA-Medienbrowser unter:

`lg_rs232_ip / CONFIG_ENTRY_ID / ism / EXPORT_ID / ISM`

Jeder Inhalt erhält ein eigenes Exportverzeichnis. Gleicher Inhalt verwendet denselben Export erneut; ältere Exporte werden nicht gelöscht. Sie können im Medienbrowser gezielt entfernt werden. Die Rückgabe enthält für jede Datei `media_id` und `usb_path`, außerdem ausdrücklich `installed_on_display: false` und `import_method: usb`.

Dateien aus diesem Verzeichnis herunterladen, auf einem USB-Stick im Ordner **ISM direkt im Stammverzeichnis** ablegen und am LG unter **Allgemein → Sicherheitsmodus → ISM-Methode → Download Benutzerbild / Benutzervideo** importieren. LG verlangt, alte ISM-Inhalte vor einem neuen Import zu entfernen; vorhandene Inhalte vorher im LG-Player prüfen. Die Integration löscht keine Display-Inhalte und führt keinen Werksreset aus.

**Ein direkter Netzwerkimport in den ISM-Speicher ist bislang nicht bestätigt.** Der geprüfte Content-Manager-Upload stellt normale Wiedergabemedien bereit und ersetzt diesen besonderen Import nicht. Daher wird kein angeblicher ISM-Upload angeboten, der nur eine gewöhnliche Datei auf dem Display ablegt. Der USB-Import selbst erfordert einen angeschlossenen USB-Datenträger und bleibt ein Schritt am Gerät. [LG webOS-4-Anleitung, ISM S. 22–23](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA).

## Schnittstellen und Grenzen für weitere Projekte

Die native Control-Manager-Oberfläche dieses Geräts verwendet `getNTPStatus`/`setNTPStatus`, `getCurrentTime`/`setCurrentTime` und `getTimeZone`. `setNTPStatus` bestätigt auf UH5F mit einem booleschen Wert. `setCurrentTime` hat hier kein verlässliches Bestätigungsereignis; die Integration prüft anschließend die Uhr erneut. Trotz des Parameternamens `utc` übergibt die LG-Weboberfläche lokale Kalenderkomponenten.

Die geprüften kommerziellen Konfigurationsschlüssel sind `ntpServerMode`, `ntpServerType`, `ntpServerUrl`, `ntpServerIpv4`, `ntpServerIpv6`, `ismMode`, `ismTimer`, `ismPeriod`, `ismTime`, `ismStartTime`, `ismEndTime` und `ismDays`. Die erlaubten Timer-, Servertyp- und Dauerwerte wurden aus der Einstellungsbeschreibung des Displays gelesen und mit dessen Menü verglichen. ISM-Start/Ende werden als Minuten seit Mitternacht gespeichert; `ismDays` ist eine Liste aus `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`. Die Erkundungsabfrage ist nicht Teil der ausgelieferten App; es gibt weiterhin keine allgemeine, frei adressierbare Luna-Schnittstelle.

See [the 2.30 native settings guide](NATIVE-SCHEDULES-AUDIO.md) for RGB calibration, audio controls, schedule entries and timezone/DST configuration.
