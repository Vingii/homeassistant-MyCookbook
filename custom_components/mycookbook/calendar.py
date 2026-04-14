"""Calendar platform for MyCookbook."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .api import MyCookbookApiError, PlannedMeal
from .const import DATA_MEALS, DOMAIN
from .coordinator import MyCookbookCoordinator


def _meal_to_event(meal: PlannedMeal) -> CalendarEvent:
    """Convert a PlannedMeal to an all-day CalendarEvent."""
    return CalendarEvent(
        start=meal.date,
        end=meal.date + timedelta(days=1),
        summary=meal.recipe_name,
        description="From fridge" if meal.from_fridge else None,
        uid=str(meal.id),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MyCookbook calendar."""
    coordinator: MyCookbookCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MyCookbookCalendar(coordinator, entry.entry_id)])


class MyCookbookCalendar(CoordinatorEntity[MyCookbookCoordinator], CalendarEntity):
    """MyCookbook meal plan calendar."""

    _attr_has_entity_name = True
    _attr_name = "Meal Plan"
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: MyCookbookCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_meal_plan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="MyCookbook",
            manufacturer="MyCookbook",
            model="Meal Planner",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming or ongoing meal."""
        today = dt_util.now().date()
        upcoming = [m for m in self.coordinator.data[DATA_MEALS] if m.date >= today]
        if not upcoming:
            return None
        return _meal_to_event(min(upcoming, key=lambda m: m.date))

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return all meal events in the requested range."""
        try:
            meals = await self.coordinator.client.async_get_planned_meals(
                start_date.date(), end_date.date()
            )
        except MyCookbookApiError:
            return []
        return [_meal_to_event(m) for m in meals]
