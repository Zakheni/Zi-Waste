# Sage Connector — Step-by-step operations manual

Odoo never talks to Sage files directly. The flow is:

**Odoo (`sage_connector`) → HTTP bridge (`sage_bridge` on `127.0.0.1:8788`) → Sage 50 Pastel (ODBC)**

Related modules:

- `sage_connector` — backends, jobs, logs, mappings, transfer wizard, invoice export
- `sage_bridge` — Windows HTTP/ODBC adapter
- `pastel_batch_payment` — batch payments and `batch.payment.export.history`

---

## Part A — One-time setup

### 1. Start the Sage bridge

1. On the Windows host where Pastel/ODBC is available, run `sage_bridge` (port **8788** by default).
2. Confirm `.env` has a valid `API_KEY`, `ODBC_DSN` (e.g. `Pastel_HEALTH_DEMO`), and adapter.
3. Optional check: open `http://127.0.0.1:8788/health` — should return OK.

### 2. Users and access

1. Give users **Sage User** / **Sage Manager** (also available on Waste Management Users where configured).
2. Finance clerks/managers need **Batch Payments** access for receipt batches and **Export History**.

### 3. Create and test the backend

1. Open **Sage Connector → Backends**.
2. Create/open the backend for your company.
3. Set bridge **URL** (e.g. `http://127.0.0.1:8788`), **API key** (same as bridge), and adapter options.
4. Click **Test Connection**.
5. Confirm health shows connected (not paused / circuit open).

### 4. Tax mappings (required for invoices)

1. Go to **Sage Connector → Tax Mappings**.
2. Map each Odoo tax to Pastel’s **numeric TaxType** (example: `15` for 15% VAT — not a label like “Zakheni Code”).
3. Without this, invoice lines fail or post with the wrong tax.

### 5. Journal mappings (for batch receipts)

1. Go to **Sage Connector → Journal Mappings**.
2. Map the Odoo bank/cash journal used on batch payments to the Sage journal/cashbook code the bridge expects.

### 6. Master data codes (critical)

| Record | Where | Rule |
|--------|--------|------|
| Customer | Partner → **Sage** tab (`sage_code` / `x_pastel_code`) | Must exist in Pastel; typically **≤ 6 characters** |
| Product | Product → **Sage** tab (`sage_code` / `x_pastel_item_code`) | Must exist as Pastel item code |
| Invoice doc no | Stored as `sage_doc_no` after export | Pastel limit **CHAR(8)** — Odoo uses short `IN######` form |

Tip: use **Sage Connector → Transfer → Import** for customers/products first so codes match Pastel.

---

## Part B — Day-to-day: Transfer wizard (bulk)

**Menu:** Sage Connector → **Transfer**

1. **Setup** — choose Backend, direction (**Import from Sage** or **Export to Sage**), and data type:
   - Customers / Suppliers / Inventory / Invoices
2. Load **Preview** (optional search / date filters).
3. Edit rows if needed; tick what to send.
4. **Confirm** → **Transfer now**.
5. A **`sage.job`** is created (`transfer_import` or `transfer_export`) and processed.
6. Check **Jobs** (Payload / Result) and **Logs** (Request / Response) if anything fails.

**Notes**

- Export **Invoices** here is the bulk path for posted customer invoices/credit notes.
- Supplier upsert may be skipped by the current adapter.

---

## Part C — Export a single invoice (`account.move`)

### Prerequisites checklist

- [ ] Bridge running and backend **Test Connection** OK
- [ ] Tax mapping set (numeric Pastel tax type)
- [ ] Customer has Sage code
- [ ] Every product line has Sage item code
- [ ] Invoice is **Posted** customer invoice or credit note

### Steps

1. Open **Accounting → Customers → Invoices** (or Credit Notes).
2. Open a **posted** invoice.
3. Click **Export to Sage** (header button).
4. Odoo will:
   - Create a **`sage.job`** of type **Export Invoice**
   - Process it immediately
   - Check Pastel if the doc already exists (`GET /v1/invoices/exists`)
   - **POST** a new document or **PUT** an update
5. On success, **Sage Doc No.** appears on the invoice (`sage_doc_no` / `x_pastel_doc_no`, e.g. `IN000053`).

### Where to verify

| Place | What to look for |
|--------|------------------|
| Invoice form | **Sage Doc No.** filled |
| Sage Connector → **Jobs** | Job type `export_invoice`, state **Done**, Payload/Result panels |
| Sage Connector → **Logs** | HTTP calls to `/v1/invoices...` |
| Pastel | `HistoryHeader` / `HistoryLines` for that doc |

### Common failures

- Missing customer or product Sage code
- Bad tax mapping (non-numeric / wrong type)
- Doc number too long for Pastel (system shortens to `IN` + id)
- Bridge down or wrong API key

---

## Part D — Batch payment export and Export History

Model: **`batch.payment.export.history`**

Menus: **Accounting → Batch Payments → Batches** and **Export History**

### Build and validate a batch

1. **Batch Payments → Batches** → create a batch.
2. Add invoices / payment lines; set journal, date, amounts.
3. **Validate** the batch (state becomes validated / ready to export or pay).

Payment in Odoo and Sage export are **independent**: you can receive payment first or export first.

### Export the batch to Sage

1. On the batch form, click **Export to Sage**.
2. The system creates a **`sage.job`** of type **`export_receipt_batch`** and processes it.
3. Sync logic:
   - For each invoice **without** a Sage doc no → export the invoice first
   - Then post the receipt batch to the bridge (`POST /v1/payments/batch`)
4. On success:
   - Batch gets `exported_ref` / Sage reference
   - State may move **validated → exported** (partial/paid states are preserved)
   - A **success** row is written to **Export History**
5. On failure:
   - A **failed** history row is written (request + error text)
   - User sees an error notification

### Read Export History

1. Open **Batch Payments → Export History** (kanban/list), **or** open the batch → tab **Export History**.
2. Open a row to see:
   - Success / Failed ribbon
   - Sage reference
   - Dark **Request** / **Response** panels (JSON)

### Related Jobs and Logs

- **Sage Connector → Jobs** — type **Export Receipt Batch**, Payload / Result
- **Sage Connector → Logs** — underlying HTTP request/response to the bridge

---

## Part E — Monitoring cheat sheet

| Question | Go to |
|----------|--------|
| Is the bridge reachable? | Backend → **Test Connection** / Health tab |
| Did my export run? | **Jobs** (filter by type / status) |
| What did we send/receive? | Job **Payload/Result** or Log **Request/Response** |
| Did this batch export before? | **Batch Payments → Export History** |
| Is this invoice in Pastel? | Invoice **Sage Doc No.** |

Job states: `pending` → `running` → `done` / `error` / `dead`

From a job form: use **Process Now** or **Retry** when needed.

---

## Recommended operating order (happy path)

1. Bridge up → **Test Connection**
2. Tax + journal mappings
3. Import/sync customers and products (codes match Pastel)
4. Post invoices in Odoo
5. Export invoices (invoice button **or** Transfer → Export → Invoices)
6. Create/validate batch payments → **Export to Sage**
7. Confirm in Jobs, Logs, Export History, and Pastel
