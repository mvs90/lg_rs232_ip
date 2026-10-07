# Energie-, Standby- und Aufweckeinstellungen

Ab **2.27.0** stehen diese Einstellungen auf der LG-Geräteseite in Home Assistant unter **Konfiguration** bereit. Sie verwenden die dokumentierte RS232/IP-Schnittstelle; Web-Anmeldung und residente App sind nicht erforderlich. Es werden nur bestätigte Gerätewerte angezeigt. Nicht unterstützte Einstellungen bleiben nicht verfügbar.

| Entität | Bedeutung | LG-Befehl |
|---|---|---|
| Auto Sleep No Signal | Abschalten nach 15 Minuten ohne Eingangssignal | `fg`, Aus `00`, Ein `01` |
| Auto Sleep No IR | Abschalten nach 4 Stunden ohne IR-Fernbedienungsbedienung | `mn`, Aus `00`, Ein `01` |
| PM-Modus | Verhalten beim Ausschalten bzw. Energiesparzustand; siehe unten | `sn 0c`, `00`–`05` |
| Einschaltstatus (nach Netzversorgung) | Verhalten nach Wiederkehr der Netzversorgung: letzter Zustand / Standby / Einschalten | `tr`, LST `00`, STD `01`, PWR `02` |
| Wake on LAN (LAN) | Aufwecken über kabelgebundenes Netzwerk am LG zulassen | `fw`, Aus `00`, Ein `01` |
| Wake on LAN (WLAN) | Entsprechende LG-Einstellung für WLAN; abhängig von Modell und WLAN-Anbindung | `sn 90`, Aus `00`, Ein `01` |
| DPM Wake Up-Steuerung | Aufwachen durch HDMI-/DVI-Takt oder durch Takt **und** Daten | `sn 0b`, Clock `00`, Clock + DATA `01` |

**Auto Sleep No Signal** ersetzt nur den bisherigen Anzeigenamen „Auto Sleep“. Die Unique-ID mit Suffix `_auto_sleep` und bereits registrierte Entitäts-IDs bleiben erhalten. Der WLAN-Schalter ist standardmäßig deaktiviert und kann bei Bedarf in den Entitätseinstellungen aktiviert werden.

No IR misst die fehlende Bedienung mit der IR-Fernbedienung, nicht fehlenden Bildinhalt. Eine laufende Wiedergabe oder HA-Bedienung ist keine Zusage, dass dieser Timer zurückgesetzt wird. Die beiden Abschaltungen sind getrennt von der bestehenden DPM-Verzögerung und vom Schalter „Kein-Signal-Bild“.

## PM-Modus und Einschalten über das Netzwerk

| PM-Auswahl | Funktion laut LG |
|---|---|
| Ausschalten | Normaler Ausschaltzustand |
| Seitenverhältnis beibehalten (EDID) | Hält EDID auch bei ausgeschaltetem Gerät bereit |
| Bildschirm aus | Schaltet bei DPM und automatischen Abschaltungen die Bildanzeige ab |
| Bildschirm immer aus | Nutzt den Bildschirm-aus-Zustand zusätzlich bei Timer und Ein-/Ausschalttasten |
| Bildschirm aus, Hintergrundbeleuchtung an | Hält einen Teil der Hintergrundbeleuchtung zur Temperaturhaltung aktiv; modellabhängig |
| Netzwerkbereit (Network Ready) | Hält Netzwerkfunktionen zur Steuerung der Stromversorgung bereit |

Für den bestehenden Einschaltweg über IP ist **Network Ready mit aktiviertem LAN-WoL** die vorgesehene Konfiguration. Andere PM-Modi können nach dem Ausschalten die Einschalttaste am Gerät oder eine IR-Fernbedienung erfordern. Die Integration behauptet nicht, dass jeder andere Modus auf jedem Modell zwingend sämtliche Aufweckwege verhindert.

Der Diagnosesensor **Netzwerk-Einschalten** zeigt die zuletzt bestätigte Konfiguration. Bei einem anderen PM-Modus oder deaktiviertem LAN-WoL erscheint zusätzlich ein **Reparaturhinweis in Home Assistant**. Er verschwindet automatisch, sobald Network Ready und LAN-WoL wieder bestätigt sind. Unvollständige Abfragen gelten nicht als erfolgreicher Nachweis der Aufweckbarkeit. Die Integration ändert keine Einstellung automatisch.

Der WoL-Schalter ist eine **Geräteeinstellung**, keine „Magic Packet senden“-Aktion. Das normale Einschalten dieser Integration verwendet weiterhin den vorhandenen IP-Einschaltbefehl. Wer außerhalb von Network Ready ein Magic Packet benötigt, muss diesen gesonderten Aufweckweg bereitstellen und am eigenen Gerät prüfen. Ohne Netzversorgung kann das Display über keinen dieser Netzwerkwege aufwachen.

**Einschaltstatus** beschreibt ausschließlich den Zustand nach Rückkehr der Netzversorgung. Er schaltet das aktuell laufende Display nicht unmittelbar ein oder aus und ersetzt weder PM-Modus noch WoL.

## DPM und HDMI-Audio-Extractor

**Clock** reagiert bereits auf das digitale Taktsignal; **Clock + DATA** verlangt zusätzlich Daten. Beide Einstellungen wirken zusammen mit der bestehenden **DPM Delay**-Auswahl. Bei ausgeschaltetem DPM ist die Auswahl gespeichert, aktiviert DPM aber nicht selbstständig.

In einer Kette mit einem dauerhaft versorgten HDMI-Audio-Extractor wie dem **FeinTech AX310** kann weiterhin ein HDMI-Signal oder Takt anliegen, obwohl Apple TV im Standby ist. Clock + DATA ist deshalb kein verlässlicher Ersatz für die mehrstufige Standby-Erkennung des AV Companion. Auch No Signal greift nur, wenn das Display tatsächlich kein Eingangssignal erkennt. Die Integration lässt die gewählte DPM-Einstellung unverändert.

## Automationen und Bestätigung

Die Einstellungen verwenden die normalen Aktionen `switch.turn_on`, `switch.turn_off` und `select.select_option`. Die tatsächlichen Entitäts-IDs finden sich auf der Geräteseite. Für Automationen gelten sprachunabhängige Auswahlwerte:

- PM: `power_off`, `sustain_aspect_ratio`, `screen_off`, `screen_off_always`, `screen_off_backlight`, `network_ready`.
- Einschaltstatus: `last_status`, `standby`, `power_on`.
- DPM Wake Up: `clock`, `clock_and_data`.

Die Gruppe wird gemeinsam einmal pro Minute gelesen. Während bestätigtem Standby oder ausgeschalteter Stromversorgung erfolgen keine Konfigurationsabfragen. Änderungen benötigen ein eingeschaltetes, erreichbar bestätigtes Display und teilen die vorhandene Steuerverbindung und Befehlssperre. Es entsteht kein zusätzlicher App-Timer, Screenshot-Abruf oder Videodecoder.

Fehlende Antworten bei der Prüfung vor einer Änderung werden höchstens dreimal abgefragt; ein bestätigtes Aus schließt Schreiben sofort aus. Nach jeder Änderung wird frisch zurückgelesen, höchstens dreimal mit kurzen Abständen. Ein verlorenes ACK führt nicht zum erneuten Senden des Schreibbefehls. Bleibt die Bestätigung aus, meldet HA einen Fehler und zeigt den tatsächlich gelesenen Zustand bzw. Nichtverfügbarkeit. PM-Änderungen verwerfen den Cache für abhängige Bild-/Backlight-Einstellungen.

## Quellen und Nachweisgrenzen

[LG webOS 4.0 User Guide](https://gscs-b2c.lge.com/open/downloadFile?fileId=c1dJJrQEObZ7aWsYE0hHA), gedruckte Seiten 16–17, 79, 85–86, 89 und 93: Menüfunktionen und Befehle. Modellabhängige Unterstützung muss durch echte Antworten bestätigt werden. Der Hardwaretest und seine Grenzen sind in [RELEASE-TESTS.md](RELEASE-TESTS.md) festgehalten.
