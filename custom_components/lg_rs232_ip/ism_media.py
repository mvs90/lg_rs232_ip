"""Prepare LG's documented USB ISM import; this is not a remote installation."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from .boot_image import prepare_boot_jpeg


def make_ism_files(sources, media_type):
    """Create bounded, actual media files: HA Media does not display ZIP files."""
    if media_type not in {"image", "video"} or not 1 <= len(sources) <= (
        4 if media_type == "image" else 1
    ):
        raise ValueError("ISM accepts 1–4 images or exactly one video")
    files = {}
    for index, source in enumerate(sources, 1):
        if media_type == "image":
            files[f"image{index:02d}.jpg"] = prepare_boot_jpeg(source)
        else:
            if not 12 <= len(source) <= 50 * 1024 * 1024 or source[4:8] != b"ftyp":
                raise ValueError("Use an MP4 video up to 50 MiB")
            files["video.mp4"] = source
    return files


def save_ism_files(media_root, entry_id, files):
    """Publish a complete, content-addressed directory without deleting user files."""
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]+", entry_id)
        or not files
        or any(not re.fullmatch(r"image0[1-4]\.jpg|video\.mp4", name) for name in files)
    ):
        raise ValueError("Invalid ISM destination")
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode())
        digest.update(hashlib.sha256(content).digest())
    root = Path(media_root).resolve()
    relative = Path("lg_rs232_ip") / entry_id / "ism" / digest.hexdigest()[:16] / "ISM"
    destination = root / relative
    if not destination.resolve().is_relative_to(root) or any(
        p.is_symlink()
        for p in [destination, *destination.parents]
        if p != root and root in p.parents
    ):
        raise ValueError("ISM destination is outside configured media or is a symlink")
    if destination.exists():
        if set(p.name for p in destination.iterdir()) != set(files) or any(
            (destination / name).is_symlink()
            or (destination / name).read_bytes() != data
            for name, data in files.items()
        ):
            raise ValueError(
                "An existing ISM export was changed; refusing to replace it"
            )
        return {name: (relative / name).as_posix() for name in files}
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(dir=destination.parent, prefix=".ism-"))
    try:
        for name, content in files.items():
            with (stage / name).open("wb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
        os.rename(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {name: (relative / name).as_posix() for name in files}


async def async_prepare_ism_media(
    player, media_ids, media_type="image", media_directory="local"
):
    if (
        media_type not in {"image", "video"}
        or not isinstance(media_ids, list)
        or not 1 <= len(media_ids) <= (4 if media_type == "image" else 1)
    ):
        raise ServiceValidationError("Choose 1–4 ISM images or exactly one MP4 video")
    root = player.hass.config.media_dirs.get(media_directory)
    if not root:
        raise ServiceValidationError(
            "Choose a configured Home Assistant media directory"
        )
    download = (
        player._async_download_native_image
        if media_type == "image"
        else player._async_download_native_video
    )
    sources = [await download(media_id) for media_id in media_ids]
    try:
        files = await player.hass.async_add_executor_job(
            make_ism_files, sources, media_type
        )
        paths = await player.hass.async_add_executor_job(
            save_ism_files, root, player._config_entry.entry_id, files
        )
    except (OSError, ValueError):
        raise HomeAssistantError(
            "Cannot prepare ISM media; check file format/size and media-directory write access"
        ) from None
    return {
        "files": [
            {
                "media_id": f"media-source://media_source/{media_directory}/{relative}",
                "usb_path": f"ISM/{name}",
            }
            for name, relative in paths.items()
        ],
        "installed_on_display": False,
        "import_method": "usb",
        "codec_verified": False if media_type == "video" else None,
        "next_step": "Download these files from HA Media into ISM at the root of a USB drive. Use LG General / Safety Mode / ISM Method / User Image or User Video Download. MP4 codec support depends on the model.",
    }
