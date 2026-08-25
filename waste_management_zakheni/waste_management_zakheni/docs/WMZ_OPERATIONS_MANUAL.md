# Waste Management — Full operations manual

In this system the **manifest** is the model `waste.service.request`, opened from **Waste Management → Waste Service**.

**Recommended setup order:** Lookups → Company links → Tariffs → Products → Containers / Points → Quote → Manifest → Worksheet → Authorise → Invoice.

Related docs:

- Company, theme, users, customers — see conversation / ops onboarding notes
- Sage export — `custom_addons/sage_connector/docs/SAGE_CONNECTOR_MANUAL.md`

---

## Section 0 — Roles cheat sheet

| Who | Where they work |
|-----|-----------------|
| Admin Clerk / Super Admin / Ops Manager / Finance | Backend: Waste Management, Sales |
| Driver | Backend worksheets (and sometimes mobile) |
| Customer (portal user) | `/my/...` — quotes, pay, log requests |
| Client Agent | Portal worksheets only (cannot log new requests) |

---

## Section 1 — Lookups (master data)

**Menu:** Waste Management → Configuration → **Waste Look-Up**

Create these first (name must match product attribute values if you use variants):

| Menu | Model | Purpose |
|------|--------|---------|
| Service Request | `service.request` | e.g. Placement, Collection & Disposal, Swapping |
| Waste Type | `waste.type` | Hazardous / General Compactable / Non-Compactable |
| Waste Details | `waste.details` | Detail text; “grease” vs septic affects **tank tariff** |
| Bin Type | `bin.type` | Bin sizes |
| Tank Volume | `tank.volume` | Tank capacities |
| Container Type | `container.type` | Bin vs Tank |

### Steps

1. Open each lookup menu → **New**.
2. Enter **Name** (and any code / attribute link `pav_id` if used).
3. Save.

---

## Section 2 — Link lookups to the company

**Menu:** Waste Management → **Company & Branches** (or Settings → Companies)

1. Open the company.
2. Tab **Waste Management**.
3. Set:
   - Waste Services for Company
   - Container Types
   - Waste Types
   - Waste Details
   - Bin Types
   - Tank Volumes
4. Save.

These lists control **what the portal customer can pick** and what the **dashboard** scopes.

Optional on a **Contact (company partner):** tab Waste Management — turn off “use company config” and override per customer.

---

## Section 3 — Transport tariffs (`waste.transport.tariff`)

**Menu:** Waste Management → Configuration → Tariff → **Transport Tariffs**

1. **New**.
2. Fill **Name**, **Rate Type** (flat, per_bin, per_trip, per_ton, per_kg, per_bin_km, tiers, hybrids, …), **Date From**.
3. Fill the rate fields for that type (base rate, per bin, per trip, etc.).
4. Set **Company** (or leave empty for global fallback).
5. Keep **Active**; avoid overlapping dates for the same company + rate type.
6. Save.

---

## Section 4 — Tank tariffs (`waste.tank.tariff`)

**Menu:** Waste Management → Configuration → Tariff → **Tank Tariff**

1. **New**.
2. Fill **Name**, **Code** (e.g. `septic`, `grease`), **Date From**.
3. Set **Base kL**, **Base Price**, **Extra Rate** (price after base volume).
4. Company / Active as for transport.
5. Save.

Tank tariffs are **not** chosen on the product form. Billing picks them from the job (waste details → grease vs septic) when tank work is done.

---

## Section 5 — Create products (Sales) and call tariffs

**Menu:** Sales → Products → Products → **New**

### Transport product (links to transport tariff)

1. Create product (type/service as you use for waste).
2. Enable **Transport Tariff** (`is_transport_service`).
3. Choose **Tariff Type** (`transport_rate_type`) matching a tariff rate type.
4. Sales price (`list_price`) fills from the **active** matching tariff (company first, then global).
   If none exists → error: no active transport tariff.
5. For variants that drive manifests, add attributes whose values match lookups:
   - Service Requested, Waste Type, Waste Details, Bin Type, Container Type, Tank Volume
6. Save.

### Tank-related products

- Still normal Sales products / variants.
- Volume billing uses **tank tariff** later on the manifest/worksheet, not the product’s Transport Tariff toggle.

On a **quotation line**, if the product has Transport Tariff, you can enter **Bins / Distance / Trips / Ton / kg** — price recalculates from tariffs.

---

## Section 6 — Quotation: create, email, confirm, portal pay

**Menu:** Sales → Orders → Quotations

### Create

1. **New** quotation.
2. Customer = **company** partner (`is_company`).
3. Add waste/transport product lines; set bins/km/trips/weight if prompted.
4. Set validity date, etc.
5. Save (state **Quotation**).

### Send by email

1. Click **Send by Email**.
2. Review template → Send.
   State often moves toward **Quotation Sent**.

### Confirm manually (backend)

1. Open the quotation.
2. Click **Confirm**.
   State → **Sales Order** (`sale`).

### Customer confirms / pays on portal

1. Customer logs into portal (`/my`).
2. Opens **Orders / Quotations** (`/my/orders`).
3. Opens the quotation.
4. Depending on company policy:
   - **Zakheni (master):** Sign only
   - **Other companies:** **Sign & Pay** (full prepayment typical)
5. After accept/pay, order becomes confirmed sales order.

Eligible SO for a new manifest: state `sale`, invoice status to invoice, validity OK, same customer, **not already linked** to a manifest.

---

## Section 7 — Portal: customer logs a service request

**Who:** Portal customer (**not** Client Agent)

1. Log in → `/my/home` or `/my/waste`.
2. **Log Service Request** → `/my/waste/request/new`.
3. Choose options from **company-allowed** lookups (service, waste type, details, bin/tank, pickup point).
4. **Submit Request**.
5. Thank-you page; request appears under `/my/waste/requests`.

Creates `waste.service.request` in **draft**, `from_portal=True`, **no SO yet**. Internal staff later attach an SO and process the manifest.

Agents who try to log get blocked (`agent_cannot_log`).

---

## Section 8 — Portal: Client Agent fills worksheet

**Who:** user in group **Client Agent**

1. Portal → open the waste request → **Worksheets**.
2. Open `/my/waste/worksheet/<id>/edit`.
3. Fill times, km, quantities, notes, docs, signatures, photos.
4. **Save Changes**.

May set worksheet **done** and advance manifest toward **service delivered**, and notify managers.

---

## Section 9 — Internal: open service request (manifest) and process it

**Menu:** Waste Management → **Waste Service**  
**Roles:** Super Admin, Admin Clerk, Ops Manager, Finance

### From a confirmed sales order (usual path)

1. Confirm SO (Section 6).
2. **Waste Service → New**.
3. Set **Customer**, then **Sales Order** (domain shows eligible SOs).
4. Selecting SO maps attributes → service, waste type, details, bin/tank, product, price, qty.
5. Set pickup / related points.
6. Smart button **Assign Bins** → fill wizard → **Apply**.
7. Workflow:

| Button | Effect |
|--------|--------|
| **Generate** | Draft → Generated; containers marked in use |
| **Schedule** | Needs planned date + (vehicle+driver **or** service provider); creates **Worksheet**; emails driver/provider → Scheduled |
| (Driver/agent work) | Dispatched → Service Delivered |
| **Authorise** | Finish with mailto wizard → **done** |
| **Reject** | From service delivered → cancelled flow |
| **Create Invoice** | When done — open related SOs to invoice |
| **Find Service Provider / Disposal Site** | Wizards when needed |

### From a portal draft

1. Filter **From portal**.
2. Attach eligible SO, assign bins, then Generate → Schedule as above.

**States (typical):** Draft → Generated → Scheduled → Dispatched → Service Delivered → Authorised (`done`) / Rejected (`cancelled`).

---

## Section 10 — Pickup points and drop-off points

**Model:** `pickup.point` (used as pickup **and** drop-off)

**Menu:** Waste Management → Configuration → Configuration → **Pickup Points**

1. **New** → **Pickup Point Name** (required).
2. Set **Customer** (company partner) and address/geo as needed.
3. Save.

Customers can also create/edit pickup points on the **portal**.

On containers / Assign Bins wizard: choose pickup and drop-off from that customer’s points.

---

## Section 11 — Disposal sites

**Menu:** Waste Management → Configuration → Configuration → **Disposal Site**  
**Model:** `waste.disposal.site`

1. **New** → Site Code, full address, waste type, capacity, license, contacts.
2. **Locate on map** if available.
3. Save.

On a manifest: **Find Disposal Site** suggests nearest licensed sites by waste type / location.

---

## Section 12 — Containers: create, assign manually, assign via manifest

**Menu:** Waste Management → **Waste Container**  
**Roles:** Super Admin, Admin Clerk

### Create

1. **New** → Bin Number (sequence/unique).
2. Container Type (Bin/Tank), Bin Type or Tank Volume.
3. Optional Customer, Pickup / Drop-off, Condition.
4. Save.

### Manual assign to customer

1. Open container.
2. Set **Customer**.
3. Set Pickup / Drop-off (limited to that partner’s points).
4. Save. Clearing customer clears points.

### Assign via manifest

1. On Waste Service form → **Assign Bins**.
2. Map lines (lifted/dropped bins, pickup/drop-off) per service type.
3. **Apply** (no duplicate bins; reservation rules apply).
4. **Generate** marks containers in use.
5. **Authorise** updates locations/status by service (placement, removal, swap, etc.).

Worksheet can also use an Assign Bins wizard.

---

## Section 13 — Worksheets (internal)

**Menu:** Waste Management → **Worksheet**

1. Auto-created when manifest is **Scheduled**.
2. Open from menu or Manifest → **Worksheet**.
3. **Start** → worksheet in progress; manifest **Dispatched**.
4. Fill arrival/return, km, qty (bins or kL), UoM, ton/kg, trips, signatures, documents, photos.
5. **Mark as done** → **Finish Worksheet** wizard (choose manager mailto).
6. Worksheet **done**; manifest often **Service Delivered**; SO qty may sync; emails sent.

Then manager **Authorise** on the manifest (Section 9).

---

## Section 14 — Service providers

**Menu:** Waste Management → Configuration → Configuration → **Service Providers**  
**Model:** `wms.service.provider`

1. **New** → Name, Location (full address), phone, mobile, email (required).
2. Optional: Agent (Client Agent user), fleet categories, province, geo.
3. **Locate on map** → Save.

On manifest: mark as provider job → **Find Service Provider** → select → **Schedule** emails them.

---

## Section 15 — Dashboard (backend)

**Menu:** **Waste Dashboard → Dashboard**  
**Roles:** Super Admin, Admin Clerk, Ops Manager, Finance (not Driver)

1. Open dashboard.
2. Filter by date, company, customer, refs; presets (Today / This month / Last 30 days).
3. Tabs: **Overview**, **Operations**, **Finance**, **Bins & Tanks**.
4. KPI cards (Active, Scheduled, On site, Authorised, Rejected) — click to open lists.
5. Charts: schedule, status mix, top customers, driver trips, tank kL, revenue.
6. Export **PDF** / **Excel**.

Scope follows allowed companies and company `wmz_*` config.

Portal `/my/waste` is a **separate** customer/agent summary, not this OWL backend dashboard.

---

## End-to-end happy path (compressed)

1. Lookups → link on **Company → Waste Management**
2. Transport + Tank **Tariffs**
3. **Products** with Transport Tariff (+ attributes)
4. **Containers**, **Pickup points**, **Disposal sites**, **Service providers**
5. **Quotation** → email → Confirm or portal Sign/Pay
6. **Waste Service** manifest + link SO + **Assign Bins** → **Generate** → **Schedule**
7. Driver/agent **Worksheet** → done → **Authorise**
8. Finance **Create Invoice** / Sales invoicing
9. Monitor on **Waste Dashboard**
