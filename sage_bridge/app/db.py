"""Shared ODBC helpers for Pastel Partner tables."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(str(x).strip().replace(",", ""))
    except Exception:
        return None


def to_date_str(d: Any) -> Optional[str]:
    if not d:
        return None
    try:
        if isinstance(d, datetime):
            return d.date().isoformat()
        if isinstance(d, date):
            return d.isoformat()
        s = str(d)
        if len(s) == 8 and s.isdigit():
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        return s
    except Exception:
        return None


def to_date_sql(s: Optional[str]):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def norm_text(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, (int, float)) and float(v) == 0:
        return None
    s = str(v).strip()
    return s or None


def to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "t", "y", "yes", "on"}:
        return True
    if s in {"0", "false", "f", "n", "no", "off", ""}:
        return False
    return None


def pick_table(cur, candidates: List[str]) -> Optional[str]:
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


def pick_col(cur, table: str, candidates: List[str]) -> Optional[str]:
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


def cast_char50(expr: str) -> str:
    return f"CAST({expr} AS CHAR(50))"


def fetch_dicts(cur) -> List[dict]:
    if not cur.description:
        return []
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
