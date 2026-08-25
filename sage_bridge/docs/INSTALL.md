# Sage 50 Pastel Partner — production install

This host is a dedicated always-on Windows machine (or VM) that already runs Pastel in multi-user mode. Odoo (Linux) talks only to HTTPS on this host. The bridge never binds to the internet.

Do **not** use this runbook for Sage 50 UK/US.

## 1. Operating system

- Windows Server 2019/2022, or a licensed Windows 11 workstation if that is the Pastel host.
- 64-bit OS with **32-bit** Python and **32-bit** ODBC. SDKCOM is 32-bit.
- Keep Pastel on the same major version as the accountants’ workstations.

## 2. Sage 50 Pastel Partner

Install, in order:

1. Sage 50 Pastel Partner (same major version as the firm).
2. Actian / Pervasive PSQL client (ships with Pastel).
3. **SDK / SDKCOM** if licensed. Required for safe invoice and receipt posting. Without it the bridge uses guarded ODBC writes (`SAGE_WRITE_MODE=odbc_guarded`) as a stop-gap: pre-checks, no silent tax defaults.

Company data:

- Put the live company on a backed-up volume, e.g. `D:\Pastel\Company`.
- All workstations **and** the bridge use that **same** folder (UNC path is fine).
- Do **not** copy the company folder for the bridge.
- Enable Pastel multi-user. The bridge must open the company in shared mode.
- Keep at least one exclusive-lock window overnight for backups.

## 3. ODBC DSN (32-bit)

1. Run `C:\Windows\SysWOW64\odbcad32.exe` (not the 64-bit administrator).
2. Create a **System DSN** pointing at the live company folder. Example name: `PastelCompany`.
3. Test with a simple `SELECT` before going live.
4. For UAT, create a **second** System DSN (`PastelUAT`) against a **cloned** company. Never point production Odoo at UAT files.

## 4. Python (32-bit) and the bridge

```bat
cd C:\sage_bridge
py -3.11-32 -m venv venv32
venv32\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```
API_KEY=<long random value, never a query-string key>
ODBC_DSN=PastelCompany
SAGE_ADAPTER=pastel_partner
SAGE_WRITE_MODE=odbc_guarded
BIND_HOST=127.0.0.1
BIND_PORT=8788
SDKCOM_PROGID=Pastel.SDK
PASTEL_COMPANY_PATH=D:\Pastel\Company
```

Set `SAGE_WRITE_MODE=sdkcom` only after the Sage SDK module is licensed and `Pastel.SDK` (or your ProgID) opens the company.

Smoke test:

```bat
scripts\run.bat
curl http://127.0.0.1:8788/health
```

`ok` must be true, `dsn_ok` true, `company_open` true.

## 5. Windows service

Run the bridge as a service under a **domain/local user** that can read/write the company folder and use the System DSN. Do **not** run it as the logged-in interactive user. Restart on failure.

NSSM (recommended):

```powershell
.\scripts\install_service.ps1 -Python "C:\sage_bridge\venv32\Scripts\python.exe" -WorkDir "C:\sage_bridge"
```

The script installs service `sage_bridge`, sets restart-on-failure, and loads `.env` from the work directory.

## 6. TLS reverse proxy (production)

- Bind the Python process to `127.0.0.1:8788` only.
- Put IIS or Caddy in front with TLS. Odoo reaches `https://pastel-bridge.internal`.
- Firewall: 443 in from the Odoo host. **Do not expose 8787 or 8788 to the internet.**
- Auth is the `x-api-key` header only. Query-string keys are not accepted.
- Optional mTLS can be added later on the reverse proxy.

## 7. Odoo

1. Install `sage_connector` (keep `pastel_connector` installed during cutover for `x_pastel_*` fields).
2. Upgrade `pastel_batch_payment` so export uses `sage.sync`.
3. Accounting → Sage Connector → Backends: one backend **per company**.
   - Base URL: `https://pastel-bridge.internal` (or `http://127.0.0.1:8788` only on a lab).
   - API key stored in `ir.config_parameter` (`sage_connector.api_key.{company_id}`).
4. Sage Connector → Tax Mappings: every sale tax used on exportable invoices.
5. Sage Connector → Journal Mappings: bank/cash journals used on batch receipts.
6. Test Connection (checks `/health` and an authenticated `/v1/customers` page). Confirm capabilities (`post_invoice`, `post_receipt_batch`).
7. Add accountants to the **Sage User** group (Settings → Users). Sage Manager can edit backends and mappings.
8. Import masters from Sage (Sage is source of truth for customer/supplier/product **codes**).
9. Enable cron **Sage: Process Job Queue**. Enable hourly import only after UAT.

## 8. Ops

- Nightly Pastel backup. Do not mishandle `.lck` files.
- Monitor `GET /health`. Five consecutive 5xx/timeouts open the Odoo circuit; health recovery closes it.
- Do not run Pastel rebuild/reindex while the bridge is posting.
- Logs: Odoo Sage Sync Logs (truncated JSON, correlation id) and Windows Event Log source `sage_bridge`. Never log full API keys.

## 9. UAT then cutover

Use a cloned company and a second DSN. Full checklist: [CUTOVER.md](CUTOVER.md).
