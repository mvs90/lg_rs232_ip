"""Media privacy/cache boundaries and room-based, non-mutating suggestions."""

import asyncio
from io import BytesIO
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
import pytest
from homeassistant.core import HomeAssistant
from custom_components.lg_rs232_ip.layout_cards import room_suggestions
from custom_components.lg_rs232_ip.layout_config import (
    element,
    make_layout,
    validate_layout,
)
from custom_components.lg_rs232_ip.layout_media import LayoutMedia, prepare_cover
from custom_components.lg_rs232_ip.layouts import DisplayLayouts


def cover(color="navy"):
    out = BytesIO()
    Image.new("RGB", (1600, 1600), color).save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
async def media(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    cache = LayoutMedia(hass)
    hass.states.async_set(
        "media_player.sonos",
        "playing",
        {
            "entity_picture": "/api/media_player_proxy/media_player.sonos?token=PRIVATE",
            "media_title": "One",
            "media_artist": "Artist",
            "media_content_id": "https://private.test/music?password=secret",
        },
    )
    player = SimpleNamespace(
        async_get_media_image=AsyncMock(return_value=(cover(), "image/png"))
    )
    hass.data["media_player"] = SimpleNamespace(
        get_entity=lambda eid: player if eid == "media_player.sonos" else None
    )
    yield cache, player
    await cache.async_close()
    await hass.async_stop(force=True)


def test_media_binding_validation_and_cover_decoding():
    cfg = make_layout()
    item = element("media", 4, 4, 50, 30)
    item["entity_id"] = "media_player.sonos"
    cfg["scenes"]["dashboard"]["elements"] = [item]
    assert validate_layout(cfg)["scenes"]["dashboard"]["elements"][0]["show_cover"]
    for key, value in (
        ("entity_id", "camera.private"),
        ("media_style", "url(evil)"),
        ("show_cover", 1),
        ("show_playback_icon", "false"),
        ("accent_color", "red"),
    ):
        saved = item.get(key)
        item[key] = value
        with pytest.raises(ValueError):
            validate_layout(cfg)
        item[key] = saved
    image = Image.open(BytesIO(prepare_cover(cover())))
    assert image.format == "JPEG" and image.size == (640, 640) and not image.getexif()
    for raw in (b"<svg/>", b"x" * (5 * 1024 * 1024 + 1)):
        with pytest.raises((ValueError, OSError)):
            prepare_cover(raw)


def test_media_colour_background_and_optional_icon_survive_validation():
    cfg = make_layout()
    scene = cfg["scenes"]["media_view"]
    assert scene["media_background_fit"] == "colors"
    card = scene["elements"][0]
    assert card["show_playback_icon"] is True
    assert validate_layout(cfg)["scenes"]["media_view"]["elements"][0][
        "show_playback_icon"
    ]
    # Older cards retain the uncluttered timeline until explicitly enabled.
    del card["show_playback_icon"]
    assert not validate_layout(cfg)["scenes"]["media_view"]["elements"][0][
        "show_playback_icon"
    ]
    for fit in ("colors", "contain", "center", "stretch"):
        scene["media_background_fit"] = fit
        assert (
            validate_layout(cfg)["scenes"]["media_view"]["media_background_fit"] == fit
        )


async def test_selected_media_metadata_does_not_leak_urls_tokens_or_unselected_entities(
    media,
):
    cache, _ = media
    hass = cache.hass
    manager = DisplayLayouts(hass, SimpleNamespace(entry_id="one", options={}))
    try:
        cfg = make_layout()
        cfg["enabled"] = True
        item = element("media", 4, 4, 50, 30)
        item["entity_id"] = "media_player.sonos"
        cfg["scenes"]["dashboard"]["elements"] = [item]
        await manager.async_save(cfg, 0)
        data = manager.values()
        serialized = json.dumps(data)
        assert data["media_player.sonos"]["media_title"] == "One"
        assert len(data["media_player.sonos"]["artwork"]) == 64
        assert not any(
            secret in serialized
            for secret in (
                "PRIVATE",
                "password",
                "private.test",
                "entity_picture",
                "media_content_id",
            )
        )
        cfg["scenes"]["dashboard"]["elements"][0]["show_cover"] = False
        await manager.async_save(cfg, 1)
        assert "artwork" not in manager.values()["media_player.sonos"]
    finally:
        await manager.async_close()


async def test_cover_requests_are_shared_cached_and_client_cancel_does_not_cancel_other_viewer(
    media,
):
    cache, player = media
    started = asyncio.Event()
    release = asyncio.Event()

    async def fetch():
        started.set()
        await release.wait()
        return cover(), "image/png"

    player.async_get_media_image.side_effect = fetch
    key = cache.key("media_player.sonos")
    one = asyncio.create_task(cache.async_image("media_player.sonos", key))
    await started.wait()
    two = asyncio.create_task(cache.async_image("media_player.sonos", key))
    await asyncio.sleep(0)
    one.cancel()
    with pytest.raises(asyncio.CancelledError):
        await one
    release.set()
    data = await two
    assert data[:2] == b"\xff\xd8"
    assert await cache.async_image("media_player.sonos", key) == data
    player.async_get_media_image.assert_awaited_once()
    assert await cache.async_image("media_player.sonos", "wrong") is None


async def test_artwork_race_discards_previous_track_and_fetches_latest(media):
    cache, player = media
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await release.wait()
        return cover("red" if calls == 1 else "blue"), "image/png"

    player.async_get_media_image.side_effect = fetch
    old = cache.key("media_player.sonos")
    one = asyncio.create_task(cache.async_image("media_player.sonos", old))
    await started.wait()
    cache.hass.states.async_set(
        "media_player.sonos",
        "playing",
        {"entity_picture": "/new", "media_title": "Two"},
    )
    key = cache.key("media_player.sonos")
    two = asyncio.create_task(cache.async_image("media_player.sonos", key))
    release.set()
    assert await one is None
    image = Image.open(BytesIO(await two))
    assert image.getpixel((20, 20))[2] > 240
    assert calls == 2


async def test_failed_artwork_has_backoff_and_off_entities_have_no_cover(media):
    cache, player = media
    player.async_get_media_image.return_value = (b"<html>", "text/html")
    key = cache.key("media_player.sonos")
    assert await cache.async_image("media_player.sonos", key) is None
    assert await cache.async_image("media_player.sonos", key) is None
    player.async_get_media_image.assert_awaited_once()
    cache.hass.states.async_set("media_player.sonos", "off", {"entity_picture": "/new"})
    assert cache.key("media_player.sonos") is None


async def test_room_suggestions_follow_entity_overrides_and_skip_hidden_diagnostics(
    media,
):
    cache, _ = media
    hass = cache.hass

    def entity(eid, area=None, device=None, **kw):
        return SimpleNamespace(
            entity_id=eid,
            domain=eid.split(".")[0],
            area_id=area,
            device_id=device,
            config_entry_id=kw.get("config_entry_id", "other"),
            disabled_by=kw.get("disabled_by"),
            hidden_by=kw.get("hidden_by"),
            entity_category=kw.get("entity_category"),
            name=None,
            original_name=None,
        )

    rows = [
        entity("media_player.lg", device="lg", config_entry_id="display"),
        entity("media_player.sonos", device="speaker"),
        entity("sensor.temp", "bedroom", "speaker"),
        entity("light.reading", "living"),
        entity("sensor.hidden", "living", hidden_by="user"),
        entity("sensor.diagnostic", "living", entity_category="diagnostic"),
        entity("sensor.disabled", "living", disabled_by="user"),
    ]
    for row in rows:
        if row.entity_id != "media_player.sonos":
            hass.states.async_set(row.entity_id, "on", {"friendly_name": row.entity_id})
    rooms = [
        SimpleNamespace(id="living", name="Wohnzimmer"),
        SimpleNamespace(id="bedroom", name="Schlafzimmer"),
    ]
    devices = {
        "lg": SimpleNamespace(area_id="living"),
        "speaker": SimpleNamespace(area_id="living"),
    }
    entities = SimpleNamespace(entities={e.entity_id: e for e in rows})
    with (
        patch(
            "custom_components.lg_rs232_ip.layout_cards.ar.async_get",
            return_value=SimpleNamespace(
                async_list_areas=lambda: rooms,
                async_get_area=lambda a: next((r for r in rooms if r.id == a), None),
            ),
        ),
        patch(
            "custom_components.lg_rs232_ip.layout_cards.dr.async_get",
            return_value=SimpleNamespace(async_get=devices.get),
        ),
        patch(
            "custom_components.lg_rs232_ip.layout_cards.er.async_get",
            return_value=entities,
        ),
        patch(
            "custom_components.lg_rs232_ip.layout_cards.er.async_entries_for_config_entry",
            return_value=[rows[0]],
        ),
    ):
        result = room_suggestions(hass, "display")
        assert result["area_id"] == "living"
        assert [(r["entity_id"], r["kind"]) for r in result["suggestions"]] == [
            ("media_player.sonos", "media"),
            ("light.reading", "status"),
        ]
        assert [
            r["entity_id"]
            for r in room_suggestions(hass, "display", "bedroom")["suggestions"]
        ] == ["sensor.temp"]
        assert room_suggestions(hass, "display", "")["suggestions"] == []
        with pytest.raises(ValueError):
            room_suggestions(hass, "display", "unknown")


def test_media_background_validation_and_entity_budget():
    from custom_components.lg_rs232_ip.layout_config import layout_entities

    cfg = make_layout()
    scene = cfg["scenes"]["dashboard"]
    # Older views stay disabled and retain the normal background.
    for key in list(scene):
        if key.startswith("media_background_"):
            del scene[key]
    assert not validate_layout(cfg)["scenes"]["dashboard"]["media_background_enabled"]
    scene.update(
        media_background_enabled=True, media_background_entity="media_player.sonos"
    )
    for mode in ("stretch", "contain", "center"):
        scene["media_background_fit"] = mode
        assert layout_entities(validate_layout(cfg)) == {"media_player.sonos"}
    for key, value in (
        ("media_background_enabled", 1),
        ("media_background_entity", "sensor.private"),
        ("media_background_entity", ""),
        ("media_background_fit", "url(evil)"),
        ("media_background_dim", 1),
        ("media_background_dim", float("nan")),
    ):
        previous = scene.get(key)
        scene[key] = value
        with pytest.raises(ValueError):
            validate_layout(cfg)
        if previous is None:
            del scene[key]
        else:
            scene[key] = previous
    for key in ("dashboard", "pip_view"):
        cfg["scenes"][key]["elements"] = [
            {
                **element("entity", 0, 0, 10, 10),
                "id": f"e{i}",
                "entity_id": f"sensor.{key}_{i}",
            }
            for i in range(16)
        ]
    with pytest.raises(ValueError, match="32 distinct"):
        validate_layout(cfg)


async def test_background_only_binding_subscribes_and_inactive_views_do_not_expose_artwork(
    media,
):
    cache, _ = media
    manager = DisplayLayouts(cache.hass, SimpleNamespace(entry_id="one", options={}))
    try:
        cfg = make_layout()
        cfg["enabled"] = True
        bg = cfg["scenes"]["dashboard"]
        bg.update(
            media_background_enabled=True, media_background_entity="media_player.sonos"
        )
        await manager.async_save(cfg, 0)
        manager.changed = changed = __import__(
            "unittest.mock", fromlist=["Mock"]
        ).Mock()
        assert manager.media_entities() == {"media_player.sonos"}
        assert len(manager.values()["media_player.sonos"]["artwork"]) == 64
        assert "PRIVATE" not in json.dumps(manager.payload())
        state = cache.hass.states.get("media_player.sonos")
        cache.hass.states.async_set(state.entity_id, "paused", dict(state.attributes))
        await cache.hass.async_block_till_done()
        await asyncio.sleep(0.35)
        changed.assert_called()
        assert manager.values()[state.entity_id]["state"] == "paused"
        bg["media_background_enabled"] = False
        cfg["scenes"]["signal"].update(
            media_background_enabled=True, media_background_entity=state.entity_id
        )
        await manager.async_save(cfg, manager.revision)
        assert manager.values() == {} and manager.media_entities() == set()
    finally:
        await manager.async_close()


async def test_cover_resolution_tiers_share_fetch_and_never_upscale(media):
    from custom_components.lg_rs232_ip.layout_media import artwork_size

    cache, player = media
    key = cache.key("media_player.sonos")
    images = await asyncio.gather(
        *(
            cache.async_image("media_player.sonos", key, size)
            for size in (640, 1280, 2160)
        )
    )
    assert [Image.open(BytesIO(data)).size for data in images] == [
        (640, 640),
        (1280, 1280),
        (1600, 1600),
    ]
    player.async_get_media_image.assert_awaited_once()
    for invalid in (0, 1, True, "640.0", 3840, "../640", None):
        with pytest.raises(ValueError):
            artwork_size(invalid)


async def test_cover_cache_evicts_lru_with_total_byte_limit(media):
    cache, _ = media
    key = cache.key("media_player.sonos")
    cache._cache["media_player.old"] = ("old", {640: b"x" * 1000000}, 0)
    with patch("custom_components.lg_rs232_ip.layout_media.MAX_CACHE_BYTES", 1000000):
        assert await cache.async_image("media_player.sonos", key)
    assert "media_player.old" not in cache._cache
    assert "media_player.sonos" in cache._cache


async def test_artwork_larger_than_cache_is_returned_without_refetch_loop(media):
    cache, player = media
    with patch("custom_components.lg_rs232_ip.layout_media.MAX_CACHE_BYTES", 1):
        assert await asyncio.wait_for(
            cache.async_image("media_player.sonos", cache.key("media_player.sonos")), 2
        )
    player.async_get_media_image.assert_awaited_once()
    assert not cache._cache
