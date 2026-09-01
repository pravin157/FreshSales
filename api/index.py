"""
Vercel serverless entry point.

Vercel's @vercel/python runtime looks for an `app` ASGI callable in this file.
We simply re-export the Starlette app built in server.py so all tools and
middleware are available through the /mcp and /health routes.
"""
from server import app  # noqa: F401  — Vercel discovers `app` automatically
