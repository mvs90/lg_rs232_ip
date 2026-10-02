"""Bundled card delivery and its backend contract."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

from custom_components.lg_rs232_ip import async_setup
from custom_components.lg_rs232_ip.frontend import CARD_PATH, CARD_URL, CARD_VERSION
from custom_components.lg_rs232_ip.media_player import LGDisplayMediaPlayer


@pytest.mark.asyncio
async def test_bundled_module_registered_without_dashboard_mutation():
    hass = SimpleNamespace(
        http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        data={DATA_EXTRA_MODULE_URL: set()},
    )
    assert await async_setup(hass, {})
    paths = hass.http.async_register_static_paths.await_args.args[0]
    assert len(paths) == 1
    assert paths[0].url_path == CARD_PATH
    assert Path(paths[0].path).is_file()
    assert paths[0].cache_headers is False
    assert hass.data[DATA_EXTRA_MODULE_URL] == {CARD_URL}
    manifest = json.loads(
        (Path(paths[0].path).parents[1] / "manifest.json").read_text()
    )
    assert manifest["version"] == CARD_VERSION
    assert "frontend" in manifest["dependencies"]


def test_remote_discovery_and_web_capability_follow_entry_options(player):
    entry = SimpleNamespace(entry_id="display", options={})
    entity = LGDisplayMediaPlayer(player, entry)
    assert entity.extra_state_attributes["integration_domain"] == "lg_rs232_ip"
    assert entity.extra_state_attributes["native_web_enabled"] is False
    entry.options["native_web_enabled"] = True
    assert entity.extra_state_attributes["native_web_enabled"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "code"),
    [("home", 0x7C), ("menu", 0x43), ("back", 0x28), ("exit", 0x5B)],
)
async def test_lg_navigation_codes_match_webos4_manual(player, command, code):
    entity = LGDisplayMediaPlayer(
        player, SimpleNamespace(entry_id="display", options={})
    )
    await entity.async_send_remote_command(command)
    player._lg_display.async_send_remote_key.assert_awaited_once_with(code)


@pytest.mark.asyncio
async def test_service_picker_matches_registered_remote_commands():
    from custom_components.lg_rs232_ip.media_player import async_setup_entry

    hass = Mock(data={"lg_rs232_ip": {"display": {"controller": Mock()}}})
    entry = SimpleNamespace(entry_id="display", options={})
    platform = Mock()
    with patch(
        "custom_components.lg_rs232_ip.media_player.async_get_current_platform",
        return_value=platform,
    ):
        await async_setup_entry(hass, entry, Mock())
    service = next(
        call
        for call in platform.async_register_entity_service.call_args_list
        if call.args[0] == "send_remote_command"
    )
    validator = next(iter(service.args[1].values()))
    root = Path(__file__).parents[1] / "custom_components/lg_rs232_ip"
    fields = yaml.safe_load((root / "services.yaml").read_text())[
        "send_remote_command"
    ]["fields"]
    assert set(fields["command"]["selector"]["select"]["options"]) == set(
        validator.container
    )
