# main.py
import os
import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union

import pyodbc
from fastapi import FastAPI, Header, HTTPException, Request, Query, Body, Path
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

# ----------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------
load_dotenv(find_dotenv(), override=True)

API_KEY = os.getenv("API_KEY", "")
DSN = os.getenv("ODBC_DSN", "")
DEFAULT_CURRENCY = os.getenv("BRIDGE_DEFAULT_CURRENCY", "ZAR")

app = FastAPI(title="Pastel Partner Bridge (Customers, Products, Suppliers, Invoices via doc_no)")

# ----------------------------------------------------------------------
# DB / Security helpers
# ----------------------------------------------------------------------
def get_conn():
    if not DSN:
        raise HTTPException(status_code=500, detail="ODBC_DSN missing from environment")
    return pyodbc.connect(f"DSN={DSN};", autocommit=True)

def require_key(header_key: Optional[str], query_key: Optional[str]):
    provided = header_key or query_key
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY missing from environment")
    if not provided or provided != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# ----------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------
def _to_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, Decimal):
        return float(x)
    s = str(x).strip()
    try:
        return float(s.replace(",", ""))
    except Exception:
        return None

def _to_date_str(d):
    if not d:
        return None
    try:
        if isinstance(d, datetime.datetime):
            return d.date().isoformat()
        if isinstance(d, datetime.date):
            return d.isoformat()
        s = str(d)
        if len(s) == 8 and s.isdigit():
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        return s
    except Exception:
        return None

def _norm_text(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and float(v) == 0:
        return None
    s = str(v).strip()
    return s or None

def _to_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (bytes, bytearray)):
        if len(v) == 1:
            return v not in (b'\x00', b'0')
        try:
            v = v.decode(errors="ignore")
        except Exception:
            v = str(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "t", "y", "yes", "on"}:
        return True
    if s in {"0", "false", "f", "n", "no", "off", "", "\x00"}:
        return False
    try:
        return bool(int(float(s)))
    except Exception:
        return False

def _qident(name: str) -> str:
    return name

def _pick_table(cur, candidates: List[str]) -> Optional[str]:
    tables = [t.table_name for t in cur.tables(tableType="TABLE").fetchall()]
    for want in candidates:
        for t in tables:
            if t and t.lower() == want.lower():
                return t
    for want in candidates:
        for t in tables:
            if t and want.lower() in t.lower():
                return t
    return None

def _pick_col_from(cur, table: str, candidates: List[str]) -> Optional[str]:
    cols = [r.column_name for r in cur.columns(table=table)]
    for want in candidates:
        for c in cols:
            if c and c.lower() == want.lower():
                return c
    for want in candidates:
        for c in cols:
            if c and want.lower() in c.lower():
                return c
    return None

def _cast_char50(expr: str) -> str:
    return f"CAST({expr} AS CHAR(50))"

def _norm_doc_no(v: str) -> str:
    return (str(v or "")).strip().upper()

def _exists_doc(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no: str, doc_type: int) -> bool:
    cur.execute(
        f"SELECT 1 FROM {hdr_tbl} WHERE UPPER(RTRIM({doc_no_col})) = ? AND {doc_type_col} = ?",
        _norm_doc_no(doc_no), int(doc_type),
    )
    return cur.fetchone() is not None

def _find_invoice_doc_type(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no) -> Optional[int]:
    cur.execute(
        f"SELECT TOP 1 {doc_type_col} FROM {hdr_tbl} WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?)",
        str(doc_no).strip()
    )
    row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else None
    

# ----------------------------------------------------------------------
# Pydantic models
# ----------------------------------------------------------------------
class CustomerOut(BaseModel):
    code: str
    name: Optional[str] = None
    address1: Optional[str] = None
    address2: Optional[str] = None
    address3: Optional[str] = None
    address4: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    contact_person: Optional[str] = None
    tax_code: Optional[str] = None
    credit_limit: Optional[float] = None
    balance: Optional[float] = None
    settlement_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    discount_percent: Optional[float] = None
    country_code: Optional[str] = None
    currency_code: Optional[str] = None
    interest_after_days: Optional[int] = None
    price_regime: Optional[str] = None
    blocked: Optional[bool] = None
    updated_on: Optional[str] = None
    create_date: Optional[str] = None
    guid: Optional[str] = None

class ProductOut(BaseModel):
    code: str
    name: Optional[str] = None
    category: Optional[str] = None
    barcode: Optional[str] = None
    unit_size: Optional[str] = None
    tax_code: Optional[Union[str, int]] = None
    gl_code: Optional[str] = None
    allow_tax: Optional[bool] = None
    weight: Optional[float] = None
    price_1: Optional[float] = None
    price_2: Optional[float] = None
    price_3: Optional[float] = None
    price_4: Optional[float] = None
    price_5: Optional[float] = None
    qty_on_hand: Optional[float] = None
    qty_on_order: Optional[float] = None
    reorder_level: Optional[float] = None
    custom_text1: Optional[str] = None
    updated_on: Optional[str] = None
    guid: Optional[str] = None

class SupplierOut(BaseModel):
    code: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    credit_limit: Optional[float] = None
    balance: Optional[float] = None
    tax_code: Optional[Union[str, int]] = None
    country_code: Optional[Union[str, int]] = None
    currency_code: Optional[Union[str, int]] = None
    payment_terms: Optional[Union[str, int]] = None
    settlement_terms: Optional[Union[str, int]] = None
    updated_on: Optional[str] = None
    guid: Optional[str] = None

class InvoiceLineOut(BaseModel):
    product_code: Optional[str] = None
    name: Optional[str] = None
    quantity: float = 0.0
    price_unit: float = 0.0
    tax_code: Optional[str] = None

class InvoiceOut(BaseModel):
    doc_no: str
    invoice_date: Optional[str] = None
    customer_code: Optional[str] = None
    amount_total: float = 0.0
    amount_total_excl: float = 0.0
    tax_amount: float = 0.0
    document_type: Optional[int] = None
    payment_reference: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_date: Optional[str] = None
    currency_code: Optional[str] = None
    lines: List[InvoiceLineOut] = []

# ----------------------------------------------------------------------
# Basic endpoints & debug
# ----------------------------------------------------------------------
@app.get("/health")
def health():
    with get_conn() as cn:
        cn.cursor().execute("SELECT 1")
    return {"ok": True}

@app.get("/debug/key")
def debug_key(req: Request):
    sent = req.headers.get("x-api-key") or ""
    return {
        "loaded_api_key_beg": (API_KEY or "")[:4],
        "loaded_api_key_len": len(API_KEY or ""),
        "sent_api_key_beg": sent[:4],
        "sent_api_key_len": len(sent),
    }

# ----------------------------------------------------------------------
# CUSTOMERS
# ----------------------------------------------------------------------
@app.get("/customers", response_model=List[CustomerOut])
def list_customers(
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    q: Optional[str] = Query(None, description="search code/name contains"),
):
    require_key(x_api_key, key)
    out: List[CustomerOut] = []
    with get_conn() as cn:
        cur = cn.cursor()
        cust_tbl = _pick_table(cur, ["CustomerMaster", "Customers", "Debtors", "ARCustomers"])
        if not cust_tbl:
            raise HTTPException(status_code=500, detail="Customer table not found")
        code_col = _pick_col_from(cur, cust_tbl, ["CustomerCode", "Code", "Account"])
        name_col = _pick_col_from(cur, cust_tbl, ["CustomerDesc", "Description", "Name"])
        addr1 = _pick_col_from(cur, cust_tbl, ["PostAddress01", "Address1"])
        addr2 = _pick_col_from(cur, cust_tbl, ["PostAddress02", "Address2"])
        addr3 = _pick_col_from(cur, cust_tbl, ["PostAddress03", "Address3"])
        addr4 = _pick_col_from(cur, cust_tbl, ["PostAddress04", "Address4"])
        pcode = _pick_col_from(cur, cust_tbl, ["PostAddress05", "PostalCode"])
        phone = _pick_col_from(cur, cust_tbl, ["Telephone", "Phone"])
        fax   = _pick_col_from(cur, cust_tbl, ["Fax"])
        email = _pick_col_from(cur, cust_tbl, ["EMail", "Email"])
        contact = _pick_col_from(cur, cust_tbl, ["Contact"])
        tax    = _pick_col_from(cur, cust_tbl, ["TaxCode", "TaxType"])
        crlim  = _pick_col_from(cur, cust_tbl, ["CreditLimit"])
        bal    = _pick_col_from(cur, cust_tbl, ["CurrBalanceThis01", "Balance", "CurrentBalance"])
        settle = _pick_col_from(cur, cust_tbl, ["SettlementTerms"])
        payt   = _pick_col_from(cur, cust_tbl, ["PaymentTerms"])
        disc   = _pick_col_from(cur, cust_tbl, ["Discount"])
        ctry   = _pick_col_from(cur, cust_tbl, ["CountryCode"])
        curr   = _pick_col_from(cur, cust_tbl, ["CurrencyCode"])
        intr   = _pick_col_from(cur, cust_tbl, ["InterestAfter"])
        price_regime = _pick_col_from(cur, cust_tbl, ["PriceRegime"])
        blocked = _pick_col_from(cur, cust_tbl, ["Blocked", "IsActive"])
        upd    = _pick_col_from(cur, cust_tbl, ["UpdatedOn", "UpdateDate"])
        created= _pick_col_from(cur, cust_tbl, ["CreateDate"])
        guid   = _pick_col_from(cur, cust_tbl, ["GUID"])

        if not code_col or not name_col:
            raise HTTPException(status_code=500, detail="Required columns not found on customer table")

        sel = [f"{code_col} AS code", f"{name_col} AS name"]
        def add(col, alias):
            if col: sel.append(f"{col} AS {alias}")
        add(addr1,"address1"); add(addr2,"address2"); add(addr3,"address3"); add(addr4,"address4")
        add(pcode,"postal_code"); add(phone,"phone"); add(fax,"fax"); add(email,"email")
        add(contact,"contact_person"); add(tax,"tax_code"); add(crlim,"credit_limit"); add(bal,"balance")
        add(settle,"settlement_terms"); add(payt,"payment_terms"); add(disc,"discount_percent")
        add(ctry,"country_code"); add(curr,"currency_code"); add(intr,"interest_after_days")
        add(price_regime,"price_regime"); add(blocked,"blocked"); add(upd,"updated_on")
        add(created,"create_date"); add(guid,"guid")

        where, params = [], []
        if q:
            like = f"%{q}%"
            where.append(f"(UPPER({code_col}) LIKE UPPER(?) OR UPPER({name_col}) LIKE UPPER(?))")
            params += [like, like]

        sql = f"""
            SELECT TOP {int(limit)} {", ".join(sel)}
            FROM {_qident(cust_tbl)}
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY {name_col}
        """
        cur.execute(sql, *params)
        cols = [c[0].lower() for c in cur.description]
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            out.append(CustomerOut(
                code=str(d.get("code") or "").strip(),
                name=_norm_text(d.get("name")),
                address1=_norm_text(d.get("address1")),
                address2=_norm_text(d.get("address2")),
                address3=_norm_text(d.get("address3")),
                address4=_norm_text(d.get("address4")),
                postal_code=_norm_text(d.get("postal_code")),
                phone=_norm_text(d.get("phone")),
                fax=_norm_text(d.get("fax")),
                email=_norm_text(d.get("email")),
                contact_person=_norm_text(d.get("contact_person")),
                tax_code=_norm_text(d.get("tax_code")),
                credit_limit=_to_float(d.get("credit_limit")),
                balance=_to_float(d.get("balance")),
                settlement_terms=_norm_text(d.get("settlement_terms")),
                payment_terms=_norm_text(d.get("payment_terms")),
                discount_percent=_to_float(d.get("discount_percent")),
                country_code=_norm_text(d.get("country_code")),
                currency_code=_norm_text(d.get("currency_code")),
                interest_after_days=int(_to_float(d.get("interest_after_days")) or 0) if d.get("interest_after_days") is not None else None,
                price_regime=_norm_text(d.get("price_regime")),
                blocked=_to_bool(d.get("blocked")),
                updated_on=_norm_text(d.get("updated_on")),
                create_date=_norm_text(d.get("create_date")),
                guid=_norm_text(d.get("guid")),
            ))
    return out

@app.put("/customers/{code}")
def upsert_customer(
    code: str,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None
):
    require_key(x_api_key, key)
    with get_conn() as cn:
        cur = cn.cursor()
        cust_tbl = _pick_table(cur, ["CustomerMaster", "Customers"])
        if not cust_tbl:
            raise HTTPException(status_code=500, detail="Customer table not found")
        code_col = _pick_col_from(cur, cust_tbl, ["CustomerCode", "Code", "Account"])
        name_col = _pick_col_from(cur, cust_tbl, ["CustomerDesc", "Description", "Name"])
        tax_col  = _pick_col_from(cur, cust_tbl, ["TaxCode", "TaxType"])
        curr_col = _pick_col_from(cur, cust_tbl, ["CurrencyCode"])
        crlim_col= _pick_col_from(cur, cust_tbl, ["CreditLimit"])
        if not (code_col and name_col):
            raise HTTPException(status_code=500, detail="Customer code/name columns missing")

        name = payload.get("name") or code
        tax  = payload.get("tax_code")
        curr = payload.get("currency_code")
        crlim= payload.get("credit_limit") or 0

        cur.execute(f"SELECT 1 FROM {cust_tbl} WHERE UPPER(RTRIM({code_col}))=UPPER(?)", code.strip())
        exists = cur.fetchone() is not None
        if exists:
            sets, vals = [f"{name_col}=?"], [name]
            if crlim_col: sets.append(f"{crlim_col}=?"); vals.append(crlim)
            if tax_col:   sets.append(f"{tax_col}=?");   vals.append(tax)
            if curr_col:  sets.append(f"{curr_col}=?");  vals.append(curr)
            vals.append(code.strip())
            cur.execute(f"UPDATE {cust_tbl} SET {', '.join(sets)} WHERE UPPER(RTRIM({code_col}))=UPPER(?)", *vals)
        else:
            cols = [code_col, name_col]
            vals = [code.strip(), name]
            if crlim_col: cols.append(crlim_col); vals.append(crlim)
            if tax_col:   cols.append(tax_col);   vals.append(tax)
            if curr_col:  cols.append(curr_col);  vals.append(curr)
            qmarks = ",".join(["?"]*len(vals))
            cur.execute(f"INSERT INTO {cust_tbl} ({', '.join(cols)}) VALUES ({qmarks})", *vals)
        return {"ok": True, "code": code, "updated": bool(exists)}

# ----------------------------------------------------------------------
# PRODUCTS
# ----------------------------------------------------------------------
@app.get("/products", response_model=List[ProductOut])
def list_products(
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    q: Optional[str] = Query(None, description="search code/name contains"),
):
    require_key(x_api_key, key)
    out: List[ProductOut] = []
    with get_conn() as cn:
        cur = cn.cursor()
        inv_tbl = _pick_table(cur, ["Inventory", "Stock", "Items"])
        if not inv_tbl:
            raise HTTPException(status_code=500, detail="Inventory table not found")
        code_col = _pick_col_from(cur, inv_tbl, ["ItemCode", "Code"])
        name_col = _pick_col_from(cur, inv_tbl, ["Description", "Name"])
        cat_col  = _pick_col_from(cur, inv_tbl, ["Category"])
        bc_col   = _pick_col_from(cur, inv_tbl, ["Barcode"])
        unit_col = _pick_col_from(cur, inv_tbl, ["UnitSize", "UOM"])
        tax_col  = _pick_col_from(cur, inv_tbl, ["SalesTaxType", "TaxType"])
        gl_col   = _pick_col_from(cur, inv_tbl, ["GLCode"])
        allow_col= _pick_col_from(cur, inv_tbl, ["AllowTax"])
        wt_col   = _pick_col_from(cur, inv_tbl, ["NettMass", "Weight"])
        custom1  = _pick_col_from(cur, inv_tbl, ["UserDefText01"])
        upd_col  = _pick_col_from(cur, inv_tbl, ["UpdatedOn", "UpdateDate"])
        guid_col = _pick_col_from(cur, inv_tbl, ["GUID"])
        if not (code_col and name_col):
            raise HTTPException(status_code=500, detail="Required columns not found on inventory table")

        sel = [f"{code_col} AS code", f"{name_col} AS name"]
        def add(c, a):
            if c: sel.append(f"{c} AS {a}")
        add(cat_col,"category"); add(bc_col,"barcode"); add(unit_col,"unit_size")
        add(tax_col,"tax_code"); add(gl_col,"gl_code"); add(allow_col,"allow_tax")
        add(wt_col,"weight"); add(custom1,"custom_text1"); add(upd_col,"updated_on"); add(guid_col,"guid")

        where, params = [], []
        if q:
            like=f"%{q}%"
            where.append(f"(UPPER({code_col}) LIKE UPPER(?) OR UPPER({name_col}) LIKE UPPER(?))")
            params += [like, like]

        sql = f"""
            SELECT TOP {int(limit)} {", ".join(sel)}
            FROM {_qident(inv_tbl)}
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY {name_col}
        """
        cur.execute(sql, *params)
        cols = [c[0].lower() for c in cur.description]
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            out.append(ProductOut(
                code=str(d.get("code") or "").strip(),
                name=_norm_text(d.get("name")),
                category=_norm_text(d.get("category")),
                barcode=_norm_text(d.get("barcode")),
                unit_size=_norm_text(d.get("unit_size")),
                tax_code=_norm_text(d.get("tax_code")),
                gl_code=_norm_text(d.get("gl_code")),
                allow_tax=_to_bool(d.get("allow_tax")),
                weight=_to_float(d.get("weight")),
                custom_text1=_norm_text(d.get("custom_text1")),
                updated_on=_norm_text(d.get("updated_on")),
                guid=_norm_text(d.get("guid")),
            ))
    return out

@app.put("/products/{code}")
def upsert_product(
    code: str,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None
):
    require_key(x_api_key, key)
    with get_conn() as cn:
        cur = cn.cursor()
        inv_tbl = _pick_table(cur, ["Inventory", "Stock", "Items"])
        if not inv_tbl:
            raise HTTPException(status_code=500, detail="Inventory table not found")
        code_col = _pick_col_from(cur, inv_tbl, ["ItemCode", "Code"])
        name_col = _pick_col_from(cur, inv_tbl, ["Description", "Name"])
        tax_col  = _pick_col_from(cur, inv_tbl, ["SalesTaxType", "TaxType"])
        if not (code_col and name_col):
            raise HTTPException(status_code=500, detail="Inventory code/name columns missing")

        name = payload.get("name") or code
        tax  = payload.get("tax_code")

        cur.execute(f"SELECT 1 FROM {inv_tbl} WHERE UPPER(RTRIM({code_col}))=UPPER(?)", code.strip())
        exists = cur.fetchone() is not None
        if exists:
            if tax_col:
                cur.execute(f"UPDATE {inv_tbl} SET {name_col}=?, {tax_col}=? WHERE UPPER(RTRIM({code_col}))=UPPER(?)",
                            name, tax, code.strip())
            else:
                cur.execute(f"UPDATE {inv_tbl} SET {name_col}=? WHERE UPPER(RTRIM({code_col}))=UPPER(?)",
                            name, code.strip())
        else:
            cols = [code_col, name_col]
            vals = [code.strip(), name]
            if tax_col:
                cols.append(tax_col); vals.append(tax)
            qmarks = ",".join(["?"]*len(vals))
            cur.execute(f"INSERT INTO {inv_tbl} ({', '.join(cols)}) VALUES ({qmarks})", *vals)
        return {"ok": True, "code": code, "updated": bool(exists)}

# ----------------------------------------------------------------------
# SUPPLIERS (read-only)
# ----------------------------------------------------------------------
@app.get("/suppliers", response_model=List[SupplierOut])
def list_suppliers(
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    q: Optional[str] = Query(None, description="search code/name contains"),
):
    require_key(x_api_key, key)
    out: List[SupplierOut] = []
    with get_conn() as cn:
        cur = cn.cursor()
        sup_tbl = _pick_table(cur, ["SupplierMaster", "CreditorMaster", "Suppliers"])
        if not sup_tbl:
            raise HTTPException(status_code=500, detail="Supplier table not found")
        code_col = _pick_col_from(cur, sup_tbl, ["SupplierCode", "CreditorCode", "Account", "Code"])
        name_col = _pick_col_from(cur, sup_tbl, ["SupplierDesc", "CreditorDesc", "Description", "Name"])
        phone_col = _pick_col_from(cur, sup_tbl, ["Telephone", "Phone"])
        email_col = _pick_col_from(cur, sup_tbl, ["EMail", "Email"])
        credit_limit_col = _pick_col_from(cur, sup_tbl, ["CreditLimit"])
        balance_col = _pick_col_from(cur, sup_tbl, ["CurrBalanceThis01", "BalanceThis01", "CurrentBalance", "Balance"])
        tax_code_col = _pick_col_from(cur, sup_tbl, ["TaxCode", "TaxType", "SalesTaxType"])
        country_col = _pick_col_from(cur, sup_tbl, ["CountryCode"])
        currency_col = _pick_col_from(cur, sup_tbl, ["CurrencyCode"])
        pay_terms_col = _pick_col_from(cur, sup_tbl, ["PaymentTerms"])
        settle_terms_col = _pick_col_from(cur, sup_tbl, ["SettlementTerms"])
        updated_on_col = _pick_col_from(cur, sup_tbl, ["UpdatedOn", "UpdateDate"])
        guid_col = _pick_col_from(cur, sup_tbl, ["GUID"])
        if not (code_col and name_col):
            raise HTTPException(status_code=500, detail="Supplier code/name columns missing")

        sel = [f"{code_col} AS code", f"{name_col} AS name"]
        def add(c, a):
            if c: sel.append(f"{c} AS {a}")
        add(phone_col,"phone"); add(email_col,"email"); add(credit_limit_col,"credit_limit")
        add(balance_col,"balance"); add(tax_code_col,"tax_code"); add(country_col,"country_code")
        add(currency_col,"currency_code"); add(pay_terms_col,"payment_terms")
        add(settle_terms_col,"settlement_terms"); add(updated_on_col,"updated_on"); add(guid_col,"guid")

        where, params = [], []
        if q:
            like=f"%{q}%"
            where.append(f"(UPPER({code_col}) LIKE UPPER(?) OR UPPER({name_col}) LIKE UPPER(?))")
            params += [like, like]

        sql = f"""
            SELECT TOP {int(limit)} {", ".join(sel)}
            FROM {_qident(sup_tbl)}
            {"WHERE " + " AND ".join(where) if where else ""}
            ORDER BY {name_col}
        """
        cur.execute(sql, *params)
        cols = [c[0].lower() for c in cur.description]
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            out.append(SupplierOut(
                code=str(d.get("code") or "").strip(),
                name=_norm_text(d.get("name")),
                phone=_norm_text(d.get("phone")),
                email=_norm_text(d.get("email")),
                credit_limit=_to_float(d.get("credit_limit")),
                balance=_to_float(d.get("balance")),
                tax_code=_norm_text(d.get("tax_code")),
                country_code=_norm_text(d.get("country_code")),
                currency_code=_norm_text(d.get("currency_code")),
                payment_terms=_norm_text(d.get("payment_terms")),
                settlement_terms=_norm_text(d.get("settlement_terms")),
                updated_on=_norm_text(d.get("updated_on")),
                guid=_norm_text(d.get("guid")),
            ))
    return out

# ----------------------------------------------------------------------
# INVOICES
# ----------------------------------------------------------------------
def _coalesce_lines_server(raw_lines):
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
    out = []
    for v in bucket.values():
        n = (v.get("name") or "").lower()
        p = (v.get("product_code") or "").lower()
        if n == "sage import" and p == "sage import":
            continue
        out.append(v)
    return out

def _insert_header_and_lines(
    cur,
    hdr_tbl, ln_tbl,
    doc_no_col, doc_date_col, cust_code_col, doc_type_col,
    total_col, total_tax_col, excl_incl_col,
    pay_ref_col, pay_terms_col, deliv_date_col, curr_code_col,
    ln_doc_no_col, ln_doc_type_col, ln_item_col, ln_desc_col, ln_qty_col, ln_price_col, ln_tax_col,
    *,
    doc_no, inv_date, customer, doc_type, pay_ref, pay_terms, deliv_dt, curr_code,
    lines
):
    # header
    h_cols, h_vals = [], []
    def add(c, v):
        if c is not None and v is not None:
            h_cols.append(c); h_vals.append(v)

    add(doc_type_col, doc_type)
    add(doc_no_col, doc_no)
    add(cust_code_col, customer)
    add(doc_date_col, inv_date)
    add(pay_terms_col, int(pay_terms) if pay_terms not in (None, "", False) else 0)
    add(deliv_date_col if deliv_dt is not None else None, deliv_dt)
    add(curr_code_col, int(curr_code) if curr_code not in (None, "", False) else 0)
    add(pay_ref_col, pay_ref)
    if excl_incl_col: add(excl_incl_col, 0)
    if total_col:     add(total_col, 0)
    if total_tax_col: add(total_tax_col, 0)

    cur.execute(
        f"INSERT INTO {hdr_tbl} ({', '.join(h_cols)}) VALUES ({', '.join(['?']*len(h_cols))})",
        *h_vals
    )

    total = 0.0
    total_tax = 0.0
    for ln in lines:
        prod_code = ln.get("product_code") or ln.get("name") or ln.get("label")
        desc      = ln.get("description") or ln.get("decription") or ln.get("name") or ln.get("label")
        qty       = float(ln.get("quantity") or 0)
        price     = float(ln.get("price_unit") or ln.get("lst_price") or 0)
        tax_code  = ln.get("tax_code")
        cur.execute(
            f"""INSERT INTO {ln_tbl}
                ({ln_doc_no_col},{ln_doc_type_col},{ln_item_col},{ln_desc_col},{ln_qty_col},{ln_price_col},{ln_tax_col})
                VALUES (?,?,?,?,?,?,?)""",
            doc_no, doc_type, prod_code, desc, qty, price, tax_code
        )
        total += qty * price

    if total_col:
        if total_tax_col:
            cur.execute(
                f"UPDATE {hdr_tbl} SET {total_col}=?, {total_tax_col}=? "
                f"WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
                total, total_tax, str(doc_no).strip(), int(doc_type)
            )
        else:
            cur.execute(
                f"UPDATE {hdr_tbl} SET {total_col}=? "
                f"WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
                total, str(doc_no).strip(), int(doc_type)
            )
    return total

@app.get("/invoices/exists")
def invoice_exists(
    doc_no: str = Query(...),
    doc_type: Optional[int] = Query(None),
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None
):
    require_key(x_api_key, key)
    with get_conn() as cn:
        cur = cn.cursor()
        hdr_tbl = _pick_table(cur, ["HistoryHeader"])
        if not hdr_tbl:
            raise HTTPException(status_code=500, detail="HistoryHeader table not found")
        doc_no_col = _pick_col_from(cur, hdr_tbl, ["DocumentNumber"])
        doc_type_col = _pick_col_from(cur, hdr_tbl, ["DocumentType"])
        if not (doc_no_col and doc_type_col):
            raise HTTPException(status_code=500, detail="Required columns missing")
        strict = False
        if doc_type is not None:
            strict = _exists_doc(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no, int(doc_type))
        found_type = _find_invoice_doc_type(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no)
        return {"exists": found_type is not None, "exists_strict": bool(strict), "doc_type": found_type}

@app.post("/invoices")
def create_invoice(
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None
):
    require_key(x_api_key, key)
    doc_no = payload.get("doc_no")
    if not doc_no:
        raise HTTPException(status_code=400, detail="doc_no required")
    return _write_invoice(doc_no, payload, mode="create")

@app.put("/invoices/{doc_no:path}")
def replace_invoice(
    doc_no: str,
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None
):
    require_key(x_api_key, key)
    payload = dict(payload or {})
    payload["doc_no"] = doc_no
    return _write_invoice_smart_replace(doc_no, payload)

def _write_invoice(doc_no: str, payload: dict, *, mode: str):
    customer   = payload.get("customer_code")
    inv_date   = payload.get("invoice_date")
    doc_type   = int(payload.get("document_type") or 3)
    lines      = _coalesce_lines_server(payload.get("lines") or [])
    pay_ref    = payload.get("payment_reference") or doc_no
    pay_terms  = payload.get("invoice_payment_term_id")
    deliv_dt   = payload.get("delivery_date") or payload.get("invoice_date_due") or inv_date
    curr_code  = payload.get("currency_id")

    if not customer:
        raise HTTPException(status_code=400, detail="customer_code required")

    with get_conn() as cn:
        cur = cn.cursor()
        hdr_tbl = _pick_table(cur, ["HistoryHeader"])
        ln_tbl  = _pick_table(cur, ["HistoryLines"])
        if not (hdr_tbl and ln_tbl):
            raise HTTPException(status_code=500, detail="History tables not found")

        doc_no_col     = _pick_col_from(cur, hdr_tbl, ["DocumentNumber"])
        doc_date_col   = _pick_col_from(cur, hdr_tbl, ["DocumentDate"])
        cust_code_col  = _pick_col_from(cur, hdr_tbl, ["CustomerCode"])
        doc_type_col   = _pick_col_from(cur, hdr_tbl, ["DocumentType"])
        total_col      = _pick_col_from(cur, hdr_tbl, ["Total"])
        total_tax_col  = _pick_col_from(cur, hdr_tbl, ["TotalTax"])
        excl_incl_col  = _pick_col_from(cur, hdr_tbl, ["ExclIncl"])
        pay_ref_col    = _pick_col_from(cur, hdr_tbl, ["PaymentReference", "OrderNumber", "Reference", "ExtReference"])
        pay_terms_col  = _pick_col_from(cur, hdr_tbl, ["PaymentTerms", "Terms"])
        deliv_date_col = _pick_col_from(cur, hdr_tbl, ["DeliveryDate", "DueDate", "ClosingDate"])
        curr_code_col  = _pick_col_from(cur, hdr_tbl, ["CurrencyCode"])

        ln_doc_no_col   = _pick_col_from(cur, ln_tbl, ["DocumentNumber"])
        ln_doc_type_col = _pick_col_from(cur, ln_tbl, ["DocumentType"])
        ln_item_col     = _pick_col_from(cur, ln_tbl, ["ItemCode"])
        ln_desc_col     = _pick_col_from(cur, ln_tbl, ["Description"])
        ln_qty_col      = _pick_col_from(cur, ln_tbl, ["Qty"])
        ln_price_col    = _pick_col_from(cur, ln_tbl, ["UnitPrice"])
        ln_tax_col      = _pick_col_from(cur, ln_tbl, ["TaxType"])

        if not all([doc_no_col, doc_type_col, ln_doc_no_col, ln_doc_type_col]):
            raise HTTPException(status_code=500, detail="Required columns missing")

        exists = _exists_doc(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no, doc_type)
        if mode == "create" and exists:
            raise HTTPException(status_code=409, detail="Invoice already exists")
        if mode == "replace" and not exists:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if mode == "replace":
            cur.execute(
                f"DELETE FROM {ln_tbl} WHERE UPPER(RTRIM({ln_doc_no_col}))=UPPER(?) AND {ln_doc_type_col}=?",
                str(doc_no).strip(), int(doc_type)
            )
            cur.execute(
                f"DELETE FROM {hdr_tbl} WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
                str(doc_no).strip(), int(doc_type)
            )

        total = _insert_header_and_lines(
            cur,
            hdr_tbl, ln_tbl,
            doc_no_col, doc_date_col, cust_code_col, doc_type_col,
            total_col, total_tax_col, excl_incl_col,
            pay_ref_col, pay_terms_col, deliv_date_col, curr_code_col,
            ln_doc_no_col, ln_doc_type_col, ln_item_col, ln_desc_col, ln_qty_col, ln_price_col, ln_tax_col,
            doc_no=doc_no, inv_date=inv_date, customer=customer, doc_type=doc_type,
            pay_ref=pay_ref, pay_terms=pay_terms, deliv_dt=deliv_dt, curr_code=curr_code,
            lines=lines
        )
    return {"ok": True, "doc_no": _norm_doc_no(doc_no), "mode": mode, "lines": len(lines), "total_excl": round(total, 2)}

def _write_invoice_smart_replace(doc_no: str, payload: dict):
    customer   = payload.get("customer_code")
    inv_date   = payload.get("invoice_date")
    req_type   = int(payload.get("document_type") or 3)
    lines      = _coalesce_lines_server(payload.get("lines") or [])
    pay_ref    = payload.get("payment_reference") or doc_no
    pay_terms  = payload.get("invoice_payment_term_id")
    deliv_dt   = payload.get("delivery_date") or payload.get("invoice_date_due") or inv_date
    curr_code  = payload.get("currency_id")

    if not customer:
        raise HTTPException(status_code=400, detail="customer_code required")

    with get_conn() as cn:
        cur = cn.cursor()
        hdr_tbl = _pick_table(cur, ["HistoryHeader"])
        ln_tbl  = _pick_table(cur, ["HistoryLines"])
        if not (hdr_tbl and ln_tbl):
            raise HTTPException(status_code=500, detail="History tables not found")

        doc_no_col     = _pick_col_from(cur, hdr_tbl, ["DocumentNumber"])
        doc_date_col   = _pick_col_from(cur, hdr_tbl, ["DocumentDate"])
        cust_code_col  = _pick_col_from(cur, hdr_tbl, ["CustomerCode"])
        doc_type_col   = _pick_col_from(cur, hdr_tbl, ["DocumentType"])
        total_col      = _pick_col_from(cur, hdr_tbl, ["Total"])
        total_tax_col  = _pick_col_from(cur, hdr_tbl, ["TotalTax"])
        excl_incl_col  = _pick_col_from(cur, hdr_tbl, ["ExclIncl"])
        pay_ref_col    = _pick_col_from(cur, hdr_tbl, ["PaymentReference", "OrderNumber", "Reference", "ExtReference"])
        pay_terms_col  = _pick_col_from(cur, hdr_tbl, ["PaymentTerms", "Terms"])
        deliv_date_col = _pick_col_from(cur, hdr_tbl, ["DeliveryDate", "DueDate", "ClosingDate"])
        curr_code_col  = _pick_col_from(cur, hdr_tbl, ["CurrencyCode"])

        ln_doc_no_col   = _pick_col_from(cur, ln_tbl, ["DocumentNumber"])
        ln_doc_type_col = _pick_col_from(cur, ln_tbl, ["DocumentType"])
        ln_item_col     = _pick_col_from(cur, ln_tbl, ["ItemCode"])
        ln_desc_col     = _pick_col_from(cur, ln_tbl, ["Description"])
        ln_qty_col      = _pick_col_from(cur, ln_tbl, ["Qty"])
        ln_price_col    = _pick_col_from(cur, ln_tbl, ["UnitPrice"])
        ln_tax_col      = _pick_col_from(cur, ln_tbl, ["TaxType"])

        if not all([doc_no_col, doc_type_col, ln_doc_no_col, ln_doc_type_col]):
            raise HTTPException(status_code=500, detail="Required columns missing")

        existing_type = _find_invoice_doc_type(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no)
        use_type = existing_type if existing_type is not None else req_type

        cur.execute(
            f"DELETE FROM {ln_tbl} WHERE UPPER(RTRIM({ln_doc_no_col}))=UPPER(?) AND {ln_doc_type_col}=?",
            str(doc_no).strip(), int(use_type)
        )
        cur.execute(
            f"DELETE FROM {hdr_tbl} WHERE UPPER(RTRIM({doc_no_col}))=UPPER(?) AND {doc_type_col}=?",
            str(doc_no).strip(), int(use_type)
        )

        total = _insert_header_and_lines(
            cur,
            hdr_tbl, ln_tbl,
            doc_no_col, doc_date_col, cust_code_col, doc_type_col,
            total_col, total_tax_col, excl_incl_col,
            pay_ref_col, pay_terms_col, deliv_date_col, curr_code_col,
            ln_doc_no_col, ln_doc_type_col, ln_item_col, ln_desc_col, ln_qty_col, ln_price_col, ln_tax_col,
            doc_no=doc_no, inv_date=inv_date, customer=customer, doc_type=use_type,
            pay_ref=pay_ref, pay_terms=pay_terms, deliv_dt=deliv_dt, curr_code=curr_code,
            lines=lines
        )
    return {"ok": True, "doc_no": _norm_doc_no(doc_no), "document_type": use_type, "mode": "replace", "total_excl": round(total, 2)}

# -------- Idempotent insert-by-doc_no (SKIPS if exists) --------
@app.post("/invoices/upsert_by_doc")
def upsert_by_doc(
    payload: dict = Body(...),
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None,
):
    require_key(x_api_key, key)

    doc_no    = payload.get("doc_no")
    customer  = payload.get("customer_code")
    inv_date  = payload.get("invoice_date")
    doc_type  = int(payload.get("document_type") or 3)

    if not doc_no:
        raise HTTPException(status_code=400, detail="doc_no required")
    if not customer:
        raise HTTPException(status_code=400, detail="customer_code required")

    doc_no_norm = _norm_doc_no(doc_no)
    lines = _coalesce_lines_server(payload.get("lines") or [])

    pay_ref   = payload.get("payment_reference") or doc_no_norm
    pay_terms = payload.get("invoice_payment_term_id")
    deliv_dt  = payload.get("delivery_date") or payload.get("invoice_date_due") or inv_date
    curr_code = payload.get("currency_id")

    with get_conn() as cn:
        cur = cn.cursor()
        hdr_tbl = _pick_table(cur, ["HistoryHeader"])
        ln_tbl  = _pick_table(cur, ["HistoryLines"])
        if not (hdr_tbl and ln_tbl):
            raise HTTPException(status_code=500, detail="History tables not found")

        doc_no_col     = _pick_col_from(cur, hdr_tbl, ["DocumentNumber"])
        doc_date_col   = _pick_col_from(cur, hdr_tbl, ["DocumentDate"])
        cust_code_col  = _pick_col_from(cur, hdr_tbl, ["CustomerCode"])
        doc_type_col   = _pick_col_from(cur, hdr_tbl, ["DocumentType"])
        total_col      = _pick_col_from(cur, hdr_tbl, ["Total"])
        total_tax_col  = _pick_col_from(cur, hdr_tbl, ["TotalTax"])
        excl_incl_col  = _pick_col_from(cur, hdr_tbl, ["ExclIncl"])
        pay_ref_col    = _pick_col_from(cur, hdr_tbl, ["PaymentReference","OrderNumber","Reference","ExtReference"])
        pay_terms_col  = _pick_col_from(cur, hdr_tbl, ["PaymentTerms","Terms"])
        deliv_date_col = _pick_col_from(cur, hdr_tbl, ["DeliveryDate","DueDate","ClosingDate"])
        curr_code_col  = _pick_col_from(cur, hdr_tbl, ["CurrencyCode"])

        ln_doc_no_col   = _pick_col_from(cur, ln_tbl, ["DocumentNumber"])
        ln_doc_type_col = _pick_col_from(cur, ln_tbl, ["DocumentType"])
        ln_item_col     = _pick_col_from(cur, ln_tbl, ["ItemCode"])
        ln_desc_col     = _pick_col_from(cur, ln_tbl, ["Description"])
        ln_qty_col      = _pick_col_from(cur, ln_tbl, ["Qty"])
        ln_price_col    = _pick_col_from(cur, ln_tbl, ["UnitPrice"])
        ln_tax_col      = _pick_col_from(cur, ln_tbl, ["TaxType"])

        if not all([doc_no_col, doc_type_col, ln_doc_no_col, ln_doc_type_col]):
            raise HTTPException(status_code=500, detail="Required columns missing")

        # DUPLICATE GUARD
        if _exists_doc(cur, hdr_tbl, doc_no_col, doc_type_col, doc_no_norm, doc_type):
            return {"ok": True, "skipped": True, "reason": "exists", "doc_no": doc_no_norm, "document_type": doc_type}

        total = _insert_header_and_lines(
            cur,
            hdr_tbl, ln_tbl,
            doc_no_col, doc_date_col, cust_code_col, doc_type_col,
            total_col, total_tax_col, excl_incl_col,
            pay_ref_col, pay_terms_col, deliv_date_col, curr_code_col,
            ln_doc_no_col, ln_doc_type_col, ln_item_col, ln_desc_col, ln_qty_col, ln_price_col, ln_tax_col,
            doc_no=doc_no_norm, inv_date=inv_date, customer=customer, doc_type=doc_type,
            pay_ref=pay_ref, pay_terms=pay_terms, deliv_dt=deliv_dt, curr_code=curr_code,
            lines=lines
        )

    return {"ok": True, "skipped": False, "doc_no": doc_no_norm, "document_type": doc_type,
            "lines": len(lines), "total_excl": round(total, 2)}

# ----------------------------------------------------------------------
# LIST invoices (with lines)
# ----------------------------------------------------------------------
@app.get("/invoices", response_model=List[InvoiceOut])
def invoices(
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None,
    limit: int = Query(200, ge=1, le=5000),
    since: Optional[str] = Query(None, description="YYYY-MM-DD: HistoryHeader.DocumentDate >= since"),
    doc_type: Optional[str] = Query(None, description="DocumentType number")
):
    require_key(x_api_key, key)
    with get_conn() as cn:
        cur = cn.cursor()

        hdr_tbl = "HistoryHeader"
        ln_tbl  = "HistoryLines"

        doc_no_col     = _pick_col_from(cur, hdr_tbl, ["DocumentNumber"])
        doc_date_col   = _pick_col_from(cur, hdr_tbl, ["DocumentDate"])
        cust_code_col  = _pick_col_from(cur, hdr_tbl, ["CustomerCode"])
        doc_type_col   = _pick_col_from(cur, hdr_tbl, ["DocumentType"])
        total_col      = _pick_col_from(cur, hdr_tbl, ["Total"])
        total_tax_col  = _pick_col_from(cur, hdr_tbl, ["TotalTax"])
        excl_incl_col  = _pick_col_from(cur, hdr_tbl, ["ExclIncl"])
        pay_ref_col    = _pick_col_from(cur, hdr_tbl, ["PaymentReference","OrderNumber","Reference","ExtReference"])
        pay_terms_col  = _pick_col_from(cur, hdr_tbl, ["PaymentTerms","Terms"])
        deliv_date_col = _pick_col_from(cur, hdr_tbl, ["DeliveryDate","DueDate","ClosingDate"])
        curr_code_col  = _pick_col_from(cur, hdr_tbl, ["CurrencyCode"])

        if not (doc_no_col and doc_date_col and cust_code_col):
            raise HTTPException(status_code=500, detail="Required columns missing.")

        where_sql, where_params = [], []
        if doc_type:
            where_sql.append(f"{doc_type_col} = ?")
            where_params.append(int(doc_type))
        if since:
            where_sql.append(f"{doc_date_col} >= ?")
            where_params.append(since)

        hdr_select = [
            f"{_cast_char50(doc_no_col)} AS doc_no",
            f"{doc_date_col} AS invoice_date",
            f"{cust_code_col} AS customer_code",
            f"{doc_type_col} AS document_type",
            f"{total_col} AS total" if total_col else "0 AS total",
            f"{total_tax_col} AS total_tax" if total_tax_col else "0 AS total_tax",
            f"{excl_incl_col} AS excl_incl" if excl_incl_col else "'0' AS excl_incl",
            f"{pay_terms_col} AS payment_terms" if pay_terms_col else "NULL AS payment_terms",
            f"{deliv_date_col} AS delivery_date" if deliv_date_col else "NULL AS delivery_date",
            f"{curr_code_col} AS currency_code" if curr_code_col else "NULL AS currency_code",
            f"{pay_ref_col} AS payment_reference" if pay_ref_col else "NULL AS payment_reference",
        ]

        sql_hdr = f"""
            SELECT TOP {int(limit)} {", ".join(hdr_select)}
            FROM {_qident(hdr_tbl)}
            {"WHERE " + " AND ".join(where_sql) if where_sql else ""}
            ORDER BY {doc_date_col} DESC, {doc_no_col} DESC
        """
        cur.execute(sql_hdr, *where_params)
        hdr_cols = [c[0].lower() for c in cur.description]
        headers = [dict(zip(hdr_cols, r)) for r in cur.fetchall()]
        if not headers:
            return []

        doc_nos = [str(h.get("doc_no") or "").strip() for h in headers]

        ln_doc_no_col   = _pick_col_from(cur, ln_tbl, ["DocumentNumber"])
        ln_item_col     = _pick_col_from(cur, ln_tbl, ["ItemCode"])
        ln_desc_col     = _pick_col_from(cur, ln_tbl, ["Description"])
        ln_qty_col      = _pick_col_from(cur, ln_tbl, ["Qty"])
        ln_price_col    = _pick_col_from(cur, ln_tbl, ["UnitPrice"])
        ln_tax_col      = _pick_col_from(cur, ln_tbl, ["TaxType"])

        qmarks = ",".join(["?"] * len(doc_nos))
        sql_lines = f"""
            SELECT {_cast_char50(ln_doc_no_col)} AS doc_no,
                   {ln_item_col} AS product_code,
                   {ln_desc_col} AS name,
                   {ln_qty_col} AS quantity,
                   {ln_price_col} AS price_unit,
                   {ln_tax_col} AS tax_code
            FROM {_qident(ln_tbl)}
            WHERE {_cast_char50(ln_doc_no_col)} IN ({qmarks})
            ORDER BY {ln_doc_no_col}
        """
        cur.execute(sql_lines, *doc_nos)
        line_cols = [c[0].lower() for c in cur.description]
        lines = [dict(zip(line_cols, r)) for r in cur.fetchall()]

        by_doc: Dict[str, List[InvoiceLineOut]] = {}
        for lr in lines:
            doc = str(lr.get("doc_no") or "").strip()
            by_doc.setdefault(doc, []).append(InvoiceLineOut(
                product_code=_norm_text(lr.get("product_code")),
                name=_norm_text(lr.get("name")),
                quantity=_to_float(lr.get("quantity")) or 0.0,
                price_unit=_to_float(lr.get("price_unit")) or 0.0,
                tax_code=_norm_text(lr.get("tax_code")),
            ))

        out: List[InvoiceOut] = []
        for h in headers:
            doc_no = str(h.get("doc_no") or "").strip()
            doc_lines = by_doc.get(doc_no, [])

            total_hdr = _to_float(h.get("total")) or 0.0
            tax_hdr   = _to_float(h.get("total_tax")) or 0.0
            excl_flag = str(h.get("excl_incl") or "0").strip()

            if (total_hdr == 0.0 and tax_hdr == 0.0) and doc_lines:
                total_excl = sum((ln.quantity or 0) * (ln.price_unit or 0) for ln in doc_lines)
                total_incl = total_excl
            else:
                if excl_flag in ("1", "Y", "Yes", "True", "true"):
                    total_incl = total_hdr
                    total_excl = max(total_hdr - tax_hdr, 0.0)
                else:
                    total_excl = total_hdr
                    total_incl = total_hdr + tax_hdr

            pay_ref = _norm_text(h.get("payment_reference")) or doc_no
            terms_val = h.get("payment_terms")
            payment_terms = "0" if (terms_val is None or str(terms_val).strip() == "") else str(terms_val).strip()
            inv_date = _to_date_str(h.get("invoice_date"))
            deliv_date = _to_date_str(h.get("delivery_date")) or inv_date

            curr_raw = h.get("currency_code")
            currency_code = DEFAULT_CURRENCY if curr_raw in (None, "", 0, "0") else str(curr_raw).strip()

            out.append(InvoiceOut(
                doc_no=doc_no,
                invoice_date=inv_date,
                customer_code=_norm_text(h.get("customer_code")) or "",
                amount_total=round(total_incl, 2),
                amount_total_excl=round(total_excl, 2),
                tax_amount=round(tax_hdr, 2),
                document_type=int(h.get("document_type")) if h.get("document_type") else 3,
                payment_reference=pay_ref,
                payment_terms=payment_terms,
                delivery_date=deliv_date,
                currency_code=currency_code,
                lines=doc_lines,
            ))
        return out


@app.delete("/invoices/{doc_no:path}")
def delete_invoice(
    doc_no: str,
    x_api_key: Optional[str] = Header(default=None),
    key: Optional[str] = None
):
    """
    Permanently delete an invoice (and its lines) by doc_no.
    Safe transactional delete, respects DocumentType if found.
    """
    require_key(x_api_key, key)
    doc_no = str(doc_no).strip()
    if not doc_no:
        raise HTTPException(status_code=400, detail="doc_no required")

    with get_conn() as cn:
        cur = cn.cursor()
        hdr_tbl = _pick_table(cur, ["HistoryHeader"])
        ln_tbl = _pick_table(cur, ["HistoryLines"])
        if not (hdr_tbl and ln_tbl):
            raise HTTPException(status_code=500, detail="History tables not found")

        doc_no_col = _pick_col_from(cur, hdr_tbl, ["DocumentNumber"])
        doc_type_col = _pick_col_from(cur, hdr_tbl, ["DocumentType"])
        ln_doc_no_col = _pick_col_from(cur, ln_tbl, ["DocumentNumber"])
        ln_doc_type_col = _pick_col_from(cur, ln_tbl, ["DocumentType"])

        # Try to detect the document type before deleting
        cur.execute(
            f"SELECT TOP 1 {doc_type_col} FROM {hdr_tbl} WHERE RTRIM({doc_no_col}) = ?", doc_no
        )
        row = cur.fetchone()
        doc_type = row[0] if row else 3  # default to 3 (invoice)

        # Delete lines first
        cur.execute(
            f"DELETE FROM {ln_tbl} WHERE RTRIM({ln_doc_no_col}) = ? AND {ln_doc_type_col} = ?",
            doc_no, doc_type
        )
        # Then delete header
        cur.execute(
            f"DELETE FROM {hdr_tbl} WHERE RTRIM({doc_no_col}) = ? AND {doc_type_col} = ?",
            doc_no, doc_type
        )



        cn.commit()

    return {"ok": True, "deleted_doc_no": doc_no, "document_type": doc_type}

