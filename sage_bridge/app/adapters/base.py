"""Sage adapter contract. Concrete Pastel editions implement this class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class SageAdapter(ABC):
    """Versioned Pastel/Sage backend used by the HTTP layer."""

    name = "base"

    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """Return supported operations for this adapter/edition."""

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Probe DSN / SDK / company open state."""

    @abstractmethod
    def pull_customers(
        self, since: Optional[str], cursor: Optional[str], limit: int, q: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Return (items, next_cursor, has_more)."""

    @abstractmethod
    def pull_suppliers(
        self, since: Optional[str], cursor: Optional[str], limit: int, q: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Return (items, next_cursor, has_more)."""

    @abstractmethod
    def pull_products(
        self, since: Optional[str], cursor: Optional[str], limit: int, q: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Return (items, next_cursor, has_more)."""

    @abstractmethod
    def pull_invoices(
        self,
        since: Optional[str],
        cursor: Optional[str],
        limit: int,
        doc_type: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """Return (items, next_cursor, has_more)."""

    @abstractmethod
    def upsert_customer(self, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a Sage customer by code."""

    @abstractmethod
    def upsert_product(self, code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a Sage inventory item by code."""

    @abstractmethod
    def invoice_exists(self, doc_no: str, doc_type: Optional[int]) -> Dict[str, Any]:
        """Return exists / exists_strict / doc_type."""

    @abstractmethod
    def post_invoice(self, payload: Dict[str, Any], replace: bool = False) -> Dict[str, Any]:
        """Post invoice or credit note. Returns Sage doc_no."""

    @abstractmethod
    def post_receipt_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Post customer receipts; allocate to invoices when supported."""
