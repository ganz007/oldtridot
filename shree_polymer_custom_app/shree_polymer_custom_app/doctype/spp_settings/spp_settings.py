# Copyright (c) 2022, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class SPPSettings(Document):
	pass

@frappe.whitelist()
def get_naming_series_options():
	try:
		naming_series = frappe.get_meta("Stock Entry").get_field("naming_series").options.split('\n')
		frappe.local.response.message = sorted(naming_series)
		frappe.local.response.status = 'success'
	except Exception:
		frappe.local.response.status = 'failed'
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.spp_settings.spp_settings.get_naming_series_options",message=frappe.get_traceback())