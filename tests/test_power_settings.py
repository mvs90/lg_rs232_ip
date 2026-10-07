"""Documented power controls, partial capabilities and wake warnings."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.lg_rs232_ip.const import DOMAIN
from custom_components.lg_rs232_ip.lg_display import LGDisplay
from custom_components.lg_rs232_ip.power_settings import (
    POWER_SETTINGS, PowerSettings, remote_power_on_status,
)
from custom_components.lg_rs232_ip.select import PowerSettingsSelect
from custom_components.lg_rs232_ip.switch import PowerSettingsSwitch
from custom_components.lg_rs232_ip.sensor import RemotePowerOnSensor


@pytest.fixture
async def power(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    display = LGDisplay('example.invalid')
    display.async_get_power_status = AsyncMock(return_value=True)
    entry = SimpleNamespace(entry_id='test', title='Test LG', async_on_unload=Mock(), pref_disable_polling=False)
    manager = PowerSettings(hass, entry, display, SimpleNamespace(_control_lock=asyncio.Lock()))
    try:
        yield manager
    finally:
        await hass.async_stop(force=True)


@pytest.mark.parametrize(('key', 'value', 'wire', 'ack'), [
    ('auto_sleep', 'on', ('f','g',1), 'g 01 OK01x'),
    ('auto_sleep_no_ir','off', ('m','n',0), 'n 01 OK00x'),
    ('wake_on_lan','on', ('f','w',1), 'w 01 OK01x'),
    ('power_on_status','standby', ('t','r',1), 'r 01 OK01x'),
    ('pm_mode','network_ready', ('s','n',12), 'n 01 OK0c05x'),
    ('dpm_wake_up','clock_and_data', ('s','n',11), 'n 01 OK0b01x'),
    ('wake_on_wlan','on', ('s','n',144), 'n 01 OK9001x'),
])
async def test_documented_wire_protocol(power, key, value, wire, ack):
    display = power.display
    display.async_send_raw_command = AsyncMock(return_value=ack)
    assert await power._write(key, value)
    args = display.async_send_raw_command.await_args
    assert args.args == wire
    suffix = args.kwargs.get('query_suffix', '')
    spec = POWER_SETTINGS[key]
    assert suffix == (f' {spec.options[value]:02x}' if spec.parameter is not None else '')
    assert await power._read(key) == value
    args = display.async_send_raw_command.await_args
    assert args.args == (*spec.command, spec.parameter if spec.parameter is not None else 255)
    assert args.kwargs.get('query_suffix','') == (' ff' if spec.parameter is not None else '')
    assert args.kwargs['use_cache'] is False


@pytest.mark.parametrize('ack', ['n 01 OK0b05x','n 01 NG0c05x','n 01 OK0c00x',None])
async def test_subcommand_ack_not_confused(power, ack):
    power.display.async_send_raw_command = AsyncMock(return_value=ack)
    assert not await power._write('pm_mode','network_ready')


async def test_rejected_write_reads_real_state_and_never_lies(power):
    power._read = AsyncMock(side_effect=['clock'] * 4)
    power._write = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError, match='did not confirm'):
        await power.async_set('dpm_wake_up', 'clock_and_data')
    assert power.data['dpm_wake_up']=='clock'
    power._write.assert_awaited_once()


async def test_lost_ack_confirmed_once_and_caches_invalidated(power):
    power._read = AsyncMock(side_effect=['power_off','network_ready'])
    power._write = AsyncMock(return_value=False)
    power.display._picture_settings_changed = Mock()
    await power.async_set('pm_mode','network_ready')
    assert power.data['pm_mode']=='network_ready'
    power._write.assert_awaited_once()
    power.display._picture_settings_changed.assert_called_once()


@pytest.mark.parametrize('state', [False,None])
async def test_no_writes_or_wake_while_off_or_unknown(power,state):
    power.display.async_get_power_status.return_value=state
    power._write=AsyncMock()
    with pytest.raises(HomeAssistantError,match='must be on'):
        await power.async_set('wake_on_lan','off')
    power._write.assert_not_awaited()


async def test_unavailable_and_invalid_values_do_not_mutate(power):
    power._read=AsyncMock(return_value=None)
    power._write=AsyncMock()
    for key, value in [('arbitrary','on'),('pm_mode','6'),('wake_on_lan',True)]:
        with pytest.raises(HomeAssistantError,match='Invalid'):
            await power.async_set(key,value)
    with pytest.raises(HomeAssistantError,match='unavailable'):
        await power.async_set('pm_mode','network_ready')
    power._write.assert_not_awaited()


async def test_partial_support_shared_poll_and_entity_identity(power):
    power._read=AsyncMock(side_effect=lambda key: {'auto_sleep':'on','auto_sleep_no_ir':'off','pm_mode':'network_ready','wake_on_lan':'on'}.get(key))
    power.async_set_updated_data(await power._async_update_data())
    sleep=PowerSettingsSwitch(power,'auto_sleep')
    ir_sleep=PowerSettingsSwitch(power,'auto_sleep_no_ir')
    pm=PowerSettingsSelect(power,'pm_mode')
    wlan=PowerSettingsSwitch(power,'wake_on_wlan')
    status=RemotePowerOnSensor(power)
    assert sleep.unique_id=='test_auto_sleep' and sleep.is_on
    assert sleep.extra_state_attributes=={'delay_seconds':900}
    assert ir_sleep.extra_state_attributes=={'delay_seconds':14400}
    assert not sleep.should_poll and not pm.should_poll
    assert not wlan.available and not wlan.entity_registry_enabled_default
    assert pm.available and pm.current_option=='network_ready'
    assert status.native_value=='network_ready'
    power.display.async_get_power_status.return_value=False
    assert await power._async_update_data()==power.data
    assert not pm.available and status.available
    power.display.async_get_power_status.return_value=None
    with pytest.raises(UpdateFailed): await power._async_update_data()


async def test_visible_warning_added_and_cleared_from_real_settings(power):
    power._read=AsyncMock(side_effect=['network_ready','power_off','power_off','network_ready'])
    power._write=AsyncMock(return_value=True)
    power.async_set_updated_data({'wake_on_lan':'on','pm_mode':'network_ready'})
    await power.async_set('pm_mode','power_off')
    registry=ir.async_get(power.hass)
    assert registry.async_get_issue(DOMAIN,power.issue_id) is not None
    assert RemotePowerOnSensor(power).native_value=='pm_mode_restricted'
    await power.async_set('pm_mode','network_ready')
    assert registry.async_get_issue(DOMAIN,power.issue_id) is None


@pytest.mark.parametrize(('values','status'), [
    ({},'unknown'),
    ({'pm_mode':'network_ready'},'unknown'),
    ({'wake_on_lan':'on'},'unknown'),
    ({'pm_mode':'network_ready','wake_on_lan':'off'},'wake_on_lan_disabled'),
    ({'pm_mode':'network_ready','wake_on_lan':'on'},'network_ready'),
    *[({'pm_mode':m,'wake_on_lan':'on'},'pm_mode_restricted') for m in POWER_SETTINGS['pm_mode'].options if m!='network_ready'],
])
def test_wake_status_is_conservative(values,status):
    assert remote_power_on_status(values)==status


async def test_delayed_readback_is_bounded_and_does_not_replay_write(power):
    power._read = AsyncMock(side_effect=['clock', None, 'clock', 'clock_and_data'])
    power._write = AsyncMock(return_value=True)
    await power.async_set('dpm_wake_up', 'clock_and_data')
    assert power.data['dpm_wake_up'] == 'clock_and_data'
    power._write.assert_awaited_once()
    assert power._read.await_count == 4


async def test_dropped_preflight_queries_recover_without_a_wake(power):
    power.display.async_get_power_status = AsyncMock(side_effect=[None, True])
    power._read = AsyncMock(side_effect=[None, 'clock', 'clock_and_data'])
    power._write = AsyncMock(return_value=True)
    await power.async_set('dpm_wake_up', 'clock_and_data')
    power._write.assert_awaited_once_with('dpm_wake_up', 'clock_and_data')
    assert power.display.async_get_power_status.await_count == 2
    assert power.data['dpm_wake_up'] == 'clock_and_data'


async def test_disconnected_supply_never_queries_or_writes(power):
    power.display.set_power_supply_state(False)
    power._read = AsyncMock()
    power._write = AsyncMock()
    assert await power._async_update_data() == {}
    with pytest.raises(HomeAssistantError, match='must be on'):
        await power.async_set('wake_on_lan', 'on')
    power.display.async_get_power_status.assert_not_awaited()
    power._read.assert_not_awaited()
    power._write.assert_not_awaited()


async def test_writes_share_controller_lock_and_unknown_readback_is_unavailable(power):
    async def write(key, value):
        assert power.controller._control_lock.locked()
        assert power._settings_lock.locked()
        return True
    power._write = AsyncMock(side_effect=write)
    power._read = AsyncMock(side_effect=['on', None, None, None])
    with pytest.raises(HomeAssistantError, match='did not confirm'):
        await power.async_set('wake_on_lan', 'off')
    assert not PowerSettingsSwitch(power, 'wake_on_lan').available
    assert not power.controller._control_lock.locked()
