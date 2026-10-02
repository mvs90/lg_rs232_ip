from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from custom_components.lg_rs232_ip.config_flow import LGDisplayOptionsFlow


@pytest.fixture
def flow():
    f = LGDisplayOptionsFlow(SimpleNamespace(entry_id="display", options={}))
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
async def test_native_requires_password_and_pin(flow):
    with patch("homeassistant.helpers.entity_registry.async_get"):
        result = await flow.async_step_init({"native_web_enabled": True})
    assert set(result["errors"]) == {"native_web_password", "native_web_fingerprint"}


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
