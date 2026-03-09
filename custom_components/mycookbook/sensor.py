"""Sensor platform for MyCookbook."""
from __future__ import annotations

from datetime import date, timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_NEXT_WEEK, DATA_TODAY, DATA_TOMORROW, DATA_WEEK, DOMAIN
from .coordinator import MyCookbookCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MyCookbook sensors."""
    coordinator: MyCookbookCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MyCookbookTodaySensor(coordinator, entry.entry_id),
            MyCookbookTomorrowSensor(coordinator, entry.entry_id),
            MyCookbookWeekSensor(coordinator, entry.entry_id),
            MyCookbookNextWeekSensor(coordinator, entry.entry_id),
        ]
    )


class MyCookbookSensorBase(CoordinatorEntity[MyCookbookCoordinator], SensorEntity):
    """Base class for MyCookbook sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "meals"

    def __init__(self, coordinator: MyCookbookCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="MyCookbook",
            manufacturer="MyCookbook",
            model="Meal Planner",
        )


class MyCookbookTodaySensor(MyCookbookSensorBase):
    """Sensor for today's planned meals."""

    _attr_name = "Meals Today"
    _attr_icon = "mdi:food"

    def __init__(self, coordinator: MyCookbookCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_meals_today"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data[DATA_TODAY])

    @property
    def extra_state_attributes(self) -> dict:
        meals = self.coordinator.data[DATA_TODAY]
        return {
            "date": date.today().isoformat(),
            "meals": [
                {
                    "name": m.recipe_name,
                    "recipe_guid": m.recipe_guid,
                    "from_fridge": m.from_fridge,
                }
                for m in meals
            ],
        }


class MyCookbookTomorrowSensor(MyCookbookSensorBase):
    """Sensor for tomorrow's planned meals."""

    _attr_name = "Meals Tomorrow"
    _attr_icon = "mdi:food-outline"

    def __init__(self, coordinator: MyCookbookCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_meals_tomorrow"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data[DATA_TOMORROW])

    @property
    def extra_state_attributes(self) -> dict:
        meals = self.coordinator.data[DATA_TOMORROW]
        return {
            "date": (date.today() + timedelta(days=1)).isoformat(),
            "meals": [
                {
                    "name": m.recipe_name,
                    "recipe_guid": m.recipe_guid,
                    "from_fridge": m.from_fridge,
                }
                for m in meals
            ],
        }


class MyCookbookWeekSensor(MyCookbookSensorBase):
    """Sensor for this week's planned meals."""

    _attr_name = "Meals This Week"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator: MyCookbookCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_meals_this_week"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data[DATA_WEEK])

    @property
    def extra_state_attributes(self) -> dict:
        meals = self.coordinator.data[DATA_WEEK]
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Group meal names by date
        days: dict[str, list[str]] = {}
        for i in range(7):
            day = (week_start + timedelta(days=i)).isoformat()
            days[day] = []
        for m in meals:
            day_key = m.date.isoformat()
            if day_key in days:
                days[day_key].append(m.recipe_name)

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "days": days,
            "total_meals": len(meals),
        }


class MyCookbookNextWeekSensor(MyCookbookSensorBase):
    """Sensor for next week's planned meals."""

    _attr_name = "Meals Next Week"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator: MyCookbookCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_meals_next_week"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data[DATA_NEXT_WEEK])

    @property
    def extra_state_attributes(self) -> dict:
        meals = self.coordinator.data[DATA_NEXT_WEEK]
        today = date.today()
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
        week_end = week_start + timedelta(days=6)

        days: dict[str, list[str]] = {}
        for i in range(7):
            day = (week_start + timedelta(days=i)).isoformat()
            days[day] = []
        for m in meals:
            day_key = m.date.isoformat()
            if day_key in days:
                days[day_key].append(m.recipe_name)

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "days": days,
            "total_meals": len(meals),
        }
