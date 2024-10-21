# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, duration_to_seconds, flt, update_progress_bar,format_time, formatdate, getdate, nowdate,now,get_datetime

class Packing(Document):
	def validate(self):
		if not self.items:
			frappe.throw("Please add some items before save..!")

	def on_submit(self):
		res = make_repack_entry(self)
		if res.get('status') == "failed":
			self.reload()
			frappe.throw(res.get('message'))
		if res.get('status') == "success":
			res.get('st_entry').notify_update()
			self.reload()

def make_repack_entry(mt_doc):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		if not spp_settings.unit_2_warehouse:
			frappe.throw("Target warehouse details not found in <b>SPP Settings</p>")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Repack"
		stock_entry.company = "SPP"
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		stock_entry.stock_entry_type = "Repack"
		stock_entry.from_warehouse = spp_settings.unit_2_warehouse
		stock_entry.to_warehouse = spp_settings.unit_2_warehouse
		for x in mt_doc.items:
			stock_entry.append("items",{
				"item_code":x.product_ref,
				"s_warehouse":spp_settings.unit_2_warehouse,
				"stock_uom": "Nos",
				"to_uom": "Nos",
				"uom": "Nos",
				"is_finished_item":0,
				"transfer_qty":x.qty_nos,
				"qty":x.qty_nos,
				# "spp_batch_number":x.spp_batch_no,
				"batch_no":x.batch_no
				})
		for x in mt_doc.items:
			status,message,sl_no = get_spp_batch_date(x.product_ref)
			if status:
				stock_entry.append("items",{
					"item_code":x.product_ref,
					"t_warehouse":spp_settings.unit_2_warehouse,
					"stock_uom": "Nos",
					"to_uom": "Nos",
					"uom": "Nos",
					"is_finished_item":1,
					"transfer_qty":x.qty_nos,
					"qty":x.qty_nos,
					"spp_batch_number":sl_no,
					"mix_barcode": x.product_ref+"_"+sl_no
				})
			else:
				return {"status":"failed","message":message}
		stock_entry.save(ignore_permissions=True)
		st_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		st_entry.docstatus=1
		st_entry.save(ignore_permissions=True)
		frappe.db.set_value(mt_doc.doctype,mt_doc.name,"stock_entry_reference",st_entry.name)
		frappe.db.commit()
		return {"status":"success","st_entry":st_entry}
	except Exception as e:
		frappe.db.rollback()
		mt_doc.reload()
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.packing.packing.make_repack_entry")
		return {"status":"failed","message":"Something went wrong, Not able to make <b>Stock Entry</b>"}
	
def get_spp_batch_date(item):
	try:
		serial_no = 1
		serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
		if serial_nos:
			serial_no = serial_nos[0].serial_no+1
		sl_no = frappe.new_doc("SPP Batch Serial")
		sl_no.posted_date = getdate()
		sl_no.compound_code = item
		sl_no.serial_no = serial_no
		sl_no.insert(ignore_permissions=True)
		month_key = getmonth(str(str(getdate()).split('-')[1]))
		l = len(str(getdate()).split('-')[0])
		compound_key = (str(getdate()).split('-')[0])[l - 2:]+month_key+str(str(getdate()).split('-')[2])+"X"+str(serial_no)
		return True,'',compound_key
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.packing.packing.generate_w_serial_no")
		return False,"SPP batch no. generation error..!",''

def getmonth(code):
	if code == "01":
		return "A"
	if code == "02":
		return "B"
	if code == "03":
		return "C"
	if code == "04":
		return "D"
	if code == "05":
		return "E"
	if code == "06":
		return "F"
	if code == "07":
		return "G"
	if code == "08":
		return "H"
	if code == "09":
		return "I"
	if code == "10":
		return "J"
	if code == "11":
		return "K"
	if code == "12":
		return "L"


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
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.packing.packing.check_available_stock")
		return {"status":"failed","message":"Something went wrong"}

@frappe.whitelist()
def validate_lot_barcode(batch_no):
	try:
		""" Validate job card """
		check_lot_issue = frappe.db.sql(""" SELECT JB.name FROM `tabJob Card` JB WHERE JB.batch_code=%(lot_no)s AND operation="Deflashing" """,{"lot_no":batch_no},as_dict=1)
		if not check_lot_issue:
			frappe.response.status = 'failed'
			frappe.response.message = f"Job Card not found for the scanned lot <b>{batch_no}</b>"
		else:
			check_exist = frappe.db.get_all("Inspection Entry",filters={"docstatus":1,"lot_no":batch_no,"inspection_type":"Incoming Inspection"})
			if check_exist:
				rept_entry = frappe.db.get_all("Deflashing Receipt Entry",{"lot_number":batch_no,"docstatus":1},["stock_entry_reference"])
				if rept_entry:
					if not rept_entry[0].stock_entry_reference:
						frappe.response.status = 'failed'
						frappe.response.message = f"Stock Entry Reference not found in <b>Deflashing Receipt Entry</b> for the lot <b>{batch_no}</b>"
					else:
						product_details = frappe.db.sql(f""" SELECT  SED.t_warehouse as from_warehouse,SED.item_code,SED.batch_no,SED.spp_batch_number FROM `tabStock Entry Detail` SED INNER JOIN `tabStock Entry` SE ON SE.name=SED.parent
															INNER JOIN `tabJob Card` JC ON JC.work_order=SE.work_order LEFT JOIN `tabJob Card Time Log` LG ON LG.parent = JC.name 
															LEFT JOIN `tabEmployee` E ON LG.employee = E.name WHERE SE.name='{rept_entry[0].stock_entry_reference}' AND SED.deflash_receipt_reference='{batch_no}' """,as_dict=1)
						if product_details:
							stock_status = check_available_stock(product_details[0].get("from_warehouse"),product_details[0].get("item_code"),product_details[0].get("batch_no",""))
							if stock_status.get('status') == "success":
								product_details[0].qty_from_item_batch = stock_status.get('qty')
								frappe.response.status = "success"
								frappe.response.message = product_details[0]
							else:
								frappe.response.status = stock_status.get('status')
								frappe.response.message = stock_status.get('message')
						else:
							frappe.response.status = 'failed'
							frappe.response.message = f"There is no <b>Stock Entry</b> found for the scanned lot <b>{batch_no}</b>"
				else:
					frappe.response.status = 'failed'
					frappe.response.message = f"There is no <b>Deflashing Receipt Entry</b> found for the lot <b>{batch_no}</b>"
			else:
				frappe.response.status = 'failed'
				frappe.response.message = f'There is no <b>Incoming Inspection Entry</b> found for the lot <b>{batch_no}</b>'	
	except Exception:
		frappe.response.status = "failed"
		frappe.response.message = "Something went wrong"
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.packing.packing.validate_lot_barcode")
