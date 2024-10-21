# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, duration_to_seconds, flt
from shree_polymer_custom_app.shree_polymer_custom_app.api import get_stock_entry_naming_series

class DeflashingDespatchEntry(Document):
	def validate(self):
		if not self.items:
			frappe.throw(" Scan and add some items before save.")

	def on_submit(self):
		make_stock_entry(self)

def make_stock_entry(self):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		for each in self.items:
			stock_entry = frappe.new_doc("Stock Entry")
			stock_entry.purpose = "Material Transfer"
			stock_entry.company = "SPP"
			stock_entry.naming_series = "MAT-STE-.YYYY.-"
			""" For identifying procees name to change the naming series the field is used """
			naming_status,naming_series = get_stock_entry_naming_series(spp_settings,"Deflashing")
			if naming_status:
				stock_entry.naming_series = naming_series
			""" End """
			stock_entry.stock_entry_type = "Material Transfer"
			stock_entry.from_warehouse = spp_settings.unit_2_warehouse
			stock_entry.to_warehouse = each.warehouse_id
			stock_entry.append("items",{
				"item_code":each.item,
				"s_warehouse":spp_settings.unit_2_warehouse,
				"t_warehouse":each.warehouse_id,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"transfer_qty":flt(each.qty, 3),
				"qty":flt(each.qty, 3),
				"batch_no":each.batch_no,
				"spp_batch_number":each.spp_batch_no
				})
			stock_entry.insert()
			sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
			sub_entry.docstatus=1
			sub_entry.save(ignore_permissions=True)
			""" Update stock entry reference in child table """
			frappe.db.set_value("Deflashing Despatch Entry Item",each.name,"stock_entry_reference",stock_entry.name)
			""" End """
			frappe.db.commit()
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_despatch_entry.deflashing_despatch_entry.make_stock_entry")
		frappe.db.rollback()

def check_available_stock(warehouse,item,batch_no):
	try:
		if batch_no:
			query = f""" SELECT qty FROM `tabItem Batch Stock Balance` WHERE item_code='{item}' AND warehouse='{warehouse}' AND batch_no='{batch_no}' """
		else:
			query = f""" SELECT qty FROM `tabItem Batch Stock Balance` WHERE item_code='{item}' AND warehouse='{warehouse}' """
		qty = frappe.db.sql(query,as_dict=1)
		if qty:
			if qty[0].qty:
				return {"status":"success","qty":qty[0].qty}
			else:
				return {"status":"failed","message":f"Stock is not available for the item <b>{item}</b>"}	
		else:
			return {"status":"failed","message":f"Stock is not available for the item <b>{item}</b>"}
	except Exception:	
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_despatch_entry.deflashing_despatch_entry.check_available_stock")
		return {"status":"failed","message":"Something went wrong"}

@frappe.whitelist()
def validate_lot_barcode(bar_code):
	try:
		exe_production_entry = frappe.db.get_value("Moulding Production Entry",{"scan_lot_number":bar_code,"docstatus":1})
		if exe_production_entry:
			# check_lot_inspe_entry = frappe.db.get_value("Lot Inspection Entry",{"lot_no":bar_code,"docstatus":1})
			check_lot_inspe_entry = frappe.db.get_value("Inspection Entry",{"lot_no":bar_code,"docstatus":1,"inspection_type":"Lot Inspection"})
			if check_lot_inspe_entry:
				job_card = frappe.db.get_value("Job Card",{"batch_code":bar_code,"docstatus":1})
				if job_card:
					card_details = frappe.db.get_value("Job Card",job_card,["production_item","total_completed_qty","work_order"],as_dict=1)
					query = f""" SELECT SED.t_warehouse as from_warehouse,SED.spp_batch_number,SED.mix_barcode,SED.batch_no,SED.qty FROM `tabStock Entry Detail` SED INNER JOIN `tabStock Entry` SE 
								 ON SED.parent=SE.name WHERE SED.item_code='{card_details.get("production_item")}' AND SE.work_order='{card_details.get("work_order")}' """
					spp_and_batch = frappe.db.sql(query,as_dict=1)
					if spp_and_batch:
						stock_status = check_available_stock(spp_and_batch[0].get("from_warehouse"),card_details.get("production_item"),spp_and_batch[0].get("batch_no",""))
						if stock_status.get('status') == "success":
							frappe.response.job_card = job_card
							frappe.response.item = card_details.get("production_item")
							frappe.response.qty = stock_status.get('qty')
							frappe.response.spp_batch_number = spp_and_batch[0].get("spp_batch_number")
							frappe.response.mix_barcode = spp_and_batch[0].get("mix_barcode")
							frappe.response.batch_no = spp_and_batch[0].get("batch_no","")
							frappe.response.from_warehouse = spp_and_batch[0].get("from_warehouse")
							frappe.response.status = "success"
						else:
							frappe.response.status = stock_status.get('status')
							frappe.response.message = stock_status.get('message')
					else:
						frappe.response.status = "failed"
						frappe.response.message = "There is no <b>Stock Entry</b> found for the scanned lot"
				else:
					frappe.response.status = "failed"
					frappe.response.message = "There is no <b>Job Card</b> found for the scanned lot"
			else:
				frappe.response.status = "failed"
				frappe.response.message = "There is no <b>Lot Inspection Entry</b> for the scanned lot"
		else:
			frappe.response.status = "failed"
			frappe.response.message = "There is no <b>Moulding Production Entry</b> for the scanned lot"
	except Exception:
		frappe.response.status = "failed"
		frappe.response.message = "Something went wrong"
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_despatch_entry.deflashing_despatch_entry.validate_lot_barcode")

@frappe.whitelist()
def validate_warehouse(bar_code):
	try:
		exe_warehouse = frappe.db.get_value("Warehouse",{"barcode_text":bar_code},["warehouse_name","name","is_group"],as_dict=1)
		if exe_warehouse:
			if exe_warehouse.get("is_group"):
				frappe.response.status = "failed"
				frappe.response.message = "Group node warehouse is not allowed to select for transactions"
			frappe.response.status = "success"
			frappe.response.warehouse_name = exe_warehouse.get("warehouse_name")
			frappe.response.name = exe_warehouse.get("name")
		else:
			frappe.response.status = "failed"
			frappe.response.message = "There is no warehouse found for scanned vendor code"
	except Exception:
		frappe.response.status = "failed"
		frappe.response.message = "Something went wrong"
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_despatch_entry.deflashing_despatch_entry.validate_warehouse")
	