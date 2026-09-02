"""
Freshsales MCP Server — Remote HTTP (Streamable HTTP transport)

Exposes every documented Freshsales module as MCP tools via a remote
Streamable-HTTP endpoint at /mcp, suitable for hosting on Railway, Render,
or Vercel and connecting from Claude Desktop or any remote MCP client.

Environment variables:
    FRESHSALES_DOMAIN  — e.g. yourcompany.myfreshworks.com
    FRESHSALES_API_KEY — Freshsales CRM API key
    MCP_AUTH_TOKEN     — (optional) Bearer token to protect /mcp
    ALLOWED_ORIGINS    — comma-separated CORS origins (default: *)
    PORT               — HTTP port for local dev (default: 8000)

Local dev:
    uvicorn server:app --reload --port 8000

Vercel / Railway: the `app` variable is the ASGI entry-point.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer as FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from freshsales_client import FreshsalesClient, FreshsalesError

load_dotenv()

# Logging — never log API keys, tokens, or sensitive payload data.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("freshsales-mcp")

mcp = FastMCP("freshsales")

_client: Optional[FreshsalesClient] = None


def get_client() -> FreshsalesClient:
    global _client
    if _client is None:
        logger.info("Freshsales client initialized")
        _client = FreshsalesClient()
    return _client


def _safe(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except FreshsalesError as e:
        logger.error("Freshsales API error [%s]: %s", e.status_code, str(e))
        return {"error": True, "status_code": e.status_code, "message": str(e), "details": e.body}
    except ValueError as e:
        logger.error("Invalid argument: %s", str(e))
        return {"error": True, "message": str(e)}


# =======================================================================
# Contacts
# =======================================================================

@mcp.tool()
def list_contacts(page: int = 1, per_page: int = 30, view_id: Optional[int] = None,
                   sort: Optional[str] = None, sort_type: Optional[str] = None) -> Any:
    """List contacts, paginated. Uses your default saved view unless view_id is given.
    sort options: lead_score, created_at, updated_at, open_deals_amount, last_contacted."""
    return _safe(get_client().list_entities, "contacts", page, per_page, view_id, sort, sort_type)


@mcp.tool()
def get_contact(contact_id: int, include: Optional[str] = None) -> Any:
    """Get a contact by ID. include (comma-separated): owner, creater, updater, source,
    campaign, tasks, appointments, notes, deals, sales_accounts, territory."""
    return _safe(get_client().get_entity, "contacts", contact_id, include)


@mcp.tool()
def create_contact(fields: dict) -> Any:
    """Create a contact. fields e.g. {"first_name":"Jane","last_name":"Doe","email":"jane@x.com"}."""
    return _safe(get_client().create_entity, "contacts", fields)


@mcp.tool()
def update_contact(contact_id: int, fields: dict) -> Any:
    """Update fields on a contact by ID."""
    return _safe(get_client().update_entity, "contacts", contact_id, fields)


@mcp.tool()
def upsert_contact(unique_identifier: dict, fields: dict) -> Any:
    """Create-or-update a contact matched on a unique field, e.g.
    unique_identifier={"emails":"jane@x.com"}."""
    return _safe(get_client().upsert_entity, "contacts", unique_identifier, fields)


@mcp.tool()
def clone_contact(contact_id: int, overrides: Optional[dict] = None) -> Any:
    """Clone a contact, optionally overriding some fields on the copy."""
    return _safe(get_client().clone_entity, "contacts", contact_id, overrides)


@mcp.tool()
def delete_contact(contact_id: int) -> Any:
    """Soft-delete a contact by ID."""
    return _safe(get_client().delete_entity, "contacts", contact_id)


@mcp.tool()
def forget_contact(contact_id: int) -> Any:
    """Permanently hard-delete a contact and all associated data. Irreversible."""
    return _safe(get_client().forget_entity, "contacts", contact_id)


@mcp.tool()
def bulk_delete_contacts(contact_ids: list[int]) -> Any:
    """Delete multiple contacts at once."""
    return _safe(get_client().bulk_destroy, "contacts", contact_ids)


@mcp.tool()
def bulk_assign_contact_owner(contact_ids: list[int], owner_id: int) -> Any:
    """Assign an owner to multiple contacts at once."""
    return _safe(get_client().bulk_assign_owner, "contacts", contact_ids, owner_id)


@mcp.tool()
def list_contact_fields(include_group: bool = False) -> Any:
    """List all contact fields, including custom fields and their IDs/types."""
    return _safe(get_client().list_fields, "contacts", include_group)


@mcp.tool()
def list_contact_activities(contact_id: int, limit: Optional[int] = None) -> Any:
    """Get the activity/timeline feed for a contact (stage changes, emails, calls, etc.)."""
    return _safe(get_client().list_activities, "contacts", contact_id, "user", limit)


# =======================================================================
# Accounts (Sales Accounts)
# =======================================================================

@mcp.tool()
def list_accounts(page: int = 1, per_page: int = 30, view_id: Optional[int] = None,
                   sort: Optional[str] = None, sort_type: Optional[str] = None) -> Any:
    """List accounts (companies), paginated. sort options: open_deals_amount,
    created_at, updated_at, last_contacted."""
    return _safe(get_client().list_entities, "sales_accounts", page, per_page, view_id, sort, sort_type)


@mcp.tool()
def get_account(account_id: int, include: Optional[str] = None) -> Any:
    """Get an account by ID. include: owner, creater, updater, territory, business_type,
    tasks, appointments, contacts, deals, industry_type, child_sales_accounts."""
    return _safe(get_client().get_entity, "sales_accounts", account_id, include)


@mcp.tool()
def create_account(fields: dict) -> Any:
    """Create an account. fields e.g. {"name":"Acme Inc","website":"acme.com"}."""
    return _safe(get_client().create_entity, "sales_accounts", fields)


@mcp.tool()
def update_account(account_id: int, fields: dict) -> Any:
    """Update fields on an account by ID."""
    return _safe(get_client().update_entity, "sales_accounts", account_id, fields)


@mcp.tool()
def upsert_account(unique_identifier: dict, fields: dict) -> Any:
    """Create-or-update an account matched on a unique field."""
    return _safe(get_client().upsert_entity, "sales_accounts", unique_identifier, fields)


@mcp.tool()
def clone_account(account_id: int, overrides: Optional[dict] = None) -> Any:
    """Clone an account, optionally overriding some fields on the copy."""
    return _safe(get_client().clone_entity, "sales_accounts", account_id, overrides)


@mcp.tool()
def delete_account(account_id: int) -> Any:
    """Soft-delete an account by ID."""
    return _safe(get_client().delete_entity, "sales_accounts", account_id)


@mcp.tool()
def forget_account(account_id: int) -> Any:
    """Permanently hard-delete an account and all associated data. Irreversible."""
    return _safe(get_client().forget_entity, "sales_accounts", account_id)


@mcp.tool()
def bulk_delete_accounts(account_ids: list[int]) -> Any:
    """Delete multiple accounts at once."""
    return _safe(get_client().bulk_destroy, "sales_accounts", account_ids)


@mcp.tool()
def list_account_fields(include_group: bool = False) -> Any:
    """List all account fields, including custom fields."""
    return _safe(get_client().list_fields, "sales_accounts", include_group)


@mcp.tool()
def list_account_activities(account_id: int, limit: Optional[int] = None) -> Any:
    """Get the activity/timeline feed for an account."""
    return _safe(get_client().list_activities, "sales_accounts", account_id, "user", limit)


# =======================================================================
# Deals
# =======================================================================

@mcp.tool()
def list_deals(page: int = 1, per_page: int = 30, view_id: Optional[int] = None,
                sort: Optional[str] = None, sort_type: Optional[str] = None) -> Any:
    """List deals, paginated. Use get_selector('deal_pipelines') and
    get_selector('deal_stages') to see valid pipeline/stage IDs first."""
    return _safe(get_client().list_entities, "deals", page, per_page, view_id, sort, sort_type)


@mcp.tool()
def get_deal(deal_id: int, include: Optional[str] = None) -> Any:
    """Get a deal by ID. include: owner, creater, updater, contacts, sales_account,
    deal_stage, deal_pipeline, deal_type, deal_reason, tasks, appointments, notes, products."""
    return _safe(get_client().get_entity, "deals", deal_id, include)


@mcp.tool()
def create_deal(fields: dict) -> Any:
    """Create a deal. fields e.g. {"name":"Acme - Q3","amount":15000,"deal_stage_id":1,
    "deal_pipeline_id":1}. Use get_selector to find valid stage/pipeline IDs."""
    return _safe(get_client().create_entity, "deals", fields)


@mcp.tool()
def update_deal(deal_id: int, fields: dict) -> Any:
    """Update fields on a deal by ID — e.g. move stage, change amount."""
    return _safe(get_client().update_entity, "deals", deal_id, fields)


@mcp.tool()
def upsert_deal(unique_identifier: dict, fields: dict) -> Any:
    """Create-or-update a deal matched on a unique field (e.g. external_id)."""
    return _safe(get_client().upsert_entity, "deals", unique_identifier, fields)


@mcp.tool()
def clone_deal(deal_id: int, overrides: Optional[dict] = None) -> Any:
    """Clone a deal, optionally overriding some fields on the copy."""
    return _safe(get_client().clone_entity, "deals", deal_id, overrides)


@mcp.tool()
def delete_deal(deal_id: int) -> Any:
    """Soft-delete a deal by ID."""
    return _safe(get_client().delete_entity, "deals", deal_id)


@mcp.tool()
def forget_deal(deal_id: int) -> Any:
    """Permanently hard-delete a deal and all associated data. Irreversible."""
    return _safe(get_client().forget_entity, "deals", deal_id)


@mcp.tool()
def bulk_delete_deals(deal_ids: list[int]) -> Any:
    """Delete multiple deals at once."""
    return _safe(get_client().bulk_destroy, "deals", deal_ids)


@mcp.tool()
def list_deal_fields(include_group: bool = False) -> Any:
    """List all deal fields, including custom fields."""
    return _safe(get_client().list_fields, "deals", include_group)


# =======================================================================
# Leads (may not exist as a separate module on unified accounts — leads
# are often merged into contacts. Tools will surface a clear error if so.)
# =======================================================================

@mcp.tool()
def list_leads(page: int = 1, per_page: int = 30, view_id: Optional[int] = None) -> Any:
    """List leads. Note: unified Freshworks accounts often have no separate
    leads module — leads live as contacts instead. This will error clearly if so."""
    return _safe(get_client().list_entities, "leads", page, per_page, view_id)


@mcp.tool()
def get_lead(lead_id: int) -> Any:
    """Get a single lead by ID (see note on list_leads about account support)."""
    return _safe(get_client().get_entity, "leads", lead_id)


@mcp.tool()
def create_lead(fields: dict) -> Any:
    """Create a lead (see note on list_leads about account support)."""
    return _safe(get_client().create_entity, "leads", fields)


@mcp.tool()
def update_lead(lead_id: int, fields: dict) -> Any:
    """Update a lead by ID (see note on list_leads about account support)."""
    return _safe(get_client().update_entity, "leads", lead_id, fields)


@mcp.tool()
def delete_lead(lead_id: int) -> Any:
    """Delete a lead by ID (see note on list_leads about account support)."""
    return _safe(get_client().delete_entity, "leads", lead_id)


# =======================================================================
# Marketing Lists
# =======================================================================

@mcp.tool()
def create_marketing_list(name: str) -> Any:
    """Create a new marketing list (a saved group of contacts)."""
    return _safe(get_client().create_list, name)


@mcp.tool()
def list_marketing_lists() -> Any:
    """Fetch all marketing lists."""
    return _safe(get_client().get_all_lists)


@mcp.tool()
def update_marketing_list(list_id: int, name: str) -> Any:
    """Rename a marketing list."""
    return _safe(get_client().update_list, list_id, name)


@mcp.tool()
def get_contacts_in_marketing_list(list_id: int) -> Any:
    """Get all contacts belonging to a marketing list."""
    return _safe(get_client().get_contacts_in_list, list_id)


@mcp.tool()
def add_contacts_to_marketing_list(list_id: int, contact_ids: list[int]) -> Any:
    """Add contacts to a marketing list."""
    return _safe(get_client().add_contacts_to_list, list_id, contact_ids)


@mcp.tool()
def remove_contacts_from_marketing_list(list_id: int, contact_ids: Optional[list[int]] = None,
                                         remove_all: bool = False) -> Any:
    """Remove specific contacts from a list, or all of them if remove_all=True."""
    return _safe(get_client().remove_contacts_from_list, list_id, contact_ids, remove_all)


@mcp.tool()
def move_contacts_between_marketing_lists(to_list_id: int, from_list_id: int,
                                           contact_ids: Optional[list[int]] = None) -> Any:
    """Move contacts from one marketing list to another. Omit contact_ids to move all."""
    return _safe(get_client().move_contacts_between_lists, to_list_id, from_list_id, contact_ids)


# =======================================================================
# Tasks
# =======================================================================

@mcp.tool()
def list_tasks(page: int = 1, per_page: int = 30, filter: Optional[str] = None) -> Any:
    """List tasks, paginated. filter can scope to e.g. 'open', 'overdue' — check
    your Freshsales UI's task filter names if unsure."""
    return _safe(get_client().list_entities, "tasks", page, per_page, None, None, None, None, filter)


@mcp.tool()
def get_task(task_id: int) -> Any:
    """Get a single task by ID."""
    return _safe(get_client().get_entity, "tasks", task_id)


@mcp.tool()
def create_task(fields: dict) -> Any:
    """Create a task. fields e.g. {"title":"Follow up","due_date":"2026-09-01T10:00:00Z",
    "targetable_type":"Contact","targetable_id":123,"owner_id":1}."""
    return _safe(get_client().create_entity, "tasks", fields)


@mcp.tool()
def update_task(task_id: int, fields: dict) -> Any:
    """Update fields on a task by ID."""
    return _safe(get_client().update_entity, "tasks", task_id, fields)


@mcp.tool()
def mark_task_done(task_id: int) -> Any:
    """Mark a task as completed."""
    return _safe(get_client().mark_task_done, task_id)


@mcp.tool()
def delete_task(task_id: int) -> Any:
    """Delete a task by ID."""
    return _safe(get_client().delete_entity, "tasks", task_id)


# =======================================================================
# Notes
# =======================================================================

@mcp.tool()
def get_notes_for_record(entity: str, entity_id: int) -> Any:
    """Fetch notes attached to a record. entity: 'contacts', 'deals', or 'sales_accounts'."""
    return _safe(get_client().list_notes_for, entity, entity_id)


@mcp.tool()
def create_note(targetable_type: str, targetable_id: int, description: str) -> Any:
    """Add a note to a record. targetable_type: 'Contact', 'Deal', or 'SalesAccount'
    (singular, capitalized exactly like this)."""
    return _safe(get_client().create_note, targetable_type, targetable_id, description)


@mcp.tool()
def update_note(note_id: int, description: str) -> Any:
    """Edit an existing note's text."""
    return _safe(get_client().update_note, note_id, description)


@mcp.tool()
def delete_note(note_id: int) -> Any:
    """Delete a note by ID."""
    return _safe(get_client().delete_note, note_id)


# =======================================================================
# Appointments
# =======================================================================

@mcp.tool()
def list_appointments(page: int = 1, per_page: int = 30, filter: Optional[str] = None) -> Any:
    """List appointments/meetings, paginated."""
    return _safe(get_client().list_entities, "appointments", page, per_page, None, None, None, None, filter)


@mcp.tool()
def get_appointment(appointment_id: int) -> Any:
    """Get a single appointment by ID."""
    return _safe(get_client().get_entity, "appointments", appointment_id)


@mcp.tool()
def create_appointment(fields: dict) -> Any:
    """Create an appointment. fields e.g. {"title":"Demo call",
    "from_date":"2026-09-01T10:00:00Z","end_date":"2026-09-01T10:30:00Z",
    "targetable_type":"Contact","targetable_id":123}."""
    return _safe(get_client().create_entity, "appointments", fields)


@mcp.tool()
def update_appointment(appointment_id: int, fields: dict) -> Any:
    """Update fields on an appointment by ID."""
    return _safe(get_client().update_entity, "appointments", appointment_id, fields)


@mcp.tool()
def delete_appointment(appointment_id: int) -> Any:
    """Delete an appointment by ID."""
    return _safe(get_client().delete_entity, "appointments", appointment_id)


# =======================================================================
# Sales Activities
# =======================================================================

@mcp.tool()
def list_sales_activities(page: int = 1, per_page: int = 30) -> Any:
    """List logged sales activities (calls, meetings, etc. with outcomes), paginated."""
    return _safe(get_client().list_entities, "sales_activities", page, per_page)


@mcp.tool()
def get_sales_activity(activity_id: int) -> Any:
    """Get a single sales activity by ID."""
    return _safe(get_client().get_entity, "sales_activities", activity_id)


@mcp.tool()
def create_sales_activity(fields: dict) -> Any:
    """Log a sales activity. Use get_selector('sales_activity_types') and
    get_selector('sales_activity_outcomes') to find valid type/outcome IDs first."""
    return _safe(get_client().create_entity, "sales_activities", fields)


@mcp.tool()
def update_sales_activity(activity_id: int, fields: dict) -> Any:
    """Update a sales activity by ID."""
    return _safe(get_client().update_entity, "sales_activities", activity_id, fields)


@mcp.tool()
def delete_sales_activity(activity_id: int) -> Any:
    """Delete a sales activity by ID."""
    return _safe(get_client().delete_entity, "sales_activities", activity_id)


@mcp.tool()
def list_sales_activity_fields() -> Any:
    """List all fields defined for sales activities."""
    return _safe(get_client().list_fields, "sales_activities")


# =======================================================================
# Phone
# =======================================================================

@mcp.tool()
def log_phone_call(fields: dict) -> Any:
    """Manually log a phone call. fields e.g. {"targetable_type":"Contact",
    "targetable_id":123,"call_type":"outgoing","duration":120,"note":"Discussed pricing"}."""
    return _safe(get_client().log_call, fields)


# =======================================================================
# Products (CPQ)
# =======================================================================

@mcp.tool()
def create_product(fields: dict) -> Any:
    """Create a product in the product catalog."""
    return _safe(get_client().create_product, fields)


@mcp.tool()
def get_product(product_id: int, include_pricing: bool = False) -> Any:
    """Get a product by ID, optionally including its pricing tiers."""
    return _safe(get_client().get_product, product_id, include_pricing)


@mcp.tool()
def update_product(product_id: int, fields: dict) -> Any:
    """Update a product's fields by ID."""
    return _safe(get_client().update_product, product_id, fields)


@mcp.tool()
def delete_product(product_id: int) -> Any:
    """Delete a product by ID (soft delete; use restore_product to undo)."""
    return _safe(get_client().delete_product, product_id)


@mcp.tool()
def restore_product(product_id: int) -> Any:
    """Restore a previously deleted product."""
    return _safe(get_client().restore_product, product_id)


@mcp.tool()
def bulk_update_products(updates: list[dict]) -> Any:
    """Update multiple products at once. Each item needs an id plus the fields to change."""
    return _safe(get_client().bulk_update_products, updates)


@mcp.tool()
def bulk_assign_product_owner(product_ids: list[int], owner_id: int) -> Any:
    """Assign an owner to multiple products at once."""
    return _safe(get_client().bulk_assign_product_owner, product_ids, owner_id)


@mcp.tool()
def bulk_delete_products(product_ids: list[int]) -> Any:
    """Delete multiple products at once."""
    return _safe(get_client().bulk_delete_products, product_ids)


@mcp.tool()
def bulk_restore_products(product_ids: list[int]) -> Any:
    """Restore multiple previously deleted products at once."""
    return _safe(get_client().bulk_restore_products, product_ids)


# =======================================================================
# Documents (CPQ quotes/proposals)
# =======================================================================

@mcp.tool()
def create_cpq_document(fields: dict) -> Any:
    """Create a CPQ document (quote/proposal)."""
    return _safe(get_client().create_cpq_document, fields)


@mcp.tool()
def get_cpq_document(document_id: int, include_products: bool = False) -> Any:
    """Get a CPQ document by ID, optionally including its line-item products."""
    return _safe(get_client().get_cpq_document, document_id, include_products)


@mcp.tool()
def update_cpq_document(document_id: int, fields: dict) -> Any:
    """Update a CPQ document's fields by ID."""
    return _safe(get_client().update_cpq_document, document_id, fields)


@mcp.tool()
def delete_cpq_document(document_id: int) -> Any:
    """Delete a CPQ document by ID."""
    return _safe(get_client().delete_cpq_document, document_id)


@mcp.tool()
def forget_cpq_document(document_id: int) -> Any:
    """Permanently hard-delete a CPQ document. Irreversible."""
    return _safe(get_client().forget_cpq_document, document_id)


@mcp.tool()
def restore_cpq_document(document_id: int) -> Any:
    """Restore a previously deleted CPQ document."""
    return _safe(get_client().restore_cpq_document, document_id)


@mcp.tool()
def get_cpq_document_related_products(document_id: int) -> Any:
    """Get the products associated with a CPQ document."""
    return _safe(get_client().get_cpq_document_related_products, document_id)


# =======================================================================
# Files & Links
# =======================================================================

@mcp.tool()
def create_link(targetable_type: str, targetable_id: int, url: str, title: Optional[str] = None) -> Any:
    """Attach a link (e.g. to an external doc) to a record.
    targetable_type: 'Contact', 'Deal', or 'SalesAccount'."""
    return _safe(get_client().create_link, targetable_type, targetable_id, url, title)


@mcp.tool()
def list_files_and_links(contact_id: int) -> Any:
    """List files and links attached to a contact."""
    return _safe(get_client().list_files_and_links, contact_id)


# =======================================================================
# Job Status (for tracking async bulk operations)
# =======================================================================

@mcp.tool()
def get_job_status(job_id: str) -> Any:
    """Check the status of an async bulk operation (e.g. a bulk_upsert), using
    the job_status_url/job_id returned when that operation was started."""
    return _safe(get_client().get_job_status, job_id)


# =======================================================================
# Configuration / Selector metadata
# (owners, deal stages, pipelines, lead sources, etc. — use these to find
# the numeric IDs referenced when creating/updating contacts, deals, etc.)
# =======================================================================

@mcp.tool()
def get_selector(name: str) -> Any:
    """
    Fetch reference/configuration data used elsewhere as numeric IDs.
    name: one of owners, territories, deal_stages, currencies, deal_reasons,
    deal_types, lead_sources, industry_types, business_types, campaigns,
    deal_payment_statuses, deal_products, deal_pipelines, contact_statuses,
    sales_activity_types, sales_activity_outcomes, sales_activity_entity_types,
    lifecycle_stages, designations.
    Use this before creating/updating deals or contacts if you need a valid ID
    for e.g. deal_stage_id, deal_pipeline_id, lead_source_id, owner_id.
    """
    return _safe(get_client().get_selector, name)


@mcp.tool()
def get_deal_stages_for_pipeline(pipeline_id: int) -> Any:
    """Get the valid deal stages for a specific deal pipeline."""
    return _safe(get_client().get_deal_stages_for_pipeline, pipeline_id)


@mcp.tool()
def get_sales_activity_outcomes_for_type(activity_type_id: int) -> Any:
    """Get the valid outcomes for a specific sales activity type."""
    return _safe(get_client().get_sales_activity_outcomes_for_type, activity_type_id)


# =======================================================================
# Custom Modules
# =======================================================================

@mcp.tool()
def create_custom_module(fields: dict) -> Any:
    """Create a new custom module (a custom entity type) in Freshsales."""
    return _safe(get_client().create_custom_module, fields)


@mcp.tool()
def get_custom_module(module_id: int) -> Any:
    """Get details of a custom module by ID."""
    return _safe(get_client().get_custom_module, module_id)


@mcp.tool()
def update_custom_module(module_id: int, fields: dict) -> Any:
    """Update a custom module's definition by ID."""
    return _safe(get_client().update_custom_module, module_id, fields)


@mcp.tool()
def delete_custom_module(module_id: int) -> Any:
    """Delete a custom module by ID."""
    return _safe(get_client().delete_custom_module, module_id)


@mcp.tool()
def create_custom_field(entity_type: str, form_id: int, field_def: dict) -> Any:
    """Add a custom field to an entity's form. field_def shape depends on field
    type (text, number, dropdown, radio, lookup, multiselect) — check Freshsales
    docs for the exact shape needed per type."""
    return _safe(get_client().create_custom_field, entity_type, form_id, field_def)


@mcp.tool()
def list_custom_module_forms(entity_type: str) -> Any:
    """List all fields/forms defined for an entity type, including custom modules."""
    return _safe(get_client().list_custom_module_forms, entity_type)


@mcp.tool()
def create_custom_module_record(entity_name: str, fields: dict) -> Any:
    """Create a record in a custom module."""
    return _safe(get_client().create_custom_module_record, entity_name, fields)


@mcp.tool()
def get_custom_module_records(entity_name: str, record_id: int) -> Any:
    """Get record(s) from a custom module by ID."""
    return _safe(get_client().get_custom_module_records, entity_name, record_id)


@mcp.tool()
def update_custom_module_record(entity_name: str, record_id: int, fields: dict) -> Any:
    """Update a custom module record by ID."""
    return _safe(get_client().update_custom_module_record, entity_name, record_id, fields)


@mcp.tool()
def delete_custom_module_record(entity_name: str, record_id: int) -> Any:
    """Delete a custom module record by ID."""
    return _safe(get_client().delete_custom_module_record, entity_name, record_id)


@mcp.tool()
def forget_custom_module_record(entity_name: str, record_id: int) -> Any:
    """Permanently hard-delete a custom module record. Irreversible."""
    return _safe(get_client().forget_custom_module_record, entity_name, record_id)


@mcp.tool()
def clone_custom_module_record(entity_name: str, record_id: int) -> Any:
    """Clone a custom module record by ID."""
    return _safe(get_client().clone_custom_module_record, entity_name, record_id)


@mcp.tool()
def bulk_delete_custom_module_records(entity_name: str, ids: list[int]) -> Any:
    """Delete multiple custom module records at once."""
    return _safe(get_client().bulk_destroy_custom_module_records, entity_name, ids)


# =======================================================================
# Search
# =======================================================================

@mcp.tool()
def search_freshsales(query: str, entities: Optional[str] = None) -> Any:
    """Fuzzy global search across Freshsales records.
    entities: optional comma-separated scope, e.g. 'contact,deal,sales_account'."""
    return _safe(get_client().search, query, entities)


@mcp.tool()
def lookup_search(query: str, field: str = "email", entities: str = "contact") -> Any:
    """Exact-match lookup search, e.g. find a contact by its exact email address.
    field: the field to match against. entities: comma-separated entity types."""
    return _safe(get_client().lookup_search, query, field, entities)


# =======================================================================
# HTTP Server — Streamable HTTP transport + OAuth 2.0 for Claude Team
# =======================================================================

from oauth import (  # noqa: E402
    oauth_metadata, protected_resource_metadata,
    oauth_authorize, oauth_token,
    validate_access_token,
)

_MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
_SERVER_URL     = os.environ.get("SERVER_URL", "http://localhost:8000")
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
] or ["*"]

# Paths that must be reachable without a Bearer token
_PUBLIC_PATHS = {
    "/health",
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/oauth/authorize",
    "/oauth/token",
}


def _get_request_path(request: Request) -> str:
    matched = (
        request.headers.get("x-matched-path")
        or request.headers.get("x-original-url")
        or request.headers.get("x-forwarded-uri")
    )
    if matched:
        return matched.split("?")[0]
    return request.url.path


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Accepts static MCP_AUTH_TOKEN or valid OAuth access token for Bearer auth requests.
    Non-Bearer requests (OAuth flows, health checks, preflights) pass through to routing.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            ok = (
                (bool(_MCP_AUTH_TOKEN) and token == _MCP_AUTH_TOKEN)
                or validate_access_token(token)
            )
            if not ok:
                logger.warning(
                    "Unauthorized MCP Bearer token from %s",
                    getattr(request.client, "host", "unknown"),
                )
                return JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={
                        "WWW-Authenticate": (
                            f'Bearer realm="{_SERVER_URL}/mcp", '
                            'error="invalid_token"'
                        )
                    },
                )

        return await call_next(request)


async def _health(request: Request) -> JSONResponse:
    """Public health-check — never exposes credentials."""
    return JSONResponse({"status": "ok", "server": "freshsales-mcp"})


_mcp_asgi = mcp.streamable_http_app(
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)

app = Starlette(
    routes=[
        Route("/health", _health),
        # OAuth 2.0 discovery + flow
        Route("/.well-known/oauth-authorization-server", oauth_metadata),
        Route("/.well-known/oauth-protected-resource", protected_resource_metadata),
        Route("/oauth/authorize", oauth_authorize, methods=["GET", "POST"]),
        Route("/oauth/token", oauth_token, methods=["POST"]),
        # MCP endpoint (FastMCP registers /mcp internally)
        Mount("/", app=_mcp_asgi),
    ],
    middleware=[
        Middleware(_BearerAuthMiddleware),
        Middleware(
            CORSMiddleware,
            allow_origins=_ALLOWED_ORIGINS,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            allow_credentials=len(_ALLOWED_ORIGINS) == 1 and _ALLOWED_ORIGINS[0] != "*",
        ),
    ],
    lifespan=_mcp_asgi.router.lifespan_context,
)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    logger.info("Starting Freshsales remote MCP server on http://0.0.0.0:%d", port)
    logger.info("  Health    : http://localhost:%d/health", port)
    logger.info("  MCP       : http://localhost:%d/mcp", port)
    logger.info("  Authorize : http://localhost:%d/oauth/authorize", port)
    uvicorn.run(app, host="0.0.0.0", port=port)