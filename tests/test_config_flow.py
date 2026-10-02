from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from custom_components.lg_rs232_ip.config_flow import LGDisplayOptionsFlow


@pytest.fixture
def flow():
    f = LGDisplayOptionsFlow(
        SimpleNamespace(entry_id="display", options={}, data={"host": "display.test"})
    )
    f.hass = Mock()
    f.hass.states.get.return_value = None
    f.async_show_form = lambda **kw: kw
    f.async_create_entry = lambda **kw: kw
    return f


@pytest.mark.asyncio
async def test_standalone_form_has_no_foreign_entities(flow):
    form = await flow.async_step_init()
    values = form["data_schema"]({})
    assert not any(
        key.startswith(("linked_", "sonos_", "power_supply", "standby_"))
        for key in values
    )
    assert values["polling_interval"] == 30


@pytest.mark.asyncio
async def test_native_requires_password_before_certificate_discovery(flow):
    with patch("homeassistant.helpers.entity_registry.async_get"):
        result = await flow.async_step_init({"native_web_enabled": True})
    assert set(result["errors"]) == {"native_web_password"}


@pytest.mark.asyncio
async def test_native_password_not_prefilled_and_preserved(flow):
    flow._config_entry.options = {"native_web_password": "test-secret"}
    form = await flow.async_step_init()
    assert "native_web_password" not in form["data_schema"]({})
    with patch("homeassistant.helpers.entity_registry.async_get"):
        result = await flow.async_step_init(
            {
                "native_web_enabled": True,
                "native_web_password": "",
                "native_web_fingerprint": "AB" * 32,
            }
        )
    assert result["data"]["native_web_password"] == "test-secret"
    assert result["data"]["native_web_fingerprint"] == "ab" * 32


@pytest.mark.asyncio
async def test_preview_needs_web_access_and_bounded_interval(flow):
    with patch("homeassistant.helpers.entity_registry.async_get"):
        result = await flow.async_step_init(
            {"preview_enabled": True, "preview_interval": 1}
        )
    assert result["errors"]["preview_enabled"] == "preview_requires_web"
    assert result["errors"]["preview_interval"] == "invalid_preview_interval"


@pytest.fixture
def setup_flow():
    from unittest.mock import AsyncMock
    from custom_components.lg_rs232_ip.config_flow import LGDisplayConfigFlow

    flow = LGDisplayConfigFlow()
    flow.hass = Mock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    flow.async_show_form = lambda **kw: {"type": "form", **kw}
    flow.async_create_entry = Mock(
        side_effect=lambda **kw: {"type": "create_entry", **kw}
    )
    return flow


async def connect_setup(flow, connected=True):
    from unittest.mock import AsyncMock

    display = Mock(
        async_connect=AsyncMock(return_value=connected), async_disconnect=AsyncMock()
    )
    with patch(
        "custom_components.lg_rs232_ip.lg_display.LGDisplay", return_value=display
    ):
        result = await flow.async_step_user(
            {"host": "display.test", "port": 9761, "name": "Office LG"}
        )
    return result


@pytest.mark.asyncio
async def test_initial_connection_opens_same_settings_before_creating_entry(
    setup_flow, flow
):
    result = await connect_setup(setup_flow)
    assert result["type"] == "form"
    assert result["step_id"] == "settings"
    setup_flow.async_create_entry.assert_not_called()
    options = await flow.async_step_init()
    assert result["data_schema"]({}) == options["data_schema"]({})
    assert {str(key) for key in result["data_schema"].schema} == {
        str(key) for key in options["data_schema"].schema
    }


@pytest.mark.asyncio
async def test_initial_settings_save_as_options_not_connection_data(setup_flow):
    form = await connect_setup(setup_flow)
    values = form["data_schema"](
        {
            "native_web_enabled": True,
            "preview_enabled": True,
            "native_web_password": "setup-secret",
            "native_web_fingerprint": "AB" * 32,
            "preview_interval": 60,
            "preview_height": "1080",
            "suppress_osd_during_switch": True,
        }
    )
    result = await setup_flow.async_step_settings(values)
    assert result["type"] == "create_entry"
    assert result["data"] == {"host": "display.test", "port": 9761, "name": "Office LG"}
    assert result["options"]["preview_enabled"] is True
    assert result["options"]["preview_interval"] == 60
    assert result["options"]["preview_height"] == "1080"
    assert result["options"]["native_web_password"] == "setup-secret"
    assert result["options"]["native_web_fingerprint"] == "ab" * 32
    assert result["options"]["suppress_osd_during_switch"] is True
    setup_flow.async_create_entry.assert_called_once()


@pytest.mark.asyncio
async def test_initial_preview_validation_keeps_settings_open(setup_flow):
    await connect_setup(setup_flow)
    result = await setup_flow.async_step_settings(
        {"preview_enabled": True, "preview_interval": 1}
    )
    assert result["step_id"] == "settings"
    assert result["errors"] == {
        "preview_enabled": "preview_requires_web",
        "preview_interval": "invalid_preview_interval",
    }
    result = await setup_flow.async_step_settings(
        {"native_web_enabled": True, "preview_enabled": True}
    )
    assert set(result["errors"]) == {"native_web_password"}
    setup_flow.async_create_entry.assert_not_called()


@pytest.mark.asyncio
async def test_failed_connection_does_not_open_settings(setup_flow):
    result = await connect_setup(setup_flow, connected=False)
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    setup_flow.async_create_entry.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_is_rechecked_before_initial_settings_commit(setup_flow):
    from homeassistant.data_entry_flow import AbortFlow

    await connect_setup(setup_flow)
    setup_flow._abort_if_unique_id_configured.side_effect = AbortFlow(
        "already_configured"
    )
    with pytest.raises(AbortFlow):
        await setup_flow.async_step_settings({})
    setup_flow.async_create_entry.assert_not_called()


@pytest.mark.asyncio
async def test_settings_fields_and_errors_have_setup_and_options_translations(
    setup_flow,
):
    import json
    from pathlib import Path

    form = await connect_setup(setup_flow)
    keys = {str(key) for key in form["data_schema"].schema}
    root = Path(__file__).parents[1] / "custom_components/lg_rs232_ip"
    for file in [
        root / "strings.json",
        root / "translations/en.json",
        root / "translations/de.json",
    ]:
        text = json.loads(file.read_text())
        assert keys <= text["config"]["step"]["settings"]["data"].keys()
        assert keys <= text["options"]["step"]["init"]["data"].keys()
        assert "invalid_preview_interval" in text["config"]["error"]
        assert "invalid_preview_interval" in text["options"]["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [True, False])
async def test_empty_pin_is_detected_and_saved_with_verification_enabled(
    setup_flow, flow, initial
):
    from unittest.mock import AsyncMock

    if initial:
        await connect_setup(setup_flow)
    submit = setup_flow.async_step_settings if initial else flow.async_step_init
    with patch(
        "custom_components.lg_rs232_ip.config_flow.async_read_certificate_fingerprint",
        new_callable=AsyncMock,
        return_value="cd" * 32,
    ) as read:
        result = await submit(
            {
                "native_web_enabled": True,
                "native_web_password": "test-secret",
                "preview_enabled": True,
            }
        )
    read.assert_awaited_once_with("display.test")
    options = result["options"] if initial else result["data"]
    assert options["native_web_fingerprint"] == "cd" * 32
    assert options.get("native_web_verify_certificate", True) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", [True, False])
async def test_failed_discovery_keeps_form_open_without_disabling_verification(
    setup_flow, flow, initial
):
    from unittest.mock import AsyncMock
    from custom_components.lg_rs232_ip.web_manager import LGWebError

    if initial:
        await connect_setup(setup_flow)
    submit = setup_flow.async_step_settings if initial else flow.async_step_init
    with patch(
        "custom_components.lg_rs232_ip.config_flow.async_read_certificate_fingerprint",
        new_callable=AsyncMock,
        side_effect=LGWebError("Unavailable"),
    ):
        result = await submit(
            {"native_web_enabled": True, "native_web_password": "test-secret"}
        )
    assert result["errors"] == {"native_web_fingerprint": "cannot_read_certificate"}
    assert result["data_schema"]({})["native_web_verify_certificate"] is True
    assert "native_web_password" not in result["data_schema"]({})


@pytest.mark.asyncio
async def test_explicit_certificate_opt_out_does_not_read_or_require_pin(setup_flow):
    from unittest.mock import AsyncMock

    await connect_setup(setup_flow)
    with patch(
        "custom_components.lg_rs232_ip.config_flow.async_read_certificate_fingerprint",
        new_callable=AsyncMock,
    ) as read:
        result = await setup_flow.async_step_settings(
            {
                "native_web_enabled": True,
                "native_web_password": "test-secret",
                "native_web_verify_certificate": False,
                "preview_enabled": True,
            }
        )
    read.assert_not_awaited()
    assert result["options"]["native_web_verify_certificate"] is False
    assert result["type"] == "create_entry"


@pytest.mark.asyncio
async def test_stored_pin_is_not_automatically_replaced(flow):
    from unittest.mock import AsyncMock

    flow._config_entry.options = {
        "native_web_enabled": True,
        "native_web_password": "test-secret",
        "native_web_fingerprint": "ab" * 32,
    }
    form = await flow.async_step_init()
    with patch(
        "custom_components.lg_rs232_ip.config_flow.async_read_certificate_fingerprint",
        new_callable=AsyncMock,
    ) as read:
        result = await flow.async_step_init(form["data_schema"]({}))
    read.assert_not_awaited()
    assert result["data"]["native_web_fingerprint"] == "ab" * 32
