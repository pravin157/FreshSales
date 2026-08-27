"""
Freshsales MCP Server

Exposes Freshsales CRM (contacts, leads, deals, tasks, notes, appointments)
as MCP tools so any MCP-compatible client (Claude Desktop, Claude Code, etc.)
can read and act on your CRM data.

Setup:
    1. pip install -r requirements.txt
    2. Set FRESHSALES_DOMAIN and FRESHSALES_API_KEY (see README.md)
    3. Run: python server.py
    4. Point your MCP client config at this script (see README.md)
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server import MCPServer

from freshsales_client import FreshsalesClient, FreshsalesError

# Load FRESHSALES_DOMAIN / FRESHSALES_API_KEY from a .env file in this
# directory, if present. Real environment variables (e.g. set in your
# MCP client config) still take priority over .env values.
load_dotenv()

mcp = MCPServer("freshsales")

_client: Optional[FreshsalesClient] = None


def get_client() -> FreshsalesClient:
    global _client
    if _client is None:
        _client = FreshsalesClient()
    return _client


def _safe(fn, *args, **kwargs) -> Any:
    """Run a client call and turn Freshsales errors into readable tool output."""
    try:
        return fn(*args, **kwargs)
    except FreshsalesError as e:
        return {"error": True, "status_code": e.status_code, "message": str(e), "details": e.body}
    except ValueError as e:
        return {"error": True, "message": str(e)}


# ---------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------

@mcp.tool()
def list_contacts(page: int = 1, per_page: int = 30, view_id: Optional[int] = None) -> Any:
    """List contacts in Freshsales, paginated. Optionally scope to a saved view_id."""
    return _safe(get_client().list_entities, "contacts", page, per_page, view_id)


@mcp.tool()
def get_contact(contact_id: int) -> Any:
    """Get a single contact by ID, including its fields."""
    return _safe(get_client().get_entity, "contacts", contact_id)


@mcp.tool()
def create_contact(fields: dict) -> Any:
    """
    Create a new contact.
    fields: dict of contact attributes, e.g.
        {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com",
         "job_title": "CTO", "mobile_number": "+1234567890"}
    """
    return _safe(get_client().create_entity, "contacts", "contact", fields)


@mcp.tool()
def update_contact(contact_id: int, fields: dict) -> Any:
    """Update fields on an existing contact by ID."""
    return _safe(get_client().update_entity, "contacts", "contact", contact_id, fields)


@mcp.tool()
def delete_contact(contact_id: int) -> Any:
    """Delete a contact by ID."""
    return _safe(get_client().delete_entity, "contacts", contact_id)


# ---------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------
# Note: unified Freshworks/Freshsales accounts (the myfreshworks.com
# domain format, created post-2020) usually have NO separate "leads"
# entity — leads are merged into contacts. These tools will return a
# clear error from Freshsales if that's the case for your account,
# rather than failing silently.

@mcp.tool()
def list_leads(page: int = 1, per_page: int = 30, view_id: Optional[int] = None) -> Any:
    """List leads in Freshsales, paginated. Optionally scope to a saved view_id.
    Note: some Freshsales accounts have no separate leads module (leads live as contacts)."""
    return _safe(get_client().list_entities, "leads", page, per_page, view_id)


@mcp.tool()
def get_lead(lead_id: int) -> Any:
    """Get a single lead by ID."""
    return _safe(get_client().get_entity, "leads", lead_id)


@mcp.tool()
def create_lead(fields: dict) -> Any:
    """
    Create a new lead.
    fields: dict of lead attributes, e.g.
        {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com",
         "company": "Acme Inc", "lead_source_id": 1}
    """
    return _safe(get_client().create_entity, "leads", "lead", fields)


@mcp.tool()
def update_lead(lead_id: int, fields: dict) -> Any:
    """Update fields on an existing lead by ID."""
    return _safe(get_client().update_entity, "leads", "lead", lead_id, fields)


@mcp.tool()
def delete_lead(lead_id: int) -> Any:
    """Delete a lead by ID."""
    return _safe(get_client().delete_entity, "leads", lead_id)


# ---------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------

@mcp.tool()
def list_deals(page: int = 1, per_page: int = 30, view_id: Optional[int] = None) -> Any:
    """List deals in Freshsales, paginated. Optionally scope to a saved view_id."""
    return _safe(get_client().list_entities, "deals", page, per_page, view_id)


@mcp.tool()
def get_deal(deal_id: int) -> Any:
    """Get a single deal by ID."""
    return _safe(get_client().get_entity, "deals", deal_id)


@mcp.tool()
def create_deal(fields: dict) -> Any:
    """
    Create a new deal.
    fields: dict of deal attributes, e.g.
        {"name": "Acme - Q3 Expansion", "amount": 15000, "deal_stage_id": 1,
         "deal_pipeline_id": 1}
    """
    return _safe(get_client().create_entity, "deals", "deal", fields)


@mcp.tool()
def update_deal(deal_id: int, fields: dict) -> Any:
    """Update fields on an existing deal by ID (e.g. move stage, change amount)."""
    return _safe(get_client().update_entity, "deals", "deal", deal_id, fields)


@mcp.tool()
def delete_deal(deal_id: int) -> Any:
    """Delete a deal by ID."""
    return _safe(get_client().delete_entity, "deals", deal_id)


# ---------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------

@mcp.tool()
def list_tasks(page: int = 1, per_page: int = 30) -> Any:
    """List tasks in Freshsales, paginated."""
    return _safe(get_client().list_entities, "tasks", page, per_page)


@mcp.tool()
def get_task(task_id: int) -> Any:
    """Get a single task by ID."""
    return _safe(get_client().get_entity, "tasks", task_id)


@mcp.tool()
def create_task(fields: dict) -> Any:
    """
    Create a new task.
    fields: dict of task attributes, e.g.
        {"title": "Follow up call", "due_date": "2026-09-01T10:00:00Z",
         "targetable_type": "Contact", "targetable_id": 123, "owner_id": 1}
    """
    return _safe(get_client().create_entity, "tasks", "task", fields)


@mcp.tool()
def update_task(task_id: int, fields: dict) -> Any:
    """Update fields on an existing task by ID (e.g. mark complete via status)."""
    return _safe(get_client().update_entity, "tasks", "task", task_id, fields)


@mcp.tool()
def delete_task(task_id: int) -> Any:
    """Delete a task by ID."""
    return _safe(get_client().delete_entity, "tasks", task_id)


# ---------------------------------------------------------------------
# Notes (attached to a contact, lead, deal, or account)
# ---------------------------------------------------------------------

@mcp.tool()
def list_notes(targetable_type: str, targetable_id: int) -> Any:
    """
    List notes attached to a record.
    targetable_type: one of "contacts", "leads", "deals", "sales_accounts"
    targetable_id: the ID of that record
    """
    return _safe(get_client().list_notes, targetable_type, targetable_id)


@mcp.tool()
def create_note(targetable_type: str, targetable_id: int, description: str) -> Any:
    """
    Add a note to a record.
    targetable_type: one of "contacts", "leads", "deals", "sales_accounts"
    targetable_id: the ID of that record
    description: the note text
    """
    return _safe(get_client().create_note, targetable_type, targetable_id, description)


# ---------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------

@mcp.tool()
def list_appointments(page: int = 1, per_page: int = 30) -> Any:
    """List appointments/meetings in Freshsales, paginated."""
    return _safe(get_client().list_entities, "appointments", page, per_page)


@mcp.tool()
def get_appointment(appointment_id: int) -> Any:
    """Get a single appointment by ID."""
    return _safe(get_client().get_entity, "appointments", appointment_id)


@mcp.tool()
def create_appointment(fields: dict) -> Any:
    """
    Create a new appointment.
    fields: dict of appointment attributes, e.g.
        {"title": "Demo call", "from_date": "2026-09-01T10:00:00Z",
         "end_date": "2026-09-01T10:30:00Z", "targetable_type": "Contact",
         "targetable_id": 123}
    """
    return _safe(get_client().create_entity, "appointments", "appointment", fields)


@mcp.tool()
def update_appointment(appointment_id: int, fields: dict) -> Any:
    """Update fields on an existing appointment by ID."""
    return _safe(get_client().update_entity, "appointments", "appointment", appointment_id, fields)


@mcp.tool()
def delete_appointment(appointment_id: int) -> Any:
    """Delete an appointment by ID."""
    return _safe(get_client().delete_entity, "appointments", appointment_id)


# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------

@mcp.tool()
def search_freshsales(query: str, entities: Optional[str] = None) -> Any:
    """
    Global search across Freshsales records.
    query: search text (name, email, phone, company, etc.)
    entities: optional comma-separated scope, e.g. "contact,lead,deal"
    """
    return _safe(get_client().search, query, entities)


if __name__ == "__main__":
    mcp.run(transport="stdio")
