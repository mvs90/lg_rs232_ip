# LG Display Remote / Fernbedienungskarte

From **2.1.0**, the integration includes its own dashboard card. It is served locally and loaded automatically by Home Assistant, in both storage and YAML dashboard mode. No additional HACS frontend repository, external library or manual resource registration is required.

## Einrichtung

1. Integration aktualisieren und Home Assistant neu starten.
2. Die Home-Assistant-Seite vollständig neu laden; in der Companion-App die Ansicht gegebenenfalls schließen und erneut öffnen.
3. Dashboard bearbeiten → **Karte hinzufügen** → nach **LG Display Remote** suchen.
4. Das LG-Display auswählen. Titel, sichtbare Bereiche und optionale Vorschaukamera im visuellen Editor einstellen.
5. Speichern. Die Karte kann mehrfach für verschiedene Displays verwendet werden.

Die Karte steuert das **LG-Display selbst**. Home und die Richtungstasten öffnen/bedienen LG-Menüs; die Lautstärke gehört zum Display. Für einen verbundenen Apple TV, Sonos oder eine Steckdose bleibt AV Companion zuständig. Dessen kombinierte Entität wird in dieser Karte nicht angeboten.

Enthalten sind Ein/Aus, benannte HDMI-Eingänge, Steuerkreuz mit OK, Zurück, Home, Menü, Beenden, Lautstärke und Stummschaltung. Während einer temporären Präsentation erscheint **Zum Eingang zurück**. Bei aktiviertem nativen LG-Webzugriff kann **Text einblenden** aufgeklappt werden. Das nutzt die bestehenden Regeln für Benachrichtigungen und keine zusätzliche Anmeldung.

Die Vorschaukamera ist optional. Zuerst in den Integrationseinstellungen nativen Webzugriff und Screenshot-Vorschau aktivieren, dann die Kamera in der Karte auswählen. Die Karte zeigt die vorhandenen periodischen Aufnahmen und deren Zeitstempel. Sie erhöht die Abfragefrequenz nicht und blendet das Bild bei Standby oder einem Aufnahmefehler aus. Das Intervall bleibt eine Einstellung der Integration.

Unbekannte/nicht erreichbare Geräte und laufende Befehle sperren die Tasten. Bei Standby ist Einschalten möglich; Navigation und Lautstärke wecken das Display nicht. Fehler werden auf der Karte angezeigt. Tastatur: Tab navigiert zwischen den Bedienelementen; die Pfeiltasten funktionieren, wenn eine Taste des Steuerkreuzes oder der Navigationsleiste fokussiert ist. Die Beschriftung folgt der HA-Sprache (Deutsch/Englisch), die Farben dem HA-Theme.

## YAML

Die Entitätsnamen durch die eigenen ersetzen; `camera_entity` kann entfallen:

```yaml
type: custom:lg-display-remote
entity: media_player.lg_display_display
name: LG Fernbedienung
camera_entity: camera.lg_display_display_preview
show_sources: true
show_volume: true
show_preview: true
show_message: true
```

`entity` ist erforderlich. Alle vier `show_…`-Optionen sind standardmäßig `true`; Textmeldungen werden zusätzlich nur mit aktiviertem Webzugriff angeboten. Ohne `name` verwendet die Karte den Namen der Display-Entität. Die Kamera wird beim Anlegen vorgeschlagen, sofern HA sie demselben Gerät zuordnet; sie kann auch manuell gewählt werden.

## English quick start

Update the integration, restart HA and reload the frontend. Edit a dashboard, choose **Add card → LG Display Remote**, select an LG display and optionally its preview camera, then save. The visual editor also exposes the title and visibility options shown above. Controls operate the LG itself; AV Companion entities are intentionally outside this card's scope. From 2.2, a visible preview opens the shared screenshot stream and automatically activates the faster capture interval (default 1 second). Click it to open the enlarged view. Hidden/offscreen cards close their stream; once all viewers close, collection returns to the normal interval. Configure both intervals in the LG integration settings. This remains a screenshot preview, not full-motion video.

## Troubleshooting and development

If the card picker does not list the card, fully reload the page after HA restarts and check that the LG integration is loaded. The integration registers `/lg_rs232_ip/lg-display-remote.js?v=2.2.0` as a frontend module. Do not add a second resource entry for it. The card bundle has no credentials and calls the existing authenticated HA entity services.

Home/Menu/Back/Exit use the LG webOS 4.0 guide's documented IR codes `7c`/`43`/`28`/`5b` (pages 67–68; [LG reference](devices/LG-UH5F-H.md)). Individual model support remains device-dependent.

Frontend tests: `npm ci`, `npx playwright install chromium`, `npm test`. Python tests also verify module delivery, card discovery metadata and the service-command contract. The card follows Home Assistant's [custom card API](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/) and uses [asynchronous static-path registration](https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/).
