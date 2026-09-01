# Prompt: Convert Existing Freshsales MCP Server to Remote MCP Server

I currently have a **Freshsales MCP Server** that is working successfully with **Claude Desktop** as a local MCP server.

I now want to convert this existing MCP server into a **remote MCP server** so that it can be hosted publicly and accessed by users through the web/remote MCP clients.

## Important requirements

Do **not** rebuild the MCP server from scratch.

First, analyze the existing codebase and understand:

* Current MCP server architecture
* MCP SDK/library being used
* Current transport mechanism
* Existing Freshsales API integration
* Existing MCP tools
* Environment variables/configuration
* Claude Desktop configuration
* Server entry point
* Error handling
* Authentication, if already implemented

Preserve all existing Freshsales MCP tools and their functionality.

---

## 1. Change local MCP transport to remote transport

The current server is likely using a local `stdio` transport for Claude Desktop.

Modify the implementation to support a remote HTTP-based MCP transport, preferably **MCP Streamable HTTP**, using the MCP SDK version already present in the project where possible.

The remote MCP endpoint should be something like:

```text
/mcp
```

For example:

```text
https://<deployment-domain>/mcp
```

The implementation must be compatible with remote MCP clients.

If the current MCP SDK/version does not support the required transport, identify the required upgrade and make the minimum necessary changes.

---

## 2. Preserve existing Freshsales MCP tools

Do not remove or change the existing MCP tools unless required for remote transport.

All existing tools should continue working exactly as they currently do.

For example, if the current server exposes tools such as:

```text
get_contacts
get_contact
search_contacts
get_leads
```

they should remain available through the remote MCP server.

The remote request flow should be:

```text
Remote MCP Client
        ↓
HTTPS
        ↓
/mcp endpoint
        ↓
Freshsales MCP Server
        ↓
Freshsales API
        ↓
Response
```

---

## 3. Create an HTTP server

Add the HTTP server required to expose the MCP endpoint.

The implementation should:

* Listen on the deployment-provided port
* Support GET/POST as required by the MCP transport
* Expose `/mcp`
* Handle MCP sessions correctly
* Handle multiple simultaneous users
* Return proper HTTP status codes
* Handle invalid MCP requests gracefully
* Handle server errors gracefully

Do not hardcode a local port.

Use:

```text
process.env.PORT
```

or the equivalent mechanism required by the selected deployment platform.

---

## 4. Environment variables

Move all secrets/configuration into environment variables.

Do NOT hardcode:

* Freshsales API key
* Freshsales domain
* Authentication secrets
* Tokens
* Client secrets

For example:

```env
FRESHSALES_DOMAIN=
FRESHSALES_API_KEY=
```

If additional environment variables are required for remote authentication, document them clearly.

Create/update:

```text
.env.example
```

with placeholder values only.

Never commit real credentials.

---

## 5. Authentication and security

Because this server will be publicly accessible, do not leave sensitive Freshsales functionality completely unprotected.

Analyze the current authentication architecture and recommend/implement an appropriate authentication mechanism for the remote MCP endpoint.

The authentication design should support:

```text
User
  ↓
Authentication
  ↓
Remote MCP endpoint
  ↓
MCP tools
  ↓
Freshsales API
```

If OAuth is required for compatibility with the target MCP client, implement the appropriate OAuth flow.

If the current use case only requires controlled access for our organization, provide a secure API-key/JWT-based option if appropriate.

Do not expose Freshsales credentials to the client.

---

## 6. CORS and HTTP security

If browser-based access is required:

* Configure appropriate CORS handling
* Do not use unrestricted `Access-Control-Allow-Origin: *` when credentials are involved
* Restrict allowed origins using an environment variable
* Add appropriate security headers where applicable

Example:

```env
ALLOWED_ORIGINS=
```

---

## 7. Health-check endpoint

Add a simple health-check endpoint such as:

```text
/health
```

It should return a simple successful response when the server is running.

Example:

```json
{
  "status": "ok"
}
```

Do not expose Freshsales credentials or sensitive information through this endpoint.

---

## 8. Local development

Make sure the server can still be tested locally.

Provide clear commands such as:

```bash
npm install
npm run dev
```

or the appropriate commands based on the existing project.

The local MCP endpoint should be testable at something similar to:

```text
http://localhost:<PORT>/mcp
```

---

## 9. Deployment

Prepare the project for deployment as a remote MCP server.

I am considering **Vercel** for deployment.

First analyze whether the current MCP implementation is compatible with Vercel's serverless/runtime model.

If it is compatible:

* Add the required Vercel configuration
* Configure the MCP route correctly
* Ensure streaming/session behavior works correctly
* Ensure environment variables are configured correctly
* Provide the exact deployment steps

If Vercel is not suitable for the current implementation, explain why and recommend a better deployment option such as:

* Google Cloud Run
* AWS
* Azure
* Railway
* Render

Do not change the hosting platform without explaining the reason.

---

## 10. Claude Desktop testing

After deployment, I should be able to configure Claude Desktop to connect to the remote MCP server instead of the local server.

Provide the exact configuration required for the deployed endpoint.

For example, if applicable:

```text
https://<deployment-domain>/mcp
```

Explain exactly where this URL needs to be configured.

---

## 11. Remote MCP testing

Create a clear testing procedure.

I need to verify:

### Test 1 — Server availability

Open:

```text
https://<deployment-domain>/health
```

Expected:

```json
{
  "status": "ok"
}
```

### Test 2 — MCP endpoint

Verify:

```text
https://<deployment-domain>/mcp
```

is reachable and correctly responds to MCP requests.

### Test 3 — Tool discovery

Verify that the remote client can discover all Freshsales MCP tools.

### Test 4 — Tool execution

Test a read-only operation such as:

```text
Get the Freshsales contacts
```

Verify:

```text
Claude/Web Client
        ↓
Remote MCP
        ↓
Freshsales API
        ↓
Contacts
```

### Test 5 — Multiple users

Verify that multiple users can connect without sharing MCP session state incorrectly.

---

## 12. Logging and error handling

Add useful server-side logging for:

* MCP connection
* Authentication failures
* Tool execution
* Freshsales API errors
* Invalid requests
* Unexpected server errors

Do not log:

* API keys
* Passwords
* OAuth secrets
* Access tokens
* Sensitive Freshsales data

---

## 13. Documentation

Update the project README with a complete section:

# Remote MCP Server

Include:

1. Architecture
2. Prerequisites
3. Environment variables
4. Local development
5. Running locally
6. Deployment
7. Vercel configuration if applicable
8. MCP endpoint
9. Authentication
10. Claude Desktop configuration
11. Remote MCP testing
12. Troubleshooting

---

## 14. Final output required

After making the changes, provide me with:

### A. Files changed

Show:

```text
Modified:
- ...
- ...

Added:
- ...
- ...
```

### B. Architecture

Show the final architecture:

```text
Claude/Web
    ↓
HTTPS
    ↓
Remote MCP Server
    ↓
Freshsales API
```

### C. Environment variables

Show the required `.env.example`.

Do not show real secrets.

### D. Local testing commands

Show the exact commands I need to run.

### E. Deployment commands

Show the exact commands required to deploy.

### F. Remote MCP URL

Tell me what the final endpoint should look like:

```text
https://<domain>/mcp
```

### G. Claude Desktop configuration

Give the exact configuration required to connect Claude Desktop to the remote MCP server.

### H. Testing checklist

Provide a checklist confirming:

* [ ] Server deployed
* [ ] `/health` works
* [ ] `/mcp` works
* [ ] MCP tools discovered
* [ ] Freshsales API works
* [ ] Authentication works
* [ ] Multiple users work
* [ ] Claude Desktop connects successfully

## Critical constraints

* Do not rebuild the project from scratch.
* Do not remove existing MCP tools.
* Do not expose Freshsales credentials.
* Do not hardcode secrets.
* Do not assume Vercel is compatible without checking the existing architecture.
* Prefer the MCP transport recommended by the current MCP SDK.
* Keep the existing Freshsales API integration intact.
* Make the minimum necessary code changes.
* Explain every architectural change before/after implementing it.
