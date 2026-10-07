# Systemeinstellungen am LG-Display

Ab Version **2.26.0** erscheinen bei eingerichtetem **nativen LG-Webzugriff** auf der HA-Geräteseite unter **Konfiguration** diese zusätzlichen Entitäten. Die residente Display-App ist dafür nicht erforderlich. Die Mobile-URL-Anmeldung und die vorhandene Zertifikatsprüfung werden wiederverwendet.

| Einstellung | Bedienung | Bedeutung |
|---|---|---|
| Intelligente Energieeinsparung | Schalter EIN/AUS | Passt die Helligkeit an den Bildinhalt an. Unabhängig vom bestehenden Auswahlfeld „Energy Saving“. |
| Signage-Name | Text, 1–32 UTF-16-Zeichen | Ändert den tatsächlichen LG-Signage-/Netzwerknamen. HA-Gerätename, Entitäts-IDs und Studio-Ansichten bleiben erhalten. |
| ID festlegen (Set ID) | Ganzzahl 1–1000 | Ändert die RS232-Steueradresse des Displays. Die Integration übernimmt und speichert die bestätigte Adresse. |
| Einschaltverzögerung | 0–250 Sekunden | Verzögert das Einschalten am Gerät. Die zuletzt bestätigte Verzögerung wird zum HA-Startzeitlimit addiert und über HA-Neustarts behalten. |
| Kein-Signal-Bild | Schalter EIN/AUS | Steuert das native LG-Bild bei fehlendem Eingangssignal. Unabhängig von der Abschaltung bei fehlendem Signal und von Studio-Widgets. |
| Temperatureinheit am Display | Celsius / Fahrenheit | Ändert die LG-Anzeigeeinheit. Home Assistant behält seine eigene Sensoreinheit. |

Die Entitätsnamen können je nach HA-Sprache oder bereits vergebenen Namen abweichen. Alle Einstellungen sind über die normalen HA-Aktionen `switch.turn_on/off`, `text.set_value`, `number.set_value` und `select.select_option` automatisierbar. Die Änderungen wecken das Display nicht; zum Schreiben muss es eingeschaltet und erreichbar sein.

## Verifikation und Ressourcen

Alle sechs Entitäten teilen sich eine Abfrage pro Minute. Pro Abfrage werden nur die vier benötigten kommerziellen Werte, die tatsächliche Set ID und der tatsächliche Signage-Name gelesen. Es gibt keinen zusätzlichen App-Timer, Videodecoder oder Screenshot-Abruf. Bei abgeschalteter Stromversorgung oder bestätigtem Standby erfolgt kein Webabruf. Ein explizites `homeassistant.update_entity` aktualisiert die Gruppe bei Bedarf.

Schreibvorgänge werden nicht automatisch wiederholt. Anschließend liest die Integration den tatsächlichen Wert erneut; eine verlorene Antwort kann dadurch trotzdem bestätigt werden. Bei Ablehnung, unbekannten Werten oder fehlendem Zugang wird kein Erfolg vorgetäuscht. Nicht unterstützte Felder sind nicht verfügbar; ein fehlender Set-ID-/Namens-Endpunkt sperrt nicht die übrigen Einstellungen.

## Set ID und Wiederanlauf

Beim Ändern der ID sind RS232-Abfragen gesperrt, bis die neue Adresse gelesen wurde. Bereits gecachte Antworten werden verworfen. Die bestätigte Adresse liegt im HA-Speicher und wird beim nächsten Laden vor der ersten RS232-Verbindung verwendet. Eine am LG-Menü geänderte ID wird beim nächsten erfolgreichen Webabruf erkannt. Bei unterbrochenem Webzugriff kann diese Erkennung erst nach dessen Wiederkehr erfolgen.

Für eine neue Integration lässt sich die bereits am Display konfigurierte **Set ID** im ersten Einrichtungsfenster angeben; Standard ist 1. Dieses Eingabefeld ändert beim Einrichten keine Geräteadresse. Adresse 0 (Broadcast) wird nicht angeboten. Mehrere Geräte in einer RS232-Kette benötigen unterschiedliche IDs; die Integration führt keine automatische Neunummerierung durch.

Die getestete UH5F-Firmware koppelt die ID an die Einschaltverzögerung: Nach dem Wechsel auf ID 1000 wurden **249 Sekunden** zurückgelesen. Die Integration zeigt diese Folgeänderung sofort an und berücksichtigt sie beim Start. Bei Bedarf danach die Einschaltverzögerung separat auf den gewünschten Wert setzen. Dieses Verhalten wird nicht für andere Modelle vorausgesetzt.

## Helligkeit und weitere Menüpunkte

Intelligente Energieeinsparung ist bildabhängig. Die vorhandene Helligkeitsregelung „Energy Saving“ mit OFF/MINIMUM/MEDIUM/MAXIMUM/AUTO bleibt davon getrennt. Die bereits geprüften Backlight-Sperren für AUTO/MAXIMUM, Helligkeitszeitplan und ausgeschaltetes Panel gelten weiter. DPM ist eine Standby-Regelung. Intelligente Energieeinsparung allein wird nicht als pauschale Backlight-Sperre behandelt. Siehe [Bildsteuerung](PICTURE-CONTROLS.md).

Zusätzlich geprüft wurden die Systeminformationen und die ID-Menüstruktur. Modell, Seriennummer, Firmware, Laufzeit und Temperatur sind bereits als Diagnoseentitäten vorhanden. Speicher-/Plattformdiagnose gibt es bei verbundener residenter App. **Auto Set ID**, ID-Reset und eine automatische Neunummerierung von RS232-Ketten sind keine Einzelgeräte-Schalter; dafür wird keine ungeprüfte Funktion angeboten. Netzwerkzugang, Kennwörter, Firmware-Update und Werkseinstellungen werden durch diese Erweiterung nicht verändert.

## Quellen und Firmwaregrenzen

- [LG webOS 4.0 User Guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA), Seiten 15 (Systeminformationen/Set ID), 17 (Einschaltverzögerung), 34 (intelligente Energieeinsparung).
- Die authentifizierte Control-Manager-Oberfläche des **75UH5F-HJ**, Software **04.13.50**, bestätigt die separaten `getSignageName`/`setSignageName`-Schnittstellen, 32 Zeichen Namenslänge und `getSetID`.
- Die tatsächliche Steueradresse liegt unter `option.setId` (Ganzzahl). `commercial.signageSetId` und `commercial.signageName` sind **keine verlässlichen Rücklesewerte** der aktiven Adresse bzw. des Namens. Das Hardware-Rücklesen hat diese Unterscheidung bestätigt; diese Nebenwerte werden von der Integration nicht geändert.
- `commercial.smartEnergy`, `powerOnDelay`, `noSignalImage` und `temperatureUnit` wurden einzeln geändert, zurückgelesen und wiederhergestellt. Das ist eine Firmware-bezogene Bestätigung, keine Zusage für alle LG-Serien und keine Messung der eingesparten Energie.
