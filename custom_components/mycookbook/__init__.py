"""MyCookbook Home Assistant integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import MyCookbookApiClient, MyCookbookApiError
from .const import CONF_API_KEY, CONF_API_URL, DOMAIN
from .coordinator import MyCookbookCoordinator

PLATFORMS = [Platform.SENSOR]


def _get_client(hass: HomeAssistant) -> MyCookbookApiClient:
    entry_id = next(iter(hass.data[DOMAIN]))
    coordinator: MyCookbookCoordinator = hass.data[DOMAIN][entry_id]
    return coordinator.client


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyCookbook from a config entry."""
    session = async_get_clientsession(hass)
    client = MyCookbookApiClient(
        session,
        entry.data[CONF_API_URL],
        entry.data[CONF_API_KEY],
    )
    coordinator = MyCookbookCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_search_recipes(call: ServiceCall) -> ServiceResponse:
        client = _get_client(hass)
        try:
            recipes = await client.async_get_recipes(
                search=call.data.get("query", ""),
                category=call.data.get("category", ""),
                tag=call.data.get("tag", ""),
            )
        except MyCookbookApiError as err:
            return {"recipes": [], "error": str(err)}
        return {
            "recipes": [
                {
                    "guid": r.guid,
                    "name": r.name,
                    "category": r.category,
                    "duration_minutes": r.duration,
                    "servings": r.servings,
                    "tags": r.tags,
                }
                for r in recipes
            ]
        }

    async def handle_get_recipe_detail(call: ServiceCall) -> ServiceResponse:
        client = _get_client(hass)
        try:
            r = await client.async_get_recipe(call.data["guid"])
        except MyCookbookApiError as err:
            return {"error": str(err)}
        return {
            "guid": r.guid,
            "name": r.name,
            "category": r.category,
            "duration_minutes": r.duration,
            "servings": r.servings,
            "tags": r.tags,
            "ingredients": [
                {"name": i.name, "amount": i.amount}
                for i in sorted(r.ingredients, key=lambda x: x.order)
            ],
            "steps": [
                {
                    "order": s.order,
                    "description": s.description,
                    "duration_seconds": s.duration_seconds,
                    "type": s.step_type,
                }
                for s in sorted(r.steps, key=lambda x: x.order)
            ],
        }

    async def handle_add_planned_meal(call: ServiceCall) -> ServiceResponse:
        client = _get_client(hass)
        try:
            from datetime import date as _date
            meal_date = _date.fromisoformat(call.data["date"])
            meal = await client.async_add_planned_meal(
                recipe_guid=call.data["recipe_guid"],
                meal_date=meal_date,
                from_fridge=call.data.get("from_fridge", False),
            )
        except (MyCookbookApiError, ValueError) as err:
            return {"error": str(err)}
        # Refresh coordinator so sensors reflect the new meal
        for coord in hass.data[DOMAIN].values():
            await coord.async_request_refresh()
        return {
            "id": meal.id,
            "recipe_name": meal.recipe_name,
            "date": meal.date.isoformat(),
        }

    async def handle_delete_planned_meal(call: ServiceCall) -> ServiceResponse:
        client = _get_client(hass)
        try:
            await client.async_delete_planned_meal(call.data["meal_id"])
        except MyCookbookApiError as err:
            return {"error": str(err)}
        for coord in hass.data[DOMAIN].values():
            await coord.async_request_refresh()
        return {"deleted": True}

    hass.services.async_register(
        DOMAIN,
        "search_recipes",
        handle_search_recipes,
        schema=vol.Schema(
            {
                vol.Optional("query"): cv.string,
                vol.Optional("category"): cv.string,
                vol.Optional("tag"): cv.string,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "get_recipe_detail",
        handle_get_recipe_detail,
        schema=vol.Schema({vol.Required("guid"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "add_planned_meal",
        handle_add_planned_meal,
        schema=vol.Schema(
            {
                vol.Required("recipe_guid"): cv.string,
                vol.Required("date"): cv.string,
                vol.Optional("from_fridge", default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "delete_planned_meal",
        handle_delete_planned_meal,
        schema=vol.Schema({vol.Required("meal_id"): vol.Coerce(int)}),
        supports_response=SupportsResponse.ONLY,
    )

    panel_url = f"{entry.data[CONF_API_URL]}?token={entry.data[CONF_API_KEY]}"
    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="MyCookbook",
        sidebar_icon="mdi:chef-hat",
        frontend_url_path="mycookbook",
        config={"url": panel_url},
        require_admin=False,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        async_remove_panel(hass, "mycookbook")
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            for svc in ("search_recipes", "get_recipe_detail", "add_planned_meal", "delete_planned_meal"):
                hass.services.async_remove(DOMAIN, svc)
    return unload_ok
