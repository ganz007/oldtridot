# Copyright (c) 2022, Tridotstech and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, duration_to_seconds, flt,add_to_date, update_progress_bar,format_time, formatdate, getdate, nowdate,now

global_st_entries = []
class BlankingDCEntry(Document):
	def validate(self):
		if self.items:
			for x in self.items:
				if not x.gross_weight>0:
					frappe.throw("Enter the Gross Weight for row "+str(x.idx)+".")
				x.net_weight = x.gross_weight - x.bin_weight
		else:
			frappe.throw("Please choose items.")

	def on_submit(self):
		""" For restrict F-product creation 'hided' on 31/2/23"""
		# status = create_blanking_wo(self)
		# if status:
		# 	tse = create_mt_stock_entry(self) 
		# else:
		# 	self.reload()
		make_material_transfer(self)
		""" end """

def make_material_transfer(mt_doc):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		if not spp_settings.from_location:
			frappe.throw("Asset Movement <b>From location</b> not mapped in SPP settings")
		if not spp_settings.to_location:
			frappe.throw("Asset Movement <b>To location</b> not mapped in SPP settings")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = "SPP"
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.employee = mt_doc.employee
		stock_entry.from_warehouse = spp_settings.default_sheeting_warehouse
		stock_entry.to_warehouse = spp_settings.unit_2_warehouse
		produced_items = frappe.db.sql(""" SELECT name,item_produced,scanned_item,available_quantity,spp_batch_number,batch_no FROM `tabBlanking DC Item` WHERE parent=%(entry_id)s GROUP BY item_produced,available_quantity,spp_batch_number,scanned_item,batch_no""",{"entry_id":mt_doc.name},as_dict=1)
		for bl_item in produced_items:
			actual_weight = sum(flt(e_item.net_weight) for e_item in mt_doc.items if e_item.get("scanned_item") == bl_item.get("scanned_item") and e_item.spp_batch_number == bl_item.spp_batch_number and e_item.batch_no == bl_item.batch_no )
			stock_entry.append("items",{
				"item_code":bl_item.get("scanned_item"),
				"s_warehouse":spp_settings.default_sheeting_warehouse,
				"t_warehouse": spp_settings.unit_2_warehouse,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"is_finished_item":1,
				"transfer_qty":actual_weight,
				"batch_no":bl_item.get("batch_no"),
				"qty":actual_weight,
				"spp_batch_number":bl_item.get("spp_batch_number"),
				"mix_barcode":bl_item.get("mix_barcode"),
				})
		stock_entry.blanking_dc_no = mt_doc.name
		# stock_entry.insert(ignore_permissions=True)
		# sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		stock_entry.docstatus=1
		stock_entry.save(ignore_permissions=True)
		""" Update stock entry ref """
		frappe.db.set_value(mt_doc.doctype,mt_doc.name,"stock_entry_reference",stock_entry.name)
		""" end """
		for x in mt_doc.items:
			item_clip_mapping = frappe.db.get_all("Item Clip Mapping",filters={"compound":x.scanned_item,"sheeting_clip":x.sheeting_clip},fields=['*'])
			if item_clip_mapping:
				if item_clip_mapping[0].qty>=x.net_weight:
					frappe.db.sql(""" UPDATE `tabItem Clip Mapping` set is_retired = 1,qty=0 WHERE compound=%(compound)s AND sheeting_clip=%(sheeting_clip)s""",{"sheeting_clip":x.sheeting_clip,"compound":x.scanned_item})
				else:
					frappe.db.sql(""" UPDATE `tabItem Clip Mapping` set qty =%(s_qty)s WHERE compound=%(compound)s AND sheeting_clip=%(sheeting_clip)s""",{"sheeting_clip":x.sheeting_clip,"s_qty":(item_clip_mapping[0].qty-x.net_weight),"compound":x.scanned_item})
				""" Update clip mapping """
				bin_mapping = frappe.get_doc({
					"doctype":"Item Bin Mapping",
					"compound":x.get('scanned_item'),
					"qty":x.net_weight,
					"is_retired":0,
					"blanking__bin":x.bin_code,
					"spp_batch_number":x.spp_batch_number
					})
				bin_mapping.save(ignore_permissions=True)
		""" Make Asset Movement """
		asset__mov = frappe.new_doc("Asset Movement")
		asset__mov.company = "SPP"
		asset__mov.transaction_date = now()
		asset__mov.purpose = "Transfer"
		for x in mt_doc.items:
			asset__mov.append("assets",{
				"asset":x.bin_code,
				"source_location":spp_settings.from_location,
				"target_location": spp_settings.to_location,
				# "from_employee":mt_doc.employee
			})
		asset__mov.insert(ignore_permissions=True)
		ass__doc = frappe.get_doc("Asset Movement",asset__mov.name)
		ass__doc.docstatus = 1
		ass__doc.save(ignore_permissions=True)
		""" End """
		frappe.db.commit()
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blanking_dc_entry.blanking_dc_entry.make_material_transfer")
		frappe.db.sql(""" DELETE FROM `tabStock Entry` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		bl_dc = frappe.get_doc("Blanking DC Entry", mt_doc.name)
		bl_dc.db_set("docstatus", 0)
		mt_doc.reload()
		frappe.db.commit()
			
@frappe.whitelist()
def get_blanking_item_group():
	spp_settings = frappe.get_single("SPP Settings")
	if spp_settings.blanking_item_group:
		return {"status":"Success","item_group":spp_settings.blanking_item_group}
	return {"status":"Failed"}

@frappe.whitelist()
def validate_clip_barcode(batch_no,item_produced=None):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		clip_mapping = frappe.db.sql(""" SELECT compound,spp_batch_number,qty,sheeting_clip FROM `tabItem Clip Mapping` CM 
									INNER JOIN `tabSheeting Clip` SC ON SC.name = CM.sheeting_clip 
									WHERE SC.barcode_text = %(mix_barcode)s AND CM.is_retired=0""",{"mix_barcode":batch_no},as_dict=1)
		if clip_mapping:
			d_items = []
			d_items.append(clip_mapping[0].compound)
			""" Only material transfer required no production entry so bom validation restricted on 31/2/23"""
			# status_,msg = validate_bom_items(item_produced,d_items)
			# if status_:
			# 	items = clip_mapping[0].compound
			# 	batch_no = clip_mapping[0].compound+"_"+clip_mapping[0].spp_batch_number.split('-')[0]
			# 	s_query = "SELECT I.item_code,I.item_name,I.description,I.batch_no,SD.spp_batch_number,SD.mix_barcode,\
			# 				I.stock_uom as uom,I.qty FROM `tabItem Batch Stock Balance` I\
			# 				INNER JOIN `tabBatch` B ON I.batch_no = B.name \
			# 				INNER JOIN  `tabStock Entry Detail` SD ON SD.batch_no = B.name\
			# 				INNER JOIN  `tabStock Entry` SE ON SE.name = SD.parent\
			# 				WHERE I.item_code ='"+items+"' AND  (SD.mix_barcode = '"+batch_no+"' OR SD.barcode_text = '"+batch_no+"')   AND \
			# 				SE.sheeting_clip like '%"+clip_mapping[0].sheeting_clip+"%' AND I.warehouse ='"+spp_settings.default_sheeting_warehouse+"' AND B.expiry_date>=curdate() AND (SD.s_warehouse <> '"+spp_settings.default_cut_bit_warehouse+"' OR SD.s_warehouse IS NULL)" 
			# 	st_details = frappe.db.sql(s_query,as_dict=1)
			# 	if not st_details:
			# 		return  {"status":"Failed","message":"Scanned clip <b>"+batch_no+"</b> not exist in the <b>"+spp_settings.default_sheeting_warehouse+"</b>"}
			# 	if clip_mapping and st_details:
			# 		st_details[0].sheeting_clip = clip_mapping[0].sheeting_clip
			# 		st_details[0].qty = clip_mapping[0].qty
			# 	return {"status":"Success","message":st_details[0]}
			# else:
			# 	return {"status":"Failed","message":msg}

			items = clip_mapping[0].compound
			batch_no = clip_mapping[0].compound+"_"+clip_mapping[0].spp_batch_number.split('-')[0]
			s_query = "SELECT I.item_code,I.item_name,I.description,I.batch_no,SD.spp_batch_number,SD.mix_barcode,\
						I.stock_uom as uom,I.qty FROM `tabItem Batch Stock Balance` I\
						INNER JOIN `tabBatch` B ON I.batch_no = B.name \
						INNER JOIN  `tabStock Entry Detail` SD ON SD.batch_no = B.name\
						INNER JOIN  `tabStock Entry` SE ON SE.name = SD.parent\
						WHERE I.item_code ='"+items+"' AND  (SD.mix_barcode = '"+batch_no+"' OR SD.barcode_text = '"+batch_no+"')   AND \
						SE.sheeting_clip like '%"+clip_mapping[0].sheeting_clip+"%' AND I.warehouse ='"+spp_settings.default_sheeting_warehouse+"' AND B.expiry_date>=curdate() AND (SD.s_warehouse <> '"+spp_settings.default_cut_bit_warehouse+"' OR SD.s_warehouse IS NULL)" 
			st_details = frappe.db.sql(s_query,as_dict=1)
			if not st_details:
				return  {"status":"Failed","message":"Scanned clip <b>"+batch_no+"</b> not exist in the <b>"+spp_settings.default_sheeting_warehouse+"</b>"}
			if clip_mapping and st_details:
				st_details[0].sheeting_clip = clip_mapping[0].sheeting_clip
				st_details[0].qty = clip_mapping[0].qty
			return {"status":"Success","message":st_details[0]}
		
			""" End """
		return  {"status":"Failed","message":"Scanned clip <b>"+batch_no+"</b> not exist in the <b>"+spp_settings.default_sheeting_warehouse+"</b>"}
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blanking_dc_entry.blanking_dc_entry.validate_clip_barcode")

@frappe.whitelist()
def validate_asset_barcode(batch_no):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		if not spp_settings.from_location:
			return  {"status":"Failed","message":"Asset Default From Location not found in SPP Settings."}
		bl_bin = frappe.db.sql("""SELECT bin_weight,name,asset_name FROM `tabAsset` WHERE barcode_text=%(barcode_text)s """,{"barcode_text":batch_no},as_dict=1)
		if bl_bin:
			bin_release = frappe.db.sql(f"""SELECT IBM.is_retired FROM `tabItem Bin Mapping` IBM WHERE IBM.blanking__bin='{bl_bin[0].name}' AND IBM.is_retired=0 """,as_dict=1)
			if bin_release:
				return {"status":"Failed","message":"Bin not yet released."}
			location = frappe.db.sql("""SELECT name FROM `tabAsset` WHERE barcode_text=%(barcode_text)s  AND location=%(location)s""",{"location":spp_settings.from_location,"barcode_text":batch_no},as_dict=1)
			if not location:
				return  {"status":"Failed","message":"Scanned Bin <b>"+batch_no+"</b> not exist in the location <b>"+spp_settings.from_location+"</b>."}
			if not bl_bin[0].bin_weight:
				return {"status":"Failed","message":"Bin weight not set in Asset..!"}
			return {"status":"Success","message":bl_bin[0]}
		return  {"status":"Failed","message":"Scanned Bin <b>"+batch_no+"</b> not exist."}
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blanking_dc_entry.blanking_dc_entry.validate_asset_barcode")
		return  {"status":"Failed","message":"Something Went Wrong..!"}

@frappe.whitelist()
def validate_bin_barcode(batch_no):
	bl_bin = frappe.db.sql("""SELECT bin_weight,name FROM `tabBlanking Bin` WHERE barcode_text=%(barcode_text)s """,{"barcode_text":batch_no},as_dict=1)
	if bl_bin:
		# By gopi on 27/1/23
		bin_release = frappe.db.sql(f"""SELECT IBM.is_retired FROM `tabItem Bin Mapping` IBM WHERE IBM.blanking_bin='{bl_bin[0].name}' AND IBM.is_retired=0 """,as_dict=1)
		if bin_release:
			return {"status":"Failed","message":"Bin not yet released."}
		# end
		return {"status":"Success","message":bl_bin[0]}
	return  {"status":"Failed","message":"Scanned Bin <b>"+batch_no+"</b> not exist."}
	
def validate_bom_items(item_code,dc_items):
	bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE B.item=%(item_code)s AND B.is_active=1""",{"item_code":item_code},as_dict=1)
	if bom:
		""" Multi Bom Validation """
		bom__ = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM` B WHERE B.item=%(bom_item)s AND B.is_Active=1 """,{"bom_item":bom[0].item},as_dict=1)
		if len(bom__) > 1:
			return False,f"Multiple BOM's found for Item to Produce - <b>{bom[0].item}</b>"
		""" End """
		bom_items = frappe.db.get_all("BOM Item",filters={"parent":bom[0].name},fields=['item_code'])
		d_items = []
		for x in dc_items:
			d_items.append(x)
		for x in bom_items:
			if not x.item_code in d_items:
				return False,"BOM is not matched with Scanned Clip."
	return True,""

def create_blanking_wo(sp_entry):
	global_st_entries = []
	produced_items = frappe.db.sql(""" SELECT name,item_produced,scanned_item,available_quantity,spp_batch_number,batch_no FROM `tabBlanking DC Item` WHERE parent=%(entry_id)s GROUP BY item_produced,available_quantity,spp_batch_number,scanned_item,batch_no""",{"entry_id":sp_entry.name},as_dict=1)
	
	for bl_item in produced_items:
		bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE  B.item=%(item_code)s AND B.is_default=1 AND B.is_active=1 """,{"item_code":bl_item.item_produced},as_dict=1)
		if bom:
			actual_weight = bl_item.available_quantity
			net_weight = sum(flt(e_item.net_weight) for e_item in sp_entry.items if e_item.item_produced == bl_item.item_produced and e_item.spp_batch_number == bl_item.spp_batch_number and e_item.batch_no == bl_item.batch_no )
			# allow_negative_stock = frappe.db.get_value("Item",bl_item.scanned_item)
			
			# if allow_negative_stock:
			# 	if allow_negative_stock == 0:
			# 		if net_weight <= actual_weight:
			# 			actual_weight = net_weight
			actual_weight = net_weight
			spp_settings = frappe.get_single("SPP Settings")
			work_station = None
			w_stations = frappe.db.get_all("BOM Operation",filters={"parent":bom[0].name},fields=['workstation'])
			if w_stations:
				work_station = w_stations[0].workstation
			import time
			wo = frappe.new_doc("Work Order")
			wo.naming_series = "MFG-WO-.YYYY.-"
			wo.company = "SPP"
			wo.fg_warehouse = spp_settings.default_blanking_warehouse
			wo.use_multi_level_bom = 0
			wo.skip_transfer = 1
			wo.source_warehouse = spp_settings.default_sheeting_warehouse
			wo.wip_warehouse = spp_settings.wip_warehouse
			wo.transfer_material_against = "Work Order"
			wo.bom_no = bom[0].name
			wo.blanking_dc_no = sp_entry.name
			wo.append("operations",{
				"operation":"Blanking",
				"bom":bom[0].name,
				"workstation":work_station,
				"time_in_mins":20,
				})
			wo.referenceid = round(time.time() * 1000)
			wo.production_item =bom[0].item
			wo.qty = actual_weight
			wo.planned_start_date = getdate()
			wo.docstatus = 1

			try:
				wo.save(ignore_permissions=True)
				update_job_cards(wo.name,actual_weight,sp_entry)
				se = make_blanking_stock_entry(sp_entry,wo.name,bl_item,"Manufacture")
				if not se:
					return False
					
			except Exception as e:
				frappe.db.rollback()
				frappe.log_error(message=frappe.get_traceback(),title="Blanking WO Error")
				frappe.db.sql(""" DELETE FROM `tabStock Entry` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":sp_entry.name})
				frappe.db.sql(""" DELETE FROM `tabWork Order` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":sp_entry.name})
				frappe.db.sql(""" DELETE FROM `tabJob Card` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":sp_entry.name})
				frappe.db.commit()
				bl_dc = frappe.get_doc("Blanking DC Entry", sp_entry.name)
				bl_dc.db_set("docstatus", 0)
				return False
		else:
			frappe.db.rollback()
			frappe.db.sql(""" DELETE FROM `tabStock Entry` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":sp_entry.name})
			frappe.db.sql(""" DELETE FROM `tabWork Order` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":sp_entry.name})
			frappe.db.sql(""" DELETE FROM `tabJob Card` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":sp_entry.name})
			frappe.db.commit()
			bl_dc = frappe.get_doc("Blanking DC Entry", sp_entry.name)
			bl_dc.db_set("docstatus", 0)
			frappe.msgprint("No BOM found for the item <b>"+bl_item.item_produced+"</b>")
			return False
	return True

def update_job_cards(wo,actual_weight,sp_entry):
	job_cards = frappe.db.get_all("Job Card",filters={"work_order":wo})
	for job_card in job_cards:
		jc = frappe.get_doc("Job Card",job_card.name)
		for time_log in jc.time_logs:
			time_log.completed_qty = flt("{:.3f}".format(actual_weight))
			# time_log.time_in_mins = 20
		jc.total_completed_qty = flt("{:.3f}".format(actual_weight))
		jc.docstatus = 1
		jc.blanking_dc_no = sp_entry.name
		jc.save(ignore_permissions=True)
def make_blanking_stock_entry(mt_doc,work_order_id,sp_entry, purpose, qty=None):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		work_order = frappe.get_doc("Work Order", work_order_id)
		if not frappe.db.get_value("Warehouse", work_order.wip_warehouse, "is_group"):
			wip_warehouse = work_order.wip_warehouse
		else:
			wip_warehouse = None
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = purpose
		stock_entry.work_order = work_order_id
		stock_entry.company = work_order.company
		stock_entry.from_bom = 1
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		stock_entry.bom_no = work_order.bom_no
		stock_entry.set_posting_time = 0
		stock_entry.use_multi_level_bom = work_order.use_multi_level_bom
		stock_entry.stock_entry_type = "Manufacture"
		# accept 0 qty as well
		stock_entry.employee = mt_doc.employee
		stock_entry.fg_completed_qty = work_order.qty
		if work_order.bom_no:
			stock_entry.inspection_required = frappe.db.get_value(
				"BOM", work_order.bom_no, "inspection_required"
			)
		stock_entry.from_warehouse = work_order.source_warehouse
		stock_entry.to_warehouse = work_order.fg_warehouse
		prod_item = None
		prod_item_qty = 0
		cl_spp_no = None
		# for x in work_order.required_items:
		if mt_doc.items:
			for b_bin in mt_doc.items:
				if b_bin.item_produced == sp_entry.item_produced and b_bin.spp_batch_number == sp_entry.spp_batch_number:
					stock_entry.append("bins",{"blanking_bin":b_bin.bin_code})
		stock_entry.append("items",{
			"item_code":sp_entry.scanned_item,
			"s_warehouse":spp_settings.default_sheeting_warehouse,
			"t_warehouse":None,
			"stock_uom": "Kg",
			"uom": "Kg",
			"conversion_factor_uom":1,
			"is_finished_item":0,
			"transfer_qty":work_order.qty,
			"qty":work_order.qty,
			"batch_no":sp_entry.batch_no,
			"spp_batch_number":sp_entry.spp_batch_number
		})
		d_spp_batch_no = get_spp_batch_date(sp_entry.item_produced)
		bcode_resp = generate_barcode("F_"+d_spp_batch_no)
		stock_entry.append("items",{
			"item_code":sp_entry.item_produced,
			"s_warehouse":None,
			"t_warehouse":work_order.fg_warehouse,
			"stock_uom": "Kg",
			"uom": "Kg",
			"conversion_factor_uom":1,
			"is_finished_item":1,
			"transfer_qty":work_order.qty,
			"qty":work_order.qty,
			"spp_batch_number":d_spp_batch_no,
			"mix_barcode":sp_entry.item_produced+"_"+d_spp_batch_no,
			"barcode_attach":bcode_resp.get("barcode"),
			"barcode_text":bcode_resp.get("barcode_text"),
			})
		
		prod_item = sp_entry.item_produced
		prod_item_qty = work_order.qty
		cl_spp_no = d_spp_batch_no
		stock_entry.blanking_dc_no = mt_doc.name
		stock_entry.insert()
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus=1
		sub_entry.save(ignore_permissions=True)
		""" Update stock entry ref """
		frappe.db.set_value("Blanking DC Item",sp_entry.name,"stock_entry_reference",sub_entry.name)
		""" end """
		for x in sub_entry.items:
			if x.is_finished_item == 1:
				global_st_entries.append({"item_code":x.item_code,
									 "qty":x.qty,
									 "spp_batch_number":x.spp_batch_number,
									 "mix_barcode":x.mix_barcode,
									 "barcode_attach":x.barcode_attach,
									 "batch_no":x.batch_no,
									 "barcode_text":x.barcode_text,
									 })
		for x in mt_doc.items:
			item_clip_mapping = frappe.db.get_all("Item Clip Mapping",filters={"compound":x.scanned_item,"sheeting_clip":x.sheeting_clip},fields=['*'])
			if item_clip_mapping:
				if item_clip_mapping[0].qty>=x.net_weight:
					frappe.db.sql(""" UPDATE `tabItem Clip Mapping` set is_retired = 1,qty=0 WHERE compound=%(compound)s AND sheeting_clip=%(sheeting_clip)s""",{"sheeting_clip":x.sheeting_clip,"compound":x.scanned_item})
					frappe.db.commit()
				else:
					frappe.db.sql(""" UPDATE `tabItem Clip Mapping` set qty =%(s_qty)s WHERE compound=%(compound)s AND sheeting_clip=%(sheeting_clip)s""",{"sheeting_clip":x.sheeting_clip,"s_qty":(item_clip_mapping[0].qty-x.net_weight),"compound":x.scanned_item})
					frappe.db.commit()
		bin_list = frappe.db.sql(""" SELECT * FROM `tabBlanking DC Item` WHERE  item_produced=%(item_produced)s and parent=%(dc_name)s""",{"item_produced":sp_entry.item_produced,"dc_name":mt_doc.name},as_dict=1)
		if bin_list:
			for clip in bin_list:
				clip_mapping = frappe.get_doc({
					"doctype":"Item Bin Mapping",
					"compound":prod_item,
					"qty":clip.net_weight,
					"is_retired":0,
					"blanking_bin":clip.bin_code,
					"spp_batch_number":cl_spp_no
					})
				clip_mapping.save(ignore_permissions=True)
				frappe.db.commit()
		serial_no = 1
		serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
		if serial_nos:
			serial_no = serial_nos[0].serial_no+1
		sl_no = frappe.new_doc("SPP Batch Serial")
		sl_no.posted_date = getdate()
		sl_no.compound_code = sp_entry.item_produced
		sl_no.serial_no = serial_no
		sl_no.insert()
		return {"status":"Success","st_entry":stock_entry}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(message=frappe.get_traceback(),title="Blanking SE Error")
		frappe.db.sql(""" DELETE FROM `tabStock Entry` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		frappe.db.sql(""" DELETE FROM `tabWork Order` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		frappe.db.sql(""" DELETE FROM `tabJob Card` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		frappe.db.sql(""" UPDATE `tabBlanking DC Item` SET stock_entry_reference='' WHERE  name=%(dc_no)s""",{"dc_no":sp_entry.name})
		frappe.db.commit()
		# frappe.throw(e)
		bl_dc = frappe.get_doc("Blanking DC Entry", mt_doc.name)
		bl_dc.db_set("docstatus", 0)
		return False
	
def create_mt_stock_entry(mt_doc):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = "SPP"
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		stock_entry.stock_entry_type = "Material Transfer"
		# accept 0 qty as well
		stock_entry.from_warehouse = spp_settings.default_blanking_warehouse
		stock_entry.to_warehouse = spp_settings.unit_2_warehouse
		# accept 0 qty as well
		stock_entry.employee = mt_doc.employee
		prod_item = None
		prod_item_qty = 0
		cl_spp_no = None
		for x in global_st_entries:
			stock_entry.append("items",{
				"item_code":x.get("item_code"),
				"s_warehouse":spp_settings.default_blanking_warehouse,
				"t_warehouse":spp_settings.unit_2_warehouse,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"is_finished_item":1,
				"transfer_qty":x.get("qty"),
				"batch_no":x.get("batch_no"),
				"qty":x.get("qty"),
				"spp_batch_number":x.get("spp_batch_number"),
				"mix_barcode":x.get("mix_barcode"),
				"barcode_attach":x.get("barcode"),
				"barcode_text":x.get("barcode_text"),
				})
			
		stock_entry.insert()
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus=1
		sub_entry.save(ignore_permissions=True)
		frappe.db.commit()
		return {"status":"Success","st_entry":stock_entry}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(message=frappe.get_traceback(),title="Blanking SE Error")
		frappe.db.sql(""" DELETE FROM `tabStock Entry` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		frappe.db.sql(""" DELETE FROM `tabWork Order` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		frappe.db.sql(""" DELETE FROM `tabJob Card` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":mt_doc.name})
		frappe.db.commit()
		# frappe.throw(e)
		bl_dc = frappe.get_doc("Blanking DC Entry", mt_doc.name)
		bl_dc.db_set("docstatus", 0)
		return {"status":"Failed"}

def get_spp_batch_date(compound):
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
