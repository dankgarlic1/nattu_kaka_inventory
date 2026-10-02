# Copyright (c) 2026, Harshit and Bagga and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StockLedger(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		entry_type: DF.Literal["Receipt", "Consume", "Transfer", "Adjustment"]
		posting_date: DF.Date
		posting_time: DF.Time
		product: DF.Link
		qty: DF.Float
		reference_id: DF.DynamicLink
		reference_type: DF.Link | None
		valuation_rate: DF.Currency
		warehouse: DF.Link
	# end: auto-generated types

	_DOCTYPE_NAME = "Stock Ledger"
