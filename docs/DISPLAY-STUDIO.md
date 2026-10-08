# Display Studio is a separate integration

From **LG Professional Display 2.32.0**, the editor, designs, themes, widgets and generic rendering belong to the independent [Display Studio repository](https://github.com/mvs90/display_studio).

1. Add that repository in HACS, category Integration, and download Display Studio.
2. Update LG Professional Display to 2.32.0 or newer; restart HA.
3. Add **Display Studio** under Devices & services, choose LG and select the existing display.
4. Existing layouts and uploaded backgrounds are copied once, preserving IDs, themes and revisions. Original LG files remain untouched. Existing Studio storage is never replaced on reload.
5. Open **Display Studio** in the sidebar. The old `/lg-display-studio` bookmark remains an alias after installing the extension.

[Detailed German editor guide](https://github.com/mvs90/display_studio/blob/main/docs/DISPLAY-STUDIO.md) · [Automation actions and browser setup](https://github.com/mvs90/display_studio#automations) · [Public adapter contract](https://github.com/mvs90/display_studio/blob/main/docs/ADAPTERS.md)

**LG owns:** power/input/settings, native content and capture, OSD suppression/restoration, SI provisioning/resident boot and hardware HDMI/PiP.

**Studio owns:** layout storage, backgrounds, themes, widget composition/data and editor; independent `display_studio.show_view` / `display_studio.show_notification` actions and a source entity. Existing LG `show_view` remains compatible while Studio is connected. All hardware switching still follows the LG controller and its OSD guard. AV Companion remains separate and receives the same Studio source list through the unchanged LG API v1.

Browser/kiosk outputs work without LG. They display Studio content and notifications but do not gain physical HDMI, native picture-in-picture, display power or capture capabilities.
