# LG Display Studio

Ab **LG Professional Display 2.9.0** startet **LG Display Studio** mit einer Galerie benannter, gespeicherter Ansichten. Ansichten lassen sich aus Vorlagen anlegen, bearbeiten, duplizieren, löschen und einem oder mehreren Anzeigeanlässen zuordnen. Nach dem Update HA neu starten und die Browserseite neu laden. Kein weiteres HACS-Paket und keine manuelle Dashboard- oder Ressourcen-Konfiguration sind nötig.

Der Editor gestaltet die auf dem LG laufende App. Für dauerhafte Ansichten müssen in den LG-Einstellungen **Display-App**, **SI-App** und **SI-Dauerbetrieb mit automatischem Start** aktiviert sein. Die App bleibt optional: Ohne aktivierte eigene Layouts funktionieren ihre bisherigen Ansichten weiter. Das Öffnen/Bearbeiten des Studios installiert keine SI-App und schaltet das Display nicht ein. **Dashboard anzeigen** ist dagegen eine ausdrückliche Quellenwahl und kann das mit Strom versorgte Display wecken.

## Ansichten verwalten

1. **LG Display Studio** öffnen und das LG-Display wählen. Die Startseite zeigt die gespeicherten Ansichten mit einer verkleinerten Layoutskizze und ihrer aktuellen Verwendung. Vorhandene Layouts werden als sechs benannte Ansichten übernommen; Wetter-, Medien-, Sensor- und Bildzuordnungen bleiben erhalten.
2. **Neue Ansicht** oder eine vorgeschlagene Vorlage wählen: **Cinema**, **Aurora**, **Sonnenstand** oder **Paper & Sand**. Einen Namen und den gewünschten **Aufbau** wählen, beispielsweise Dashboard, HDMI/PiP oder Meldung. Die neue Ansicht wird zunächst als unabhängiger Entwurf angelegt.
3. **Bearbeiten** öffnet genau eine Ansicht. Name, Hintergrund, Widgets, Position, Größe, Farben und Schrift anpassen. Eine Vorlage im Editor ersetzt nur diese Ansicht; andere Ansichten bleiben erhalten. **Alle Ansichten** führt zurück zur Übersicht und erhält ungespeicherte Änderungen.
4. **Duplizieren** erstellt eine unabhängige Kopie einschließlich Widgets und Hintergrundverweis. **Löschen** entfernt eine Ansicht aus dem Entwurf. Betroffene Anzeigezuordnungen wechseln zu **Standard**; Rückgängig stellt Ansicht und Zuordnungen wieder her.
5. Unter **Wann wird welche Ansicht angezeigt?** gespeicherte Ansichten für **Mit HDMI**, **Ohne HDMI**, **Dashboard**, **Meldung · Overlay**, **Meldung · PiP** und **Meldung · Vollbild** auswählen. Eine Ansicht darf mehrfach verwendet werden; ihre Bearbeitung gilt dann für alle diese Zuordnungen. **Standard** verwendet die integrierte Cinema-Grundansicht des jeweiligen Anlasses.
6. **Speichern** speichert die gesamte Bibliothek, Zuordnungen und Einstellungen gemeinsam. Eine verbundene App übernimmt Änderungen an zugeordneten Ansichten sofort. Unzugeordnete Ansichten bleiben in der Bibliothek und werden nicht zum LG übertragen. **Anzeigen** auf einer gespeicherten Ansicht ordnet diese dem Dashboard zu, aktiviert eigene Layouts und wählt die Dashboard-Quelle. Ungespeicherte Änderungen müssen vorher gespeichert werden.

Bis zu **24 Ansichten pro Display**, jeweils 16 Widgets. Auch eine leere Bibliothek ist erlaubt. **Rückgängig/Wiederholen** umfasst Anlegen, Bearbeiten, Duplizieren, Löschen und Zuordnen. Der Verlauf gilt für die aktuelle Editorsitzung; nach einem Neuladen ist nur der gespeicherte Stand verfügbar. Eine Versionsprüfung verhindert das Überschreiben einer inzwischen in einer anderen Sitzung geänderten Bibliothek.

## Eine Ansicht gestalten

Elemente anklicken, ziehen und über die Ecke vergrößern. Position und Größe lassen sich auch in Prozent eingeben. Pfeiltasten verschieben um 1 %, Umschalt + Pfeiltaste um 0,1 %. Die Elementliste regelt die Ebenenreihenfolge. **Widget-Typ** tauscht ein Element aus und erhält seine Geometrie/Gestaltung; unpassende Entitätszuordnungen werden geleert. **×**, **Element entfernen** oder Entf/Backspace entfernen jedes Widget, auch HDMI und Meldungsfenster.

Für Wetter, Kalender und weitere Informationen passende HA-Entitäten wählen oder **Karten aus deinem Raum** verwenden. Vorlagen wählen keine privaten Entitäten automatisch. Zusätzliche Widgets über **+** ergänzen. Die Vorschau nutzt denselben Renderer und aktuelle HA-Zustände; HDMI erscheint als Platzhalter ohne zusätzlichen Screenshot-Stream. Wetterprognosen und Kalenderabfragen werden nur für gespeicherte, zugeordnete Ansichten vorbereitet. Aktuelle Zustände lassen sich bereits im Entwurf sehen. Ungespeicherte Änderungen bleiben bei HA-Updates und beim Wechsel zwischen Ansichten erhalten.

**Eigenes Layout verwenden**, HDMI-Signalmodus, Signalpause und Sonnenentität sind gemeinsame Einstellungen des Displays. Eine Änderung daran gilt für alle Ansichten. **Exportieren/Importieren** im Editor überträgt die gesamte Bibliothek und ihre Zuordnungen, maximal 1 MiB. Eigene Bilddateien zusätzlich übertragen. Importieren ändert zunächst nur den Entwurf; ältere Layout-Exporte werden als sechs Ansichten übernommen.

## Dashboard als eigene Quelle

Das Dashboard ist unabhängig von der automatischen Ansicht **Ohne HDMI**. Die Quellenwahl bleibt über einen HA-Neustart und einen normalen Display-Standby erhalten. Auch im Dashboard darf ein frei positioniertes HDMI-/PiP-Element ergänzt werden. Ohne HDMI-Element bleibt die Videoebene verborgen; eine Meldung holt das TV-Bild dann nicht ungewollt zurück. Nach einer Meldung erscheint wieder das Dashboard.

Beispielaktion für eine Morgen-Automation:

```yaml
action: media_player.select_source
target:
  entity_id: media_player.lg_display_display
data:
  source: Dashboard
```

Entity-ID anpassen. Die Quelle erscheint, wenn eigene Layouts und SI-Dauerbetrieb aktiviert sind. Ist ein physischer HDMI-Eingang schon „Dashboard“ genannt, erhält die App-Quelle einen eindeutigen Zusatz „(App)“; der aktuelle Name steht im Attribut `dashboard_source`. Die Studio-Schaltfläche berücksichtigt diesen Namen automatisch.

Die reine LG-Integration schaltet keine Steckdose und keinen Zuspieler. Ein bewusst stromlos geschaltetes Display muss zuerst über das AV-System versorgt werden. Die vorhandene AV-Companion-Schutzabfrage erkennt das ausgewählte Dashboard als aktive Anzeige und beendet es nicht wegen eines inaktiven Zuspielers. Explizites Ausschalten und die Wahl eines HDMI-Eingangs bleiben möglich. Nach bestätigtem Ausschalten darf die vorhandene Steckdosenlogik die Versorgung wieder trennen. Ab **AV Companion 1.1.0** erscheint die Quelle auch am kombinierten AV-Mediaplayer und damit in dessen HomeKit-Quellenliste. Ältere AV-Versionen schützen die Anzeige bereits vor automatischem Standby, bieten die zusätzliche Quelle aber nur über die LG-Entität an. Ein HDMI-Zuspieler wird durch die Dashboard-Wahl nicht automatisch pausiert oder ausgeschaltet.

## Vorlagen und Hintergründe

| Vorlage | Gestaltung |
|---|---|
| Cinema | HDMI im Vollbild, dunkle Informationsübersichten |
| Aurora | Grüne Lichtflächen, ruhige Karten, HDMI neben Informationen |
| Sonnenstand | Ruhige Informationsflächen; Himmel, Farben und Lichtposition folgen der Sonne |
| Paper & Sand | Helle Typografie und Karten auf sandfarbenem Hintergrund |

Jede gespeicherte Ansicht hat eigene Hintergrund-, Farb- und Widget-Einstellungen. Neben sechs festen Hintergründen gibt es **Eigener Verlauf** (Grund-/Akzentfarbe und Winkel), **Sonnenstand** und **Eigenes Bild**. Schriftart, Textgröße/-farbe, Kartengrund, Deckkraft, Rundung, Ausrichtung, Position und Ebenenreihenfolge sind frei einstellbar.

**Sonnenstand** (früher Vorlage „Morgenlicht“) nutzt standardmäßig `sun.sun`; im Editor ist eine andere `sun.*`-Entität wählbar. Sonnenhöhe, Azimut und steigende/fallende Sonne bestimmen einen ruhigen Verlauf für Nacht, Morgendämmerung, Tag und Abend. Für `sun.sun` berechnet HA die aktuelle Sonnenhöhe und den Azimut alle **30 Sekunden** anhand seiner Standort-/Zeiteinstellungen. Die laufende App und die geöffnete Studio-Vorschau aktualisieren den Verlauf ohne Neuladen. Andere ausgewählte Sonnenentitäten folgen ihren Zustandsupdates. Es gibt keine dauernde Animation oder zusätzliche Display-Screenshot-Abfrage. Fehlt die Sonnenentität, bleibt ein dunkler Hintergrund. [HA-Sonnenintegration](https://www.home-assistant.io/integrations/sun/).

**Eigene Bilder:** JPEG oder PNG bis 5 MiB und 20 Megapixel hochladen. HA entfernt Metadaten und bereitet ein JPEG mit höchstens 1920×1080 Pixeln vor; Bildverarbeitung läuft außerhalb der HA-Ereignisschleife. Im Editor Bild, Ausfüllen/Einpassen und Abdunklung wählen, dann speichern. Bis zu 24 Bilder pro Display; identische Uploads werden wiederverwendet. **Unbenutzte Bilder entfernen** bewahrt gespeicherte Szenen sowie Bilder in den aktuellen Rückgängig-/Wiederholen-Schritten. Die App lädt Bilder lokal von HA; keine externen Bild-, Schrift- oder Icon-Dienste sind erforderlich.

**Exportieren/Importieren** überträgt JSON mit Gestaltung und Entity-IDs, ohne Zugangsdaten oder aktuelle Zustände/Termine. Eigene Bilddateien sind **nicht im JSON enthalten**: auf einer anderen Installation dieselben Originalbilder zusätzlich hochladen. Fehlende Bilder verhindern das Speichern, damit kein unvollständiges Layout unbemerkt übernommen wird. Ein Import ändert nur den Entwurf. Eine Versionsprüfung verhindert stilles Überschreiben durch einen veralteten Editor.

## Wetter

Pro Wetter-Widget sind **Aktuelles Wetter**, **Tagesvorschau** oder **Stundenvorschau**, **1–8 Prognosezeiträume**, Karten-/Himmel-/transparente Gestaltung und ein animiertes aktuelles Symbol wählbar. Die Prognose zeigt Zeitpunkt, Wettersymbol, Temperatur, bei Tageswerten Tiefstwert sowie die vom Anbieter gelieferte Niederschlagswahrscheinlichkeit. Gleiche Entitäten dürfen in mehreren Widgets mit unterschiedlichen Prognosetypen erscheinen.

HA fragt nur benötigte Typen mit `weather.get_forecasts` ab. Nicht jeder Anbieter unterstützt beide Typen. Bei fehlender Prognose bleiben die aktuellen Werte mit einem entsprechenden Hinweis sichtbar; es werden keine Prognosen erfunden. [HA-Wetterprognosen](https://www.home-assistant.io/actions/weather.get_forecasts/).

Das aktuelle Symbol berücksichtigt `sun.sun`. Stundenwerte verwenden die Tag-/Nacht-Angabe des Anbieters oder eine Berechnung auf HA anhand der eingestellten Position/Zeitzone. Die Standortkoordinaten werden dabei nicht an die Display-App übertragen. Nur das große aktuelle Symbol wird dezent animiert; kleine Prognosesymbole bleiben statisch. Animationen sind abschaltbar und berücksichtigen „Bewegung reduzieren“ in unterstützenden Browsern. Auf kleinen Widgets weniger Zeiträume oder eine kleinere Schrift wählen.

## Medienplayer und Raumvorschläge

Unter **Karten aus deinem Raum** schlägt Studio passende Karten für den gewählten HA-Raum vor. Ist dem LG-Gerät oder seiner Medienplayer-Entität ein Raum zugewiesen, wird dieser automatisch gewählt. Die explizite Raumzuordnung einer Entität hat Vorrang vor der ihres Geräts. Ohne LG-Raumzuordnung einmal einen Raum wählen. Die Zuordnung erfolgt anhand der [HA-Raumverwaltung](https://www.home-assistant.io/docs/organizing/areas/), nicht anhand von Gerätenamen.

Ein Vorschlag fügt eine gestaltete Karte in die **aktuelle Ansicht** ein. Medienplayer bekommen eine Coverkarte, Wetter und Kalender ihre jeweiligen Widgets, weitere Zustände eine Statuskarte. Verborgene, deaktivierte und Diagnose-/Konfigurationsentitäten sowie das LG selbst werden ausgelassen. Bis zu 24 Vorschläge priorisieren Medien, Licht und Raumklima; andere Entitäten können weiterhin manuell gebunden werden. **Vorschläge aktualisieren** lädt Änderungen der Raumzuordnung. Vorschläge werden nicht selbständig gespeichert oder auf dem Display eingeblendet.

**Medienplayer:** Über einen Raumvorschlag oder Elementtyp **Medienplayer → +** eine Karte anlegen, dann die `media_player.*`-Entität von Sonos oder einem anderen in HA eingebundenen Player wählen. **Cover neben Text** und **Großes Cover** zeigen Titel, Interpret, Album und Wiedergabestatus. Cover, Fortschritt und Lautstärke lassen sich separat ausblenden; Akzent, Schrift, Fläche und Geometrie sind anpassbar. Fehlendes Cover erhält ein lokales Musiksymbol. Bei Aus/Standby/Nicht verfügbar verschwinden alte Titel und Cover. Fortschritt erscheint nur, wenn der Anbieter Dauer und Position liefert, und läuft während einer Pause nicht weiter. Radiosender und TV-Quellen können weniger Metadaten liefern. Die Karte zeigt Informationen; sie steuert die Wiedergabe auf dem LG nicht.

**Statuskarte:** Symbole und Zustandsfarben passen sich dem HA-Domain-/Gerätetyp an, etwa Temperatur, Luftfeuchte, Licht, Tür/Fenster, Schloss, Klima oder Rollladen. Helligkeit, Soll-/Isttemperatur und Öffnungsposition ergänzen den Hauptzustand, wenn verfügbar. Zustandsfarben lassen sich abschalten. Numerische Messwerte erhalten keine erfundenen Gut-/Schlecht-Grenzwerte.

Alle Karten lassen sich über **×** in der Elementliste oder **Element entfernen** löschen und per Rückgängig wiederherstellen. Der zugehörige Raumvorschlag wird danach wieder auswählbar. Neue Karten suchen einen freien Platz. Ist keiner groß genug, weist Studio auf die Überlappung hin; anschließend verschieben, verkleinern oder vorhandene Karten entfernen. Erst **Speichern** überträgt den Entwurf auf das LG.

**Cover und Ressourcen:** HA liest das Cover über die vorhandene Medienplayer-Integration, damit auch deren besondere Authentifizierung und Bildbeschaffung genutzt werden. Das LG erhält ausschließlich einen an diese Kopplung und gespeicherte Medienkarten gebundenen Bildabruf, keine Quell-URL, Medien-ID oder HA-Zugangsdaten. Bilder werden auf höchstens 640 × 640 Pixel verkleinert, als JPEG ohne Metadaten ausgegeben und im Arbeitsspeicher zwischengespeichert. Maximal zwei parallele Abrufe, acht Sekunden Zeitlimit, 32 Cache-Einträge/8 MiB und 30 Sekunden Wiederholungspause bei Fehlern begrenzen den Aufwand. Titelwechsel tauschen das Cover aus; unveränderte Bilder werden wiederverwendet. Fortschritt läuft lokal im vorhandenen Sekundentakt, ohne zusätzliche HA-/Sonos-Abfragen. Ob eine konkrete Integration Cover und Metadaten liefern kann, hängt von deren Unterstützung und der wiedergegebenen Quelle ab.

## Meldungsfenster

**Meldung · Overlay**, **Meldung · PiP** und **Meldung · Vollbild** gestalten Nachrichtenansichten unabhängig. Position, Größe, Farben und Schrift des Meldungsfensters sind frei einstellbar. Auch hier dürfen alle Elemente entfernt oder ergänzt werden. **Ohne Meldungsfenster ist der Nachrichtentext bewusst unsichtbar**; die Szene läuft trotzdem für die angeforderte Dauer und kehrt danach zurück.

`lg_rs232_ip.show_display_app` nutzt mit `layout: overlay`, `pip` oder `fullscreen` die passende Szene. Titel und Nachricht kommen aus der Aktion. **Meldung ausprobieren** sendet eine zehnsekündige Nachricht; vorher speichern. Schutz für dringende Meldungen, Ruhezeiten und Energiezustand bleibt wirksam.

Layoutwechsel in der laufenden App brauchen keinen physischen Eingangsbefehl. Bei einer echten App-/Eingangsumschaltung, beispielsweise nativen Videos/Websites oder App-Neustart, gilt die OSD-Unterdrückung mit Wiederherstellung des zuvor ermittelten Zustands. Sie gilt auch bei der bewussten Dashboard-/HDMI-Quellenwahl.

## Daten, Signal und Ressourcen

- **HDMI:** Ein externes Videoelement pro Szene, frei positionierbar von 2–100 %. Es bleibt bei Layoutwechseln erhalten. PiP bedeutet ein HDMI-Bild neben/unter App-Inhalten, nicht zwei HDMI-Eingänge gleichzeitig.
- **Automatische Signalerkennung:** Nutzt die vom Videoelement gemeldete Bildbereitschaft. Nach einer Pause von 0–30 Sekunden (Standard 5) erscheint **Ohne HDMI**, bei Rückkehr wieder **Mit HDMI**. Alternativ fest erzwingen. Diese automatische Ansicht allein verhindert keinen AV-Standby; nur die ausdrücklich gewählte Dashboard-Quelle gilt als aktive Anzeige.
- **Uhr:** HA-Zeitzone, minutenweise zwischengespeicherte Formatierung, keine HA-Abfrage pro Sekunde.
- **Kalender:** Bis zu sechs Termine der nächsten sieben Tage über `calendar.get_events`; sonst aktueller/nächster Termin aus Attributen. Ganztagstermine behalten ihr Datum. Listen bleiben auf die Widgetgröße begrenzt.
- **HA-Entität:** Name, Zustand und Einheit einer explizit gewählten Entität, etwa Temperatur, Luftqualität, Energie, Anwesenheit oder Türstatus. Zustandsanzeige ohne interaktive Steuerung auf dem LG, keine vollständigen Attribute oder Historien.
- **Begrenzung:** 16 Elemente pro Szene, 32 verschiedene Widget-Entity-IDs plus eine Sonnenentität. Schnelle Zustandsänderungen werden gebündelt. Kalender/Wetter alle zehn Minuten, maximal zwei parallele Abfragen mit je acht Sekunden Zeitlimit, doppelte Prognoseabfragen zusammengefasst. Fehler können bis zu eine Stunde alte, als letzter Stand markierte Daten erhalten. Nicht verfügbare Wetterentitäten verbergen ihre Prognosen.
- **Verbindungsverlust:** Meldungen enden nach 15 Sekunden ohne HA-Antwort. Das gespeicherte Dashboard mit zuletzt empfangenen Werten bleibt in der geladenen App sichtbar; diese Werte sind nicht live. Kaltstart der gehosteten App benötigt erreichbares HA.
- **Zugriff:** Editor und Bildverwaltung nur für HA-Administratoren. Die gekoppelte App liest ausgewählte Daten und gespeicherten Szenen zugeordnete Bilder, kann aber keine Layouts/Bilder bearbeiten oder beliebige HA-Aktionen ausführen. Frei ausführbares HTML/Jinja und beliebige Lovelace-Karten werden nicht unterstützt.

Die Galerie nutzt Layoutskizzen; die vollständige Live-Vorschau öffnet sich über **Bearbeiten**.

Die Darstellung ist auf **16:9 im Querformat** ausgelegt und auf LG 75UH5F-HJ / webOS 4 geprüft. Andere Plattformen können sich bei Videoebenen, Überlagerung, Schriften und Signalstatus unterscheiden. Es werden keine fremden Schriftdateien geladen. Die ressourcenschonende Umsetzung ersetzt keine Messung von LG-Gesamtspeicher oder Langzeitstabilität.

## Diagnose und Speicherung

Der Sensor **Display app** zeigt `layout_scene` (`signal`, `no_signal`, `dashboard`, `overlay`, `pip`, `fullscreen`), `layout_revision` und `dashboard_selected`. Der Fünfsekunden-Heartbeat ist eine Diagnose, keine Messung der tatsächlichen Reaktionszeit.

Bibliothek, Zuordnungen und aktive Layouts werden gemeinsam in `.storage/lg_rs232_ip.<entry_id>.layouts` gespeichert. Bilder: `.storage/lg_rs232_ip.<entry_id>.backgrounds/`. Die Quellenwahl liegt im vorhandenen App-Wiederherstellungsjournal. Vorhandene Layouts bleiben beim Update erhalten und erscheinen als sechs Ansichten. Neue Vorlagen lassen sich als zusätzliche Ansicht anlegen oder auf die gerade bearbeitete Ansicht anwenden.

Weitere Informationen: [App-Einrichtung](DISPLAY-APP.md), [Prüfergebnisse](RELEASE-TESTS.md), [Gerätereferenz](devices/LG-UH5F-H.md).
