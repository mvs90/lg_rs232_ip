"""LG USB media exports are browsable in HA and do not replace user files."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from PIL import Image
import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from custom_components.lg_rs232_ip.ism_media import (
    make_ism_files,
    save_ism_files,
    async_prepare_ism_media,
)


def jpeg(size=(640, 360)):
    data = BytesIO()
    Image.new("RGB", size, "blue").save(data, "JPEG")
    return data.getvalue()


def test_images_are_real_media_with_bounded_resolution():
    files = make_ism_files([jpeg((2500, 1400)), jpeg()], "image")
    assert set(files) == {"image01.jpg", "image02.jpg"}
    for content in files.values():
        with Image.open(BytesIO(content)) as image:
            assert (
                image.size == (1920, 1080)
                and image.format == "JPEG"
                and not image.getexif()
            )


@pytest.mark.parametrize(
    ("sources", "kind"),
    [
        ([], "image"),
        ([b"x"] * 5, "image"),
        ([b"x"] * 2, "video"),
        ([b"bad"], "image"),
        ([b"bad"], "video"),
        ([b"x"], "other"),
    ],
)
def test_reject_unsupported_counts_and_formats(sources, kind):
    with pytest.raises(ValueError):
        make_ism_files(sources, kind)


def test_video_is_not_transcoded_or_misrepresented():
    video = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32
    assert make_ism_files([video], "video") == {"video.mp4": video}


def test_complete_exports_are_scoped_idempotent_and_preserve_previous(tmp_path):
    paths = save_ism_files(str(tmp_path), "test_entry", {"image01.jpg": b"first"})
    relative = paths["image01.jpg"]
    assert relative.startswith("lg_rs232_ip/test_entry/ism/") and relative.endswith(
        "/ISM/image01.jpg"
    )
    assert (
        save_ism_files(str(tmp_path), "test_entry", {"image01.jpg": b"first"}) == paths
    )
    second = save_ism_files(str(tmp_path), "test_entry", {"video.mp4": b"second"})
    assert (tmp_path / relative).read_bytes() == b"first"
    assert (tmp_path / second["video.mp4"]).read_bytes() == b"second"
    (tmp_path / relative).write_bytes(b"user change")
    with pytest.raises(ValueError):
        save_ism_files(str(tmp_path), "test_entry", {"image01.jpg": b"first"})
    with pytest.raises(ValueError):
        save_ism_files(str(tmp_path), "../escape", {"image01.jpg": b"x"})
    with pytest.raises(ValueError):
        save_ism_files(str(tmp_path), "test", {"../escape": b"x"})
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "media"
    (root / "lg_rs232_ip").mkdir(parents=True)
    (root / "lg_rs232_ip" / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        save_ism_files(str(root), "escape", {"image01.jpg": b"x"})


async def test_prepare_service_no_device_io(tmp_path):
    async def executor(fn, *args):
        return fn(*args)

    player = SimpleNamespace(
        hass=SimpleNamespace(
            config=SimpleNamespace(media_dirs={"local": str(tmp_path)}),
            async_add_executor_job=executor,
        ),
        _config_entry=SimpleNamespace(entry_id="test"),
        _async_download_native_image=AsyncMock(return_value=jpeg()),
        _async_download_native_video=AsyncMock(),
    )
    result = await async_prepare_ism_media(
        player, ["media-source://media_source/local/test.jpg"]
    )
    assert result["installed_on_display"] is False and result["import_method"] == "usb"
    assert result["files"][0]["media_id"].endswith("/ISM/image01.jpg")
    assert result["files"][0]["usb_path"] == "ISM/image01.jpg"
    assert len(list(tmp_path.rglob("image01.jpg"))) == 1
    with pytest.raises(ServiceValidationError):
        await async_prepare_ism_media(player, [], media_type="video")
    with pytest.raises(ServiceValidationError):
        await async_prepare_ism_media(player, ["x"], media_directory="missing")
    player._async_download_native_image.return_value = b"bad"
    with pytest.raises(HomeAssistantError):
        await async_prepare_ism_media(player, ["x"])
