# LG Display Studio

Ab **LG Professional Display 2.16.0 / App 1.13.0** beginnt das Studio mit **Nur HDMI**, den weiteren festen Ansichten und eigenen Ansichten. Die drei Mitteilungen stehen in einer eigenen Sektion darunter. Nach dem Update Home Assistant neu starten und die Browserseite neu laden. Das Studio erscheint automatisch in der Seitenleiste; kein weiteres HACS-Paket ist nötig.

Die App bleibt optional. Für dauerhafte Quellen müssen **Display-App**, **SI-App**, **SI-Dauerbetrieb mit automatischem Start** und **Eigenes Layout verwenden** aktiv sein. Das Öffnen und Bearbeiten installiert keine SI-App und weckt das Display nicht. **Anzeigen** ist eine ausdrückliche Quellenwahl und kann das mit Strom versorgte Display wecken.

## Ansichten verwalten

| Feste Ansicht | Verwendung |
|---|---|
| Nur HDMI | Gemeinsame, bearbeitbare Gestaltung für HDMI 1, 2 und 3; Standard ist Vollbild |
| Dashboard | Dauerhafte Quelle, beispielsweise für Wetter und Tagesübersicht |
| Dashboard PiP | Dauerhafte Quelle mit dem zuletzt gewählten HDMI-Eingang |
| Mediaplayer | Dauerhafte Quelle mit Cover und Medieninformationen |
| Mitteilung | Zeitlich begrenzte Überblendung |
| Mitteilung PiP | Zeitlich begrenzte Mitteilung mit HDMI-Fenster |
| Mitteilung Vollbild | Zeitlich begrenzte Vollbildmitteilung |

Diese sieben Ansichten lassen sich gestalten und duplizieren. Namen und Vorhandensein sind fest: Umbenennen und Löschen sind gesperrt, auch in der API. **Standard wiederherstellen** setzt ausschließlich die gewählte Ansicht auf ihre Cinema-Grundgestaltung zurück, einschließlich Widgets, Hintergründen und Entitätsbindungen. Die Schaltfläche steht in der Übersicht und im Editor. Erst **Speichern** übernimmt die Änderung; **Rückgängig** holt den vorherigen Entwurf zurück.

**Neue Ansicht** oder eine Vorlage (**Cinema**, **Aurora**, **Sonnenstand**, **Paper & Sand**) legt eine unabhängige Ansicht an. Name und Aufbau wählen, Inhalte gestalten und speichern: Sie erscheint automatisch als eigene Quelle am LG-Mediaplayer und in der Fernbedienung. Eine weitere Zuordnung entfällt vollständig. Auch Kopien fester Ansichten sind eigene Quellen. Eigene Ansichten lassen sich umbenennen, duplizieren und löschen; ihre interne Kennung bleibt beim Umbenennen erhalten. Beim Löschen einer gerade angezeigten Ansicht wechselt das Display zum Dashboard. Die festen Mitteilungsansichten bleiben zeitlich begrenzte Aktionen; sie sind keine dauerhaften Quellen.

**Bearbeiten** öffnet genau eine Ansicht. Links stehen Farbthemes und Hintergründe, rechts Widgets und Inhalte. Ein Theme verändert ausschließlich Farben und Hintergrund; Entitäten, Texte, Positionen, Größen und Reihenfolge bleiben erhalten. **Alle Ansichten** erhält offene Entwürfe. **Speichern** übernimmt die gesamte Bibliothek gemeinsam. Die App aktualisiert gespeicherte Änderungen ohne Quellenwechsel. **Anzeigen** verwendet stets die gespeicherte Quelle; offene Entwürfe werden dabei nicht automatisch gespeichert. In der Galerie müssen offene Änderungen zuerst gespeichert werden.

Es gibt **sieben feste und bis zu 24 eigene Ansichten**, jeweils mit höchstens 16 Widgets. Über alle verwendbaren Ansichten gilt weiterhin die gemeinsame Grenze von 32 Entitäten. **Rückgängig/Wiederholen** umfasst Gestaltung, Anlegen, Duplizieren, Löschen und Zurücksetzen innerhalb der Editorsitzung. Versionsprüfungen verhindern, dass ein alter Editor neuere Änderungen überschreibt.

Beim Update von 2.14 wird ausschließlich die neue Standardansicht **Nur HDMI** ergänzt; sämtliche vorhandenen Ansichten bleiben erhalten. Bei älteren Versionen werden bestehende Zuordnungen einmalig in die entsprechenden festen Ansichten übernommen. Mehrfach verwendete Designs werden unabhängig kopiert. Übrige eigene und frühere Ohne-HDMI-Ansichten bleiben als eigene Quellen erhalten und können gelöscht werden. Inhalte, Entitäten und Hintergründe werden dabei bewahrt. Das Format wird erst beim nächsten Speichern dauerhaft umgestellt. Die bisherige Quelle **PiP** heißt jetzt **Dashboard PiP**; vorhandene Automationen mit einem fest eingetragenen Quellennamen entsprechend anpassen.

## Eine Ansicht gestalten

Die Buttons oben öffnen direkt **Nur HDMI**, **Dashboard**, **Dashboard PiP**, **Mediaplayer**, **Mitteilung**, **Mitteilung PiP** und **Mitteilung Vollbild**. Dabei bleiben Entwürfe erhalten und die tatsächliche Displayquelle unverändert. **Nur HDMI** lässt sich wie die anderen Ansichten gestalten: Video positionieren und skalieren, Hintergrund ändern oder Widgets ergänzen und entfernen. **Standard wiederherstellen** setzt sie auf ein bildfüllendes HDMI-Element zurück. Sie ist die gemeinsame Vorlage für die bestehenden HDMI-Quellen und fügt keine zusätzliche Quelle hinzu. Links Farben/Hintergrund anpassen, rechts Widgets und Inhalte bearbeiten. Raumvorschläge und Ausgabebuttons stehen im mittleren Bereich.

Elemente anklicken, ziehen und über die Ecke vergrößern. Position und Größe lassen sich auch in Prozent eingeben. Pfeiltasten verschieben um 1 %, Umschalt + Pfeiltaste um 0,1 %. Die Elementliste regelt die Ebenenreihenfolge. **Widget-Typ** tauscht ein Element aus und erhält seine Geometrie/Gestaltung; unpassende Entitätszuordnungen werden geleert. **×**, **Element entfernen** oder Entf/Backspace entfernen jedes Widget, auch HDMI und Meldungsfenster.

Für Wetter, Kalender und weitere Informationen passende HA-Entitäten wählen oder **Karten aus deinem Raum** verwenden. Vorlagen wählen keine privaten Entitäten automatisch. Zusätzliche Widgets über **+** ergänzen. Die Vorschau nutzt denselben Renderer und aktuelle HA-Zustände; HDMI erscheint als Platzhalter ohne zusätzlichen Screenshot-Stream. Wetterprognosen und Kalenderabfragen werden nur für gespeicherte Ansichten vorbereitet. Aktuelle Zustände lassen sich bereits im Entwurf sehen. Ungespeicherte Änderungen bleiben bei HA-Updates und beim Wechsel zwischen Ansichten erhalten.

**Eigenes Layout verwenden** und Sonnenentität sind gemeinsame Einstellungen des Displays. Eine Änderung daran gilt für alle Ansichten. **Exportieren/Importieren** im Editor überträgt die gesamte Bibliothek und ihre Einstellungen, maximal 1 MiB. Eigene Bilddateien zusätzlich übertragen. Importieren ändert zunächst nur den Entwurf; ältere Layout-Exporte werden als sechs Ansichten übernommen.

## Ansichten als Quellen

### Animiert zwischen Vollbild und PiP wechseln

Neben **Anzeigen** wählst du im Dropdown **Direkt** oder **Animiert**. Im Editor steht dieselbe Auswahl bei den Ausgabebuttons. Sie gilt für die folgenden Anzeigen-Klicks im geöffneten Studio und verändert keine gespeicherte Ansicht. Beim nächsten Laden ist wieder **Direkt** ausgewählt.

**Animiert** bewegt und skaliert das aktuelle HDMI-Bild in 0,7 Sekunden auf die gespeicherte Position und Größe der Zielansicht. Das funktioniert in beide Richtungen zwischen **Nur HDMI**, **Dashboard PiP** und eigenen Ansichten mit HDMI-Element. Derselbe HDMI-Eingang und die verbundene SI-App sind Voraussetzung. Die übrigen Elemente der Zielansicht erscheinen direkt. Enthält eine Ansicht kein HDMI, ist der Eingang neu oder wird dieselbe Geometrie gewählt, erfolgt ein direkter Wechsel. Eine vom Browser gemeldete Einstellung für reduzierte Bewegung wird berücksichtigt.

Die App verwendet weiter denselben HDMI-Decoder. Sie bewegt ausschließlich dessen Rechteck mit maximal 30 Geometrieänderungen pro Sekunde, ohne Screenshot-Schleife oder zusätzliche Videokopie. Wiederholte Zustandsabfragen starten die Animation nicht erneut. Neue direkte Zielgeometrien und Ansichten ohne HDMI brechen eine laufende Bewegung ab. Die OSD-Unterdrückung bleibt bis zur Bestätigung der Endposition aktiv; der bisherige OSD-Zustand wird anschließend wiederhergestellt.

Für Automationen ist dieselbe Funktion verfügbar; `view` ist die stabile Ansichts-ID (bei eigenen Ansichten im Export):

```yaml
action: lg_rs232_ip.show_view
target:
  entity_id: media_player.lg_display_display
data:
  view: pip_view
  transition: smooth
```

Mit `view: hdmi_full` geht es zum aktuellen HDMI-Eingang zurück; `transition: none` schaltet direkt. Ungespeicherte Entwürfe werden dabei nicht übernommen.


**Anzeigen** auf der Karte **Nur HDMI** und **Nur HDMI anzeigen** im Editor zeigen den aktuell gewählten HDMI-Eingang in dieser gespeicherten Ansicht. Das funktioniert auch, während Dashboard, Dashboard PiP, Mediaplayer oder eine eigene Ansicht läuft. Der Eingang wird beim Klick frisch von Home Assistant abgefragt; umbenannte und in der Quellenliste ausgeblendete Eingänge werden berücksichtigt. Ist noch kein Eingang bekannt, fordert das Studio zur Auswahl in der Fernbedienung auf. Ungespeicherte Layoutänderungen bleiben im Entwurf.

**HDMI 1/2/3** zeigt das gewählte Videosignal in der gespeicherten Ansicht **Nur HDMI**, auch ohne Signal. Standardmäßig füllt das Video die Fläche aus. **Dashboard**, **Dashboard PiP**, **Mediaplayer** und alle eigenen Ansichten laden ihre jeweilige gespeicherte Gestaltung. HDMI-Elemente verwenden den zuletzt gewählten Eingang. Fehlt ein HDMI-Element, bleibt die Videoebene auch während einer Mitteilung verborgen. Nach einer Mitteilung kehrt die App zur gewählten Quelle zurück. Quellen bleiben über HA-Neustart und normalen Standby erhalten. Auch die Auswahl desselben HDMI-Eingangs kehrt zu **Nur HDMI** zurück. Alle Wechsel verwenden die vorhandene OSD-Unterdrückung mit Wiederherstellung des vorherigen Zustands.

Beispielaktion für eine Morgen-Automation:

```yaml
action: media_player.select_source
target:
  entity_id: media_player.lg_display_display
data:
  source: Dashboard
```

Entity-ID und Quellenname anpassen, beispielsweise `source: Dashboard PiP` oder den Namen einer eigenen Ansicht. Bei Kollisionen mit HDMI-Namen oder anderen Ansichten wird „(App)“ ergänzt. Das Attribut `view_sources` ordnet stabile Ansichtskennungen den tatsächlich verfügbaren Quellennamen zu. `selected_view` zeigt die aktive Kennung. Studio und Fernbedienung berücksichtigen die Namen automatisch.

**AV Companion 1.4.0** übernimmt mit LG 2.14 alle diese Quellen in den kombinierten Player und dessen HomeKit-Quellenliste. Auswahl und Umbenennung folgen derselben stabilen Kennung. Ein bewusst stromloses Display wird nur durch das AV-System versorgt; die reine LG-Integration schaltet keine Steckdose. Eine gewählte Ansicht bleibt vor automatischem Standby wegen eines inaktiven Zuspielers geschützt. Explizites Ausschalten und HDMI-Auswahl bleiben möglich. Die Auswahl einer Ansicht startet oder pausiert keinen Zuspieler. Ältere AV-Versionen stellen eigene zusätzliche Ansichten nicht als Quellen bereit.

## Mediaplayer im Vollbild

Ab **LG 2.12.0 / App 1.9.0** gibt es die eigenständige Quelle **Mediaplayer** neben Dashboard und Dashboard PiP. Im Studio oben **Mediaplayer** öffnen oder beim Anlegen einer Ansicht den Aufbau **Mediaplayer** wählen. Die Grundansicht zeigt ein großes quadratisches Cover, Titel, Interpret, Album, Fortschritt und eine Uhr. Die Medienkarte auswählen und rechts ihre **Home-Assistant-Entität** setzen, beispielsweise den Sonos im gewünschten Raum. Es wird die vorhandene HA-Medienintegration genutzt; ein weiterer Sonos-Zugang ist nicht erforderlich.

Unter **Mediengestaltung** stehen **Vollbild · Cover & Titel**, **Cover neben Text** und **Großes Cover** zur Wahl. Cover, Fortschritt und Lautstärke lassen sich einzeln ausblenden. Position, Größe, Schriften, Farben und sämtliche Widgets bleiben frei änderbar und entfernbar. Die linke Hintergrundauswahl einschließlich Cover und Randfarben funktioniert unabhängig von der Medienkarte. Die feste Ansicht speichern und **Mediaplayer anzeigen** wählen. Eine zusätzlich angelegte Medienansicht erhält ihren eigenen Quellennamen. Die Quelle lässt sich auch per `media_player.select_source` mit `source: Mediaplayer` aufrufen; bei einer Namenskollision steht der tatsächliche Name im Attribut `media_view_source`.

Ab **LG 2.13.0 / App 1.10.0** verwendet die neue Vollbildvorlage **Nur Coverfarben · ohne Bild**. Links den Hintergrund-Medienplayer auswählen und **Bei Wiedergabe anzeigen** aktivieren: Der Hintergrund übernimmt die Coverfarben, ohne das Cover nochmals groß einzublenden. Bestehende gespeicherte Darstellungsmodi bleiben erhalten und können dort umgestellt werden.

Alle Medienkarten verzichten auf Statuswörter wie „Wiedergabe“, „Pausiert“ oder „Bereit“. Rechts in der ausgewählten Medienkarte lässt sich **Play-/Pause-Symbol anzeigen** einschalten: **▶** kennzeichnet laufende Wiedergabe, **⏸** eine Pause. Das Symbol steht links neben der Zeitleiste und ist eine Zustandsanzeige, keine Steuertaste. Es benötigt aktivierten Fortschritt sowie Dauer und Position vom Player; bei TV-/Radioquellen ohne Zeitdaten, Leerlauf oder Puffern erscheint es nicht. Neue Vollbildvorlagen aktivieren die Option; neue normale Karten und bestehende Karten ohne diese Einstellung lassen sie ausgeschaltet.

Die ausgewählte Quelle bleibt über Standby/Neustart erhalten. Benachrichtigungen kehren anschließend zur Musikansicht zurück. Die Standardansicht enthält kein HDMI-Element; HDMI bleibt auch während einer Meldung verborgen. Die HDMI-Quelle kehrt zur gespeicherten **Nur HDMI**-Ansicht zurück. Quellenwechsel verwenden die bestehende OSD-Unterdrückung und stellen einen zuvor manuell deaktivierten OSD nicht an. Die Musikansicht zeigt den Zustand des Players an; ihre Auswahl startet oder pausiert dessen Wiedergabe nicht.

**AV Companion 1.3.0** bietet Mediaplayer ebenfalls am kombinierten Player und in dessen HomeKit-Quellenliste an, wenn LG 2.12 verfügbar ist. Die aktive Musikansicht ist vor dem automatischen Standby wegen eines inaktiven HDMI-Zuspielers geschützt. Ältere LG-Versionen bleiben mit AV Companion kompatibel; die zusätzliche Quelle fehlt dort.

## Auflösung und 4K

Texte, SVG-Symbole und Layoutgeometrie skalieren mit dem Webrenderer. Cover werden anhand ihrer tatsächlichen Anzeigefläche **und Pixeldichte** in Stufen von **640, 1280 oder 2160 Pixeln** bereitgestellt. Kleine Karten laden kleinere Varianten. Ein Titel benötigt nur einen Abruf bei der Medienintegration; HA erzeugt die Varianten außerhalb der Ereignisschleife. Der gemeinsame Cache ist auf 32 Player und insgesamt 32 MiB JPEG-Daten begrenzt; gleichzeitig laufen höchstens zwei Abrufe. Kleinere Originalcover werden nicht künstlich hochgerechnet.

Eigene Hintergründe behalten bis zu **3840×2160 Pixel**. Farbflächen werden als CSS-Verläufe gezeichnet, ein dezentes statisches 64×64-Dithering mindert sichtbare Abstufungen. Es gibt keinen zusätzlichen Animationsloop, großflächigen Blurfilter oder permanenten Screenshot zur Darstellung. Vor dem Update bereits auf Full HD verkleinerte Hintergrundbilder bei Bedarf aus dem Original erneut hochladen.

Am **75UH5F-HJ / webOS 4.0.1-136** meldet die laufende SI-App **1920×1080 CSS-Pixel und `devicePixelRatio: 2`**. Das entspricht einem Zielraster von 3840×2160 für die Auswahl der Bildressourcen. Die Diagnose **Display app → rendering** zeigt die tatsächlichen Werte jedes Geräts. Diese Messung bestätigt weder eine bestimmte interne GPU-Pufferauflösung noch 10-Bit-Farbverarbeitung. Die native Screenshot-API liefert weiterhin höchstens 1920×1080. Die Qualität eines Covers hängt zusätzlich vom Medienanbieter ab: Der reale Wohnzimmer-Sonos lieferte im AirPlay-Test nur 512×512 Pixel, auch bei einer angeforderten größeren Variante.

## Vorlagen und Hintergründe

| Vorlage | Gestaltung |
|---|---|
| Cinema | HDMI im Vollbild, dunkle Informationsübersichten |
| Aurora | Grüne Lichtflächen, ruhige Karten, HDMI neben Informationen |
| Sonnenstand | Ruhige Informationsflächen; Himmel, Farben und Lichtposition folgen der Sonne |
| Paper & Sand | Helle Typografie und Karten auf sandfarbenem Hintergrund |

Jede gespeicherte Ansicht hat eigene Hintergrund-, Farb- und Widget-Einstellungen. Neben sechs festen Hintergründen gibt es **Eigener Verlauf** (Grund-/Akzentfarbe und Winkel), **Sonnenstand** und **Eigenes Bild**. Schriftart, Textgröße/-farbe, Kartengrund, Deckkraft, Rundung, Ausrichtung, Position und Ebenenreihenfolge sind frei einstellbar.

**Sonnenstand** (früher Vorlage „Morgenlicht“) nutzt standardmäßig `sun.sun`; im Editor ist eine andere `sun.*`-Entität wählbar. Sonnenhöhe, Azimut und steigende/fallende Sonne bestimmen einen ruhigen Verlauf für Nacht, Morgendämmerung, Tag und Abend. Für `sun.sun` berechnet HA die aktuelle Sonnenhöhe und den Azimut alle **30 Sekunden** anhand seiner Standort-/Zeiteinstellungen. Die laufende App und die geöffnete Studio-Vorschau aktualisieren den Verlauf ohne Neuladen. Andere ausgewählte Sonnenentitäten folgen ihren Zustandsupdates. Es gibt keine dauernde Animation oder zusätzliche Display-Screenshot-Abfrage. Fehlt die Sonnenentität, bleibt ein dunkler Hintergrund. [HA-Sonnenintegration](https://www.home-assistant.io/integrations/sun/).

**Eigene Bilder:** JPEG oder PNG bis 5 MiB und 20 Megapixel hochladen. HA entfernt Metadaten und bereitet ein JPEG mit höchstens 3840×2160 Pixeln vor; Bildverarbeitung läuft außerhalb der HA-Ereignisschleife. Im Editor Bild, Ausfüllen/Einpassen und Abdunklung wählen, dann speichern. Bis zu 24 Bilder pro Display; identische Uploads werden wiederverwendet. **Unbenutzte Bilder entfernen** bewahrt gespeicherte Szenen sowie Bilder in den aktuellen Rückgängig-/Wiederholen-Schritten. Die App lädt Bilder lokal von HA; keine externen Bild-, Schrift- oder Icon-Dienste sind erforderlich.

**Exportieren/Importieren** überträgt JSON mit Gestaltung und Entity-IDs, ohne Zugangsdaten oder aktuelle Zustände/Termine. Eigene Bilddateien sind **nicht im JSON enthalten**: auf einer anderen Installation dieselben Originalbilder zusätzlich hochladen. Fehlende Bilder verhindern das Speichern, damit kein unvollständiges Layout unbemerkt übernommen wird. Ein Import ändert nur den Entwurf. Eine Versionsprüfung verhindert stilles Überschreiben durch einen veralteten Editor.

## Coverfarben und Cover als Hintergrund

Ab **2.11.0** kann jede gespeicherte Ansicht den Hintergrund während der Wiedergabe durch das Cover eines frei wählbaren `media_player.*` ersetzen. Im Editor links oben unter **Coverfarben & Hintergrund** den **Hintergrund-Medienplayer** auswählen, **Bei Wiedergabe anzeigen** aktivieren und speichern. Eine Medienkarte ist dafür nicht erforderlich; ihre Player-Zuordnung bleibt unabhängig. Sonos und andere Player nutzen ihre bereits in HA eingebundene Medienintegration.

| Darstellung | Verhalten |
| --- | --- |
| **Nur Coverfarben · ohne Bild** | Ab 2.13: Zeigt ausschließlich den aus den Coverrändern gebildeten Farbverlauf. Das Cover der Medienkarte bleibt einmal sichtbar. Voreinstellung für neue Mediaplayer-Vollbildansichten. |
| **Gestreckt · ganze Fläche** | Füllt den Bildschirm vollständig; das Cover darf dabei verzerrt werden. |
| **Skaliert · vollständig einpassen** | Vergrößert oder verkleinert proportional, ohne das Cover abzuschneiden. Freie Flächen zeigen den Randverlauf. |
| **Mittig · ohne Vergrößern** | Zentriert das von HA bereitgestellte Cover in seiner Größe innerhalb der 1920×1080-Entwurfsfläche. Vorschau und Display behalten dieselben Proportionen; die auf höchstens 640×640 begrenzte Coverdatei wird nicht weiter vergrößert. |

**Cover und Randverlauf abdunkeln** verbessert die Lesbarkeit darüberliegender Karten (0–90 %, Standard 35 %). Der Verlauf entsteht aus den tatsächlichen linken, rechten, oberen und unteren Coverrändern und ändert sich bei einem neuen Titel/Cover ohne Neuladen. Widgets und HDMI/PiP bleiben darüber. Die feste HDMI-Vollbildquelle wird dadurch nicht in eine andere Ansicht umgeschaltet.

Die Einblendung gilt ausschließlich für den HA-Zustand **`playing`** mit verfügbarem Cover. Bei Pause, Stopp/Leerlauf, Aus/Standby, nicht verfügbarem Player, fehlendem Cover oder Ladefehler bleibt der normale Hintergrund der Ansicht sichtbar: Farbtheme, Sonnenstand, Verlauf oder eigenes Bild. Bei erneutem Start kommt das aktuelle Cover zurück. Ein Themewechsel erhält Player, Aktivierung, Darstellungsmodus und Abdunklung; Duplizieren, Export/Import und Rückgängig umfassen diese Einstellungen. Standardmäßig ist die Funktion ausgeschaltet.

Es gibt keine neue Abfragefrequenz: HA-Zustandsereignisse melden Wiedergabe-/Titelwechsel, der vorhandene Covercache teilt Bildabrufe zwischen Karte, Hintergrund und Studio. Die App analysiert ein neues Cover einmal anhand einer **32×32-Pixel-Probe**. Unveränderte Cover und reine Größen-/Abdunklungsänderungen benötigen keine erneute Farbanalyse. Der Modus **Nur Coverfarben** decodiert hierfür nur die Variante mit höchstens 640 Pixeln, auch auf einem 4K-Bildschirm; die sichtbare Coverkarte darf unabhängig eine größere Variante nutzen. Keine dauernden Canvas-/Blur-Effekte, kein HDMI-Neuladen und keine Bildschirmaufnahmen. Verspätete Antworten eines vorherigen Titels oder einer inzwischen geschlossenen Ansicht können kein altes Cover zurückbringen. Bei Bildfehlern gilt eine Wiederholungspause von mindestens 30 Sekunden.

## Wetter

Pro Wetter-Widget sind **Aktuelles Wetter**, **Tagesvorschau** oder **Stundenvorschau**, **1–8 Prognosezeiträume**, Karten-/Himmel-/transparente Gestaltung und ein animiertes aktuelles Symbol wählbar. Die Prognose zeigt Zeitpunkt, Wettersymbol, Temperatur, bei Tageswerten Tiefstwert sowie die vom Anbieter gelieferte Niederschlagswahrscheinlichkeit. Gleiche Entitäten dürfen in mehreren Widgets mit unterschiedlichen Prognosetypen erscheinen.

HA fragt nur benötigte Typen mit `weather.get_forecasts` ab. Nicht jeder Anbieter unterstützt beide Typen. Bei fehlender Prognose bleiben die aktuellen Werte mit einem entsprechenden Hinweis sichtbar; es werden keine Prognosen erfunden. [HA-Wetterprognosen](https://www.home-assistant.io/actions/weather.get_forecasts/).

Das aktuelle Symbol berücksichtigt `sun.sun`. Stundenwerte verwenden die Tag-/Nacht-Angabe des Anbieters oder eine Berechnung auf HA anhand der eingestellten Position/Zeitzone. Die Standortkoordinaten werden dabei nicht an die Display-App übertragen. Nur das große aktuelle Symbol wird dezent animiert; kleine Prognosesymbole bleiben statisch. Animationen sind abschaltbar und berücksichtigen „Bewegung reduzieren“ in unterstützenden Browsern. Auf kleinen Widgets weniger Zeiträume oder eine kleinere Schrift wählen.

## Medienplayer und Raumvorschläge

Unter **Karten aus deinem Raum** schlägt Studio passende Karten für den gewählten HA-Raum vor. Ist dem LG-Gerät oder seiner Medienplayer-Entität ein Raum zugewiesen, wird dieser automatisch gewählt. Die explizite Raumzuordnung einer Entität hat Vorrang vor der ihres Geräts. Ohne LG-Raumzuordnung einmal einen Raum wählen. Die Zuordnung erfolgt anhand der [HA-Raumverwaltung](https://www.home-assistant.io/docs/organizing/areas/), nicht anhand von Gerätenamen.

Ein Vorschlag fügt eine gestaltete Karte in die **aktuelle Ansicht** ein. Medienplayer bekommen eine Coverkarte, Wetter und Kalender ihre jeweiligen Widgets, weitere Zustände eine Statuskarte. Verborgene, deaktivierte und Diagnose-/Konfigurationsentitäten sowie das LG selbst werden ausgelassen. Bis zu 24 Vorschläge priorisieren Medien, Licht und Raumklima; andere Entitäten können weiterhin manuell gebunden werden. **Vorschläge aktualisieren** lädt Änderungen der Raumzuordnung. Vorschläge werden nicht selbständig gespeichert oder auf dem Display eingeblendet.

**Medienplayer:** Über einen Raumvorschlag oder Elementtyp **Medienplayer → +** eine Karte anlegen, dann die `media_player.*`-Entität von Sonos oder einem anderen in HA eingebundenen Player wählen. **Cover neben Text** und **Großes Cover** zeigen Titel, Interpret und Album. Cover, Fortschritt und Lautstärke lassen sich separat ausblenden; Akzent, Schrift, Fläche und Geometrie sind anpassbar. Fehlendes Cover erhält ein lokales Musiksymbol. Bei Aus/Standby/Nicht verfügbar verschwinden alte Titel und Cover. Fortschritt erscheint nur, wenn der Anbieter Dauer und Position liefert, und läuft während einer Pause nicht weiter. Radiosender und TV-Quellen können weniger Metadaten liefern. Die Karte zeigt Informationen; sie steuert die Wiedergabe auf dem LG nicht.

**Statuskarte:** Symbole und Zustandsfarben passen sich dem HA-Domain-/Gerätetyp an, etwa Temperatur, Luftfeuchte, Licht, Tür/Fenster, Schloss, Klima oder Rollladen. Helligkeit, Soll-/Isttemperatur und Öffnungsposition ergänzen den Hauptzustand, wenn verfügbar. Zustandsfarben lassen sich abschalten. Numerische Messwerte erhalten keine erfundenen Gut-/Schlecht-Grenzwerte.

Alle Karten lassen sich über **×** in der Elementliste oder **Element entfernen** löschen und per Rückgängig wiederherstellen. Der zugehörige Raumvorschlag wird danach wieder auswählbar. Neue Karten suchen einen freien Platz. Ist keiner groß genug, weist Studio auf die Überlappung hin; anschließend verschieben, verkleinern oder vorhandene Karten entfernen. Erst **Speichern** überträgt den Entwurf auf das LG.

**Cover und Ressourcen:** HA liest das Cover über die vorhandene Medienplayer-Integration, damit auch deren besondere Authentifizierung und Bildbeschaffung genutzt werden. Das LG erhält ausschließlich einen an diese Kopplung und aktive gespeicherte Medienkarten oder Cover-Hintergründe gebundenen Bildabruf, keine Quell-URL, Medien-ID oder HA-Zugangsdaten. Bilder werden passend zur Anzeigefläche auf höchstens 640, 1280 oder 2160 Pixel verkleinert, als JPEG ohne Metadaten ausgegeben und im Arbeitsspeicher zwischengespeichert. Maximal zwei parallele Abrufe, acht Sekunden Zeitlimit, 32 Cache-Einträge/32 MiB und 30 Sekunden Wiederholungspause bei Fehlern begrenzen den Aufwand. Titelwechsel tauschen das Cover aus; unveränderte Bilder werden wiederverwendet. Fortschritt läuft lokal im vorhandenen Sekundentakt, ohne zusätzliche HA-/Sonos-Abfragen. Ob eine konkrete Integration Cover und Metadaten liefern kann, hängt von deren Unterstützung und der wiedergegebenen Quelle ab.

## Meldungsfenster

**Mitteilung**, **Mitteilung PiP** und **Mitteilung Vollbild** gestalten Nachrichtenansichten unabhängig. Position, Größe, Farben und Schrift des Meldungsfensters sind frei einstellbar. Auch hier dürfen alle Elemente entfernt oder ergänzt werden. **Ohne Meldungsfenster ist der Nachrichtentext bewusst unsichtbar**; die Szene läuft trotzdem für die angeforderte Dauer und kehrt danach zurück.

`lg_rs232_ip.show_display_app` nutzt mit `layout: overlay`, `pip` oder `fullscreen` die passende Szene. Titel und Nachricht kommen aus der Aktion. **Meldung ausprobieren** sendet eine zehnsekündige Nachricht; vorher speichern. Schutz für dringende Meldungen, Ruhezeiten und Energiezustand bleibt wirksam.

Layoutwechsel in der laufenden App brauchen keinen physischen Eingangsbefehl. Bei einer echten App-/Eingangsumschaltung, beispielsweise nativen Videos/Websites oder App-Neustart, gilt die OSD-Unterdrückung mit Wiederherstellung des zuvor ermittelten Zustands. Sie gilt auch bei der bewussten Dashboard-/HDMI-Quellenwahl.

## Daten, Signal und Ressourcen

- **HDMI:** Ein externes Videoelement pro Szene, frei positionierbar von 2–100 %. Es bleibt bei Layoutwechseln erhalten. PiP bedeutet ein HDMI-Bild neben/unter App-Inhalten, nicht zwei HDMI-Eingänge gleichzeitig.
- **Signalstatus:** Die Bildbereitschaft bleibt für die Diagnose verfügbar. HDMI verwendet unabhängig davon die **Nur HDMI**-Ansicht; Dashboard, Dashboard PiP, Mediaplayer und eigene Quellen werden ausdrücklich gewählt. Alle gelten als aktive Anzeige für den AV-Standbyschutz. Die bisherigen Signalmodus-/Verzögerungsfelder werden nur für alte Exporte erhalten und steuern keine automatischen Layoutwechsel mehr.
- **Uhr:** HA-Zeitzone, minutenweise zwischengespeicherte Formatierung, keine HA-Abfrage pro Sekunde.
- **Kalender:** Bis zu sechs Termine der nächsten sieben Tage über `calendar.get_events`; sonst aktueller/nächster Termin aus Attributen. Ganztagstermine behalten ihr Datum. Listen bleiben auf die Widgetgröße begrenzt.
- **HA-Entität:** Name, Zustand und Einheit einer explizit gewählten Entität, etwa Temperatur, Luftqualität, Energie, Anwesenheit oder Türstatus. Zustandsanzeige ohne interaktive Steuerung auf dem LG, keine vollständigen Attribute oder Historien.
- **Begrenzung:** 16 Elemente pro Szene, 32 verschiedene Entity-IDs für Widgets und aktivierte Cover-Hintergründe plus eine Sonnenentität. Schnelle Zustandsänderungen werden gebündelt. Kalender/Wetter alle zehn Minuten, maximal zwei parallele Abfragen mit je acht Sekunden Zeitlimit, doppelte Prognoseabfragen zusammengefasst. Fehler können bis zu eine Stunde alte, als letzter Stand markierte Daten erhalten. Nicht verfügbare Wetterentitäten verbergen ihre Prognosen.
- **Verbindungsverlust:** Meldungen enden nach 15 Sekunden ohne HA-Antwort. Das gespeicherte Dashboard mit zuletzt empfangenen Werten bleibt in der geladenen App sichtbar; diese Werte sind nicht live. Kaltstart der gehosteten App benötigt erreichbares HA.
- **Zugriff:** Editor und Bildverwaltung nur für HA-Administratoren. Die gekoppelte App liest ausgewählte Daten und gespeicherten Szenen zugeordnete Bilder, kann aber keine Layouts/Bilder bearbeiten oder beliebige HA-Aktionen ausführen. Frei ausführbares HTML/Jinja und beliebige Lovelace-Karten werden nicht unterstützt.

Die Galerie nutzt Layoutskizzen; die vollständige Live-Vorschau öffnet sich über **Bearbeiten**.

Die Darstellung ist auf **16:9 im Querformat** ausgelegt und auf LG 75UH5F-HJ / webOS 4 geprüft. Andere Plattformen können sich bei Videoebenen, Überlagerung, Schriften und Signalstatus unterscheiden. Es werden keine fremden Schriftdateien geladen. Die ressourcenschonende Umsetzung ersetzt keine Messung von LG-Gesamtspeicher oder Langzeitstabilität.

## Diagnose und Speicherung

Der Sensor **Display app** zeigt `layout_scene` (`signal` für HDMI-Vollbild, `dashboard`, `pip_view`, `overlay`, `pip`, `fullscreen`), `layout_revision`, `dashboard_selected` und `pip_selected`. Der Fünfsekunden-Heartbeat ist eine Diagnose, keine Messung der tatsächlichen Reaktionszeit.

Bibliothek, Zuordnungen und aktive Layouts werden gemeinsam in `.storage/lg_rs232_ip.<entry_id>.layouts` gespeichert. Bilder: `.storage/lg_rs232_ip.<entry_id>.backgrounds/`. Die Quellenwahl liegt im vorhandenen App-Wiederherstellungsjournal. Vorhandene Ansichten bleiben beim Update erhalten. Neue vollständige Vorlagen werden als zusätzliche Ansicht angelegt; im Editor werden nur Farbthemes übernommen.

Weitere Informationen: [App-Einrichtung](DISPLAY-APP.md), [Prüfergebnisse](RELEASE-TESTS.md), [Gerätereferenz](devices/LG-UH5F-H.md).
