"""Config flow, coordinator and sensors against a mocked API."""

from __future__ import annotations

from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.spotwatts.const import CONF_VAT, CONF_ZONE, DOMAIN

from .conftest import API, day_json

# Thursday 12.11.2026, 09:05 UTC = 10:05 in Stockholm: before the auction
NOW = datetime(2026, 11, 12, 9, 5, tzinfo=UTC)
AFTER_AUCTION = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
TODAY = [1.0] * 40 + [0.2] * 4 + [3.0] * 52  # 0:00-10:00 at 1, 10:00-11:00 at 0.2, then 3
TOMORROW = [0.5] * 96
TODAY_URL = f"{API}/se3/2026-11-12.json"
TOMORROW_URL = f"{API}/se3/2026-11-13.json"


def mock_api(aioclient_mock: AiohttpClientMocker, tomorrow: int = 404) -> None:
    aioclient_mock.get(TODAY_URL, json=day_json("SE3", "2026-11-12", TODAY))
    if tomorrow == 200:
        aioclient_mock.get(TOMORROW_URL, json=day_json("SE3", "2026-11-13", TOMORROW))
    else:
        aioclient_mock.get(TOMORROW_URL, status=tomorrow)


async def setup(hass: HomeAssistant, vat: bool = True) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SE3", data={CONF_ZONE: "SE3"}, options={CONF_VAT: vat})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def requested(aioclient_mock: AiohttpClientMocker, url: str) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == url)


async def test_config_flow_creates_one_entry_per_zone(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
):
    freezer.move_to(NOW)
    mock_api(aioclient_mock)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "se3", CONF_VAT: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Spotwatts SE3"
    assert result["data"] == {CONF_ZONE: "SE3"}
    assert result["options"] == {CONF_VAT: False}
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "se3", CONF_VAT: True})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(("status", "error"), [(500, "cannot_connect"), (404, "no_prices")])
async def test_config_flow_errors_and_recovery(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory, status: int, error: str
):
    freezer.move_to(NOW)
    aioclient_mock.get(TODAY_URL, status=status)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "se3", CONF_VAT: True})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_ZONE: "se3", CONF_VAT: True})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_switches_vat_and_reloads(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
):
    freezer.move_to(NOW)
    mock_api(aioclient_mock)
    entry = await setup(hass)
    assert hass.states.get("sensor.spotwatts_se3_price").state == "0.25"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_VAT: False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.spotwatts_se3_price").state == "0.2"
    assert hass.states.get("sensor.spotwatts_se3_price").attributes["vat_included"] is False


async def test_sensors_before_the_auction(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
):
    freezer.move_to(NOW)
    mock_api(aioclient_mock)
    await setup(hass)

    # 10:05 in Stockholm is in the quarter 10:00-10:15, priced 0.2 + 25 % VAT
    price = hass.states.get("sensor.spotwatts_se3_price")
    assert price.state == "0.25"
    assert price.attributes["start"] == "2026-11-12T10:00:00+01:00"
    assert price.attributes["unit_of_measurement"] == "SEK/kWh"
    assert len(price.attributes["today"]) == 96
    assert price.attributes["tomorrow"] == []
    assert price.attributes["tomorrow_valid"] is False
    assert price.attributes["attribution"].startswith("Prices: Spotwatts")

    assert hass.states.get("sensor.spotwatts_se3_lowest_today").state == "0.25"
    assert hass.states.get("sensor.spotwatts_se3_highest_today").state == "3.75"
    assert hass.states.get("sensor.spotwatts_se3_average_tomorrow").state == "unknown"

    # The cheap hour is under way: the cheapest whole hour starting from now is 10:15-11:15
    assert hass.states.get("sensor.spotwatts_se3_cheapest_hour").state == "2026-11-12T09:15:00+00:00"

    assert requested(aioclient_mock, TOMORROW_URL) == 0


@pytest.mark.parametrize("vat", [True, False])
async def test_tomorrow_after_the_auction(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory, vat: bool
):
    freezer.move_to(AFTER_AUCTION)
    mock_api(aioclient_mock, tomorrow=200)
    await setup(hass, vat)

    factor = 1.25 if vat else 1
    assert float(hass.states.get("sensor.spotwatts_se3_average_tomorrow").state) == pytest.approx(0.5 * factor)
    price = hass.states.get("sensor.spotwatts_se3_price")
    assert price.attributes["tomorrow_valid"] is True
    assert len(price.attributes["raw_tomorrow"]) == 96
    # Tomorrow's 0.5 beats today's 3: the 4-hour window starts at tomorrow's midnight
    assert hass.states.get("sensor.spotwatts_se3_cheapest_4_hours").state == "2026-11-12T23:00:00+00:00"


async def test_a_failed_tomorrow_keeps_today(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
):
    freezer.move_to(AFTER_AUCTION)
    mock_api(aioclient_mock, tomorrow=500)
    await setup(hass)

    assert hass.states.get("sensor.spotwatts_se3_price").state == "3.75"
    assert hass.states.get("sensor.spotwatts_se3_average_tomorrow").state == "unknown"


async def test_no_requests_while_both_days_are_known_and_midnight_reuses_tomorrow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
):
    freezer.move_to(AFTER_AUCTION)
    mock_api(aioclient_mock, tomorrow=200)
    entry = await setup(hass)
    calls = aioclient_mock.call_count

    freezer.tick(1800)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == calls

    # 00:00:01 in Stockholm: tomorrow becomes today without a request, the new tomorrow is not asked for yet
    freezer.move_to(datetime(2026, 11, 12, 23, 0, 1, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.today.date.isoformat() == "2026-11-13"
    assert entry.runtime_data.data.tomorrow is None
    assert aioclient_mock.call_count == calls
    assert hass.states.get("sensor.spotwatts_se3_price").state == "0.625"


async def test_a_started_window_is_kept_until_it_ends(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
):
    freezer.move_to(datetime(2026, 11, 12, 8, 50, tzinfo=UTC))  # 9:50 in Stockholm
    mock_api(aioclient_mock)
    await setup(hass)
    assert hass.states.get("sensor.spotwatts_se3_cheapest_hour").state == "2026-11-12T09:00:00+00:00"

    freezer.move_to(datetime(2026, 11, 12, 9, 30, 1, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.spotwatts_se3_cheapest_hour").state == "2026-11-12T09:00:00+00:00"

    freezer.move_to(datetime(2026, 11, 12, 10, 0, 1, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.spotwatts_se3_cheapest_hour").state != "2026-11-12T09:00:00+00:00"
