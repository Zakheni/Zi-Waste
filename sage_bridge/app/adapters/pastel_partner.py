"""Pastel Partner adapter: ODBC reads, SDKCOM writes with guarded ODBC fallback."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import pyodbc
from fastapi import HTTPException

from .. import config
from ..db import (
    cast_char50,
    fetch_dicts,
    norm_text,
    pick_col,
    pick_table,
    to_bool,
    to_date_sql,
    to_date_str,
    to_float,
)
from .base import SageAdapter
from .sdkcom import post_invoice_sdk, post_receipt_sdk, sdk_available

_logger = logging.getLogger(__name__)

CURRENCY_MAP = {"ZAR": 0, "USD": 1, "EUR": 2, "GBP": 3}


class PastelPartnerOdbcSdkAdapter(SageAdapter):
    """Sage 50 Pastel Partner via 32-bit ODBC + optional SDKCOM."""

    name = "pastel_partner"

    def __init__(self):
        self.write_mode = config.WRITE_MODE
        if self.write_mode == "sdkcom" and not sdk_available(config.SDKCOM_PROGID):
            _logger.warning("SDKCOM unavailable; falling back to odbc_guarded writes")
            self.write_mode = "odbc_guarded"

    def _conn(self):
        if not config.ODBC_DSN:
            raise HTTPException(status_code=500, detail="ODBC_DSN missing from environment")
        return pyodbc.connect(f"DSN={config.ODBC_DSN};", autocommit=True)

    def capabilities(self) -> Dict[str, bool]:
        return {
            "pull_customers": True,
            "pull_suppliers": True,
            "pull_products": True,
            "pull_invoices": True,
            "upsert_customer": True,
            "upsert_product": True,
            "post_invoice": True,
            "credit_notes": True,
            "post_receipt_batch": True,
            "invoice_allocation": True,
            "supplier_payments": False,
        }

    def health(self) -> Dict[str, Any]:
        dsn_ok = False
        company_open = False
        try:
            with self._conn() as cn:
                cn.cursor().execute("SELECT 1")
                dsn_ok = True
                company_open = True
        except Exception as exc:
            _logger.warning("DSN health failed: %s", exc)
        return {
            "ok": dsn_ok,
            "adapter": self.name,
            "adapter_version": "pastel_partner",
            "write_mode": self.write_mode,
            "dsn_ok": dsn_ok,
            "company_open": company_open,
            "capabilities": self.capabilities(),
        }

    def _page_master(
        self,
        table_candidates: List[str],
        code_candidates: List[str],
        name_candidates: List[str],
        extra_cols: List[Tuple[List[str], str]],
        since: Optional[str],
        cursor: Optional[str],
        limit: int,
        q: Optional[str],
        missing_table: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        with self._conn() as cn:
            cur = cn.cursor()
            tbl = pick_table(cur, table_candidates)
            if not tbl:
                raise HTTPException(status_code=500, detail=f"{missing_table} table not found")
            code_col = pick_col(cur, tbl, code_candidates)
            name_col = pick_col(cur, tbl, name_candidates)
            if not code_col or not name_col:
                raise HTTPException(status_code=500, detail=f"Required columns missing on {tbl}")
            sel = [f"{code_col} AS code", f"{name_col} AS name"]
            for cands, alias in extra_cols:
                col = pick_col(cur, tbl, cands)
                if col:
                    sel.append(f"{col} AS {alias}")
            where, params = [], []
            if q:
                like = f"%{q}%"
                where.append(f"(UPPER({code_col}) LIKE UPPER(?) OR UPPER({name_col}) LIKE UPPER(?))")
                params += [like, like]
            if cursor:
                where.append(f"UPPER(RTRIM({code_col})) > UPPER(?)")
                params.append(cursor.strip())
            upd = pick_col(cur, tbl, ["UpdatedOn", "UpdateDate"])
            if since and upd:
                where.append(f"{upd} >= ?")
                params.append(since)
            fetch_limit = int(limit) + 1
            sql = f"""
                SELECT TOP {fetch_limit} {", ".join(sel)}
                FROM {tbl}
                {"WHERE " + " AND ".join(where) if where else ""}
                ORDER BY {code_col}
            """
            cur.execute(sql, *params)
            rows = fetch_dicts(cur)
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = []
        for d in rows:
            item = {k: d.get(k) for k in d}
            item["code"] = str(d.get("code") or "").strip()
            item["name"] = norm_text(d.get("name"))
            for key in ("phone", "email", "tax_code", "currency_code", "category",
                        "barcode", "unit_size", "gl_code", "guid", "country_code",
                        "payment_terms", "settlement_terms", "updated_on"):
                if key in d:
                    item[key] = norm_text(d.get(key))
            for key in ("credit_limit", "balance", "weight"):
                if key in d:
                    item[key] = to_float(d.get(key))
            if "allow_tax" in d:
                item["allow_tax"] = to_bool(d.get("allow_tax"))
            items.append(item)
        next_cursor = items[-1]["code"] if items and has_more else None
        return items, next_cursor, has_more

    def pull_customers(self, since, cursor, limit, q):
        extras = [
            (["Telephone", "Phone"], "phone"),
            (["EMail", "Email"], "email"),
            (["TaxCode", "TaxType"], "tax_code"),
            (["CreditLimit"], "credit_limit"),
            (["CurrBalanceThis01", "Balance", "CurrentBalance"], "balance"),
            (["CurrencyCode"], "currency_code"),
            (["UpdatedOn", "UpdateDate"], "updated_on"),
            (["GUID"], "guid"),
        ]
        return self._page_master(
            ["CustomerMaster", "Customers", "Debtors", "ARCustomers"],
            ["CustomerCode", "Code", "Account"],
            ["CustomerDesc", "Description", "Name"],
            extras, since, cursor, limit, q, "Customer",
        )

    def pull_suppliers(self, since, cursor, limit, q):
        extras = [
            (["Telephone", "Phone"], "phone"),
            (["EMail", "Email"], "email"),
            (["CreditLimit"], "credit_limit"),
            (["CurrBalanceThis01", "BalanceThis01", "CurrentBalance", "Balance"], "balance"),
            (["TaxCode", "TaxType", "SalesTaxType"], "tax_code"),
            (["CountryCode"], "country_code"),
            (["CurrencyCode"], "currency_code"),
            (["PaymentTerms"], "payment_terms"),
            (["SettlementTerms"], "settlement_terms"),
            (["UpdatedOn", "UpdateDate"], "updated_on"),
            (["GUID"], "guid"),
        ]
        return self._page_master(
            ["SupplierMaster", "CreditorMaster", "Suppliers"],
            ["SupplierCode", "CreditorCode", "Account", "Code"],
            ["SupplierDesc", "CreditorDesc", "Description", "Name"],
            extras, since, cursor, limit, q, "Supplier",
        )

    def pull_products(self, since, cursor, limit, q):
        extras = [
            (["Category"], "category"),
            (["Barcode"], "barcode"),
            (["UnitSize", "UOM"], "unit_size"),
            (["SalesTaxType", "TaxType"], "tax_code"),
            (["GLCode"], "gl_code"),
            (["AllowTax"], "allow_tax"),
            (["NettMass", "Weight"], "weight"),
            (["UpdatedOn", "UpdateDate"], "updated_on"),
            (["GUID"], "guid"),
        ]
        return self._page_master(
            ["Inventory", "Stock", "Items"],
            ["ItemCode", "Code"],
            ["Description", "Name"],
            extras, since, cursor, limit, q, "Inventory",
        )

    def pull_invoices(self, since, cursor, limit, doc_type):
        with self._conn() as cn:
            cur = cn.cursor()
            hdr_tbl = "HistoryHeader"
            ln_tbl = "HistoryLines"
            doc_no_col = pick_col(cur, hdr_tbl, ["DocumentNumber"])
            doc_date_col = pick_col(cur, hdr_tbl, ["DocumentDate"])
            cust_code_col = pick_col(cur, hdr_tbl, ["CustomerCode"])
            doc_type_col = pick_col(cur, hdr_tbl, ["DocumentType"])
            total_col = pick_col(cur, hdr_tbl, ["Total"])
            total_tax_col = pick_col(cur, hdr_tbl, ["TotalTax"])
            pay_ref_col = pick_col(cur, hdr_tbl, ["PaymentReference", "OrderNumber", "Reference"])
            if not (doc_no_col and doc_date_col and cust_code_col):
                raise HTTPException(status_code=500, detail="Required invoice columns missing")
            where, params = [], []
            if doc_type is not None:
                where.append(f"{doc_type_col}=?")
                params.append(int(doc_type))
            if since:
                where.append(f"{doc_date_col}>=?")
                params.append(since)
            if cursor:
                where.append(f"UPPER(RTRIM({doc_no_col})) < UPPER(?)")
                params.append(cursor.strip())
            fetch_limit = int(limit) + 1
            sql = f"""
                SELECT TOP {fetch_limit}
                    {cast_char50(doc_no_col)} AS doc_no,
                    {doc_date_col} AS invoice_date,
                    {cust_code_col} AS customer_code,
                    {doc_type_col} AS document_type,
                    {total_col + " AS total" if total_col else "0 AS total"},
                    {total_tax_col + " AS total_tax" if total_tax_col else "0 AS total_tax"},
                    {pay_ref_col + " AS payment_reference" if pay_ref_col else "NULL AS payment_reference"}
                FROM {hdr_tbl}
                {"WHERE " + " AND ".join(where) if where else ""}
                ORDER BY {doc_date_col} DESC, {doc_no_col} DESC
            """
            cur.execute(sql, *params)
            headers = fetch_dicts(cur)
            has_more = len(headers) > limit
            headers = headers[:limit]
            if not headers:
                return [], None, False
            doc_nos = [str(h.get("doc_no") or "").strip() for h in headers]
            ln_doc = pick_col(cur, ln_tbl, ["DocumentNumber"])
            ln_item = pick_col(cur, ln_tbl, ["ItemCode"])
            ln_desc = pick_col(cur, ln_tbl, ["Description"])
            ln_qty = pick_col(cur, ln_tbl, ["Qty"])
            ln_price = pick_col(cur, ln_tbl, ["UnitPrice"])
            ln_tax = pick_col(cur, ln_tbl, ["TaxType"])
            qmarks = ",".join(["?"] * len(doc_nos))
            cur.execute(
                f"""SELECT {cast_char50(ln_doc)} AS doc_no,
                           {ln_item} AS product_code, {ln_desc} AS name,
                           {ln_qty} AS quantity, {ln_price} AS price_unit, {ln_tax} AS tax_code
                    FROM {ln_tbl} WHERE {cast_char50(ln_doc)} IN ({qmarks})""",
                *doc_nos,
            )
            by_doc: Dict[str, list] = {}
            for lr in fetch_dicts(cur):
                doc = str(lr.get("doc_no") or "").strip()
                by_doc.setdefault(doc, []).append({
                    "product_code": norm_text(lr.get("product_code")),
                    "name": norm_text(lr.get("name")),
                    "quantity": to_float(lr.get("quantity")) or 0.0,
                    "price_unit": to_float(lr.get("price_unit")) or 0.0,
                    "tax_code": norm_text(lr.get("tax_code")),
                })
        items = []
        for h in headers:
            doc_no = str(h.get("doc_no") or "").strip()
            total = to_float(h.get("total")) or 0.0
            tax = to_float(h.get("total_tax")) or 0.0
            items.append({
                "doc_no": doc_no,
                "invoice_date": to_date_str(h.get("invoice_date")),
                "customer_code": norm_text(h.get("customer_code")) or "",
                "document_type": int(h.get("document_type") or 3),
                "amount_total": round(total + tax, 2),
                "amount_total_excl": round(total, 2),
                "tax_amount": round(tax, 2),
                "payment_reference": norm_text(h.get("payment_reference")) or doc_no,
                "lines": by_doc.get(doc_no, []),
            })
        next_cursor = items[-1]["doc_no"] if items and has_more else None
        return items, next_cursor, has_more

    def upsert_customer(self, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._conn() as cn:
            cur = cn.cursor()
            tbl = pick_table(cur, ["CustomerMaster", "Customers"])
            if not tbl:
                raise HTTPException(status_code=500, detail="Customer table not found")
            code_col = pick_col(cur, tbl, ["CustomerCode", "Code", "Account"])
            name_col = pick_col(cur, tbl, ["CustomerDesc", "Description", "Name"])
            tax_col = pick_col(cur, tbl, ["TaxCode", "TaxType"])
            curr_col = pick_col(cur, tbl, ["CurrencyCode"])
            crlim_col = pick_col(cur, tbl, ["CreditLimit"])
            name = payload.get("name") or code
            tax = payload.get("tax_code")
            curr = payload.get("currency_code")
            crlim = payload.get("credit_limit") or 0
            cur.execute(f"SELECT 1 FROM {tbl} WHERE UPPER(RTRIM({code_col}))=UPPER(?)", code.strip())
            exists = cur.fetchone() is not None
            if exists:
                sets, vals = [f"{name_col}=?"], [name]
                if crlim_col:
                    sets.append(f"{crlim_col}=?"); vals.append(crlim)
                if tax_col:
                    sets.append(f"{tax_col}=?"); vals.append(tax)
                if curr_col:
                    sets.append(f"{curr_col}=?"); vals.append(curr)
                vals.append(code.strip())
                cur.execute(f"UPDATE {tbl} SET {', '.join(sets)} WHERE UPPER(RTRIM({code_col}))=UPPER(?)", *vals)
            else:
                cols, vals = [code_col, name_col], [code.strip(), name]
                if crlim_col:
                    cols.append(crlim_col); vals.append(crlim)
                if tax_col:
                    cols.append(tax_col); vals.append(tax)
                if curr_col:
                    cols.append(curr_col); vals.append(curr)
                cur.execute(f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({','.join(['?']*len(vals))})", *vals)
            return {"ok": True, "code": code, "updated": bool(exists)}

    def upsert_product(self, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._conn() as cn:
            cur = cn.cursor()
            tbl = pick_table(cur, ["Inventory", "Stock", "Items"])
            if not tbl:
                raise HTTPException(status_code=500, detail="Inventory table not found")
            code_col = pick_col(cur, tbl, ["ItemCode", "Code"])
            name_col = pick_col(cur, tbl, ["Description", "Name"])
            tax_col = pick_col(cur, tbl, ["SalesTaxType", "TaxType"])
            name = payload.get("name") or code
            tax = payload.get("tax_code")
            cur.execute(f"SELECT 1 FROM {tbl} WHERE UPPER(RTRIM({code_col}))=UPPER(?)", code.strip())
            exists = cur.fetchone() is not None
            if exists:
                if tax_col:
                    cur.execute(
                        f"UPDATE {tbl} SET {name_col}=?, {tax_col}=? WHERE UPPER(RTRIM({code_col}))=UPPER(?)",
                        name, tax, code.strip(),
                    )
                else:
                    cur.execute(
                        f"UPDATE {tbl} SET {name_col}=? WHERE UPPER(RTRIM({code_col}))=UPPER(?)",
                        name, code.strip(),
                    )
            else:
                cols, vals = [code_col, name_col], [code.strip(), name]
                if tax_col:
                    cols.append(tax_col); vals.append(tax)
                cur.execute(f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({','.join(['?']*len(vals))})", *vals)
            return {"ok": True, "code": code, "updated": bool(exists)}

    def _exists_doc(self, cur, hdr, doc_no_col, doc_type_col, doc_no, doc_type) -> bool:
        cur.execute(
            f"SELECT 1 FROM {hdr} WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
            str(doc_no).strip(), int(doc_type),
        )
        return cur.fetchone() is not None

    def invoice_exists(self, doc_no: str, doc_type: Optional[int]) -> Dict[str, Any]:
        with self._conn() as cn:
            cur = cn.cursor()
            hdr = pick_table(cur, ["HistoryHeader"])
            if not hdr:
                raise HTTPException(status_code=500, detail="HistoryHeader table not found")
            doc_no_col = pick_col(cur, hdr, ["DocumentNumber"])
            doc_type_col = pick_col(cur, hdr, ["DocumentType"])
            strict = False
            if doc_type is not None:
                strict = self._exists_doc(cur, hdr, doc_no_col, doc_type_col, doc_no, int(doc_type))
            cur.execute(
                f"SELECT {doc_type_col} FROM {hdr} WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?)",
                str(doc_no).strip(),
            )
            row = cur.fetchone()
            found = int(row[0]) if row else None
            return {"exists": found is not None, "exists_strict": bool(strict), "doc_type": found}

    def _coalesce_lines(self, raw_lines):
        bucket = {}
        for ln in raw_lines or []:
            name = (ln.get("name") or ln.get("label") or "").strip()
            key = (
                (ln.get("product_code") or "").strip(),
                name,
                round(float(ln.get("price_unit") or 0.0), 4),
                str(ln.get("tax_code") if ln.get("tax_code") is not None else "0"),
            )
            if key not in bucket:
                bucket[key] = {
                    "product_code": key[0] or None,
                    "name": name,
                    "quantity": float(ln.get("quantity") or 0.0),
                    "price_unit": key[2],
                    "tax_code": key[3],
                }
            else:
                bucket[key]["quantity"] += float(ln.get("quantity") or 0.0)
        return [v for v in bucket.values() if (v.get("name") or "").lower() != "sage import"]

    def post_invoice(self, payload: Dict[str, Any], replace: bool = False) -> Dict[str, Any]:
        if self.write_mode == "sdkcom":
            try:
                return post_invoice_sdk(
                    payload,
                    progid=config.SDKCOM_PROGID,
                    company_path=config.PASTEL_COMPANY_PATH,
                    username=config.PASTEL_USERNAME,
                    password=config.PASTEL_PASSWORD,
                )
            except Exception as exc:
                _logger.warning("SDKCOM invoice post failed, using ODBC fallback: %s", exc)
        return self._post_invoice_odbc(payload, replace=replace)

    def _post_invoice_odbc(self, payload: Dict[str, Any], replace: bool = False) -> Dict[str, Any]:
        customer = (payload.get("customer_code") or "").strip()
        if not customer:
            raise HTTPException(status_code=400, detail="customer_code required")
        if len(customer) > 6:
            raise HTTPException(
                status_code=400,
                detail="customer_code must be max 6 characters for Pastel (got %r)" % customer,
            )
        for ln in payload.get("lines") or []:
            if ln.get("tax_code") in (None, ""):
                raise HTTPException(
                    status_code=400,
                    detail="Mapped Sage tax_code is required on every line (no silent VAT default)",
                )
        doc_no = (payload.get("doc_no") or "").strip()
        if not doc_no:
            raise HTTPException(status_code=400, detail="doc_no required for ODBC guarded write")
        # Pastel HistoryHeader.DocumentNumber is CHAR(8)
        if len(doc_no) > 8 or "/" in doc_no:
            raise HTTPException(
                status_code=400,
                detail=(
                    "doc_no must be max 8 characters and cannot contain '/' "
                    "(Pastel DocumentNumber CHAR(8)). Got %r — use a short Sage Doc No."
                ) % doc_no,
            )
        doc_type = int(payload.get("document_type") or 3)
        lines = self._coalesce_lines(payload.get("lines") or [])
        inv_date = payload.get("invoice_date")
        pay_ref = (payload.get("payment_reference") or doc_no)[:30]
        deliv_dt = payload.get("delivery_date") or inv_date
        curr_code = payload.get("currency") or payload.get("currency_code") or "ZAR"
        try:
            with self._conn() as cn:
                cur = cn.cursor()
                hdr = pick_table(cur, ["HistoryHeader"])
                ln_tbl = pick_table(cur, ["HistoryLines"])
                doc_no_col = pick_col(cur, hdr, ["DocumentNumber"])
                doc_date_col = pick_col(cur, hdr, ["DocumentDate"])
                cust_code_col = pick_col(cur, hdr, ["CustomerCode"])
                doc_type_col = pick_col(cur, hdr, ["DocumentType"])
                total_col = pick_col(cur, hdr, ["Total"])
                total_tax_col = pick_col(cur, hdr, ["TotalTax"])
                pay_ref_col = pick_col(cur, hdr, ["PaymentReference", "OrderNumber", "Reference"])
                deliv_date_col = pick_col(cur, hdr, ["DeliveryDate", "DueDate"])
                curr_code_col = pick_col(cur, hdr, ["CurrencyCode"])
                ln_doc = pick_col(cur, ln_tbl, ["DocumentNumber"])
                ln_type = pick_col(cur, ln_tbl, ["DocumentType"])
                ln_item = pick_col(cur, ln_tbl, ["ItemCode"])
                ln_desc = pick_col(cur, ln_tbl, ["Description"])
                ln_qty = pick_col(cur, ln_tbl, ["Qty"])
                ln_price = pick_col(cur, ln_tbl, ["UnitPrice"])
                ln_tax = pick_col(cur, ln_tbl, ["TaxType"])
                exists = self._exists_doc(cur, hdr, doc_no_col, doc_type_col, doc_no, doc_type)
                if exists and not replace:
                    raise HTTPException(status_code=409, detail="Invoice already exists")
                if replace and not exists:
                    raise HTTPException(status_code=404, detail="Invoice not found")
                if replace and exists:
                    cur.execute(
                        f"DELETE FROM {ln_tbl} WHERE UPPER(RTRIM({ln_doc}))=UPPER(?) AND {ln_type}=?",
                        doc_no, int(doc_type),
                    )
                    cur.execute(
                        f"DELETE FROM {hdr} WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
                        doc_no, int(doc_type),
                    )
                h_cols, h_vals = [doc_type_col, doc_no_col, cust_code_col], [doc_type, doc_no, customer]
                if doc_date_col:
                    h_cols.append(doc_date_col); h_vals.append(inv_date)
                if deliv_date_col:
                    h_cols.append(deliv_date_col); h_vals.append(deliv_dt)
                if curr_code_col:
                    h_cols.append(curr_code_col); h_vals.append(CURRENCY_MAP.get(str(curr_code).upper(), 0))
                if pay_ref_col:
                    h_cols.append(pay_ref_col); h_vals.append(pay_ref)
                cur.execute(
                    f"INSERT INTO {hdr} ({', '.join(h_cols)}) VALUES ({','.join(['?']*len(h_vals))})",
                    *h_vals,
                )
                total = 0.0
                for ln in lines:
                    qty = float(ln.get("quantity") or 0)
                    price = float(ln.get("price_unit") or 0)
                    tax_code = ln.get("tax_code")
                    if tax_code in (None, ""):
                        raise HTTPException(
                            status_code=400,
                            detail="Each invoice line needs a mapped Sage tax_code (no silent default)",
                        )
                    try:
                        tax_type = int(str(tax_code).strip())
                    except (TypeError, ValueError):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Sage tax_code must be a Pastel TaxType number "
                                "(e.g. 15 for standard VAT), got %r"
                            ) % tax_code,
                        )
                    item_code = (ln.get("product_code") or ln.get("name") or "")[:16]
                    desc = (ln.get("name") or "")[:40]
                    cur.execute(
                        f"INSERT INTO {ln_tbl} ({ln_doc},{ln_type},{ln_item},{ln_desc},{ln_qty},{ln_price},{ln_tax}) "
                        f"VALUES (?,?,?,?,?,?,?)",
                        doc_no, doc_type, item_code, desc, qty, price, tax_type,
                    )
                    total += qty * price
                if total_col:
                    if total_tax_col:
                        cur.execute(
                            f"UPDATE {hdr} SET {total_col}=?, {total_tax_col}=? "
                            f"WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
                            total, 0, doc_no, int(doc_type),
                        )
                    else:
                        cur.execute(
                            f"UPDATE {hdr} SET {total_col}=? "
                            f"WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
                            total, doc_no, int(doc_type),
                        )
        except HTTPException:
            raise
        except Exception as exc:
            _logger.exception("ODBC invoice post failed")
            raise HTTPException(status_code=500, detail="ODBC invoice write failed: %s" % exc)
        return {
            "ok": True,
            "doc_no": doc_no,
            "write_mode": "odbc_guarded",
            "created": not exists or replace,
        }

    def post_receipt_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ptype = (payload.get("partner_type") or "customer").lower().strip()
        if ptype != "customer":
            raise HTTPException(status_code=501, detail="Supplier payments are not supported by this adapter")
        if not payload.get("batch_ref") or not payload.get("lines"):
            raise HTTPException(status_code=400, detail="batch_ref and at least one line are required")
        if self.write_mode == "sdkcom":
            sdk_res = post_receipt_sdk(
                payload,
                progid=config.SDKCOM_PROGID,
                company_path=config.PASTEL_COMPANY_PATH,
                username=config.PASTEL_USERNAME,
                password=config.PASTEL_PASSWORD,
            )
            if sdk_res:
                return sdk_res
        return self._post_receipts_odbc(payload)

    def _post_receipts_odbc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pay_date = to_date_sql(payload.get("payment_date"))
        with self._conn() as cn:
            cur = cn.cursor()
            tables = [t.table_name for t in cur.tables(tableType="TABLE").fetchall()]
            if not any((t or "").lower() == "receipttransactions" for t in tables):
                raise HTTPException(status_code=500, detail="ReceiptTransactions table not found")
            tbl = "ReceiptTransactions"
            rcpt_no_col = pick_col(cur, tbl, ["ReceiptNumber", "ReferenceNo", "Number", "DocNo"])
            rcpt_date_col = pick_col(cur, tbl, ["ReceiptDate", "Date"])
            cust_code_col = pick_col(cur, tbl, ["CustomerCode", "Code", "Account"])
            amount_col = pick_col(cur, tbl, ["Amount", "TotalAmount", "ReceiptAmount", "Value"])
            ref_col = pick_col(cur, tbl, ["Reference", "ExtReference", "Description"])
            curr_col = pick_col(cur, tbl, ["CurrencyCode", "Currency"])
            bank_col = pick_col(cur, tbl, ["BankAccount", "BankCode", "Cashbook", "Journal"])
            inv_col = pick_col(cur, tbl, ["InvoiceNumber", "DocumentNumber", "AllocDocNo"])
            if not (rcpt_no_col and rcpt_date_col and cust_code_col and amount_col):
                raise HTTPException(status_code=500, detail="Required ReceiptTransactions columns missing")
            inserted = 0
            allocated = 0
            batch_id = payload["batch_ref"].strip()
            for idx, ln in enumerate(payload.get("lines") or [], start=1):
                amt = float(ln.get("amount") or 0.0)
                if amt <= 0:
                    continue
                rcpt_no = f"{batch_id}-{idx:03d}"
                cols = [rcpt_no_col, rcpt_date_col, cust_code_col, amount_col]
                vals = [rcpt_no, pay_date, (ln.get("partner_code") or "").strip(), amt]
                if ref_col:
                    cols.append(ref_col); vals.append(ln.get("reference") or batch_id)
                if curr_col:
                    cols.append(curr_col); vals.append(ln.get("currency_code") or payload.get("currency_code") or "ZAR")
                if bank_col and payload.get("journal_code"):
                    cols.append(bank_col); vals.append(payload.get("journal_code"))
                if inv_col and ln.get("invoice_doc_no") and ln.get("allocate", True):
                    cols.append(inv_col); vals.append(ln.get("invoice_doc_no"))
                    allocated += 1
                cur.execute(
                    f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
                    *vals,
                )
                inserted += 1
            return {
                "ok": True,
                "batch_id": batch_id,
                "partner_type": "customer",
                "inserted": inserted,
                "allocated": allocated,
                "write_mode": "odbc_guarded",
                "invoice_allocation": bool(inv_col),
            }


ADAPTERS = {
    "pastel_partner": PastelPartnerOdbcSdkAdapter,
    "pastel_partner_18": PastelPartnerOdbcSdkAdapter,
    "pastel_partner_21": PastelPartnerOdbcSdkAdapter,
}


def get_adapter() -> SageAdapter:
    cls = ADAPTERS.get(config.ADAPTER_NAME, PastelPartnerOdbcSdkAdapter)
    return cls()
