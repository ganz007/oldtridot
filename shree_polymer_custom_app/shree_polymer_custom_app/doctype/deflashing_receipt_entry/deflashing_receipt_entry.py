# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt,getdate,add_to_date,now
from shree_polymer_custom_app.shree_polymer_custom_app.api import get_stock_entry_naming_series

class DeflashingReceiptEntry(Document):
	def validate(self):
		if (flt(self.product_weight, 3)+flt(self.scrap_weight, 3))>flt(self.qty, 3):
			frappe.throw("The <b>Product Weight and Scrap Weight</b> can't be grater than <b>Available Stock</b>")

	def on_submit(self):
		wo = create_work_order(self)
		if wo:
			mse = make_stock_entry(self,wo)
			if mse:
				if self.scrap_weight and self.scrap_weight>0:
					mmt = make_material_transfer(self)
					if not mmt:
						frappe.db.rollback()
						frappe.db.set_value(self.doctype,self.name,"docstatus",0)
						frappe.db.commit()
						frappe.throw("Scrap Material Transfer Entry creation error.")	
			else:
				frappe.db.rollback()
				frappe.db.set_value(self.doctype,self.name,"docstatus",0)
				frappe.db.commit()
				frappe.throw("Product Manufacture Entry creation error.")
		else:
			frappe.db.rollback()
			frappe.db.set_value(self.doctype,self.name,"docstatus",0)
			frappe.db.commit()
			frappe.throw("Work Order creation error.")

def make_stock_entry(self,work_order):
	try:		
		spp_settings = frappe.get_single("SPP Settings")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Manufacture"
		stock_entry.work_order = work_order.name
		stock_entry.company = work_order.company
		stock_entry.from_bom = 1
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		""" For identifying procees name to change the naming series the field is used """
		naming_status,naming_series = get_stock_entry_naming_series(spp_settings,"Deflashing Receipt (For Internal Vendor)" if self.warehouse == "U3-Store - SPP INDIA" else "Deflashing Receipt (For External Vendor)")
		if naming_status:
			stock_entry.naming_series = naming_series
		""" End """
		stock_entry.bom_no = work_order.bom_no
		stock_entry.set_posting_time = 0
		stock_entry.use_multi_level_bom = work_order.use_multi_level_bom
		stock_entry.stock_entry_type = "Manufacture"
		stock_entry.fg_completed_qty = work_order.qty
		if work_order.bom_no:
			stock_entry.inspection_required = frappe.db.get_value("BOM", work_order.bom_no, "inspection_required")
		stock_entry.from_warehouse = work_order.source_warehouse
		stock_entry.to_warehouse = work_order.fg_warehouse
		d_spp_batch_no = get_spp_batch_date(work_order.production_item)
		bcode_resp = generate_barcode("P_"+d_spp_batch_no)
		for x in work_order.required_items:
			stock_entry.append("items",{
				"item_code":x.item_code,
				"s_warehouse":work_order.source_warehouse,
				"t_warehouse":None,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"is_finished_item":0,
				"transfer_qty":flt(self.product_weight, 3),
				"qty":flt(self.product_weight, 3),
				"spp_batch_number":self.spp_batch_no,
				"batch_no":self.batch_no,
				"mix_barcode":None})
		stock_entry.append("items",{
			"item_code":work_order.production_item,
			"s_warehouse":None,
			"t_warehouse":work_order.fg_warehouse,
			"stock_uom": "Nos",
			"uom": "Nos",
			"conversion_factor_uom":1,
			"is_finished_item":1,
			"transfer_qty":flt(work_order.qty, 3),
			"qty":flt(work_order.qty, 3),
			"spp_batch_number": d_spp_batch_no,
			"mix_barcode":work_order.production_item+"_"+d_spp_batch_no,
			"barcode_attach":bcode_resp.get("barcode"),
			"barcode_text":bcode_resp.get("barcode_text"),
			"deflash_receipt_reference":self.lot_number
			})
		stock_entry.insert(ignore_permissions=True)
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus=1
		sub_entry.save(ignore_permissions=True)
		frappe.db.set_value(self.doctype,self.name,"stock_entry_reference",stock_entry.name)
		serial_no = 1
		serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
		if serial_nos:
			serial_no = serial_nos[0].serial_no+1
		sl_no = frappe.new_doc("SPP Batch Serial")
		sl_no.posted_date = getdate()
		sl_no.compound_code = work_order.production_item
		sl_no.serial_no = serial_no
		sl_no.insert()
		return True
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.make_stock_entry")
		frappe.db.rollback()
		return False

def make_material_transfer(self):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		if not spp_settings.scrap_warehouse:
			frappe.throw("Value not found for Scrap Warehouse in SPP Settings")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = "SPP"
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.from_warehouse = self.from_warehouse_id
		stock_entry.to_warehouse = spp_settings.scrap_warehouse
		stock_entry.append("items",{
			"item_code":self.item,
			"s_warehouse":self.from_warehouse_id,
			"t_warehouse":spp_settings.scrap_warehouse,
			"stock_uom": "Kg",
			"uom": "Kg",
			"conversion_factor_uom":1,
			"transfer_qty":flt(self.scrap_weight, 3),
			"qty":flt(self.scrap_weight, 3),
			"spp_batch_number":self.spp_batch_no,
			"batch_no":self.batch_no
			})
		stock_entry.insert(ignore_permissions=True)
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus=1
		sub_entry.save(ignore_permissions=True)
		frappe.db.commit()
		return True
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.make_material_transfer")
		frappe.db.rollback()
		return False

def create_work_order(doc_info):
	wo = None
	try:
		import time
		spp_settings = frappe.get_single("SPP Settings")
		if not spp_settings.deflash_default_time:
			frappe.throw("Value not found for default time in SPP Settings")
		if not spp_settings.deflash_workstation:
			frappe.throw("Value not found for default workstation in SPP Settings")
		if not spp_settings.unit_2_warehouse:
			frappe.throw("Value not found for unit 2 Warehouse in SPP Settings")
		if not spp_settings.wip_warehouse:
			frappe.throw("Value not found for Work in Progress Warehouse in SPP Settings")
		bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE  BI.item_code=%(item_code)s AND B.is_default=1 AND B.is_active=1 """,{"item_code":doc_info.item},as_dict=1)
		if bom:
			check_uom = frappe.db.get_all("UOM Conversion Detail",filters={"parent":bom[0].item,"uom":"Kg"},fields=['conversion_factor'])
			if check_uom:
				# each_no_qty = 1/check_uom[0].conversion_factor
				t_qty = check_uom[0].conversion_factor*doc_info.product_weight
				actual_weight = t_qty
				# actual_weight = doc_info.product_weight
				wo = frappe.new_doc("Work Order")
				wo.naming_series = "MFG-WO-.YYYY.-"
				wo.company = "SPP"
				wo.fg_warehouse = spp_settings.unit_2_warehouse
				wo.use_multi_level_bom = 0
				wo.skip_transfer = 1
				wo.source_warehouse = doc_info.from_warehouse_id
				wo.wip_warehouse = spp_settings.wip_warehouse
				wo.transfer_material_against = "Work Order"
				wo.bom_no = bom[0].name
				wo.append("operations",{
					"operation":"Deflashing",
					"bom":bom[0].name,
					"workstation":spp_settings.deflash_workstation,
					"time_in_mins":spp_settings.deflash_default_time,
					})
				wo.referenceid = round(time.time() * 1000)
				wo.production_item = bom[0].item
				wo.qty = flt(actual_weight, 3)
				wo.insert(ignore_permissions=True)
				wo_ = frappe.get_doc("Work Order",wo.name)
				wo_.docstatus = 1
				wo_.save(ignore_permissions=True)
				update_job_cards(wo.name,actual_weight,doc_info,doc_info.item)
				return wo
			else:
				frappe.throw("Please define UOM for Kgs for the item <b>"+bom[0].item+"</b>")
				return False
		else:
			frappe.throw("No BOM found associated with the item <b>"+doc_info.item+"</b>")
			return False
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.create_work_order")
		frappe.db.rollback()
		return False

def update_job_cards(wo,actual_weight,doc_info,item):
	job_cards = frappe.db.get_all("Job Card",filters={"work_order":wo})
	operations = frappe.db.get_all("Work Order Operation",filters={"parent":wo},fields=['time_in_mins'])
	for job_card in job_cards:
		jc = frappe.get_doc("Job Card",job_card.name)
		for time_log in jc.time_logs:
			# time_log.employee = employee
			time_log.completed_qty = flt("{:.3f}".format(actual_weight))
			if operations:
				time_log.from_time = now()
				time_log.to_time = add_to_date(now(),minutes=0,as_datetime=True)
				time_log.time_in_mins = 0
		# if spp_settings.auto_submit_job_cards:
		jc.total_completed_qty = flt("{:.3f}".format(actual_weight))
		""" For mainting single lot number to all process the moulding lot number replaced """
		jc.batch_code = doc_info.lot_number
		""" End """
		jc.docstatus = 1
		jc.save(ignore_permissions=True)

def get_spp_batch_date(compound=None):
	serial_no = 1
	serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
	if serial_nos:
		serial_no = serial_nos[0].serial_no+1
	month_key = getmonth(str(str(getdate()).split('-')[1]))
	l = len(str(getdate()).split('-')[0])
	compound_key = (str(getdate()).split('-')[0])[l - 2:]+month_key+str(str(getdate()).split('-')[2])+"X"+str(serial_no)
	return compound_key

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

def generate_barcode(compound):
	try:
		import code128
		import io
		from PIL import Image, ImageDraw, ImageFont
		barcode_param = barcode_text = str(compound)
		barcode_image = code128.image(barcode_param, height=120)
		w, h = barcode_image.size
		margin = 5
		new_h = h +(2*margin) 
		new_image = Image.new( 'RGB', (w, new_h), (255, 255, 255))
		# put barcode on new image
		new_image.paste(barcode_image, (0, margin))
		# object to draw text
		draw = ImageDraw.Draw(new_image)
		new_image.save(str(frappe.local.site)+'/public/files/{filename}.png'.format(filename=barcode_text), 'PNG')
		barcode = "/files/" + barcode_text + ".png"
		return {"barcode":barcode,"barcode_text":barcode_text}
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.generate_barcode")

def check_uom_bom(item):
	try:
		bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name INNER JOIN `tabItem` I ON I.name=B.item  WHERE BI.item_code=%(item_code)s AND B.is_active=1 AND I.default_bom=B.name """,{"item_code":item},as_dict=1)
		if bom:
			""" Multi Bom Validation """
			bom__ = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM` B WHERE B.item=%(bom_item)s AND B.is_Active=1 """,{"bom_item":bom[0].item},as_dict=1)
			if len(bom__) > 1:
				return {"status":"failed","message":f"Multiple BOM's found for Item to Produce - <b>{bom[0].item}</b>"}
			""" End """
			check_uom = frappe.db.get_all("UOM Conversion Detail",filters={"parent":bom[0].item,"uom":"Kg"},fields=['conversion_factor'])
			if check_uom:
				return {"status":"success"}
			else:
				return {"status":"failed","message":"Please define UOM for Kgs for the item <b>"+bom[0].item+"</b>"}
		else:
			return {"status":"failed","message":"No BOM found associated with the item <b>"+item+"</b>"}
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.check_uom_bom")
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
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.check_available_stock")
		return {"status":"failed","message":"Something went wrong"}
	
@frappe.whitelist()
def validate_lot_barcode(bar_code,w__barcode):
	try:
		deflashing_desp = frappe.db.sql(f""" SELECT DDEI.lot_number,DDEI.job_card,DDEI.batch_no,DDEI.item,DDEI.spp_batch_no,DDEI.qty,DDEI.warehouse_id
									 FROM `tabDeflashing Despatch Entry Item` DDEI INNER JOIN `tabDeflashing Despatch Entry` DDE ON DDE.name=DDEI.parent
									 WHERE DDE.docstatus=1 AND DDEI.lot_number='{bar_code}' """,as_dict=1)
		if deflashing_desp:
			""" Fetch warehouse details and check stock details """
			exe_warehouse = frappe.db.get_value("Warehouse",{"barcode_text":w__barcode},["warehouse_name","name","is_group"],as_dict=1)
			if exe_warehouse:
				if exe_warehouse.get("is_group"):
					frappe.response.status = "failed"
					frappe.response.error_type = "warehouse"
					frappe.response.message = "Group node warehouse is not allowed to select for transactions"
				else:
					frappe.response.status = "success"
					frappe.response.warehouse_name = exe_warehouse.get("warehouse_name")
					frappe.response.name = exe_warehouse.get("name")
					stock_status = check_available_stock(exe_warehouse.get("name"),deflashing_desp[0].get("item"),deflashing_desp[0].get("batch_no",""))
					if stock_status.get('status') == "success":
						bom_uom_resp = check_uom_bom(deflashing_desp[0].get("item"))
						if bom_uom_resp.get('status') == "success":
							frappe.response.job_card = deflashing_desp[0].get("job_card")
							frappe.response.item = deflashing_desp[0].get("item")
							frappe.response.qty = stock_status.get('qty')
							frappe.response.spp_batch_number = deflashing_desp[0].get("spp_batch_no")
							frappe.response.batch_no = deflashing_desp[0].get("batch_no","")
							frappe.response.from_warehouse = exe_warehouse.get("name")
							frappe.response.status = "success"
						else:
							frappe.response.status = bom_uom_resp.get('status')
							frappe.response.message = bom_uom_resp.get('message')
					else:
						frappe.response.status = stock_status.get('status')
						frappe.response.message = stock_status.get('message')
			else:
				frappe.response.status = "failed"
				frappe.response.error_type = "warehouse"
				frappe.response.message = "There is no warehouse found for scanned vendor code"
		else:
			frappe.response.status = "failed"
			frappe.response.message = "There is no <b>Deflashing Despatch Entry</b> found for the scanned lot"
	except Exception:
		frappe.response.status = "failed"
		frappe.response.message = "Something went wrong"
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.validate_lot_barcode")

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
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.deflashing_receipt_entry.deflashing_receipt_entry.validate_warehouse")
	