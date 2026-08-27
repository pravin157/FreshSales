"""
Thin wrapper around the Freshsales (Freshworks CRM) REST API.

API docs: https://developers.freshworks.com/crm/api/

Auth: Token-based, sent as:
    Authorization: Token token=<api_key>

Base URL format (current, unified Freshworks accounts):
    https://<bundle-alias>.myfreshworks.com/crm/sales/api

Note: "view-based" entities (contacts, leads, deals, sales_accounts) do NOT
support a plain `GET /api/contacts` listing. You must first fetch that
entity's saved filters (`GET /api/contacts/filters`) to get a view_id, then
list with `GET /api/contacts/view/<view_id>`. This client's list_entities()
handles that automatically if you don't pass a view_id (it picks the
default filter). Tasks and appointments use a simpler flat endpoint with an
optional `filter` query param instead.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class FreshsalesError(Exception):
    """Raised when the Freshsales API returns an error response."""

    def __init__(self, status_code: int, message: str, body: Any = None):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Freshsales API error {status_code}: {message}")


class FreshsalesClient:
    """Synchronous-style client (using httpx's sync API) for Freshsales CRM."""

    def __init__(self, domain: Optional[str] = None, api_key: Optional[str] = None, timeout: float = 30.0):
        domain = domain or os.environ.get("FRESHSALES_DOMAIN")
        api_key = api_key or os.environ.get("FRESHSALES_API_KEY")

        if not domain:
            raise ValueError(
                "Freshsales domain not set. Pass domain= or set FRESHSALES_DOMAIN "
                "(e.g. 'yourcompany' for yourcompany.freshsales.io)."
            )
        if not api_key:
            raise ValueError(
                "Freshsales API key not set. Pass api_key= or set FRESHSALES_API_KEY."
            )

        # Allow user to pass a full URL, a full host, or a bare bundle alias.
        domain = domain.strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            # Strip to bare host, then re-run the same host-based logic
            # below so a pasted URL and a pasted host behave identically.
            domain = domain.split("://", 1)[1].rstrip("/")

        if domain.endswith("/api") or "/crm/sales/api" in domain:
            # Caller already gave the exact API base — use as-is.
            base_url = f"https://{domain}" if not domain.startswith("http") else domain
            base_url = base_url.rstrip("/")
        elif ".myfreshworks.com" in domain or ".freshworks.com" in domain:
            # Current unified Freshworks accounts: /crm/sales/api
            base_url = f"https://{domain}/crm/sales/api"
        elif ".freshsales.io" in domain:
            # Legacy classic Freshsales accounts: no /crm/sales segment
            base_url = f"https://{domain}/api"
        else:
            # Bare bundle alias (e.g. "acmecorp") -> assume current
            # unified format, since that's what new/most accounts use.
            base_url = f"https://{domain}.myfreshworks.com/crm/sales/api"

        self.base_url = base_url
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Token token={api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def close(self):
        self._client.close()

    # -- low level -----------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                message = body.get("message") or body.get("error") or str(body)
            except Exception:
                body = resp.text
                message = resp.text
            raise FreshsalesError(resp.status_code, message, body)
        if resp.status_code == 204 or not resp.content:
            return {"success": True}
        return resp.json()

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Optional[dict] = None) -> Any:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: Optional[dict] = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # -- generic entity CRUD helpers -----------------------------------
    # Freshsales uses a consistent pattern per entity type: contacts,
    # leads, deals, tasks, notes, appointments, sales_accounts, etc.
    # Each is wrapped as: {"<entity_singular>": {...fields...}}

    # Entities that require a saved view to list (no flat "GET /entity").
    _VIEW_BASED_ENTITIES = {"contacts", "deals", "sales_accounts", "leads"}

    def get_filters(self, entity: str) -> Any:
        """Fetch saved views/filters for a view-based entity."""
        return self.get(f"/{entity}/filters")

    def _default_view_id(self, entity: str) -> int:
        data = self.get_filters(entity)
        filters = data.get("filters", []) if isinstance(data, dict) else []
        if not filters:
            raise FreshsalesError(
                404,
                f"No saved views/filters found for '{entity}' — cannot list without a view_id.",
                data,
            )
        return filters[0]["id"]

    def list_entities(self, entity: str, page: int = 1, per_page: int = 30,
                       view_id: Optional[int] = None, filter_id: Optional[int] = None,
                       sort: Optional[str] = None, sort_type: Optional[str] = None,
                       include: Optional[str] = None) -> Any:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if filter_id is not None:
            params["filter_id"] = filter_id
        if sort:
            params["sort"] = sort
        if sort_type:
            params["sort_type"] = sort_type
        if include:
            params["include"] = include

        if entity in self._VIEW_BASED_ENTITIES:
            # contacts/deals/sales_accounts/leads can't be listed flat —
            # they must be listed against a saved view.
            resolved_view_id = view_id if view_id is not None else self._default_view_id(entity)
            return self.get(f"/{entity}/view/{resolved_view_id}", params=params)

        # tasks, appointments, sales_activities etc. support flat listing.
        if view_id is not None:
            params["view_id"] = view_id
        return self.get(f"/{entity}", params=params)

    def get_entity(self, entity: str, entity_id: int, include: Optional[str] = None) -> Any:
        params = {"include": include} if include else None
        return self.get(f"/{entity}/{entity_id}", params=params)

    def create_entity(self, entity: str, singular: str, fields: dict) -> Any:
        return self.post(f"/{entity}", json={singular: fields})

    def update_entity(self, entity: str, singular: str, entity_id: int, fields: dict) -> Any:
        return self.put(f"/{entity}/{entity_id}", json={singular: fields})

    def delete_entity(self, entity: str, entity_id: int) -> Any:
        return self.delete(f"/{entity}/{entity_id}")

    def search(self, query: str, entities: Optional[str] = None) -> Any:
        """
        Global search across entities (contacts, deals, accounts...).
        entities: comma-separated list to restrict scope, e.g. "contact,deal,sales_account"
        Note: unified Freshworks accounts (post-2020) generally don't have a
        separate "lead" entity — leads are merged into contacts.
        """
        params = {"q": query}
        if entities:
            params["include"] = entities
        return self.get("/search", params=params)

    # -- notes are attached to a specific parent (targetable_type/id) ---

    def list_notes(self, targetable_type: str, targetable_id: int) -> Any:
        return self.get(f"/{targetable_type}/{targetable_id}/notes")

    def create_note(self, targetable_type: str, targetable_id: int, description: str) -> Any:
        return self.post(
            f"/{targetable_type}/{targetable_id}/notes",
            json={"note": {"description": description, "targetable_type": targetable_type.rstrip("s").capitalize(), "targetable_id": targetable_id}},
        )
