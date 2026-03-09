"""DataUpdateCoordinator for MyCookbook."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyCookbookApiClient, MyCookbookApiError
from .const import (
    DATA_NEXT_WEEK,
    DATA_TODAY,
    DATA_TOMORROW,
    DATA_WEEK,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _week_bounds(today: date) -> tuple[date, date]:
    """Return the Monday and Sunday of the current ISO week."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


class MyCookbookCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that fetches all MyCookbook data on a schedule."""

    def __init__(self, hass: HomeAssistant, client: MyCookbookApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        week_start, week_end = _week_bounds(today)
        next_week_start = week_start + timedelta(weeks=1)
        next_week_end = week_end + timedelta(weeks=1)

        try:
            async with asyncio.timeout(15):
                (
                    meals_today,
                    meals_tomorrow,
                    meals_week,
                    meals_next_week,
                ) = await asyncio.gather(
                    self.client.async_get_planned_meals(today, today),
                    self.client.async_get_planned_meals(tomorrow, tomorrow),
                    self.client.async_get_planned_meals(week_start, week_end),
                    self.client.async_get_planned_meals(next_week_start, next_week_end),
                )
        except MyCookbookApiError as err:
            raise UpdateFailed(f"MyCookbook API error: {err}") from err

        return {
            DATA_TODAY: meals_today,
            DATA_TOMORROW: meals_tomorrow,
            DATA_WEEK: meals_week,
            DATA_NEXT_WEEK: meals_next_week,
        }
