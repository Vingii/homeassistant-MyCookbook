"""MyCookbook Home Assistant integration."""
from __future__ import annotations

import voluptuous as vol

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "search_recipes")
            hass.services.async_remove(DOMAIN, "get_recipe_detail")
    return unload_ok
