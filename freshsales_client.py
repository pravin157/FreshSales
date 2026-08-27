"""
Full-coverage wrapper around the Freshsales (Freshworks CRM) REST API.

API docs: https://developers.freshworks.com/crm/api/

Auth: Token-based, sent as:
    Authorization: Token token=<api_key>

Base URL format (current, unified Freshworks accounts):
    https://<bundle-alias>.myfreshworks.com/crm/sales/api

Key API quirks this client handles for you:
- "View-based" entities (contacts, sales_accounts, deals, leads) do NOT
  support a plain `GET /api/<entity>` listing. You must first fetch that
  entity's saved filters (`GET /api/<entity>/filters`) to get a view_id,
  then list with `GET /api/<entity>/view/<view_id>`. list_entities()
  handles this automatically if you don't pass a view_id.
- Tasks, appointments, sales_activities support flat listing with an
  optional `filter` query param instead.
- Products and Documents live under a `/cpq/` prefix with their own
  bulk-operation naming.
- Notes are NOT listed via their own endpoint — they're fetched by
  requesting `include=notes` on the parent entity (contact/deal/account).
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

    # Entities that require a saved view to list (no flat "GET /entity").
    _VIEW_BASED_ENTITIES = {"contacts", "deals", "sales_accounts", "leads"}

    # Map plural entity name -> singular key used in request/response JSON.
    _SINGULAR = {
        "contacts": "contact",
        "deals": "deal",
        "sales_accounts": "sales_account",
        "leads": "lead",
        "tasks": "task",
        "appointments": "appointment",
        "sales_activities": "sales_activity",
        "notes": "note",
    }

    def __init__(self, domain: Optional[str] = None, api_key: Optional[str] = None, timeout: float = 30.0):
        domain = domain or os.environ.get("FRESHSALES_DOMAIN")
        api_key = api_key or os.environ.get("FRESHSALES_API_KEY")

        if not domain:
            raise ValueError(
                "Freshsales domain not set. Pass domain= or set FRESHSALES_DOMAIN "
                "(e.g. 'yourcompany.myfreshworks.com')."
            )
        if not api_key:
            raise ValueError(
                "Freshsales API key not set. Pass api_key= or set FRESHSALES_API_KEY. "
                "Use the CRM API key, not the Chat/Freshchat one."
            )

        # Allow user to pass a full URL, a full host, or a bare bundle alias.
        domain = domain.strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            domain = domain.split("://", 1)[1].rstrip("/")

        if domain.endswith("/api") or "/crm/sales/api" in domain:
            base_url = f"https://{domain}".rstrip("/")
        elif ".myfreshworks.com" in domain or ".freshworks.com" in domain:
            base_url = f"https://{domain}/crm/sales/api"
        elif ".freshsales.io" in domain:
            base_url = f"https://{domain}/api"
        else:
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
                message = body.get("message") or body.get("error") or body.get("errors") or str(body)
            except Exception:
                body = resp.text
                message = resp.text
            raise FreshsalesError(resp.status_code, message, body)
        if resp.status_code == 204 or not resp.content:
            return {"success": True}
        try:
            return resp.json()
        except Exception:
            return {"success": True, "raw": resp.text}

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: Optional[dict] = None, files: Optional[dict] = None, data: Optional[dict] = None) -> Any:
        if files is not None:
            headers = {k: v for k, v in self._client.headers.items() if k.lower() != "content-type"}
            return self._request("POST", path, data=data, files=files, headers=headers)
        return self._request("POST", path, json=json)

    def put(self, path: str, json: Optional[dict] = None) -> Any:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def _singular(self, entity: str) -> str:
        return self._SINGULAR.get(entity, entity.rstrip("s"))

    # ===================================================================
    # Generic view-based / flat entity CRUD
    # (contacts, deals, sales_accounts, leads, tasks, appointments,
    #  sales_activities)
    # ===================================================================

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
                       view_id: Optional[int] = None,
                       sort: Optional[str] = None, sort_type: Optional[str] = None,
                       include: Optional[str] = None, filter: Optional[str] = None) -> Any:
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if sort:
            params["sort"] = sort
        if sort_type:
            params["sort_type"] = sort_type
        if include:
            params["include"] = include

        if entity in self._VIEW_BASED_ENTITIES:
            resolved_view_id = view_id if view_id is not None else self._default_view_id(entity)
            return self.get(f"/{entity}/view/{resolved_view_id}", params=params)

        if filter:
            params["filter"] = filter
        return self.get(f"/{entity}", params=params)

    def get_entity(self, entity: str, entity_id: int, include: Optional[str] = None) -> Any:
        params = {"include": include} if include else None
        return self.get(f"/{entity}/{entity_id}", params=params)

    def create_entity(self, entity: str, fields: dict) -> Any:
        return self.post(f"/{entity}", json={self._singular(entity): fields})

    def update_entity(self, entity: str, entity_id: int, fields: dict) -> Any:
        return self.put(f"/{entity}/{entity_id}", json={self._singular(entity): fields})

    def delete_entity(self, entity: str, entity_id: int) -> Any:
        return self.delete(f"/{entity}/{entity_id}")

    def forget_entity(self, entity: str, entity_id: int) -> Any:
        """Hard-delete an entity and all associated data. Irreversible."""
        return self.delete(f"/{entity}/{entity_id}/forget")

    def clone_entity(self, entity: str, entity_id: int, overrides: Optional[dict] = None) -> Any:
        payload = {self._singular(entity): overrides} if overrides else {}
        return self.post(f"/{entity}/{entity_id}/clone", json=payload)

    def bulk_destroy(self, entity: str, ids: list[int]) -> Any:
        return self.post(f"/{entity}/bulk_destroy", json={"selected_ids": ids})

    def bulk_assign_owner(self, entity: str, ids: list[int], owner_id: int) -> Any:
        return self.post(f"/{entity}/bulk_assign_owner", json={"selected_ids": ids, "owner_id": owner_id})

    def upsert_entity(self, entity: str, unique_identifier: dict, fields: dict) -> Any:
        return self.post(f"/{entity}/upsert", json={
            "unique_identifier": unique_identifier,
            self._singular(entity): fields,
        })

    def bulk_upsert(self, entity: str, items: list[dict]) -> Any:
        return self.post(f"/{entity}/bulk_upsert", json={entity: items})

    def manage_team_members(self, entity: str, entity_id: int, team_users: list[dict]) -> Any:
        return self.post(f"/{entity}/{entity_id}/manage_team_members", json={"team_users": team_users})

    def list_fields(self, entity: str, include_group: bool = False) -> Any:
        params = {"include": "field_group"} if include_group else None
        return self.get(f"/settings/{entity}/fields", params=params)

    def list_activities(self, entity: str, entity_id: int, include: Optional[str] = None, limit: Optional[int] = None) -> Any:
        params: dict[str, Any] = {}
        if include:
            params["include"] = include
        if limit:
            params["limit"] = limit
        return self.get(f"/{entity}/{entity_id}/activities", params=params)

    # ===================================================================
    # Notes
    # ===================================================================

    def create_note(self, targetable_type: str, targetable_id: int, description: str) -> Any:
        """targetable_type: 'Contact', 'Deal', or 'SalesAccount' (singular, capitalized)."""
        return self.post("/notes", json={
            "note": {
                "description": description,
                "targetable_type": targetable_type,
                "targetable_id": targetable_id,
            }
        })

    def update_note(self, note_id: int, description: str) -> Any:
        return self.put(f"/notes/{note_id}", json={"note": {"description": description}})

    def delete_note(self, note_id: int) -> Any:
        return self.delete(f"/notes/{note_id}")

    def list_notes_for(self, entity: str, entity_id: int) -> Any:
        """Convenience: fetch a parent record with its notes embedded."""
        return self.get_entity(entity, entity_id, include="notes")

    # ===================================================================
    # Search
    # ===================================================================

    def search(self, query: str, entities: Optional[str] = None) -> Any:
        params = {"q": query}
        if entities:
            params["include"] = entities
        return self.get("/search", params=params)

    def lookup_search(self, query: str, field: str = "email", entities: str = "contact") -> Any:
        return self.get("/lookup", params={"q": query, "f": field, "entities": entities})

    # ===================================================================
    # Marketing Lists
    # ===================================================================

    def create_list(self, name: str) -> Any:
        return self.post("/lists", json={"name": name})

    def get_all_lists(self) -> Any:
        return self.get("/lists")

    def update_list(self, list_id: int, name: str) -> Any:
        return self.put(f"/lists/{list_id}", json={"name": name})

    def get_contacts_in_list(self, list_id: int) -> Any:
        return self.get(f"/contacts/lists/{list_id}")

    def add_contacts_to_list(self, list_id: int, contact_ids: list[int]) -> Any:
        return self.put(f"/lists/{list_id}/add_contacts", json={"ids": contact_ids})

    def remove_contacts_from_list(self, list_id: int, contact_ids: Optional[list[int]] = None, all_contacts: bool = False) -> Any:
        payload = {"all": True} if all_contacts else {"ids": contact_ids or []}
        return self.put(f"/lists/{list_id}/remove_contacts", json=payload)

    def move_contacts_between_lists(self, to_list_id: int, from_list_id: int, contact_ids: Optional[list[int]] = None) -> Any:
        payload: dict[str, Any] = {"from_list_id": from_list_id}
        if contact_ids:
            payload["ids"] = contact_ids
        return self.put(f"/lists/{to_list_id}/move_contacts", json=payload)

    # ===================================================================
    # Tasks
    # ===================================================================

    def mark_task_done(self, task_id: int) -> Any:
        return self.update_entity("tasks", task_id, {"status": "COMPLETED"})

    # ===================================================================
    # Phone
    # ===================================================================

    def log_call(self, fields: dict) -> Any:
        return self.post("/phone_calls", json={"phone_call": fields})

    # ===================================================================
    # Products (CPQ)
    # ===================================================================

    def create_product(self, fields: dict) -> Any:
        return self.post("/cpq/products", json={"product": fields})

    def get_product(self, product_id: int, include_pricing: bool = False) -> Any:
        params = {"include": "product_pricings"} if include_pricing else None
        return self.get(f"/cpq/products/{product_id}", params=params)

    def update_product(self, product_id: int, fields: dict) -> Any:
        return self.put(f"/cpq/products/{product_id}", json={"product": fields})

    def delete_product(self, product_id: int) -> Any:
        return self.delete(f"/cpq/products/{product_id}")

    def restore_product(self, product_id: int) -> Any:
        return self.post(f"/cpq/products/{product_id}/restore")

    def bulk_update_products(self, updates: list[dict]) -> Any:
        return self.post("/cpq/products/products_bulk_update", json={"products": updates})

    def bulk_assign_product_owner(self, product_ids: list[int], owner_id: int) -> Any:
        return self.post("/cpq/products/products_bulk_assign", json={"selected_ids": product_ids, "owner_id": owner_id})

    def bulk_delete_products(self, product_ids: list[int]) -> Any:
        return self.post("/cpq/products/products_bulk_delete", json={"selected_ids": product_ids})

    def bulk_restore_products(self, product_ids: list[int]) -> Any:
        return self.post("/cpq/products/products_bulk_restore", json={"selected_ids": product_ids})

    # ===================================================================
    # Documents (CPQ quotes/proposals)
    # ===================================================================

    def create_cpq_document(self, fields: dict) -> Any:
        return self.post("/cpq/cpq_documents", json={"cpq_document": fields})

    def get_cpq_document(self, document_id: int, include_products: bool = False) -> Any:
        params = {"include": "products"} if include_products else None
        return self.get(f"/cpq/cpq_documents/{document_id}", params=params)

    def update_cpq_document(self, document_id: int, fields: dict) -> Any:
        return self.put(f"/cpq/cpq_documents/{document_id}", json={"cpq_document": fields})

    def delete_cpq_document(self, document_id: int) -> Any:
        return self.delete(f"/cpq/cpq_documents/{document_id}")

    def forget_cpq_document(self, document_id: int) -> Any:
        return self.delete(f"/cpq/cpq_documents/{document_id}/forget")

    def restore_cpq_document(self, document_id: int) -> Any:
        return self.post(f"/cpq/cpq_documents/{document_id}/restore")

    def get_cpq_document_related_products(self, document_id: int) -> Any:
        return self.get(f"/cpq/cpq_documents/{document_id}/related_products")

    # ===================================================================
    # Files & Links
    # ===================================================================

    def create_link(self, targetable_type: str, targetable_id: int, url: str, title: Optional[str] = None) -> Any:
        payload = {"targetable_type": targetable_type, "targetable_id": targetable_id, "url": url}
        if title:
            payload["title"] = title
        return self.post("/document_links", json={"link": payload})

    def list_files_and_links(self, contact_id: int) -> Any:
        """Freshsales exposes this specifically for contacts."""
        return self.get(f"/contacts/{contact_id}/document_associations")

    # ===================================================================
    # Job Status
    # ===================================================================

    def get_job_status(self, job_id: str) -> Any:
        return self.get(f"/job_statuses/{job_id}")

    # ===================================================================
    # Configuration / Selector metadata
    # ===================================================================

    _SELECTORS = {
        "owners", "territories", "deal_stages", "currencies", "deal_reasons",
        "deal_types", "lead_sources", "industry_types", "business_types",
        "campaigns", "deal_payment_statuses", "deal_products", "deal_pipelines",
        "contact_statuses", "sales_activity_types", "sales_activity_outcomes",
        "sales_activity_entity_types", "lifecycle_stages", "designations",
    }

    def get_selector(self, name: str) -> Any:
        if name not in self._SELECTORS:
            raise ValueError(f"Unknown selector '{name}'. Valid: {sorted(self._SELECTORS)}")
        return self.get(f"/selector/{name}")

    def get_deal_stages_for_pipeline(self, pipeline_id: int) -> Any:
        return self.get(f"/selector/deal_pipelines/{pipeline_id}/deal_stages")

    def get_sales_activity_outcomes_for_type(self, activity_type_id: int) -> Any:
        return self.get(f"/selector/sales_activity_types/{activity_type_id}/sales_activity_outcomes")

    # ===================================================================
    # Custom Modules
    # ===================================================================

    def create_custom_module(self, fields: dict) -> Any:
        return self.post("/settings/module_customizations", json=fields)

    def get_custom_module(self, module_id: int) -> Any:
        return self.get(f"/settings/module_customizations/{module_id}")

    def update_custom_module(self, module_id: int, fields: dict) -> Any:
        return self.put(f"/settings/module_customizations/{module_id}", json=fields)

    def delete_custom_module(self, module_id: int) -> Any:
        return self.delete(f"/settings/module_customizations/{module_id}")

    def create_custom_field(self, entity_type: str, form_id: int, field_def: dict) -> Any:
        return self.post(f"/settings/{entity_type}/forms/{form_id}/fields", json=field_def)

    def list_custom_module_forms(self, entity_type: str) -> Any:
        return self.get(f"/settings/{entity_type}/forms")

    def create_custom_module_record(self, entity_name: str, fields: dict) -> Any:
        return self.post(f"/custom_module/{entity_name}", json=fields)

    def get_custom_module_records(self, entity_name: str, record_id: int) -> Any:
        return self.get(f"/custom_module/{entity_name}/{record_id}")

    def update_custom_module_record(self, entity_name: str, record_id: int, fields: dict) -> Any:
        return self.put(f"/custom_module/{entity_name}/{record_id}", json=fields)

    def delete_custom_module_record(self, entity_name: str, record_id: int) -> Any:
        return self.delete(f"/custom_module/{entity_name}/{record_id}")

    def forget_custom_module_record(self, entity_name: str, record_id: int) -> Any:
        return self.delete(f"/custom_module/{entity_name}/{record_id}/forget")

    def clone_custom_module_record(self, entity_name: str, record_id: int) -> Any:
        return self.post(f"/custom_module/{entity_name}/{record_id}/clone")

    def bulk_destroy_custom_module_records(self, entity_name: str, ids: list[int]) -> Any:
        return self.post(f"/custom_module/{entity_name}/bulk_destroy", json={"selected_ids": ids})