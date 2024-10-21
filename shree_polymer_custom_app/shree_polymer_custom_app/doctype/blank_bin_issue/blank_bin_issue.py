# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BlankBinIssue(Document):
	def on_submit(self):
		if not self.items:
			frappe.throw("Please add some items before submit.")

@frappe.whitelist()
def validate_blank_issue_barcode(barcode,scan_type,docname):
	try:
		if scan_type == "scan_production_lot":
			job_card = frappe.db.get_value("Job Card",{"batch_code":barcode},["name","production_item","for_quantity","workstation","mould_reference"],as_dict=1)
			if job_card:
				""" For checking exe bin issue """
				# blank_bin_issue = frappe.db.sql("""SELECT I.name FROM `tabBlank Bin Issue Item` I  
				# 				  INNER JOIN `tabBlank Bin Issue` B ON B.name=I.parent
				# 				  WHERE I.is_completed=0 AND I.job_card=%(job_card)s AND B.name<>%(docname)s""",{"job_card":job_card.get('name'),"docname":docname},as_dict=1)
				# if blank_bin_issue:
				# 	frappe.response.status = 'failed'
				# 	frappe.response.message = "Scanned job card <b>"+barcode+"</b> is already issued."
				# else:
				# 	job_card['mould_reference'] = frappe.db.get_value("Asset",{"name":job_card.get('mould_reference')},"item_code")
				# 	frappe.response.status = 'success'
				# 	frappe.response.message = job_card

				job_card['mould_reference'] = frappe.db.get_value("Asset",{"name":job_card.get('mould_reference')},"item_code")
				frappe.response.status = 'success'
				frappe.response.message = job_card
				
				""" End """
			else:
				frappe.response.status = 'failed'
				frappe.response.message = "Scanned job card <b>"+barcode+"</b> not exist."
			
		elif scan_type == "scan_bin":
			# bl_bin = frappe.db.sql(""" SELECT IBM.compound,IBM.spp_batch_number,IBM.qty,BB.name,BB.bin_weight,IBM.is_retired FROM `tabBlanking Bin` BB INNER JOIN `tabItem Bin Mapping` IBM ON BB.name=IBM.blanking_bin 
			# 						WHERE barcode_text=%(barcode_text)s ORDER BY IBM.creation desc""",{"barcode_text":barcode},as_dict=1)
			bl_bin = frappe.db.sql(""" SELECT IBM.compound,IBM.spp_batch_number,IBM.qty,A.name,A.bin_weight,IBM.is_retired,A.asset_name FROM `tabAsset` A INNER JOIN `tabItem Bin Mapping` IBM ON A.name=IBM.blanking__bin 
									WHERE A.barcode_text=%(barcode_text)s ORDER BY IBM.creation desc""",{"barcode_text":barcode},as_dict=1)
			if bl_bin:
				if bl_bin[0].is_retired == 1:
					frappe.response.status = 'failed'
					frappe.response.message = "No item found in Scanned Bin."
				if not bl_bin[0].bin_weight:
					frappe.response.status = 'failed'
					frappe.response.message = "Bin weight not set in Asset..!"
				spp_settings = frappe.get_single("SPP Settings")
				if not spp_settings.to_location:
					frappe.response.status = 'failed'
					frappe.response.message = "Asset Default To Location not found in SPP Settings."
				location = frappe.db.sql("""SELECT name FROM `tabAsset` WHERE barcode_text=%(barcode_text)s  AND location=%(location)s""",{"location":spp_settings.to_location,"barcode_text":barcode},as_dict=1)
				if not location:
					frappe.response.status = 'failed'
					frappe.response.message = "Scanned Bin <b>"+barcode+"</b> not exist in the location <b>"+spp_settings.from_location+"</b>."
				else:
					frappe.response.status = 'success'
					frappe.response.message= bl_bin[0]
			else:
				frappe.response.status = 'failed'
				frappe.response.message = "Scanned Bin <b>"+barcode+"</b> not exist."
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_issue.blank_bin_issue.validate_blank_issue_barcode")
		frappe.response.status = 'failed'
		frappe.response.message = "Something went wrong."