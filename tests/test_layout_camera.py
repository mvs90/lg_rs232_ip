"""Camera boundaries, shared work and optional automation installation."""

import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.lg_rs232_ip.blueprint import install_blueprint
from custom_components.lg_rs232_ip.layout_camera import LayoutCamera
from custom_components.lg_rs232_ip.layout_config import (
    element,
    make_layout,
    validate_layout,
)


def test_camera_scene_accepts_one_video_and_rejects_invalid_sources():
    config = make_layout()
    item = element("camera", 65, 5, 30, 30)
    config["scenes"]["hdmi_full"]["elements"][0]["width"] = 60
    config["scenes"]["hdmi_full"]["elements"].append(item)
    assert (
        validate_layout(config)["scenes"]["hdmi_full"]["elements"][1]["camera_source"]
        == "test"
    )
    for values in (
        {"camera_interval": 0.5},
        {"camera_interval": 31},
        {"camera_mode": "rtsp"},
        {"camera_source": "https://secret"},
        {"entity_id": "media_player.wrong"},
        {"camera_fit": "css"},
    ):
        bad = deepcopy(config)
        bad["scenes"]["hdmi_full"]["elements"][1].update(values)
        with pytest.raises(ValueError):
            validate_layout(bad)
    config["scenes"]["hdmi_full"]["elements"].append({**item, "id": "second"})
    with pytest.raises(ValueError, match="one additional"):
        validate_layout(config)


@pytest.fixture
async def cameras(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.states.async_set("camera.door", "idle")
    manager = LayoutCamera(hass)
    manager.registry = {}
    with patch(
        "custom_components.lg_rs232_ip.layout_camera.er.async_get",
        return_value=SimpleNamespace(async_get=manager.registry.get),
    ):
        yield manager
    await manager.async_close()
    await hass.async_stop(force=True)


async def test_camera_requests_are_demand_driven_coalesced_cached_and_resized(cameras):
    source = Path("tests/fixtures/media-cover.png").read_bytes()
    fetch = AsyncMock(return_value=SimpleNamespace(content=source))
    with patch(
        "custom_components.lg_rs232_ip.layout_camera.camera.async_get_image", fetch
    ):
        first, second = await asyncio.gather(
            *(cameras.async_get("camera.door", "image") for _ in range(2))
        )
        assert first == second and first.startswith(b"\xff\xd8\xff")
        assert await cameras.async_get("camera.door", "image") == first
        fetch.assert_awaited_once()
        await cameras.async_close()
        assert not cameras._cache and not cameras._tasks
        assert await cameras.async_get("camera.door", "image") is None


async def test_only_ha_hls_endpoint_is_shared_and_failures_are_cached(cameras):
    fetch = AsyncMock(return_value="rtsp://user:password@camera.local/")
    with patch(
        "custom_components.lg_rs232_ip.layout_camera.camera.async_request_stream", fetch
    ):
        assert await cameras.async_get("camera.door", "stream") is None
        assert await cameras.async_get("camera.door", "stream") is None
        fetch.assert_awaited_once()
        cameras._cache.clear()
        fetch.return_value = "/api/hls/scoped-token/master_playlist.m3u8"
        assert (await cameras.async_get("camera.door", "stream")).startswith(
            "/api/hls/"
        )


async def test_lg_preview_feedback_and_unavailable_entities_are_blocked(cameras):
    entry = SimpleNamespace(entity_id="camera.lg_preview", platform="lg_rs232_ip")
    cameras.registry[entry.entity_id] = entry
    cameras.hass.states.async_set(entry.entity_id, "idle")
    assert not cameras.allowed(entry.entity_id)
    assert not cameras.allowed("camera.unknown")
    cameras.hass.states.async_set("camera.door", "unavailable")
    assert not cameras.allowed("camera.door")


async def test_unload_cancels_camera_work_without_leaking_cache(cameras):
    started = asyncio.Event()

    async def fetch(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    with patch(
        "custom_components.lg_rs232_ip.layout_camera.camera.async_get_image", fetch
    ):
        task = asyncio.create_task(cameras.async_get("camera.door", "image"))
        await asyncio.wait_for(started.wait(), 1)
        await cameras.async_close()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not cameras._tasks and not cameras._cache


def test_blueprint_install_does_not_overwrite_local_edits(tmp_path):
    install_blueprint(tmp_path)
    path = tmp_path / "blueprints/automation/lg_rs232_ip/event_view.yaml"
    assert "lg_rs232_ip.show_view" in path.read_text()
    path.write_text("user modified this")
    install_blueprint(tmp_path)
    assert path.read_text() == "user modified this"


def test_native_stream_overlap_is_rejected_but_auto_and_snapshot_overlays_work():
    config = make_layout()
    item = element("camera", 64, 60, 32, 32)
    config["scenes"]["hdmi_full"]["elements"].append(item)
    with pytest.raises(ValueError, match="beside HDMI"):
        validate_layout(config)
    item.update(camera_source="entity", camera_mode="stream", entity_id="camera.door")
    with pytest.raises(ValueError, match="beside HDMI"):
        validate_layout(config)
    for mode in ("auto", "snapshot"):
        item["camera_mode"] = mode
        assert (
            validate_layout(config)["scenes"]["hdmi_full"]["elements"][1]["camera_mode"]
            == mode
        )
