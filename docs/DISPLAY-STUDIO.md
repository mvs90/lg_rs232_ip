# LG Display Studio

Ab **LG Professional Display 2.6.0** erscheint für Administratoren automatisch **LG Display Studio** in der Home-Assistant-Seitenleiste. Nach dem Update HA neu starten und die Browserseite neu laden. Kein weiteres HACS-Paket und keine manuelle Dashboard- oder Ressourcen-Konfiguration sind nötig.

Der Editor gestaltet die auf dem LG laufende App. Für dauerhafte Ansichten müssen in den LG-Einstellungen **Display-App**, **SI-App** und **SI-Dauerbetrieb mit automatischem Start** aktiviert sein. Die App bleibt optional: Ohne aktivierte eigene Layouts funktionieren ihre bisherigen Ansichten weiter. Das Studio schaltet weder das Display ein noch installiert es ungefragt eine SI-App.

## In wenigen Schritten

1. **LG Display Studio** öffnen und oben das gewünschte LG-Display wählen.
2. Eine Vorlage auswählen: **Cinema**, **Aurora**, **Morgenlicht** oder **Paper & Sand**. Jede Vorlage enthält alle fünf Ansichten; Auswahl und Änderungen sind zunächst nur ein Entwurf.
3. **Mit HDMI** und **Ohne HDMI** einzeln gestalten. Unter **Ansicht auf dem Display** automatische Signalerkennung oder eine dauerhaft erzwungene Ansicht wählen. So lässt sich das Dashboard auch bei vorhandenem HDMI-Signal ohne Videofenster anzeigen.
4. Elemente anklicken, verschieben und über die Ecke vergrößern. Rechts sind Position und Größe auch in Prozent einstellbar. Pfeiltasten verschieben um 1 %, Umschalt + Pfeiltaste um 0,1 %. Die Elementliste regelt die Ebenenreihenfolge.
5. Für Wetter, Kalender und weitere Informationen die passende **Home-Assistant-Entität** auswählen. Vorlagen wählen keine privaten Entitäten automatisch aus. Zusätzliche Texte, Uhren, Kalender, Wetter- und Zustandsfelder über **+** hinzufügen.
6. **Eigenes Layout verwenden** einschalten und **Speichern & anwenden** drücken. Eine verbundene App übernimmt die Änderung ohne erneuten App-Start oder HDMI-Eingangsbefehl. Rückgängig/Wiederholen betrifft den lokalen Entwurf; nach einer Rücknahme erneut speichern, wenn auch das Display zurückgesetzt werden soll.

Die Vorschau zeigt dieselbe Darstellung wie die App und aktuelle HA-Zustände. HDMI wird im Editor als Platzhalter angezeigt, damit kein zusätzlicher Screenshot-Stream nötig ist. Forecasts und kommende Termine erscheinen nach dem Speichern und der HA-Abfrage; der Editor holt deren Cache alle 30 Sekunden ab. Nicht gespeicherte Änderungen bleiben bei normalen HA-Zustandsupdates erhalten. Vor einem Verlassen/Neuladen des Editors den Entwurf speichern oder exportieren.

## Vorlagen und Hintergründe

| Vorlage | Mit HDMI | Ohne HDMI |
|---|---|---|
| Cinema | HDMI im Vollbild | Dunkle Übersicht mit Uhr, Wetter, Terminen und Raumklima |
| Aurora | HDMI neben Uhr, Wetter und Kalender | Grüne Lichtflächen und ruhige Informationskarten |
| Morgenlicht | HDMI mit warmer Informationsleiste | Warme Farbverläufe für eine Morgenübersicht |
| Paper & Sand | Helle Flächen mit HDMI-Fenster | Helle Typografie auf sandfarbenem Hintergrund |

Jede Szene lässt sich unabhängig anpassen: sechs Hintergründe (einschließlich Ozean und einfarbig), Grund-/Akzentfarbe, Schriftart, Textgröße/-farbe, Kartengrund, Deckkraft, Rundung und Ausrichtung. Hintergründe werden als lokale CSS-Farbverläufe erzeugt; es gibt keine externen Bilddownloads oder Videoschleifen. Eigene Hintergrundbilder, frei ausführbares HTML/Jinja und beliebige Lovelace-Karten sind in dieser Version nicht vorgesehen.

**Exportieren/Importieren** überträgt eine JSON-Vorlage zwischen Installationen. Ein Export enthält die Gestaltung und ausgewählte Entity-IDs, keine HA-Zugangsdaten, LG-Passwörter, aktuellen Zustände oder Kalendertermine. Importierte Entitäten müssen in der Zielinstallation vorhanden sein. Ein Import verändert zunächst nur den Entwurf. Gleichzeitige Bearbeitung wird über eine Versionsprüfung abgesichert: Ein älterer Editor darf eine neuere Speicherung nicht still überschreiben.

## Meldungsfenster

Die Tabs **Meldung · Overlay**, **Meldung · PiP** und **Meldung · Vollbild** gestalten die drei Nachrichtenansichten unabhängig. Position, Größe, Farben, Schrift und Hintergrund des Meldungsfensters sind frei einstellbar. Auch HDMI und zusätzliche Informationsfelder lassen sich dort verschieben, entfernen oder ergänzen. Das eigentliche Meldungsfenster bleibt als Pflichtbestandteil erhalten.

Die Aktion `lg_rs232_ip.show_display_app` verwendet mit `layout: overlay`, `pip` oder `fullscreen` die entsprechende gespeicherte Ansicht. Titel und Nachricht kommen weiterhin aus der Aktion. Nach Ablauf oder Abbruch erscheint die aktuelle Daueransicht wieder. **Meldung ausprobieren** sendet eine zehnsekündige Nachricht an das ausgewählte Display; vorher speichern. Der vorhandene Schutz für dringende Meldungen, Ruhezeiten und den Energiezustand bleibt wirksam.

Ein Layoutwechsel innerhalb der laufenden App braucht keinen Eingangsbefehl. Wo ein echter App-/Eingangswechsel nötig ist, etwa bei nativen Videos/Websites oder einem App-Neustart, gilt weiterhin die OSD-Unterdrückung mit Wiederherstellung des zuvor ermittelten Zustands.

## Daten, Signal und Ressourcen

- **HDMI:** Ein externes Videoelement pro Szene; frei positionierbar von 2–100 % des Bildschirms. Es bleibt bei Layoutwechseln erhalten. Ohne HDMI-Element wird die Videoebene verborgen. PiP bedeutet ein HDMI-Bild neben/unter App-Inhalten, nicht zwei HDMI-Eingänge gleichzeitig.
- **Signalerkennung:** Die App nutzt die vom Videoelement gemeldete Bildbereitschaft. Nach der einstellbaren Signalpause (0–30 Sekunden, Standard 5) erscheint die Ansicht ohne HDMI. Ein zurückkehrendes Signal zeigt wieder die HDMI-Ansicht. Auf Firmware mit unzuverlässiger Video-Signalmeldung kann die gewünschte Ansicht fest eingestellt werden. Das schaltet das Display nicht in Standby; AV Companion behält seine eigene Standby-/Steckdosenlogik.
- **Uhr:** Uhrzeit und Datum verwenden die Zeitzone von HA. Formatierungen werden minutenweise zwischengespeichert; die Uhr braucht keine HA-Abfrage pro Sekunde.
- **Wetter:** Aktueller Zustand, Temperatur und Feuchte sowie bis zu vier tägliche Vorhersagen über `weather.get_forecasts`. Ohne Unterstützung dieser Aktion bleiben die aktuellen Werte sichtbar.
- **Kalender:** Bis zu sechs Termine aus den nächsten sieben Tagen über `calendar.get_events`; ohne unterstützte Aktion wird der aktuelle/nächste Termin aus den Kalenderattributen verwendet. Ganztagstermine behalten ihr Datum. Lange Listen werden innerhalb des Elements abgeschnitten; Größe und Schrift an den Inhalt anpassen.
- **HA-Entität:** Name, Zustand und Einheit einer explizit gewählten Entität, etwa Temperatur, Luftqualität, Energie, Anwesenheit oder Türstatus. Zustandsanzeige ohne interaktive Steuerung auf dem LG. Keine vollständigen Attribute oder Historien werden übertragen.
- **Begrenzung:** 16 Elemente pro Szene, insgesamt 32 verschiedene Entity-IDs. HA bündelt schnelle Zustandsänderungen; Kalender/Wetter werden alle zehn Minuten mit höchstens zwei parallelen Abfragen und jeweils acht Sekunden Zeitlimit aktualisiert. Fehler können bis zu eine Stunde alte, als letzter Stand markierte Daten erhalten; danach gilt der Attribut-Fallback.
- **Verbindungsverlust:** Eine laufende Meldung endet nach 15 Sekunden ohne erfolgreiche HA-Antwort. Das gespeicherte Dashboard mit seinen zuletzt empfangenen Werten bleibt wie HDMI in der geladenen App sichtbar; diese Werte sind dann nicht live. Ein Kaltstart der gehosteten App benötigt erreichbares HA.
- **Zugriff:** Der Editor und seine API sind nur für HA-Administratoren zugänglich. Die gekoppelte LG-App kann nur die dafür ausgewählten Daten lesen und begrenzte Status-/Bildantworten senden; sie kann keine Layouts bearbeiten oder beliebige HA-Aktionen ausführen.

Die aktuelle Gestaltung ist auf **16:9 im Querformat** ausgelegt. Getestet auf LG 75UH5F-HJ / webOS 4; andere Plattformen können sich bei nativen Videoebenen, Überlagerung und Signalstatus unterscheiden. Kleine Unterschiede durch verfügbare Systemschriften sind möglich. Es werden keine fremden Schriftdateien geladen.

## Diagnose

Der Sensor **Display app** zeigt `layout_scene` (signal, no_signal, overlay, pip, fullscreen) und `layout_revision` aus dem letzten App-Heartbeat. Die Rückmeldung folgt innerhalb des üblichen Fünfsekunden-Heartbeat-Intervalls; sie ist keine Messung der tatsächlichen Reaktionszeit einer Nachricht. Bei getrennter Verbindung sind diese Attribute leer. Einstellungen liegen getrennt von den Zugangsdaten in HA unter `.storage/lg_rs232_ip.<entry_id>.layouts`.

Weitere Informationen: [App-Einrichtung](DISPLAY-APP.md), [Prüfergebnisse](RELEASE-TESTS.md), [Gerätereferenz](devices/LG-UH5F-H.md).
