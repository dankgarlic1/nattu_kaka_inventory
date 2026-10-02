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
				self.make_ledger_entry(row, row.target_warehouse, row.qty, "Receipt")

			elif self.purpose == "Consume":
				self.make_ledger_entry(row, row.source_warehouse, -row.qty, "Consume")

			elif self.purpose == "Transfer":
				self.make_ledger_entry(row, row.source_warehouse, -row.qty, "Transfer")
				self.make_ledger_entry(row, row.target_warehouse, row.qty, "Transfer")

		self.update_valuations()

	def make_ledger_entry(self, row, warehouse, qty, entry_type):
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
				"entry_type": entry_type,
			}
		)
		ledger_doc.insert()

	def update_valuations(self):
		"""Any movement can change later averages (backdated or cancelled), so revalue every product in it."""
		for product in {row.product for row in self.items}:
			self.update_product_valuation(product)

	def update_product_valuation(self, product_id):
		"""Replays the product's ledger in posting order to calculate true moving average via total value."""
		ledger = frappe.qb.DocType("Stock Ledger")
		entries = (
			frappe.qb.from_(ledger)
			.select(ledger.qty, ledger.valuation_rate, ledger.entry_type)
			.where(ledger.product == product_id)
			.orderby(ledger.posting_date, ledger.posting_time, ledger.creation)
		).run(as_dict=True)

		stock_value = 0.0
		qty_on_hand = 0.0
		avg_rate = 0.0

		for entry in entries:
			qty, rate = flt(entry.qty), flt(entry.valuation_rate)

			stock_value += qty * rate
			qty_on_hand += qty

			if qty_on_hand > 0:
				avg_rate = stock_value / qty_on_hand
			else:
				avg_rate = 0.0
				stock_value = 0.0

		frappe.db.set_value("Product", product_id, "unit_price", avg_rate)

	def on_cancel(self):
		"""Posts reverse adjustment entries on cancellation."""
		ledgers = frappe.get_all(
			"Stock Ledger",
			filters={
				"reference_type": self.doctype,
				"reference_id": self.name,
			},
			fields=["product", "warehouse", "qty", "valuation_rate"],
		)

		for entry in ledgers:
			reverse_row = frappe._dict(
				{
					"product": entry.product,
					"cost_price": entry.valuation_rate,
				}
			)

			self.make_ledger_entry(reverse_row, entry.warehouse, -entry.qty, "Adjustment")

		self.update_valuations()
