# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LotResourceTagging(Document):
	pass


@frappe.whitelist()
def validate_lot_number(barcode,docname,operation_type):
	try:
		if not frappe.db.get_value("Lot Resource Tagging",{"scan_lot_no":barcode,"name":["!=",docname],"operation_type":operation_type,"docstatus":1}):
			job_card = frappe.db.get_value("Job Card",{"batch_code":barcode,"operation":"Deflashing"},["name","production_item","bom_no","moulding_lot_number"],as_dict=1)
			if job_card:
				# if frappe.db.get_value("Deflashing Receipt Entry",{"lot_number":job_card.moulding_lot_number,"docstatus":1}):
				if frappe.db.get_value("Deflashing Receipt Entry",{"lot_number":barcode,"docstatus":1}):
					opeartion_exe = frappe.db.sql(""" SELECT BP.name FROM `tabBOM Operation` BP INNER JOIN `tabBOM` B ON BP.parent = B.name WHERE B.is_default=1 AND B.is_active=1 AND BP.operation=%(operation)s AND B.name=%(bom)s""",{"bom":job_card.bom_no,"operation":operation_type},as_dict=1)
					if opeartion_exe:
						frappe.response.status = 'success'
						frappe.response.message = job_card
					else:
						frappe.response.status = 'failed'
						frappe.response.message = f"The <b>{operation_type}</b> operation is not found in <b>BOM</b>"
				else:
					frappe.response.status = 'failed'
					frappe.response.message = "<b>Deflashing Receipt Entry</b> not found for the Scanned job card <b>"+barcode+"</b>."
			else:
				frappe.response.status = 'failed'
				frappe.response.message = "Scanned job card <b>"+barcode+"</b> not exist."
		else:
			frappe.response.status = 'failed'
			frappe.response.message = f" Entry for scanned job card <b>{barcode}</b> and operation <b>{operation_type}</b> is already exists. "
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.lot_resource_tagging.lot_resource_tagging.validate_lot_number")
		frappe.response.status = 'failed'
		frappe.response.message = "Something went wrong."

@frappe.whitelist()
def validate_inspector_barcode(b__code):
	try:
		check_emp = frappe.db.sql("""SELECT name,employee_name FROM `tabEmployee` WHERE status='Active' AND barcode_text=%(barcode)s""",{"barcode":b__code},as_dict=1)
		if check_emp:
			frappe.response.status = 'success'
			frappe.response.message = check_emp[0]
		else:
			frappe.response.status = 'failed'
			frappe.response.message = "Employee not found."
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.lot_resource_tagging.lot_resource_tagging.validate_inspector_barcode")
		frappe.response.status = 'failed'
		frappe.response.message = "Something went wrong."