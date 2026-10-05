# LG Professional Display 2.0

Diese Integration steuert ausschließlich das LG-Display. Für Apple TV, Sonos, Steckdose und einen gemeinsamen HomeKit-TV gibt es die separate Erweiterung [AV Companion](https://github.com/mvs90/av_companion). Beide Pakete haben eigene HACS-Repositories und Releases. Es wird eine neue Einrichtung ohne Migration vorausgesetzt.

## Installation

1. In HACS `https://github.com/mvs90/lg_rs232_ip` als benutzerdefiniertes Repository, Kategorie **Integration**, hinzufügen.
2. Herunterladen und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → LG Professional Display**.
4. Display-Adresse und Port eingeben; Standardport ist **9761**.
5. Die anschließend angezeigten Display-Einstellungen bestätigen. Für die Vorschaukamera **nativen Webzugriff** und **Screenshot-Vorschau** aktivieren sowie das Mobile-URL-Passwort eintragen. Das Fingerabdruckfeld kann zur automatischen Ermittlung leer bleiben. Erst danach folgt die Raumzuordnung.

Ab HA 2025.3; geprüft unter 2025.3.4 und 2026.9.4. Die Integration ist noch nicht im allgemeinen HACS-Katalog enthalten.

Ab **2.1.0** wird eine Fernbedienungskarte automatisch mitgeliefert: Nach HA-Neustart die Browserseite neu laden, Dashboard bearbeiten → Karte hinzufügen → **LG Display Remote**. Display und optionale Kamera im visuellen Editor wählen. [Bedienung und YAML-Beispiel](DASHBOARD-CARD.md).

## Layout-Dashboard

Ab **2.6.0** erscheint für Administratoren automatisch **LG Display Studio** in der Seitenleiste. Vier anpassbare Vorlagen, getrennte Ansichten mit/ohne HDMI sowie gestaltbare Overlay-, PiP- und Vollbildmeldungen werden mitgeliefert. HDMI, Uhr, Wetter, Kalender, Texte und HA-Zustandsfelder lassen sich frei verschieben und skalieren. Ab **2.7.0** gibt es zusätzlich **Dashboard** als eigene Quelle, Tages-/Stundenwetter mit animierten Symbolen, Sonnenstand-Farbverläufe und eigene JPEG-/PNG-Hintergründe. Jedes Widget einschließlich Meldungsfenster kann entfernt oder in einen anderen Typ geändert werden. Für dauerhafte Ansichten die optionale SI-App im Dauerbetrieb aktivieren. **[Einrichtung und Bedienung](DISPLAY-STUDIO.md)**.

## Displayfunktionen

Ein/Aus, HDMI-Eingänge, Displaylautstärke, Stummschaltung, Navigation, unterstützte Bild-/Energieeinstellungen und Statussensoren bleiben vollständig eigenständig. Erweiterte Einstellungen sind modellabhängig und teilweise standardmäßig deaktiviert. Kein Zuspieler und keine Steckdose werden von dieser Integration geschaltet.

In **Konfigurieren** den nativen Webzugriff aktivieren, wenn Inhalte oder Screenshots benötigt werden. Das separate Passwort steht am LG unter **Home → Mobile URL**. Der SHA-256-Fingerabdruck wird beim Speichern automatisch ermittelt und gespeichert, wenn das Feld leer ist. Er wird bei späteren Verbindungen weiter geprüft und niemals wegen eines Fehlers automatisch ersetzt. Optional kann ein eigener Abdruck eingetragen oder **LG-HTTPS-Zertifikat prüfen** ausdrücklich ausgeschaltet werden. Ohne Prüfung bleibt HTTPS verschlüsselt, die Identität des Displays wird jedoch nicht geprüft. Die automatische Ermittlung vertraut dem bei der Einrichtung gelieferten Zertifikat; `tools/read_web_certificate.py` bleibt für einen unabhängigen Vergleich verfügbar. Ein leeres Passwortfeld behält das gespeicherte Passwort bei.

| Aktion | Funktion |
| --- | --- |
| `lg_rs232_ip.show_toast` | Text über dem laufenden Bild; Dauer/Layout bestimmt LG |
| `lg_rs232_ip.show_native_image` | PNG/JPEG bis 5 MiB, temporär mit Rückkehr |
| `lg_rs232_ip.show_native_video` | MP4 bis 50 MiB, Upload vor Wiedergabe |
| `lg_rs232_ip.show_stream` | Direkte HTTP(S)-Video-/HLS-URL |
| `lg_rs232_ip.show_website` | Webseite über den LG-URL-Player |
| `lg_rs232_ip.clear_content` | Warteschlange abbrechen und Darstellung aufräumen |
| `lg_rs232_ip.prepare_boot_image` | 1920×1080-JPEG für USB-Import vorbereiten |
| `lg_rs232_ip.send_remote_command` | LG-Navigation |

Vollbilder werden für 1–3600 Sekunden angezeigt. Warteschlange, Ruhezeiten und Rückkehr zum vorherigen Eingang sind enthalten. Aufwecken für temporäre Inhalte ist standardmäßig aus; Toasts setzen ein eingeschaltetes Display voraus. Ein Fehler nach der Annahme steht in `presentation_error`. Externe Eingangs-/App-Wechsel haben Vorrang vor der automatischen Wiederherstellung.

Die Option **OSD bei Umschaltung unterdrücken** liest den vorherigen Zustand und stellt nur ein ursprünglich aktives OSD wieder her. Ein manuell ausgeschaltetes OSD bleibt ausgeschaltet. Am geprüften LG erfolgt die Wiederherstellung gegebenenfalls erst nach der Rückkehr zu HDMI.

**Bootlogo:** Der Schalter steuert die echte LG-Einstellung ohne Neustart. Ein eigenes Bild wird durch `prepare_boot_image` vorbereitet und muss danach über USB am LG importiert werden; ein Netzwerkimport ist nicht bestätigt.

**Vorschau:** Native Webanmeldung plus Screenshot-Vorschau aktivieren. Intervall 10–3600 Sekunden, Auflösung 360/720/1080p. Die Kamera weckt das Display nicht und verwirft veraltete Bilder bei Aufnahmefehlern. Ein flüssiger Live-Videostream ist nicht verfügbar.

Der ältere LG-Browser unterstützt nicht jede moderne Webseite. DRM, RTSP/RTMP und automatische Transkodierung sind nicht implementiert. Native LG-Audiosignale gelangen mit der dokumentierten AX310-Verkabelung nicht automatisch zu Sonos.

## Gemeinsame AV-Anlage

[AV Companion](https://github.com/mvs90/av_companion) zusätzlich installieren und darin den LG auswählen. Diese Erweiterung übernimmt die mehrstufige Standby-Erkennung und optional den Display-Stromanschluss. Bei stromlos gemeldetem Display kann nur die Erweiterung dessen Steckdose wieder einschalten; die Basis kennt keine Steckdosen-Entität.

**Apple TV → FeinTech AX310 → LG HDMI 1**, AX310 eARC → Sonos. Der AX310 bleibt dauerhaft versorgt; nur der LG hängt an der schaltbaren Steckdose. [Anschlussreferenz](devices/FEINTECH-AX310.md).

Die vollständigen Beispiele und Grenzen stehen in [FEATURES](FEATURES.md), [NATIVE-MEDIA](NATIVE-MEDIA.md) und der [Gerätereferenz 75UH5F-HJ](devices/LG-UH5F-H.md). [Prüfbericht](RELEASE-TESTS.md).

Ab **2.2.0** beschleunigt sich die Vorschau automatisch, solange die Fernbedienung sichtbar oder die Kamera-Großansicht geöffnet ist. Standard: **1 Sekunde**, anschließend wieder das normale Intervall (standardmäßig 30 Sekunden). Unter **Konfigurieren** sind beide Intervalle einstellbar; **0** beim Intervall für die geöffnete Vorschau deaktiviert die Beschleunigung. Ein Klick auf das Vorschaubild öffnet die Großansicht. Mehrere Ansichten teilen sich dieselbe Aufnahme. Das LG liefert einzelne Screenshots, deshalb entsteht kein flüssiges Video mit 25/30 Bildern pro Sekunde.

## Optionale Display-App (2.5)

Die [Display-App](DISPLAY-APP.md) wird direkt von Home Assistant bereitgestellt und automatisch für eine Anzeige als SI-App eingerichtet. Sie unterstützt Vollbildmeldungen, ausgewählte Sensoren, Einblendungen über HDMI und HDMI als Bild-in-Bild. Die Startmethode, HA-Adresse und Sensorfreigaben befinden sich in den Integrationseinstellungen. Die Fernbedienung bietet die Ansichten zur Auswahl. Bei temporären Anzeigen bleiben OSD-Unterdrückung, Warteschlange und Rückkehr zum vorherigen Eingang wirksam; vorhandene SI-Apps werden nicht überschrieben. Optional kann die SI-App dauerhaft mit Autostart laufen. HDMI bleibt zwischen Meldungen sichtbar; Overlay und PiP benötigen dann keinen App-Neustart. Textmeldungen und Vorschaukamera nutzen automatisch die verbundene App und fallen bei Ausfall auf die vorhandenen LG-Wege zurück. Für PiP bleibt eine funktionsfähige SI-App erforderlich. Das aktive Vorschauintervall ist bis 0,5 Sekunden einstellbar; die Hardware begrenzt die tatsächliche Bildrate. Die bereits geladene App zeigt HDMI auch bei HA-Ausfall weiter; beim Kaltstart muss HA erreichbar sein.

Im Dauerbetrieb wechseln HDMI-Auswahlen aus Home Assistant jetzt den Eingang **innerhalb der App**. Ein vorübergehend fehlendes HDMI-Signal beendet die App nicht. Neue normale App-Meldungen ersetzen sofort die vorherige; eine dringende Meldung bleibt vor normalen Meldungen geschützt, während nur die neueste normale Meldung wartet. Native Bild-/Video-/Website-Wiedergaben behalten ihre Warteschlange und erfordern weiterhin einen App-Wechsel.

Die App hält ein einziges HDMI-Videoelement offen. Lange HTTP-Abfragen warten auf Änderungen, unveränderte Inhalte erzeugen keine neuen DOM-Knoten, und Screenshots laufen nur auf HA-Anforderung einzeln mit anschließender Freigabe der Plattformverbindung. Die vorhandene OSD-Unterdrückung schützt auch HDMI-Wechsel innerhalb der App und erhält ein manuell ausgeschaltetes OSD.

### Medien- und Statuskarten (2.8.0)

Im **LG Display Studio** unter **Karten aus deinem Raum** einen HA-Raum wählen und passende Vorschläge einzeln übernehmen. Sonos und andere `media_player` erhalten Cover, Titel, Interpret und Wiedergabestatus; Raumzustände passende Symbole und Farben. Karten sind frei gestaltbar und über **×** entfernbar. Über **Medienplayer → +** ist auch eine manuelle Zuordnung möglich. Erst **Speichern** ändert die Anzeige. [Anleitung und Grenzen](DISPLAY-STUDIO.md#medienplayer-und-raumvorschläge).

### Gespeicherte Ansichten (2.9.0)

Das Studio startet mit einer Galerie. Über **Neue Ansicht** ein benanntes Design aus einer Vorlage anlegen; bestehende Ansichten lassen sich bearbeiten, unabhängig duplizieren und löschen. In der Übersicht die Verwendung für Dashboard, HDMI und Meldungen zuordnen und **Speichern**. Die Vorlage **Sonnenstand** ersetzt „Morgenlicht“ und aktualisiert Farben und Lichtposition auch während der laufenden Anzeige. [Ansichten verwalten](DISPLAY-STUDIO.md#ansichten-verwalten).

### Farbthemes und PiP-Quelle (2.10.0)

Im Editor links nur Farben und Hintergrund ändern; Inhalte, Entitäten und Positionen bleiben beim Theme-Wechsel erhalten. Oben direkt zwischen HDMI-Vollbild, Dashboard, PiP und Mitteilungsansichten wechseln. HDMI-Quellen erscheinen immer im Vollbild in der App; **Dashboard** und **PiP** laden ihre eigenen zugeordneten Ansichten. PiP behält den zuletzt gewählten HDMI-Eingang. Für diese Quellen im kombinierten Player AV Companion 1.2.0 verwenden.


### Seitenverhältnis und Backlight (2.10.1)

**Aspect Ratio** bietet **Full Screen** (Fläche ausfüllen) und **Original** (Proportionen beibehalten). Das gilt auch für die HDMI-Fläche in der optionalen App; PiP-Position und Größe bleiben im Studio einstellbar. Der alte Zahlenregler heißt **Aspect Ratio Code** und akzeptiert nur noch 2 oder 6.

**Backlight** ist bei Energiesparen **AUTO/MAXIMUM**, aktiver LG-Helligkeitsplanung oder ausgeschaltetem Panel gesperrt. Der Sensor **Backlight Control** zeigt den Grund. Für manuelle Regelung **Energy Saving → OFF, MINIMUM oder MEDIUM** wählen. Ein konfigurierter DPM-Timer allein verhindert die Regelung nicht; DPM und Energiesparen werden niemals automatisch umgestellt. Bildmoduswechsel können einen anderen gespeicherten Backlight-Wert laden. [Abhängigkeiten, Bedienung und Gerätetest](PICTURE-CONTROLS.md).

## Mediaplayer-Vollbild und 4K

Ab LG 2.12.0 bietet Display Studio den Aufbau und die Quelle **Mediaplayer** neben Dashboard und PiP. Medienkarte mit einer vorhandenen Sonos-/Player-Entität verbinden, Gestaltung speichern und **Mediaplayer anzeigen** wählen. Cover, Titel, Interpret, Status, Fortschritt und Widgets sind anpassbar. Hintergründe behalten bis zu 4K; Cover berücksichtigen die Pixeldichte des Displays. Details und Geräte-Grenzen: [Display Studio](DISPLAY-STUDIO.md#mediaplayer-im-vollbild).
