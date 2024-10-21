import frappe
from frappe.model.document import Document
from frappe.utils import (
	cint,
	date_diff,
	flt,
	get_datetime,
	get_link_to_form,
	getdate,
	nowdate
)
from frappe.utils import cint, cstr, duration_to_seconds, flt,add_to_date, update_progress_bar,format_time, formatdate, getdate, nowdate,now
from shree_polymer_custom_app.shree_polymer_custom_app.api import get_stock_entry_naming_series


class InspectionEntry(Document):
	def validate(self):
		if self.lot_no:
			check_exist = frappe.db.get_all("Inspection Entry",filters={"name":("!=",self.name),"docstatus":1,"lot_no":self.lot_no,"inspection_type":self.inspection_type})
			if check_exist:
				frappe.throw(f"Inspection Entry for lot <b>{self.lot_no}</b> already exists..!")
		if self.items:
			for each_item in self.items:
				if self.lot_no and self.lot_no != each_item.lot_no:
					frappe.throw(f"The Lot no. <b>{self.lot_no}</b> mismatch in row {each_item.idx}")
				
	def on_submit(self):
		if self.total_rejected_qty:
			if self.inspection_type == "Line Inspection" or self.inspection_type == "Lot Inspection":
				make_stock_entry(self)
			elif self.inspection_type == "Incoming Inspection" or self.inspection_type == "Patrol Inspection" or self.inspection_type == "Final Inspection":
				make_inc_stock_entry(self)

def check_available_stock(warehouse,item,batch_no):
	try:
		if batch_no:
			query = f""" SELECT qty FROM `tabItem Batch Stock Balance` WHERE item_code='{item}' AND warehouse='{warehouse}' AND batch_no='{batch_no}' """
		else:
			query = f""" SELECT qty FROM `tabItem Batch Stock Balance` WHERE item_code='{item}' AND warehouse='{warehouse}' """
		qty = frappe.db.sql(query,as_dict=1)
		if qty:
			if qty[0].qty:
				return {"status":"Success","qty":qty[0].qty}
			else:
				return {"status":"Failed","message":f"Stock is not available for the item <b>{item}</b>"}	
		else:
			return {"status":"Failed","message":f"Stock is not available for the item <b>{item}</b>"}
	except Exception:	
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.check_available_stock")
		return {"status":"Failed","message":"Something went wrong"}

@frappe.whitelist()
def validate_lot_number(batch_no,docname,inspection_type):
	try:
		if inspection_type == "Line Inspection" or inspection_type == "Lot Inspection":
			check_exist = frappe.db.get_all("Inspection Entry",filters={"name":("!=",docname),"docstatus":1,"lot_no":batch_no,"inspection_type":inspection_type})
			if check_exist:
				return {"status":"Failed","message":"Already Inspection Entry is created for this lot number."}
			else:
				check_lot_issue = frappe.db.sql(""" SELECT JB.total_qty_after_inspection,JB.total_completed_qty,JB.workstation,JB.work_order,JB.name as job_card,JB.production_item,JB.batch_code,
								E.employee_name as employee FROM `tabJob Card` JB 
								LEFT JOIN `tabJob Card Time Log` LG ON LG.parent = JB.name
								LEFT JOIN `tabEmployee` E ON LG.employee = E.name
								WHERE JB.batch_code=%(lot_no)s
								""",{"lot_no":batch_no},as_dict=1)
				if not check_lot_issue:
					return {"status":"Failed","message":f"Job Card not found for the scanned lot <b>{batch_no}</b>"}
				else:
					rept_entry = frappe.db.get_all("Moulding Production Entry",{"scan_lot_number":batch_no,"docstatus":1},["stock_entry_reference"])
					if not rept_entry:
						return {"status":"Failed","message":f"There is no <b>Moulding Production Entry</b> found for the lot <b>{batch_no}</b>"}
					else:
						query = f""" SELECT SED.t_warehouse as from_warehouse,SED.batch_no FROM `tabStock Entry Detail` SED INNER JOIN `tabStock Entry` SE 
									ON SED.parent=SE.name WHERE SED.item_code='{check_lot_issue[0].get("production_item")}' AND SE.work_order='{check_lot_issue[0].get("work_order")}' """
						spp_and_batch = frappe.db.sql(query,as_dict=1)
						if spp_and_batch:
							stock_status = check_available_stock(spp_and_batch[0].get("from_warehouse"),check_lot_issue[0].get("production_item"),spp_and_batch[0].get("batch_no",""))
							if stock_status.get('status') == "Success":
								check_lot_issue[0].qty_from_item_batch = stock_status.get('qty')
								""" Multi Bom Validation """
								bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name INNER JOIN `tabItem` I ON I.name=B.item  WHERE BI.item_code=%(item_code)s AND B.is_active=1 AND I.default_bom=B.name """,{"item_code":check_lot_issue[0].production_item},as_dict=1)
								if bom:
									bom__ = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM` B WHERE B.item=%(bom_item)s AND B.is_Active=1 """,{"bom_item":bom[0].item},as_dict=1)
									if len(bom__) > 1:
										return {"status":"Failed","message":f"Multiple BOM's found for Item to Produce - <b>{bom[0].item}</b>"}
									""" Add UOM for rejection in No's """
									check_uom = frappe.db.get_all("UOM Conversion Detail",filters={"parent":bom[0].item,"uom":"Kg"},fields=['conversion_factor'])
									if check_uom:
										""" This is equal to 1 No's """
										check_lot_issue[0].one_no_qty_equal_kgs = flt(1 / check_uom[0].conversion_factor , 3)
									else:
										return {"status":"Failed","message":f"Please define UOM for Kgs for the item <b>"+bom[0].item+"</b>"}
									""" End """
								else:
									return {"status":"Failed","message":f"BOM is not found for <b>Item to Produce</b>"}
								""" End """
								user_name = frappe.db.get_value("User",frappe.session.user,"full_name")
								item_batch_no = ""
								# st_details = frappe.db.sql(""" SELECT IB.spp_batch_number FROM `tabBlank Bin Issue Item` BI 
								# 			INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
								# 			INNER JOIN `tabItem Bin Mapping` IB ON BI.bin = IB.blanking_bin
								# 			INNER JOIN `tabBlank Bin Issue` B ON B.name = BI.parent
								# 			INNER JOIN `tabBlanking Bin` BB ON IB.blanking_bin=BB.name
								# 			WHERE BI.job_card=%(jb_name)s AND IB.job_card = %(jb_name)s
								# 			""",{"jb_name":check_lot_issue[0].job_card},as_dict=1)
								st_details = frappe.db.sql(""" SELECT IB.spp_batch_number FROM `tabBlank Bin Issue Item` BI 
											INNER JOIN `tabJob Card` JB ON JB.name= BI.job_card
											INNER JOIN `tabItem Bin Mapping` IB ON BI.bin = IB.blanking__bin
											INNER JOIN `tabBlank Bin Issue` B ON B.name = BI.parent
											INNER JOIN `tabAsset` A ON IB.blanking__bin=A.name
											WHERE BI.job_card=%(jb_name)s AND IB.job_card = %(jb_name)s
											""",{"jb_name":check_lot_issue[0].job_card},as_dict=1)
								check_lot_issue[0].spp_batch_no = ""
								if st_details:
									f_spp_batch_no = st_details[0].spp_batch_number
									se_ref = frappe.db.sql(""" SELECT SD.batch_no,SD.parent from `tabStock Entry Detail` SD 
															inner join `tabStock Entry` SE ON SE.name=SD.parent
															where SD.spp_batch_number = %(f_spp_batch_no)s AND SE.stock_entry_type='Manufacture'""",{"f_spp_batch_no":f_spp_batch_no},as_dict=1)
									if se_ref:
										spp_settings = frappe.get_single("SPP Settings")
										s_batch = frappe.db.sql(""" SELECT SD.spp_batch_number from `tabStock Entry Detail` SD 
																inner join `tabStock Entry` SE ON SE.name=SD.parent
																where SD.parent = %(se_name)s AND SE.stock_entry_type='Material Transfer' AND SD.s_warehouse = %(sheeting_warehouse)s""",{"sheeting_warehouse":spp_settings.default_sheeting_warehouse,"se_name":se_ref[0].parent},as_dict=1)
										if s_batch:
											check_lot_issue[0].spp_batch_no = s_batch[0].spp_batch_number.split('-')[0] if s_batch[0].spp_batch_number else s_batch[0].spp_batch_number
								chk_st_details = frappe.db.sql(""" SELECT SD.batch_no FROM `tabStock Entry Detail` SD
															INNER JOIN `tabStock Entry` SE ON SE.name = SD.parent
															INNER JOIN `tabWork Order` W ON W.name = SE.work_order
															INNER JOIN `tabJob Card` JB ON JB.work_order = W.name
															WHERE JB.batch_code = %(lot_no)s AND SD.t_warehouse is not null
															""",{"lot_no":batch_no},as_dict=1)
								if chk_st_details:
									item_batch_no = chk_st_details[0].batch_no
								check_lot_issue[0].batch_no = item_batch_no
								check_lot_issue[0].user_name = user_name
								return {"status":"Success","message":check_lot_issue[0]}
							else:
								return {"status":stock_status.get('status'),"message":stock_status.get('message')}	
						else:
							return {"status":"Failed","message":"There is no <b>Stock Entry</b> found for the scanned lot"}
		
		elif inspection_type == "Incoming Inspection" or inspection_type == "Patrol Inspection" or inspection_type == "Final Inspection":
			check_exist = frappe.db.get_value("Inspection Entry",{"lot_no":batch_no,"docstatus":1,"inspection_type":inspection_type,"name":("!=",docname)})
			if check_exist:
				return {"status":"Failed","message":f" Already Incoming Lot Inspection Entry is created for this lot number <b>{batch_no}</b>."}
			""" Validate job card """
			check_lot_issue = frappe.db.sql(""" SELECT JB.name FROM `tabJob Card` JB WHERE JB.batch_code=%(lot_no)s AND operation="Deflashing" """,{"lot_no":batch_no},as_dict=1)
			if not check_lot_issue:
				return {"status":"Failed","message":f"Job Card not found for the scanned lot <b>{batch_no}</b>"}
			else:
				rept_entry = frappe.db.get_all("Deflashing Receipt Entry",{"lot_number":batch_no,"docstatus":1},["stock_entry_reference"])
				if rept_entry:
					if not rept_entry[0].stock_entry_reference:
						return {"status":"Failed","message":f"Stock Entry Reference not found in <b>Deflashing Receipt Entry</b> for the lot <b>{batch_no}</b>"}
					else:
						product_details = frappe.db.sql(f""" SELECT  JC.work_order,E.employee_name as employee,SED.item_code as production_item,JC.batch_code,JC.workstation,SED.qty as total_completed_qty,SED.batch_no FROM `tabStock Entry Detail` SED INNER JOIN `tabStock Entry` SE ON SE.name=SED.parent
															INNER JOIN `tabJob Card` JC ON JC.work_order=SE.work_order LEFT JOIN `tabJob Card Time Log` LG ON LG.parent = JC.name 
															LEFT JOIN `tabEmployee` E ON LG.employee = E.name WHERE SE.name='{rept_entry[0].stock_entry_reference}' AND SED.deflash_receipt_reference='{batch_no}' """,as_dict=1)
						if product_details:
							query = f""" SELECT SED.t_warehouse as from_warehouse,SED.batch_no FROM `tabStock Entry Detail` SED INNER JOIN `tabStock Entry` SE 
										ON SED.parent=SE.name WHERE SED.item_code='{product_details[0].get("production_item")}' AND SE.work_order='{product_details[0].get("work_order")}' """
							spp_and_batch = frappe.db.sql(query,as_dict=1)
							if spp_and_batch:
								stock_status = check_available_stock(spp_and_batch[0].get("from_warehouse"),product_details[0].get("production_item"),spp_and_batch[0].get("batch_no",""))
								if stock_status.get('status') == "Success":
									product_details[0].qty_from_item_batch = stock_status.get('qty')
									return {"status":"Success","message":product_details[0]}
								else:
									return {"status":stock_status.get('status'),"message":stock_status.get('message')}	
							else:
								return {"status":"Failed","message":f"There is no <b>Stock Entry</b> found for the scanned lot <b>{batch_no}</b>"}
						else:
							return {"status":"Failed","message":f"Detail not found for the lot no <b>{batch_no}</b>"}
				else:
					return {"status":"Failed","message":f"There is no <b>Deflashing Receipt Entry</b> found for the lot <b>{batch_no}</b>"}
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.validate_lot_number")
		return {"status":"Failed","message":"Something went wrong."}

def make_stock_entry(self):
	try:
		bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name INNER JOIN `tabItem` I ON I.name=B.item  WHERE BI.item_code=%(item_code)s AND B.is_active=1 AND I.default_bom=B.name """,{"item_code":self.product_ref_no},as_dict=1)
		if bom:
			check_uom = frappe.db.get_all("UOM Conversion Detail",filters={"parent":bom[0].item,"uom":"Kg"},fields=['conversion_factor'])
			if check_uom:
				each_no_qty = 1 / check_uom[0].conversion_factor
				t_qty = each_no_qty * self.total_rejected_qty
				if flt(t_qty, 3)>0:
					spp_settings = frappe.get_single("SPP Settings")
					stock_entry = frappe.new_doc("Stock Entry")
					stock_entry.purpose = "Material Transfer"
					stock_entry.company = "SPP"
					stock_entry.naming_series = "MAT-STE-.YYYY.-"
					""" For identifying procees name to change the naming series the field is used """
					naming_status,naming_series = get_stock_entry_naming_series(spp_settings,self.inspection_type)
					if naming_status:
						stock_entry.naming_series = naming_series
					""" End """
					stock_entry.stock_entry_type = "Material Transfer"
					stock_entry.from_warehouse = spp_settings.unit_2_warehouse
					stock_entry.to_warehouse = spp_settings.rejection_warehouse
					stock_entry.append("items",{
						"item_code":self.product_ref_no,
						"s_warehouse":spp_settings.unit_2_warehouse,
						"t_warehouse":spp_settings.rejection_warehouse,
						"stock_uom": "Kg",
						"uom": "Kg",
						"batch_no":self.batch_no,
						"conversion_factor_uom":1,
						"transfer_qty":flt(t_qty, 3),
						"qty":flt(t_qty, 3),
						})
					
					stock_entry.insert(ignore_permissions=True)
					sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
					sub_entry.docstatus=1
					sub_entry.save(ignore_permissions=True)
					frappe.db.set_value(self.doctype,self.name,"stock_entry_reference",stock_entry.name)
					""" Update balance stock in job card after inspection completed """
					# balance_qty_kgs = frappe.db.get_value("Job Card",{"batch_code":self.lot_no},"total_qty_after_inspection") - t_qty
					# frappe.db.sql(""" UPDATE `tabJob Card` SET total_qty_after_inspection={0} WHERE batch_code='{1}' """.format(balance_qty_kgs,self.lot_no))
					""" End """
					frappe.db.commit()
			else:
				frappe.throw("Please define UOM for Kgs for the item <b>"+bom[0].item+"</b>")
		else:
			frappe.throw("No BOM found associated with the item <b>"+self.product_ref_no+"</b>")
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.make_stock_entry")
		frappe.db.rollback()

def make_inc_stock_entry(self):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Material Transfer"
		stock_entry.company = "SPP"
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		""" For identifying procees name to change the naming series the field is used """
		naming_status,naming_series = get_stock_entry_naming_series(spp_settings,self.inspection_type)
		if naming_status:
			stock_entry.naming_series = naming_series
		""" End """
		stock_entry.stock_entry_type = "Material Transfer"
		stock_entry.from_warehouse = spp_settings.unit_2_warehouse
		stock_entry.to_warehouse = spp_settings.rejection_warehouse
		stock_entry.append("items",{
			"item_code":self.product_ref_no,
			"s_warehouse":spp_settings.unit_2_warehouse,
			"t_warehouse":spp_settings.rejection_warehouse,
			"stock_uom": "Nos",
			"uom": "Nos",
			# "conversion_factor_uom":1,
			"batch_no":self.batch_no,
			"transfer_qty":self.total_rejected_qty,
			"qty":self.total_rejected_qty,
			})
		stock_entry.insert()
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus=1
		sub_entry.save(ignore_permissions=True)
		frappe.db.set_value(self.doctype,self.name,"stock_entry_reference",stock_entry.name)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.make_stock_entry")
		frappe.db.rollback()

@frappe.whitelist()
def validate_inspector_barcode(b__code,inspection_type):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		designation = None
		if spp_settings and spp_settings.designation_mapping:
			for desc in spp_settings.designation_mapping:
				if desc.spp_process == f"{inspection_type.split(' ')[0]} Inspector":
					if desc.designation:
						designation = desc.designation
		if designation:
			check_emp = frappe.db.sql("""SELECT name,employee_name FROM `tabEmployee` WHERE status='Active' AND barcode_text=%(barcode)s AND designation=%(desc)s""",{"barcode":b__code,"desc":designation},as_dict=1)
			if check_emp:
				frappe.response.status = 'success'
				frappe.response.message = check_emp[0]
			else:
				frappe.response.status = 'failed'
				frappe.response.message = "Employee not found."
		else:
			frappe.response.status = 'failed'
			frappe.response.message = "Designation not mapped in SPP Settings."
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.validate_inspector_barcode")
		frappe.response.status = 'failed'
		frappe.response.message = "Something went wrong."