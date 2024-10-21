# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WorkPlanItemTarget(Document):
	def validate(self):
		if self.is_new() and frappe.db.get_value(self.doctype,{"item":self.item}):
			frappe.throw(f"Target value of item <b>{self.item}</b> already exists..!")
