"""Integration composition and lifecycle, with real coordinators and HA storage."""

from importlib import import_module
from inspect import isawaitable
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries
from homeassistant.helpers import entity_registry as er, device_registry as dr

import custom_components.lg_rs232_ip as integration
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.web_manager import LGWebManager


@pytest.fixture
async def lifecycle(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    if hasattr(dr, "async_setup"):
        dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    devices, webs = [], []

    def device(*args, **kwargs):
        display = LGDisplay(*args, **kwargs)
        display.model_name = "75UH5F-HJ"
        display.software_version = "test"
        display.async_connect = AsyncMock(return_value=True)
        display.async_disconnect = AsyncMock()
        display.async_get_power_status = AsyncMock(return_value=True)
        display.async_send_raw_command = AsyncMock(return_value=None)
        devices.append(display)
        return display

    def web(*args, **kwargs):
        client = AsyncMock(spec=LGWebManager)
        for key in (
            "async_get_display_settings",
            "async_get_maintenance_settings",
            "async_get_picture_options",
            "async_get_native_schedules",
        ):
            getattr(client, key).return_value = {}
        webs.append(client)
        return client

    monkeypatch.setattr(integration, "LGDisplay", device)
    monkeypatch.setattr(integration, "LGWebManager", web)
    forward = AsyncMock()
    unload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", forward)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload)
    entries = []

    def entry(name="one", native=False, app=False, preview=False):
        callbacks = []
        value = SimpleNamespace(
            entry_id=name,
            title="LG " + name,
            data={"host": name + ".invalid", "device_id": 1},
            options={
                "native_web_enabled": native,
                "native_web_password": "private-test-password",
                "native_web_verify_certificate": False,
                "display_app_enabled": app,
                "display_app_base_url": "http://ha.test:8123",
                "preview_enabled": preview,
            },
            pref_disable_polling=False,
            add_update_listener=Mock(return_value=lambda: None),
            async_on_unload=callbacks.append,
            callbacks=callbacks,
        )
        entries.append(value)
        return value

    try:
        yield SimpleNamespace(
            hass=hass,
            devices=devices,
            webs=webs,
            entry=entry,
            forward=forward,
            unload=unload,
        )
    finally:
        for item in entries:
            if item.entry_id in hass.data.get("lg_rs232_ip", {}):
                await integration.async_unload_entry(hass, item)
            for callback in item.callbacks:
                result = callback()
                if isawaitable(result):
                    await result
        await hass.async_stop(force=True)


@pytest.mark.parametrize(
    "native,app,preview",
    [
        (False, False, False),
        (True, False, False),
        (True, False, True),
        (True, True, False),
        (True, True, True),
    ],
)
async def test_setup_platform_composition_and_unload(lifecycle, native, app, preview):
    env = lifecycle
    entry = env.entry(native=native, app=app, preview=preview)
    assert await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    assert ("web_manager" in data) is native
    assert ("maintenance" in data) is native
    assert ("native_schedules" in data) is native
    assert ("display_app" in data) is native
    entities = {}
    menu = json.loads((Path(integration.__file__).parent / "www/device-menu.json").read_text())
    menu_keys = {key for group in menu["groups"] for section in group["sections"] for key in section["entities"]}
    with patch(
        "custom_components.lg_rs232_ip.media_player.async_get_current_platform",
        return_value=Mock(),
    ):
        for domain in integration.PLATFORMS:
            added = []
            await import_module(
                "custom_components.lg_rs232_ip." + domain
            ).async_setup_entry(env.hass, entry, added.extend)
            entities[str(domain)] = added
            identities = [x.unique_id for x in added]
            assert len(identities) == len(set(identities)), (domain, identities)
            for entity in added:
                assert entity.device_info["identifiers"] == {
                    ("lg_rs232_ip", entry.entry_id)
                }
                if entity.entity_category == "config":
                    key = f"{domain}:{entity.unique_id.removeprefix(entry.entry_id + '_')}"
                    assert key in menu_keys, f"Unmapped device setting: {key}"
    assert bool(entities["camera"]) is (native and preview)
    assert bool(entities["text"]) is native
    assert bool(entities["datetime"]) is native
    assert bool(entities["time"]) is native
    buttons = {x.key for x in entities["button"]}
    assert {"picture_reset", "picture_apply_all_inputs"} <= buttons
    assert ("test_display_app" in buttons) is (native and app)
    assert await integration.async_unload_entry(env.hass, entry)
    assert entry.entry_id not in env.hass.data["lg_rs232_ip"]
    assert data["controller"]._ha_stopping
    assert data["controller"]._poll_unsub is None
    env.devices[0].async_disconnect.assert_awaited()
    if native:
        env.webs[0].async_close.assert_awaited_once()


async def test_failed_platform_unload_keeps_working_entry(lifecycle):
    env = lifecycle
    entry = env.entry(native=True)
    await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    env.unload.return_value = False
    assert not await integration.async_unload_entry(env.hass, entry)
    assert env.hass.data["lg_rs232_ip"][entry.entry_id] is data
    assert not data["controller"]._ha_stopping
    env.webs[0].async_close.assert_not_awaited()
    env.unload.return_value = True


async def test_two_entries_unload_and_recreate_without_cross_device_effects(lifecycle):
    from custom_components.lg_rs232_ip.api import get_display_api

    env = lifecycle
    one, two = env.entry("one", native=True, app=True), env.entry("two")
    for item in (one, two):
        await integration.async_setup_entry(env.hass, item)
    api_one, api_two = (
        get_display_api(env.hass, "one"),
        get_display_api(env.hass, "two"),
    )
    old = api_one.controller
    assert await integration.async_unload_entry(env.hass, one)
    assert not api_one.ready and api_two.ready
    assert await api_two.async_get_power_status(use_cache=False) is True
    env.devices[1].async_disconnect.assert_not_awaited()
    await integration.async_setup_entry(env.hass, one)
    assert api_one.ready and api_one.controller is not old
    assert old._ha_stopping and old._poll_unsub is None


async def test_partial_setup_failure_releases_created_resources(lifecycle):
    env = lifecycle
    entry = env.entry(native=True, app=True)
    env.forward.side_effect = RuntimeError("simulated platform failure")
    with pytest.raises(RuntimeError, match="platform failure"):
        await integration.async_setup_entry(env.hass, entry)
    assert entry.entry_id not in env.hass.data["lg_rs232_ip"]
    env.devices[0].async_disconnect.assert_awaited()
    env.webs[0].async_close.assert_awaited_once()


async def test_one_cleanup_failure_does_not_leak_other_resources(lifecycle):
    env = lifecycle
    entry = env.entry(native=True)
    await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    data["display_app"].async_close = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    assert await integration.async_unload_entry(env.hass, entry)
    assert entry.entry_id not in env.hass.data["lg_rs232_ip"]
    env.devices[0].async_disconnect.assert_awaited()
    env.webs[0].async_close.assert_awaited_once()


@pytest.mark.parametrize("stored,expected", [(1000, 1000), (0, 1), ("corrupt", 1)])
async def test_address_survives_reload_and_invalid_storage_uses_safe_default(
    lifecycle, stored, expected
):
    from homeassistant.helpers.storage import Store

    env = lifecycle
    entry = env.entry()
    await Store(env.hass, 1, "lg_rs232_ip.one.address").async_save(
        {"device_id": stored}
    )
    await integration.async_setup_entry(env.hass, entry)
    assert env.devices[0].device_id == expected


async def test_native_disabled_can_only_use_saved_recovery_client(
    lifecycle, monkeypatch
):
    from homeassistant.helpers.storage import Store
    from custom_components.lg_rs232_ip.display_app import DisplayAppManager

    env = lifecycle
    entry = env.entry()
    await Store(env.hass, 1, "lg_rs232_ip.one.display_app").async_save(
        {"previous": {"appLaunchMode": "none"}}
    )
    recover = AsyncMock()
    monkeypatch.setattr(DisplayAppManager, "async_recover_si", recover)
    await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    assert "recovery_web" in data and "web_manager" not in data
    assert "maintenance" not in data and "system_settings" not in data
    recover.assert_awaited()
    assert await integration.async_unload_entry(env.hass, entry)
    env.webs[0].async_close.assert_awaited_once()


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("power", [False, None])
async def test_setup_while_off_or_unreachable_keeps_controls_without_waking(
    lifecycle, monkeypatch, native, power
):
    env = lifecycle
    factory = integration.LGDisplay

    def device(*args, **kwargs):
        value = factory(*args, **kwargs)
        value.async_get_power_status.return_value = power
        return value

    monkeypatch.setattr(integration, "LGDisplay", device)
    entry = env.entry(native=native)
    assert await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    assert data["controller"].power is power
    env.devices[0].async_send_raw_command.assert_not_awaited()
    assert not data["picture_settings"].awake
    if native:
        env.webs[0].async_write_display_setting.assert_not_awaited()
        env.webs[0].async_set_si_settings.assert_not_awaited()


async def test_cancelled_setup_also_closes_partial_resources(lifecycle):
    import asyncio

    env = lifecycle
    entry = env.entry(native=True, app=True)
    reached = asyncio.Event()

    async def forward(*args):
        reached.set()
        await asyncio.Event().wait()

    env.forward.side_effect = forward
    task = asyncio.create_task(integration.async_setup_entry(env.hass, entry))
    await reached.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert entry.entry_id not in env.hass.data["lg_rs232_ip"]
    env.devices[0].async_disconnect.assert_awaited()
    env.webs[0].async_close.assert_awaited_once()


@pytest.mark.parametrize(
    "disabled", [er.RegistryEntryDisabler.INTEGRATION, er.RegistryEntryDisabler.USER]
)
async def test_setup_enables_picture_mode_default_but_preserves_user_disable(
    lifecycle, disabled
):
    env = lifecycle
    registry = er.async_get(env.hass)
    entity = registry.async_get_or_create(
        "select", "lg_rs232_ip", "one_picture_mode", disabled_by=disabled
    )
    await integration.async_setup_entry(env.hass, env.entry())
    assert registry.async_get(entity.entity_id).disabled_by == (
        None if disabled is er.RegistryEntryDisabler.INTEGRATION else disabled
    )


async def test_diagnostics_omit_credentials_urls_and_content(lifecycle):
    import json
    from custom_components.lg_rs232_ip.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    env = lifecycle
    entry = env.entry(native=True, app=True)
    await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    app = data["display_app"]
    app.begin("private title", "private message", 10)
    result = await async_get_config_entry_diagnostics(env.hass, entry)
    serialized = json.dumps(result)
    for private in [
        "private-test-password",
        "one.invalid",
        "ha.test",
        app.token,
        "private title",
        "private message",
    ]:
        assert private not in serialized
    assert result["model"] == "75UH5F-HJ"
    assert result["native_web_configured"] is True


async def test_unload_cancellation_still_closes_remaining_resources(lifecycle):
    import asyncio

    env = lifecycle
    entry = env.entry(native=True)
    await integration.async_setup_entry(env.hass, entry)
    data = env.hass.data["lg_rs232_ip"][entry.entry_id]
    close_layouts = data["display_app"].async_close

    async def cancelled_close():
        await close_layouts()
        raise asyncio.CancelledError

    data["display_app"].async_close = cancelled_close
    with pytest.raises(asyncio.CancelledError):
        await integration.async_unload_entry(env.hass, entry)
    assert entry.entry_id not in env.hass.data["lg_rs232_ip"]
    env.devices[0].async_disconnect.assert_awaited()
    env.webs[0].async_close.assert_awaited_once()
