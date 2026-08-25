# Sage 50 Pastel Bridge

Windows HTTP service that sits in front of Sage 50 Pastel Partner. Odoo never talks to company files or COM.

- OpenAPI: `openapi.yaml`
- Default bind: `127.0.0.1:8788`
- Auth: `x-api-key` header only (no `?key=`)
- Writes: SDKCOM when licensed, otherwise guarded ODBC (`SAGE_WRITE_MODE=odbc_guarded`)

Install and production cutover: [docs/INSTALL.md](docs/INSTALL.md)
