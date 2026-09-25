# Copyright (c) 2026, Harshit and Bagga and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.nestedset import NestedSet


# Notice we changed 'Document' to 'NestedSet' inside the parentheses
class Warehouse(NestedSet):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		address: DF.Link | None
		capacity: DF.Int
		contact: DF.Link | None
		is_group: DF.Check
		lft: DF.Int
		old_parent: DF.Link | None
		parent_warehouse: DF.Link | None
		rgt: DF.Int
		warehouse_name: DF.Data
		warehouse_type: DF.Literal["Warehouse", "Floor", "Aisle", "Shelf"]
	# end: auto-generated types

	pass
