"""MyCookbook API client."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import aiohttp


class MyCookbookApiError(Exception):
    """Exception raised for API errors."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class PlannedMeal:
    """A meal in the planner."""

    id: int
    recipe_id: int
    recipe_guid: str
    recipe_name: str
    date: date
    from_fridge: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannedMeal:
        return cls(
            id=data["id"],
            recipe_id=data["recipeId"],
            recipe_guid=str(data["recipeGuid"]),
            recipe_name=data["recipeName"],
            date=date.fromisoformat(data["date"]),
            from_fridge=data.get("fromFridge", False),
        )


@dataclass
class Ingredient:
    """A recipe ingredient."""

    id: int
    name: str
    amount: str | None
    order: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ingredient:
        return cls(
            id=data["id"],
            name=data["name"],
            amount=data.get("amount"),
            order=data["order"],
        )


@dataclass
class Step:
    """A recipe step."""

    id: int
    description: str
    order: int
    duration_seconds: int | None
    step_type: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        return cls(
            id=data["id"],
            description=data["description"],
            order=data["order"],
            duration_seconds=data.get("durationSeconds"),
            step_type=data.get("stepType", "Active"),
        )


@dataclass
class Recipe:
    """A recipe."""

    guid: str
    name: str
    category: str | None
    duration: int | None
    duration_text: str
    servings: int
    last_cooked: date | None
    is_favorite: bool
    tags: list[str]
    ingredients: list[Ingredient] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        last_cooked = None
        if data.get("lastCooked"):
            try:
                last_cooked = date.fromisoformat(data["lastCooked"][:10])
            except (ValueError, TypeError):
                pass

        return cls(
            guid=str(data["guid"]),
            name=data["name"],
            category=data.get("category"),
            duration=data.get("duration"),
            duration_text=data.get("durationText", ""),
            servings=data.get("servings", 1),
            last_cooked=last_cooked,
            is_favorite=data.get("isFavorite", False),
            tags=data.get("tags", []),
            ingredients=[
                Ingredient.from_dict(i) for i in data.get("ingredients", [])
            ],
            steps=[Step.from_dict(s) for s in data.get("steps", [])],
        )


class MyCookbookApiClient:
    """Async HTTP client for the MyCookbook API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(
                url, headers=self._headers, params=params
            ) as resp:
                if resp.status == 401:
                    raise MyCookbookApiError("Invalid API key", status=401)
                if resp.status != 200:
                    raise MyCookbookApiError(
                        f"API returned {resp.status}", status=resp.status
                    )
                return await resp.json()
        except aiohttp.ClientConnectorError as err:
            raise MyCookbookApiError(f"Cannot connect: {err}") from err
        except aiohttp.ClientError as err:
            raise MyCookbookApiError(f"Request failed: {err}") from err

    async def async_validate_auth(self) -> bool:
        """Validate auth by fetching tags (lightweight endpoint)."""
        await self._get("/api/tags")
        return True

    async def async_get_planned_meals(
        self, from_date: date, to_date: date
    ) -> list[PlannedMeal]:
        """Fetch planned meals for a date range."""
        data = await self._get(
            "/api/planner",
            params={"from": from_date.isoformat(), "to": to_date.isoformat()},
        )
        return [PlannedMeal.from_dict(item) for item in data]

    async def async_get_recipes(
        self,
        search: str = "",
        category: str = "",
        tag: str = "",
    ) -> list[Recipe]:
        """Fetch all recipes with optional filters."""
        params: dict[str, str] = {}
        if search:
            params["search"] = search
        if category:
            params["category"] = category
        if tag:
            params["tag"] = tag
        data = await self._get("/api/recipes", params=params or None)
        return [Recipe.from_dict(item) for item in data]

    async def async_get_recipe(self, guid: str) -> Recipe:
        """Fetch a single recipe by GUID."""
        data = await self._get(f"/api/recipes/{guid}")
        return Recipe.from_dict(data)

    async def async_get_random_recipe(self) -> Recipe:
        """Fetch a random recipe."""
        data = await self._get("/api/recipes/random")
        return Recipe.from_dict(data)

    async def async_get_tags(self) -> list[str]:
        """Fetch all tags."""
        return await self._get("/api/tags")
