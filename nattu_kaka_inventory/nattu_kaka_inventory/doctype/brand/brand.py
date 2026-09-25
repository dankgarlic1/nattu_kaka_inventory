# Copyright (c) 2026, Harshit and Bagga and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Brand(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		brand_name: DF.Data
		description: DF.TextEditor | None
		website: DF.Data | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Brand"
