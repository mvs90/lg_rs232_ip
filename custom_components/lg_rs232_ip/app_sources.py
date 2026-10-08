"""Names for optional external Studio input sources."""

SOURCE_VIEWS = {
    "dashboard": "Dashboard",
    "pip_view": "Dashboard PiP",
    "media_view": "Mediaplayer",
}


def source_names(views, occupied):
    """Keep all HDMI, fixed and user-defined source labels unambiguous."""
    used, result = set(occupied), {}
    for key, title in views.items():
        name = title
        while name in used:
            name += " (App)"
        used.add(name)
        result[key] = name
    return result
