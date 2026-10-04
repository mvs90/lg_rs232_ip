"""Image boundaries, metadata stripping and authenticated background lifecycle."""

from io import BytesIO
from types import SimpleNamespace
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image
import pytest
from homeassistant.core import HomeAssistant
from custom_components.lg_rs232_ip.layouts import DisplayLayouts
from custom_components.lg_rs232_ip.layout_api import (
    LayoutBackgroundView,
    LayoutEditorView,
)
from custom_components.lg_rs232_ip.layout_backgrounds import (
    prepare_background,
    MAX_BYTES,
)
from custom_components.lg_rs232_ip.layout_config import make_layout


def png():
    out = BytesIO()
    Image.new("RGBA", (2400, 1600), (20, 70, 100, 220)).save(out, format="PNG")
    return out.getvalue()


def test_background_decode_is_bounded_and_reencoded_without_metadata():
    data = prepare_background(png())
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG" and image.width <= 1920 and image.height <= 1080
        assert not image.getexif() and image.mode == "RGB"
    for data in (b"<svg><script>alert(1)</script></svg>", b"", b"x" * (MAX_BYTES + 1)):
        with pytest.raises(ValueError):
            prepare_background(data)


async def test_upload_is_private_deduplicated_and_referenced_images_cannot_be_deleted(
    tmp_path,
):
    hass = HomeAssistant(str(tmp_path))
    manager = DisplayLayouts(hass, SimpleNamespace(entry_id="one", options={}))
    await manager.async_start()
    hass.data["lg_rs232_ip"] = {"one": {"layouts": manager}}

    @web.middleware
    async def auth(request, handler):
        request["ha_authenticated"] = request.headers.get("X-Auth") == "yes"
        request["hass_user"] = SimpleNamespace(
            is_admin=request.headers.get("X-Admin") == "yes"
        )
        return await handler(request)

    app = web.Application(middlewares=[auth])
    view = LayoutBackgroundView(hass)
    view.register(hass, app, app.router)
    LayoutEditorView(hass).register(hass, app, app.router)
    base = "/api/lg_rs232_ip/layout_background/one/"
    headers = {"X-Auth": "yes", "X-Admin": "yes"}
    try:
        async with TestClient(TestServer(app)) as client:
            assert (await client.post(base + "upload", data=png())).status == 401
            assert (
                await client.post(
                    base + "upload", data=png(), headers={"X-Auth": "yes"}
                )
            ).status == 403
            response = await client.post(base + "upload", data=png(), headers=headers)
            assert response.status == 200
            identifier = (await response.json())["image_id"]
            again = await client.post(base + "upload", data=png(), headers=headers)
            assert (await again.json())["image_id"] == identifier
            assert await manager.backgrounds.async_list() == [identifier]
            response = await client.get(base + identifier, headers=headers)
            assert response.status == 200 and response.content_type == "image/jpeg"
            config = make_layout()
            config["scenes"]["dashboard"].update(
                background="image", image_id=identifier
            )
            await manager.async_save(config, 0)
            assert (
                await client.delete(base + identifier, headers=headers)
            ).status == 409
            await manager.async_save(make_layout(), 1)
            assert (
                await client.delete(base + identifier, headers=headers)
            ).status == 200
            assert (await client.get(base + identifier, headers=headers)).status == 404
            with pytest.raises(ValueError):
                await manager.async_save(config, 2)
            assert (
                await client.post(base + "upload", headers=headers, data=b"<svg/>")
            ).status == 400
            assert (
                await client.post(
                    base + "upload", headers=headers, data=b"x" * (MAX_BYTES + 1)
                )
            ).status == 413
            with pytest.raises(ValueError):
                await manager.backgrounds.async_read("../../secrets")
    finally:
        await manager.async_close()
        await hass.async_stop(force=True)
