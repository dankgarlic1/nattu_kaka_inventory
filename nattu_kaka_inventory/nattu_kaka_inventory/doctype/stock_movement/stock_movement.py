# Copyright (c) 2026, Harshit and Bagga and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import flt, nowdate, nowtime


class StockMovement(Document):
	def validate(self):
		self.set_default_dates()
		self.set_outgoing_rates()
		self.validate_stock_availability()

	def set_default_dates(self):
		if not self.posting_date:
			self.posting_date = nowdate()

	def set_outgoing_rates(self):
		"""Outgoing stock leaves at the product's current moving average, not a typed-in price."""
		if self.purpose not in ["Consume", "Transfer"]:
			return

		for row in self.items:
			row.cost_price = flt(frappe.db.get_value("Product", row.product, "unit_price"))

	def validate_stock_availability(self):
		"""Prevents saving if Jethalal tries to move stock he doesn't have."""
		for row in self.items:
			if self.purpose in ["Consume", "Transfer"]:
				if not row.source_warehouse:
					frappe.throw(
						_("Row {0}: Source Warehouse is mandatory for a {1}").format(row.idx, self.purpose)
					)

				available_qty = self.get_available_qty(row.product, row.source_warehouse)
				if row.qty > available_qty:
					frappe.throw(
						_(
							"Row {0}: Insufficient stock for {1} in {2}. <br>Available: {3} <br>Requested: {4}"
						).format(
							row.idx,
							frappe.bold(row.product),
							frappe.bold(row.source_warehouse),
							available_qty,
							row.qty,
						)
					)

			if self.purpose in ["Receipt", "Transfer"]:
				if not row.target_warehouse:
					frappe.throw(
						_("Row {0}: Target Warehouse is mandatory for a {1}").format(row.idx, self.purpose)
					)

	def get_available_qty(self, product, warehouse):
		"""The Stateless Ledger Query using Query Builder"""

		ledger = frappe.qb.DocType("Stock Ledger")

		query = (
			frappe.qb.from_(ledger)
			.select(Sum(ledger.qty).as_("total_qty"))
			.where((ledger.product == product) & (ledger.warehouse == warehouse))
		)

		result = query.run(as_dict=True)

		return result[0].total_qty if result and result[0].total_qty else 0.0

	def on_submit(self):
		"""Generates the immutable ledger entries."""
		for row in self.items:
			if self.purpose == "Receipt":
				self.make_ledger_entry(row, row.target_warehouse, row.qty)

			elif self.purpose == "Consume":
				self.make_ledger_entry(row, row.source_warehouse, -row.qty)

			elif self.purpose == "Transfer":
				self.make_ledger_entry(row, row.source_warehouse, -row.qty)
				self.make_ledger_entry(row, row.target_warehouse, row.qty)

		self.update_valuations()

	def make_ledger_entry(self, row, warehouse, qty):
		"""Helper function to create a single ledger row."""
		ledger_doc = frappe.get_doc(
			{
				"doctype": "Stock Ledger",
				"product": row.product,
				"warehouse": warehouse,
				"qty": qty,
				"valuation_rate": row.cost_price,
				"posting_date": self.posting_date,
				"posting_time": nowtime(),
				"reference_type": self.doctype,
				"reference_id": self.name,
			}
		)
		ledger_doc.insert()

	def update_valuations(self):
		"""Any movement can change later averages (backdated or cancelled), so revalue every product in it."""
		for product in {row.product for row in self.items}:
			self.update_product_valuation(product)

	def update_product_valuation(self, product_id):
		"""Replays the product's ledger in posting order to get its moving average rate.

		Only Receipts change the rate: (stock value on hand + incoming value) / total qty.
		Consumes and Transfers move qty out at the current rate, so the rate stays the same.
		"""

		ledger = frappe.qb.DocType("Stock Ledger")
		movement = frappe.qb.DocType("Stock Movement")

		entries = (
			frappe.qb.from_(ledger)
			.join(movement)
			.on(ledger.reference_id == movement.name)
			.select(ledger.qty, ledger.valuation_rate, movement.purpose)
			.where((ledger.product == product_id) & (ledger.reference_type == "Stock Movement"))
			.orderby(ledger.posting_date, ledger.posting_time, ledger.creation)
		).run(as_dict=True)

		qty_on_hand = 0.0
		avg_rate = 0.0

		for entry in entries:
			qty, rate = flt(entry.qty), flt(entry.valuation_rate)

			if entry.purpose == "Receipt":
				if qty_on_hand > 0:
					avg_rate = (qty_on_hand * avg_rate + qty * rate) / (qty_on_hand + qty)
				else:
					avg_rate = rate

			qty_on_hand += qty

		frappe.db.set_value("Product", product_id, "unit_price", avg_rate)

	def on_cancel(self):
		"""Cleans up the ledger using Query Builder deletion"""
		# do not delete the entry! do the adjustment entry instead
		ledger = frappe.qb.DocType("Stock Ledger")

		(
			frappe.qb.from_(ledger)
			.delete()
			.where((ledger.reference_type == self.doctype) & (ledger.reference_id == self.name))
		).run()

		self.update_valuations()

		# how to make tree view default on desk
		# make ux better add swarehosue in stock movement global
