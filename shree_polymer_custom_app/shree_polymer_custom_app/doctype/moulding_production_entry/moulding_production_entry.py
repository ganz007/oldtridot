# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, duration_to_seconds, flt,add_to_date, update_progress_bar,format_time, formatdate, getdate, nowdate,now
from shree_polymer_custom_app.shree_polymer_custom_app.api import get_stock_entry_naming_series

class MouldingProductionEntry(Document):	
	def on_submit(self):
		if self.no_balance_bin == 0:
			if not self.weight_of_balance_bin>0:
				frappe.throw("Please enter the gross weight of bin")
		tolerance_val = validate_tolerance(self)
		if tolerance_val.get("status"):
			make_stock_entry(self)
		else:
			frappe.throw(tolerance_val.get("message"))

	def on_cancel(self):
		try:
			if self.stock_entry_reference:
				try:
					se = frappe.get_doc("Stock Entry",self.stock_entry_reference)
					se.docstatus = 2
					se.save(ignore_permissions=True)
				except Exception:
					frappe.throw("Can't cancel/change Sales invoice..!")
				if se:
					try:
						frappe.db.sql(f"UPDATE `tabWork Order` SET status='Not Started' WHERE name='{se.work_order}'")
						frappe.db.sql(f"UPDATE `tabWork Order Operation` SET status='Pending' WHERE parent='{se.work_order}' AND parentfield='operations' AND parenttype='Work Order' ")
						frappe.db.sql(f"UPDATE `tabJob Card` SET status='Work In Progress',docstatus=0 WHERE work_order='{se.work_order}'")
					except Exception:
						frappe.throw("Can't cancel/change Work Order,Job card .. !")
			else:
				frappe.throw("Stock Entry reference not found.")
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"{self.doctype }- on cancel failed",message=frappe.get_traceback())

@frappe.whitelist()
def validate_operator(operator):
	check_emp = frappe.db.sql("""SELECT name FROM `tabEmployee` WHERE status='Active' AND barcode_text=%(barcode)s""",{"barcode":operator},as_dict=1)
	if check_emp:
		return {"status":"Success","message":check_emp[0].name}
	return {"status":"Failed","message":"Employee not found."}
	
@frappe.whitelist()
def validate_lot_number(batch_no):
	try:
		check_lot_issue = frappe.db.sql(""" SELECT IB.spp_batch_number,BI.name,B.job_card,JB.name as job_card FROM `tabBlank Bin Issue Item` BI 
						INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
						INNER JOIN `tabBlank Bin Issue` B ON B.name = BI.parent
						INNER JOIN `tabItem Bin Mapping` IB ON BI.bin = IB.blanking__bin
						WHERE BI.is_completed = 0 AND JB.batch_code=%(lot_no)s AND IB.is_retired = 0
						""",{"lot_no":batch_no},as_dict=1)
		if not check_lot_issue:
			return {"status":"Failed","message":"There is no entry for Blank Bin Issue for the scanned lot number."}
		else:
			""" For fetching batch number """	
			# batch_no = frappe.db.sql(f""" SELECT SED.batch_no FROM `tabStock Entry` SE INNER JOIN `tabStock Entry Detail` SED ON SED.parent=SE.name WHERE SE.stock_entry_type="Manufacture" AND SED.spp_batch_number = '{check_lot_issue[0].spp_batch_number}'  """,as_dict=1)
			batch_no = frappe.db.sql(f""" SELECT SED.batch_no FROM `tabStock Entry` SE INNER JOIN `tabStock Entry Detail` SED ON SED.parent=SE.name WHERE SE.stock_entry_type="Material Transfer" AND SED.spp_batch_number = '{check_lot_issue[0].spp_batch_number}'  """,as_dict=1)
			if batch_no:
				check_lot_issue[0].batch_no__ =  batch_no[0].batch_no
			else:
				""" For get f name from bom """
				f__name = frappe.db.sql(""" SELECT BI.item_code FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name INNER JOIN `tabJob Card` J ON J.bom_no = B.name WHERE J.name=%(name)s AND B.is_active=1""",{"name":check_lot_issue[0].job_card},as_dict=1)
				if f__name:
					return {"status":"Failed","message":f"The Batch No. not found for the item - <b>{f__name[0].item_code}</b>"}	
				else:
					return {"status":"Failed","message":f"The Batch No. not found for the source item"}
			""" End """
			""" Multi Bom Validation """
			f__name = frappe.db.sql(""" SELECT B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name INNER JOIN `tabJob Card` J ON J.bom_no = B.name WHERE J.name=%(name)s AND B.is_active=1""",{"name":check_lot_issue[0].job_card},as_dict=1)
			if f__name:
				bom__ = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM` B WHERE B.item=%(bom_item)s AND B.is_Active=1 """,{"bom_item":f__name[0].item},as_dict=1)
				if len(bom__) > 1:
					return {"status":"Failed","message":f"Multiple BOM's found for Item to Produce - <b>{f__name[0].item}</b>"}
			else:
				return {"status":"Failed","message":f"BOM is not found for <b>Item to Produce</b>"}
			""" End """
			return {"status":"Success","message":check_lot_issue[0]}
	except Exception:
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.moulding_production_entry.moulding_production_entry.validate_lot_number",message=frappe.get_traceback())

@frappe.whitelist()
def validate_bin(batch_no,job_card):
	# check_retired = frappe.db.sql(""" SELECT IB.name FROM `tabItem Bin Mapping` IB
	# 							  INNER JOIN `tabBlanking Bin` BB ON IB.blanking_bin=BB.name
	# 							  WHERE BB.barcode_text=%(barcode)s AND IB.is_retired=0""",{"barcode":batch_no},as_dict=1)
	check_retired = frappe.db.sql(""" SELECT IB.name FROM `tabItem Bin Mapping` IB
								  INNER JOIN `tabAsset` A ON IB.blanking__bin=A.name
								  WHERE A.barcode_text=%(barcode)s AND IB.is_retired=0""",{"barcode":batch_no},as_dict=1)
	if not check_retired:
		return {"status":"Failed","message":"The Scanned bin already released."}

	# check_lot_issue = frappe.db.sql(""" SELECT IB.spp_batch_number,BB.bin_weight,BI.name,B.job_card,BB.name as blanking_bin FROM `tabBlank Bin Issue Item` BI 
	# 				INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
	# 				INNER JOIN `tabItem Bin Mapping` IB ON BI.bin = IB.blanking__bin
	# 				INNER JOIN `tabBlank Bin Issue` B ON B.name = BI.parent
	# 				INNER JOIN `tabBlanking Bin` BB ON IB.blanking_bin=BB.name
	# 				WHERE BI.is_completed = 0 AND BB.barcode_text=%(barcode)s AND IB.is_retired=0
	# 				 """,{"barcode":batch_no},as_dict=1)
	check_lot_issue = frappe.db.sql(""" SELECT IB.spp_batch_number,A.bin_weight,BI.name,B.job_card,A.name as blanking_bin,A.asset_name FROM `tabBlank Bin Issue Item` BI 
					INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
					INNER JOIN `tabItem Bin Mapping` IB ON BI.bin = IB.blanking__bin
					INNER JOIN `tabBlank Bin Issue` B ON B.name = BI.parent
					INNER JOIN `tabAsset` A ON IB.blanking__bin=A.name
					WHERE BI.is_completed = 0 AND A.barcode_text=%(barcode)s AND IB.is_retired=0
					 """,{"barcode":batch_no},as_dict=1)
	if not check_lot_issue:
		return {"status":"Failed","message":"The Scanned bin not issue for the Job Card"+job_card+"."}
	else:
		return {"status":"Success","bin_weight":check_lot_issue[0].bin_weight,"blanking_bin":check_lot_issue[0].blanking_bin,"asset_name":check_lot_issue[0].asset_name}	

@frappe.whitelist()
def validate_bin_weight(weight,bin,bin_Weight):
	item_bin = frappe.db.get_all("Item Bin Mapping",filters={"blanking__bin":bin,"is_retired":0},fields=['qty'])
	if item_bin:
		if (flt(weight) - flt(bin_Weight))>flt(item_bin[0].qty):
			return {"status":"Failed","message":"The quantity in the bin "+bin+" is "+str('%.3f' %(item_bin[0].qty))}
	return  {"status":"Success"}

@frappe.whitelist()
def validate_tolerance(self):
	spp_settings = frappe.get_single("SPP Settings")
	total_bins_weight = frappe.db.sql(""" SELECT sum(IB.qty) as total_qty FROM `tabItem Bin Mapping` IB
						INNER JOIN `tabBlank Bin Issue Item` BI ON IB.blanking__bin = BI.bin
						INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
						WHERE IB.is_retired = 0 AND BI.is_completed=0 AND JB.name=%(job_card)s""",{"job_card":self.job_card}
						,as_dict=1)
	if spp_settings.production_tolerance!=0 and total_bins_weight and total_bins_weight[0].total_qty:
		from_wt = total_bins_weight[0].total_qty-((total_bins_weight[0].total_qty * spp_settings.production_tolerance)/100)
		to_wt = total_bins_weight[0].total_qty + ((total_bins_weight[0].total_qty * spp_settings.production_tolerance)/100)
		if not self.weight>=from_wt and self.weight<to_wt:
			return {"status":False,"message":"Mat bin weight should be between <b>"+str('%.3f' %(from_wt))+"</b> to <b>"+'%.3f' %(to_wt)+"</b>"}
	return {"status":True}

def make_stock_entry(self):
	try:
		# frappe.db.transaction_writes = 0
		# frappe.db.begin()
		# frappe.db.savepoint(f"{self.name.replace('-','')}")
		jc = frappe.get_doc("Job Card",self.job_card)
		for time_log in jc.time_logs:
			time_log.completed_qty =flt(self.weight,3)
			time_log.time_in_mins = 1
			time_log.employee = self.employee
		jc.total_completed_qty =flt(self.weight,3)
		jc.for_quantity =flt(self.weight,3)
		jc.number_of_lifts =self.number_of_lifts
		jc.docstatus=1
		if self.special_instructions:
			jc.remarks = self.special_instructions
		jc.save(ignore_permissions=True)
		spp_settings = frappe.get_single("SPP Settings")
		if not spp_settings.from_location:
			frappe.throw("Asset Movement <b>From location</b> not mapped in SPP settings")
		if not spp_settings.to_location:
			frappe.throw("Asset Movement <b>To location</b> not mapped in SPP settings")
		work_order_id = frappe.db.get_value("Job Card",self.job_card,"work_order")
		work_order = frappe.get_doc("Work Order", work_order_id)
		if not frappe.db.get_value("Warehouse", work_order.wip_warehouse, "is_group"):
			wip_warehouse = work_order.wip_warehouse
		else:
			wip_warehouse = None
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Manufacture"
		stock_entry.work_order = work_order_id
		stock_entry.company = work_order.company
		stock_entry.from_bom = 1
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		""" For identifying procees name to change the naming series the field is used """
		naming_status,naming_series = get_stock_entry_naming_series(spp_settings,"Moulding Entry")
		if naming_status:
			stock_entry.naming_series = naming_series
		""" End """
		stock_entry.bom_no = work_order.bom_no
		stock_entry.set_posting_time = 0
		stock_entry.use_multi_level_bom = work_order.use_multi_level_bom
		stock_entry.stock_entry_type = "Manufacture"
		stock_entry.fg_completed_qty = self.weight
		if work_order.bom_no:
			stock_entry.inspection_required = frappe.db.get_value(
				"BOM", work_order.bom_no, "inspection_required"
			)
		stock_entry.from_warehouse = work_order.source_warehouse
		stock_entry.to_warehouse = work_order.fg_warehouse
		d_spp_batch_no = get_spp_batch_date(work_order.production_item)
		bcode_resp = generate_barcode("T_"+d_spp_batch_no)
		for x in work_order.required_items:
			stock_entry.append("items",{
				"item_code":x.item_code,
				"s_warehouse": work_order.source_warehouse,
				"t_warehouse":None,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"is_finished_item":0,
				"transfer_qty":self.weight,
				"qty":self.weight,
				"spp_batch_number":self.spp_batch_number,
				"batch_no":self.batch_no
			})
		stock_entry.append("items",{
			"item_code":work_order.production_item,
			"s_warehouse":None,
			"t_warehouse":work_order.fg_warehouse,
			"stock_uom": "Kg",
			"uom": "Kg",
			"conversion_factor_uom":1,
			"is_finished_item":1,
			"transfer_qty":self.weight,
			"qty":self.weight,
			"spp_batch_number":d_spp_batch_no,
			"mix_barcode":work_order.production_item+"_"+d_spp_batch_no,
			"barcode_attach":bcode_resp.get("barcode"),
			"barcode_text":bcode_resp.get("barcode_text"),
			})
		stock_entry.blanking_dc_no = self.name
		stock_entry.insert(ignore_permissions=True)
		# frappe.db.rollback(save_point=f"{self.name.replace('-','')}")
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus = 1
		sub_entry.save(ignore_permissions=True)
		# stock_entry.docstatus = 1
		# stock_entry.save(ignore_permissions=True)
		""" Update stock entry reference """
		frappe.db.set_value(self.doctype,self.name,"stock_entry_reference",stock_entry.name)
		""" End """
		frappe.db.set_value("Work Order",work_order.name,"status","Completed")
		check_bins = frappe.db.sql(""" SELECT BI.bin,BI.name  FROM `tabBlank Bin Issue Item` BI 
					INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
					INNER JOIN `tabBlank Bin Issue` B ON B.name = BI.parent
					WHERE BI.is_completed = 0 AND JB.name=%(lot_no)s
					 """,{"lot_no":self.job_card},as_dict=1)
		for x in check_bins:
			if self.no_balance_bin:
				frappe.db.sql("""UPDATE `tabItem Bin Mapping` set is_retired=1 , job_card = %(job_card)s where blanking__bin=%(bin)s and is_retired=0""",{"bin":x.bin,'job_card':self.job_card})
				frappe.db.sql("""UPDATE `tabBlank Bin Issue Item` set is_completed=1 where bin=%(bin)s and is_completed=0""",{"bin":x.bin})
			else:
				if x.bin != self.bin_code:
					frappe.db.sql("""UPDATE `tabItem Bin Mapping` set is_retired=1 , job_card = %(job_card)s  where blanking__bin=%(bin)s and is_retired=0""",{"bin":x.bin,'job_card':self.job_card})
					frappe.db.sql("""UPDATE `tabBlank Bin Issue Item` set is_completed=1 where bin=%(bin)s and is_completed=0""",{"bin":x.bin})
				else:
					# frappe.db.sql(""" UPDATE `tabItem Bin Mapping` set qty=(%(qty)s) where blanking__bin=%(bin)s and is_retired=0 """,{"bin":x.bin,"qty":self.net_weight})
					frappe.db.sql(""" UPDATE `tabItem Bin Mapping` set qty=(%(qty)s), job_card = %(job_card)s where blanking__bin=%(bin)s and is_retired=0 """,{"bin":x.bin,"qty":self.net_weight,'job_card':self.job_card})
			""" Make Asset Relocation Movement """
			asset__mov = frappe.new_doc("Asset Movement")
			asset__mov.company = "SPP"
			asset__mov.transaction_date = now()
			asset__mov.purpose = "Transfer"
			asset__mov.append("assets",{
				"asset":x.bin,
				"source_location":spp_settings.to_location,
				"target_location":spp_settings.from_location,
				# "from_employee":mt_doc.employee
			})
			asset__mov.insert(ignore_permissions=True)
			ass__doc = frappe.get_doc("Asset Movement",asset__mov.name)
			ass__doc.docstatus = 1
			ass__doc.save(ignore_permissions=True)
			""" End """
		serial_no = 1
		serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
		if serial_nos:
			serial_no = serial_nos[0].serial_no + 1
		sl_no = frappe.new_doc("SPP Batch Serial")
		sl_no.posted_date = getdate()
		sl_no.compound_code = work_order.production_item
		sl_no.serial_no = serial_no
		sl_no.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(message=frappe.get_traceback(),title="Moulding SE Error")
		frappe.db.sql(""" DELETE FROM `tabStock Entry` WHERE  blanking_dc_no=%(dc_no)s""",{"dc_no":self.name})
		frappe.db.sql(""" UPDATE `tabJob Card` SET docstatus = 0, status = "Work In Progress" WHERE  name=%(name)s""",{"name":self.job_card})
		bl_dc = frappe.get_doc(self.doctype, self.name)
		bl_dc.db_set("docstatus", 0)
		frappe.db.commit()
		self.reload()
		# self.reload()
		# frappe.db.rollback(save_point=f"{self.name.replace('-','')}")
		# frappe.db.release_savepoint(savepoint)	
		
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
