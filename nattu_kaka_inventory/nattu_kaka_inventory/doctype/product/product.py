# Copyright (c) 2026, Harshit and Bagga and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Product(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		brand: DF.Link | None
		description: DF.TextEditor | None
		image: DF.AttachImage | None
		product_name: DF.Data
		sku: DF.Data
		unit_price: DF.Currency
	# end: auto-generated types

	_DOCTYPE_NAME = "Product"
