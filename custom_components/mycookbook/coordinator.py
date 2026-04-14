"""DataUpdateCoordinator for MyCookbook."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MyCookbookApiClient, MyCookbookApiError
from .const import DATA_MEALS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _week_bounds(today: date) -> tuple[date, date]:
    """Return the Monday and Sunday of the ISO week containing *today*."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


class MyCookbookCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that fetches upcoming meal plan data on a schedule."""

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
        _, next_week_end = _week_bounds(today + timedelta(weeks=2))

        try:
            async with asyncio.timeout(15):
                meals = await self.client.async_get_planned_meals(today, next_week_end)
        except MyCookbookApiError as err:
            raise UpdateFailed(f"MyCookbook API error: {err}") from err

        return {DATA_MEALS: meals}
