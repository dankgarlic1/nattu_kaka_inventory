# Copyright (c) 2026, Harshit and Bagga and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestStockMovement(IntegrationTestCase):
	def setUp(self):
		"""Creates the test master data before running the tests."""
		self.setup_master_data()
		# Rollback only happens once per class, so start every test with an empty ledger
		frappe.db.delete("Stock Ledger", {"product": "TEST-TV-001"})

	def setup_master_data(self):
		if not frappe.db.exists("Brand", "Sony Test"):
			frappe.get_doc({"doctype": "Brand", "brand_name": "Sony Test"}).insert()

		if not frappe.db.exists("Product", "TEST-TV-001"):
			frappe.get_doc(
				{
					"doctype": "Product",
					"sku": "TEST-TV-001",
					"product_name": "Test Bravia",
					"brand": "Sony Test",
				}
			).insert()

		for wh in ["Mumbai Godown", "Delhi Store"]:
			if not frappe.db.exists("Warehouse", wh):
				frappe.get_doc({"doctype": "Warehouse", "warehouse_name": wh, "is_group": 0}).insert()

	def create_stock_movement(self, purpose, qty, cost_price, source=None, target=None):
		"""Helper function to quickly generate transactions in tests."""
		sm = frappe.get_doc(
			{
				"doctype": "Stock Movement",
				"purpose": purpose,
				"items": [
					{
						"product": "TEST-TV-001",
						"qty": qty,
						"cost_price": cost_price,
						"source_warehouse": source,
						"target_warehouse": target,
					}
				],
			}
		)
		sm.insert()
		sm.submit()
		return sm

	def get_unit_price(self):
		return frappe.db.get_value("Product", "TEST-TV-001", "unit_price")

	def test_receipt_and_moving_average(self):
		"""Verify incoming stock calculates moving average correctly."""
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")

		self.create_stock_movement("Receipt", 20, 130, target="Mumbai Godown")

		product = frappe.get_doc("Product", "TEST-TV-001")
		self.assertEqual(product.unit_price, 120.0)

	def test_transfer_ledger_creation(self):
		"""Verify a transfer creates + and - ledger entries."""
		# Stock up Mumbai first so this test doesn't depend on test order
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")

		# Transfer 5 units from Mumbai to Delhi
		sm = self.create_stock_movement("Transfer", 5, 120, source="Mumbai Godown", target="Delhi Store")

		# Check the ledger records attached to this movement
		ledgers = frappe.get_all(
			"Stock Ledger", filters={"reference_id": sm.name}, fields=["warehouse", "qty"]
		)

		self.assertEqual(len(ledgers), 2)

		# Verify Mumbai lost 5, Delhi gained 5
		for entry in ledgers:
			if entry.warehouse == "Mumbai Godown":
				self.assertEqual(entry.qty, -5.0)
			elif entry.warehouse == "Delhi Store":
				self.assertEqual(entry.qty, 5.0)

	def test_negative_stock_validation(self):
		"""Verify the system blocks transferring more than available."""
		sm = frappe.get_doc(
			{
				"doctype": "Stock Movement",
				"purpose": "Consume",
				"items": [
					{
						"product": "TEST-TV-001",
						"qty": 9999,  # Intentionally triggering an error
						"source_warehouse": "Mumbai Godown",
					}
				],
			}
		)

		# Assert that trying to save this document raises a ValidationError
		with self.assertRaises(frappe.exceptions.ValidationError):
			sm.insert()

	def test_moving_average_spec_example(self):
		"""10 @ 100 + 20 @ 120 averages to 113.33; selling 15 is valued at 1700 and leaves 1700 in stock."""
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")
		self.create_stock_movement("Receipt", 20, 120, target="Mumbai Godown")
		self.assertAlmostEqual(self.get_unit_price(), 113.33, places=2)

		sm = self.create_stock_movement("Consume", 15, 0, source="Mumbai Godown")

		consumed = frappe.get_all(
			"Stock Ledger", filters={"reference_id": sm.name}, fields=["qty", "valuation_rate"]
		)[0]
		self.assertAlmostEqual(consumed.qty * consumed.valuation_rate, -1700, places=2)

		ledger = frappe.get_all(
			"Stock Ledger", filters={"product": "TEST-TV-001"}, fields=["qty", "valuation_rate"]
		)
		stock_value = sum(entry.qty * entry.valuation_rate for entry in ledger)
		self.assertAlmostEqual(stock_value, 1700, places=2)

		# Selling doesn't change the rate of what's left
		self.assertAlmostEqual(self.get_unit_price(), 113.33, places=2)

	def test_transfer_does_not_skew_valuation(self):
		"""The incoming leg of a transfer is not a purchase and must not count toward the average."""
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")
		self.create_stock_movement("Transfer", 5, 0, source="Mumbai Godown", target="Delhi Store")
		self.create_stock_movement("Receipt", 10, 200, target="Mumbai Godown")

		self.assertEqual(self.get_unit_price(), 150.0)

	def test_consumption_before_receipt(self):
		"""Stock that's already gone shouldn't drag down the rate of new stock."""
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")
		self.create_stock_movement("Consume", 10, 0, source="Mumbai Godown")
		self.create_stock_movement("Receipt", 10, 200, target="Mumbai Godown")

		self.assertEqual(self.get_unit_price(), 200.0)

	def test_outgoing_rows_use_current_valuation(self):
		"""A typed-in cost price on a Consume is replaced by the product's moving average."""
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")
		self.create_stock_movement("Receipt", 10, 200, target="Mumbai Godown")

		sm = self.create_stock_movement("Consume", 5, 999, source="Mumbai Godown")

		self.assertEqual(sm.items[0].cost_price, 150.0)
		self.assertEqual(
			frappe.get_all("Stock Ledger", filters={"reference_id": sm.name}, pluck="valuation_rate"),
			[150.0],
		)
		self.assertEqual(self.get_unit_price(), 150.0)

	def test_cancel_receipt_restores_valuation_and_creates_adjustment(self):
		"""Cancelling a receipt restores valuation and creates an Adjustment ledger entry (No Deletion)."""
		self.create_stock_movement("Receipt", 10, 100, target="Mumbai Godown")
		second = self.create_stock_movement("Receipt", 10, 200, target="Mumbai Godown")
		self.assertEqual(self.get_unit_price(), 150.0)

		second.cancel()

		self.assertEqual(self.get_unit_price(), 100.0)

		ledgers = frappe.get_all(
			"Stock Ledger",
			filters={"reference_id": second.name},
			fields=["qty", "entry_type"],
			order_by="creation asc",
		)

		self.assertEqual(len(ledgers), 2)

		# Assert the first row is the original Receipt
		self.assertEqual(ledgers[0].entry_type, "Receipt")
		self.assertEqual(ledgers[0].qty, 10.0)

		# Assert the second row is the exact opposite Adjustment
		self.assertEqual(ledgers[1].entry_type, "Adjustment")
		self.assertEqual(ledgers[1].qty, -10.0)
