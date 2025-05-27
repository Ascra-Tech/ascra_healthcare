# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.utils import flt, today

from healthcare.healthcare.doctype.clinical_procedure_template.clinical_procedure_template import (
	make_item_price,
	update_item_and_item_price,
)


class LabTestTemplate(Document):
	def before_insert(self):
		if self.link_existing_item and self.item:
			price_list = frappe.db.get_all(
				"Item Price", {"item_code": self.item}, ["price_list_rate"], order_by="valid_from desc"
			)
			if price_list:
				self.lab_test_rate = price_list[0].get("price_list_rate")

	def after_insert(self):
		if not self.item and not self.link_existing_item:
			create_item_from_template(self)

	def validate(self):
		if (
			self.is_billable
			and not self.link_existing_item
			and (not self.lab_test_rate or self.lab_test_rate <= 0.0)
		):
			frappe.throw(_("Standard Selling Rate should be greater than zero."))

		if self.sample and flt(self.sample_qty) <= 0:
			frappe.throw(_("Sample Quantity cannot be negative or 0"), title=_("Invalid Quantity"))

		self.validate_conversion_factor()
		self.enable_disable_item()

	def on_update(self):
		# If change_in_item update Item and Price List
		if self.change_in_item:
			update_item_and_item_price(self)

	def on_trash(self):
		# Remove template reference from item and disable item
		if self.item:
			try:
				item = self.item
				self.db_set("item", "")
				frappe.delete_doc("Item", item)
			except Exception:
				frappe.throw(_("Not permitted. Please disable the Lab Test Template"))

	def enable_disable_item(self):
		if self.is_billable:
			if self.disabled:
				frappe.db.set_value("Item", self.item, "disabled", 1)
			else:
				frappe.db.set_value("Item", self.item, "disabled", 0)

	def update_item(self):
		item = frappe.get_doc("Item", self.item)
		if item:
			item.update(
				{
					"item_name": self.lab_test_name,
					"item_group": self.lab_test_group,
					"disabled": 0,
					"standard_rate": self.lab_test_rate,
					"description": self.lab_test_description,
				}
			)
			item.flags.ignore_mandatory = True
			item.save(ignore_permissions=True)

	def item_price_exists(self):
		item_price = frappe.db.exists("Item Price", {"item_code": self.item, "valid_from": today()})
		if item_price:
			return item_price
		return False

	def validate_conversion_factor(self):
		if self.lab_test_template_type == "Single" and self.secondary_uom and not self.conversion_factor:
			frappe.throw(_("Conversion Factor is mandatory"))
		if self.lab_test_template_type == "Compound":
			for item in self.normal_test_templates:
				if item.secondary_uom and not item.conversion_factor:
					frappe.throw(_("Row #{0}: Conversion Factor is mandatory").format(item.idx))
		if self.lab_test_template_type == "Grouped":
			for group in self.lab_test_groups:
				if (
					group.template_or_new_line == "Add New Line"
					and group.secondary_uom
					and not group.conversion_factor
				):
					frappe.throw(_("Row #{0}: Conversion Factor is mandatory").format(group.idx))


def create_item_from_template(doc):
    try:
        uom = frappe.db.exists("UOM", "Unit") or frappe.db.get_single_value("Stock Settings", "stock_uom")
        disabled = 0 if doc.is_billable and not doc.disabled else doc.disabled
        
        # Create item directly using SQL to bypass validation
        item_code = doc.lab_test_code
        item_name = doc.lab_test_name
        
        # Get the HSN code value
        hsn_code = doc.hsnsac if hasattr(doc, 'hsnsac') else '3822'
        
        # Directly insert item with only the essential columns that exist in your Item table
        frappe.db.sql("""
            INSERT INTO `tabItem` 
            (name, item_code, item_name, item_group, description, 
            is_sales_item, is_purchase_item, is_stock_item, 
            disabled, stock_uom, gst_hsn_code, creation, owner, modified, modified_by, docstatus) 
            VALUES (%s, %s, %s, %s, %s, 1, 0, 0, %s, %s, %s, NOW(), %s, NOW(), %s, 0)
        """, (
            item_code, item_code, item_name, doc.lab_test_group, doc.lab_test_description or "",
            disabled, uom, hsn_code, 
            frappe.session.user, frappe.session.user
        ))
        
        # Commit changes
        frappe.db.commit()
        
        # Create item price
        if doc.is_billable and doc.lab_test_rate != 0.0:
            price_list_name = frappe.db.get_value(
                "Selling Settings", None, "selling_price_list"
            ) or frappe.db.get_value("Price List", {"selling": 1})
            if doc.lab_test_rate:
                make_item_price(item_code, doc.lab_test_rate)
            else:
                make_item_price(item_code, 0.0)
                
        # Update template to refer to the item
        frappe.db.set_value("Lab Test Template", doc.name, "item", item_code)
        doc.reload()
        
    except Exception as e:
        frappe.log_error(f"Error creating item from template: {str(e)}")
        frappe.throw(f"Error creating item: {str(e)}")


@frappe.whitelist()
def change_test_code_from_template(lab_test_code, doc):
	doc = frappe._dict(json.loads(doc))
	if frappe.db.exists({"doctype": "Item", "item_code": lab_test_code}):
		frappe.throw(_("Lab Test Item {0} already exist").format(lab_test_code))
	else:
		rename_doc("Item", doc.item, lab_test_code, ignore_permissions=True)
		frappe.db.set_value(
			"Lab Test Template", doc.name, {"lab_test_code": lab_test_code, "lab_test_name": lab_test_code}
		)
		rename_doc("Lab Test Template", doc.name, lab_test_code, ignore_permissions=True)
	return lab_test_code
