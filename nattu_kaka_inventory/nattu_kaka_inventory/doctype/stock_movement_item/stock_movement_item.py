# Copyright (c) 2026, Harshit and Bagga and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StockMovementItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cost_price: DF.Currency
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		product: DF.Link
		qty: DF.Float
		source_warehouse: DF.Link | None
		target_warehouse: DF.Link | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Stock Movement Item"
