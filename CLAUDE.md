# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Home Assistant custom integration for MyCookbook (self-hosted ASP.NET Core 8 recipe/meal planning app). Distributed via HACS. No build step — Python files are loaded directly by Home Assistant.

For reference on the MyCookbook backend API (request/response shapes, endpoint behaviour, auth flow), see the sibling repository at `../MyCookbook`.

## Development Commands

There is no local test runner configured. To validate the integration:
- Load it into a Home Assistant dev instance (e.g. via Docker or `hass -c config/`)
- Or use `hassfest` to validate manifest/strings: `python -m script.hassfest` (from HA core repo)

To lint:
```bash
ruff check custom_components/mycookbook/
mypy custom_components/mycookbook/
```

## Architecture

### Data Flow

```
ConfigFlow (config_flow.py)
  → validates credentials via MyCookbookApiClient.async_validate_auth()

async_setup_entry (__init__.py)
  → creates MyCookbookApiClient + MyCookbookCoordinator
  → coordinator.async_config_entry_first_refresh() (blocks startup)
  → registers four HA services: search_recipes, get_recipe_detail, add_planned_meal, delete_planned_meal

MyCookbookCoordinator (coordinator.py)
  → polls every 30 min
  → parallel asyncio.gather() of 4 date-range planner calls
  → stores dict keyed by DATA_TODAY / DATA_TOMORROW / DATA_WEEK / DATA_NEXT_WEEK

Four sensors (sensor.py) all share one DeviceInfo, extend CoordinatorEntity[MyCookbookCoordinator]
```

### Key Design Decisions

- **No PyPI dependencies** — uses `async_get_clientsession(hass)` (HA built-in aiohttp session)
- **MRO order**: `CoordinatorEntity` before `SensorEntity` in class definition
- **Services return data** via `SupportsResponse.ONLY` — callable from automations/scripts
- Week bounds use ISO week (Monday–Sunday), computed in `coordinator._week_bounds()`
- **No custom conversation entity** — natural language meal planning ("plan chicken for Tuesday") is handled by native HA Assist intent scripts that call the exposed `add_planned_meal` / `delete_planned_meal` services. Keep NLU in HA, not in this integration.

### API Client (`api.py`)

- All data models are dataclasses with `from_dict()` classmethods
- `MyCookbookApiError(message, status)` is the single exception type
- Auth: `Authorization: Bearer <token>` header on every request
- `async_validate_auth()` hits `/api/tags` as a lightweight auth check

### HA Patterns

- `UpdateFailed` (not `MyCookbookApiError`) is what `_async_update_data` raises on failure
- `async_config_entry_first_refresh()` — validates connectivity at setup time
- Entities use `should_poll = False` (coordinator pushes updates)
- Re-auth flow (`async_step_reauth`) handles API key rotation without losing config

## HACS Distribution

`hacs.json` at repo root. The integration lives entirely under `custom_components/mycookbook/`. Version is in `manifest.json` — bump it on every release.
