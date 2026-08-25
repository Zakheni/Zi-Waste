# Sage connector cutover

Keep production on the old pipe until staging UAT passes. Ship `sage_bridge` + `sage_connector` **alongside** `pastel_connector` and `Pastel Partner Bridge`. Do not drop `x_pastel_*` columns.

## Staging UAT

1. Clone the live Pastel company to a second folder. Create System DSN `PastelUAT` (32-bit `odbcad32.exe`).
2. Run `sage_bridge` with `ODBC_DSN=PastelUAT` on `127.0.0.1:8788`. Do **not** stop the old 8787 process until production cutover.
3. On a **staging** Odoo database, install `sage_connector` and upgrade `pastel_batch_payment`.
4. Create `sage.backend` for the staging company. Point it at the UAT bridge. Map taxes and journals.
5. Import customers, suppliers, products.
6. Post one customer invoice in Odoo → Export to Sage. Confirm the stored number is Sage’s `doc_no`, not the Odoo id.
7. Validate one batch payment → Export to Sage. Confirm receipts and (if supported) invoice allocation.
8. Confirm Sage Connector → Jobs / Logs. Failed jobs must retry with backoff and must not re-post invoices after a receipt failure.

Never point production Odoo at UAT files.

## Production cutover

1. Freeze Pastel posting (or pick a quiet window). Take a Pastel backup.
2. Install `sage_connector` on production. Upgrade `pastel_batch_payment`.
3. Create the production `sage.backend` (live DSN, HTTPS URL, API key). Copy tax/journal mappings from staging.
4. Test Connection against the live bridge (still on localhost + reverse proxy).
5. Disable leftover Pastel Connector crons (already inactive in `pastel_connector/data/ir_cron.xml`). Confirm they stay off.
6. Stop the old FastAPI process (`Pastel Partner Bridge/main.py`, typically port 8787). Start Windows service `sage_bridge`.
7. Run one live invoice and one live batch receipt. Watch Sage Connector jobs.
8. Leave `pastel_connector` installed until `x_pastel_*` aliases are no longer needed, then uninstall.

`pastel.sync.export_invoice` and `import_all` delegate to `sage.sync` when an active `sage.backend` exists. Batch payment no longer stores `pastel_batch_payment.bridge_base` / `bridge_key` and no longer hardcodes tax `"1"` or `document_type = 3`.

## Rollback

1. Stop `sage_bridge`.
2. Start the old Pastel Partner Bridge on 8787 if you must.
3. Re-enable old pastel_connector settings URL/key only if `sage.backend` is archived (`active=False`). Batch payment will not talk to 8787 while `sage_connector` is installed — roll back the `pastel_batch_payment` module only if you must restore the old HTTP exporter.
