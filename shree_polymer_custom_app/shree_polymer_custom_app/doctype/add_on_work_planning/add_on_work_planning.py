# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate,flt

class AddOnWorkPlanning(Document):
	""" Store target item qty and bom for work order creation and validation """
	qty_wt_item = []
	bom_wt_item = []
	""" End """
	def validate(self):
		self.validate_amended()
		# self.validate_shift_mould()
		if self.items:
			""" Target Qty Validation """
			item_array = []
			condt = ''
			for each_item in self.items:
				item_array.append(each_item.item)
				condt += f'"{each_item.item}",'
			condt = condt[:-1]
			query = f"""  SELECT item,target_qty FROM `tabWork Plan Item Target` WHERE item IN ({condt}) AND target_qty != 0 """
			result = frappe.db.sql(query,as_dict=1) 
			unset_qty = result if result else []
			unset_qtys = []
			for u_qty in unset_qty:
				unset_qtys.append(u_qty.item)
				self.qty_wt_item.append({"item":u_qty.item,"qty":u_qty.target_qty})
			if len(item_array) != len(unset_qty):
				not_qty_item = list(filter(lambda x: x not in unset_qtys, item_array))
				if not_qty_item:
					frappe.throw(f"Target qty value of items <b>{', '.join(not_qty_item)}</b> is not found...!")
		else:
			frappe.throw("Please add items before save.")

	""" Change the job card / work order flag for appending the custom button when amend the form """
	def validate_amended(self):
		if self.is_new() and self.amended_from:
			self.job_card_wo = 0

	def validate_shift_mould(self):
		exe_shift = frappe.db.get_value(self.doctype,{"date":getdate(self.date),"shift_number":self.shift_number,"name":["!=",self.name],"docstatus":1})
		if exe_shift:
			frappe.throw(f"The shift <b>{self.shift_number}</b> already scheduled in the plan <b>{exe_shift}</b>")

	def on_submit_value(self):
		valididate = validate_bom(self)
		if valididate.get("status"):
			if self.items:
				wo = self.create_work_order()
				""" For custom button api response added """
				if wo:
					frappe.db.set_value(self.doctype,self.name,"job_card_wo",1)
					frappe.db.commit()
					return True
				else:
					return False
			else:
				return False
			""" End """ 
		else:
			frappe.throw(valididate.get("message"))
			return False

	def on_cancel(self):
		if self.items:
			try:
				for item in self.items:
					if item.job_card:
						jc = frappe.get_doc("Job Card",item.job_card)
						wo = frappe.get_doc("Work Order",jc.work_order)
						wo.docstatus = 2
						wo.save(ignore_permissions=True)
						frappe.db.delete("Job Card",{"name":jc.name})
						frappe.db.delete("Work Order",{"name":wo.name})
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				frappe.throw("Somthing went wrong , Can't Cancel Delete Job Card/Work Order")
				frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.add_on_work_planning.add_on_work_planning.on_cancel")
				
	def create_work_order(doc_info):
		try:
			import time
			spp_settings = frappe.get_single("SPP Settings")
			if not spp_settings.target_qty:
				frappe.throw("Value not found for no.of times to add qty in SPP Settings")
			if not spp_settings.default_time:
				frappe.throw("Value not found for default time in SPP Settings")
			for item in doc_info.items:
				# bom = list(filter(lambda x: x.get('item') == item.item,doc_info.bom_wt_item))[0].get('bom')
				bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE  B.item=%(item_code)s AND B.is_default=1 AND B.is_active=1 """,{"item_code":item.item},as_dict=1)
				actual_weight = flt(spp_settings.target_qty) * list(filter(lambda x: x.get('item') == item.item,doc_info.qty_wt_item))[0].get('qty')
				wo = frappe.new_doc("Work Order")
				wo.naming_series = "MFG-WO-.YYYY.-"
				wo.company = "SPP"
				wo.fg_warehouse = spp_settings.unit_2_warehouse
				wo.use_multi_level_bom = 0
				wo.skip_transfer = 1
				wo.source_warehouse = spp_settings.unit_2_warehouse
				wo.wip_warehouse = spp_settings.wip_warehouse
				wo.transfer_material_against = "Work Order"
				wo.bom_no = bom[0].name
				wo.append("operations",{
					"operation":"Moulding",
					"bom":bom[0].name,
					"workstation":item.work_station,
					"time_in_mins":spp_settings.default_time,
					})
				wo.referenceid = round(time.time() * 1000)
				wo.production_item = bom[0].item
				wo.qty = actual_weight
				wo.planned_start_date = getdate(doc_info.date)
				wo.docstatus = 1
				wo.save(ignore_permissions=True)
				jo_card = update_job_cards(wo.name,actual_weight,doc_info,item)
				if not jo_card:
					frappe.db.rollback()
					return False
			frappe.db.commit()
			return True
		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.add_on_work_planning.add_on_work_planning.create_work_order")
			return False

def update_job_cards(wo,actual_weight,doc_info,item):
	try:
		job_cards = frappe.db.get_all("Job Card",filters={"work_order":wo})
		lot_number = get_spp_batch_date(doc_info.shift_number)
		barcode = generate_barcode(lot_number)
		for job_card in job_cards:
			jc = frappe.get_doc("Job Card",job_card.name)
			for time_log in jc.time_logs:
				time_log.completed_qty =flt(actual_weight,3)
				time_log.time_in_mins = 1
			jc.total_completed_qty =flt(actual_weight,3)
			jc.for_quantity =flt(actual_weight,3)
			jc.batch_code = lot_number
			jc.barcode_image_url = barcode.get('barcode')
			jc.barcode_text = barcode.get('barcode_text')
			jc.shift_number = doc_info.shift_number
			#for molud reference update
			asset_id = frappe.db.get_value("Asset",{"item_code":item.get('mould')})
			if asset_id:
				jc.mould_reference = asset_id 
			# end
			mould_info = frappe.db.get_all("Mould Specification",filters={"mould_ref":item.get("mould")},fields=["*"])
			if mould_info:
				jc.no_of_running_cavities = mould_info[0].noof_cavities
				jc.blank_type = mould_info[0].blank_type
				jc.blank_wt = mould_info[0].avg_blank_wtproduct_gms
			press_info = frappe.db.get_all("Press Mould Specification",filters={"mould":item.get("mould"),"press":item.get('work_station')},fields=["*"])
			if press_info:
				jc.bottom_plate_temp = press_info[0].bottom_plate_temp
				jc.top_plate_temp = press_info[0].top_plate_temp
				jc.low_pressure_setting = press_info[0].low_pressure_setting
				jc.high_pressure_setting = press_info[0].high_pressure_setting
			jc.save(ignore_permissions=True)
			""" Update job card reference in child table """
			frappe.db.set_value("Add On Work Plan Item",item.name,{"job_card":jc.name,"lot_number":jc.batch_code})
			""" End """
			serial_no = 1
			serial_nos = frappe.db.get_all("Moulding Serial No",filters={"posted_date":getdate(),'shift_no':doc_info.shift_number},fields=['serial_no'],order_by="serial_no DESC")
			if serial_nos:
				serial_no = serial_nos[0].serial_no+1
			sl_no = frappe.new_doc("Moulding Serial No")
			sl_no.posted_date = getdate()
			sl_no.compound_code = item.get("item")
			sl_no.serial_no = serial_no
			sl_no.shift_no = doc_info.shift_number
			sl_no.insert()
		frappe.db.commit()
		return True
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.add_on_work_planning.add_on_work_planning.update_job_cards")
		return False

def get_spp_batch_date(shift_no,compound=None):
	serial_no = 1
	serial_nos = frappe.db.get_all("Moulding Serial No",filters={"posted_date":getdate(),'shift_no':shift_no},fields=['serial_no'],order_by="serial_no DESC")
	if serial_nos:
		serial_no = serial_nos[0].serial_no+1
	month_key = getmonth(str(str(getdate()).split('-')[1]))
	l = len(str(getdate()).split('-')[0])
	serial_no = 30*(int(shift_no)-1)+int(serial_no)
	compound_key = (str(getdate()).split('-')[0])[l - 2:]+month_key+str(str(getdate()).split('-')[2])+str("{:02d}".format(serial_no))
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

@frappe.whitelist()
def validate_bom(self):
	for x in self.items:
		bom = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE  B.item=%(item_code)s AND B.is_default=1 AND B.is_active=1 """,{"item_code":x.item},as_dict=1)
		if not bom:
			return {"status":False,"message":"BOM not found for item <b>"+x.item+"</b>"}
		else:
			""" Multi Bom Validation """
			bom__ = frappe.db.sql(""" SELECT B.name,B.item FROM `tabBOM` B WHERE B.item=%(bom_item)s AND B.is_Active=1 """,{"bom_item":bom[0].item},as_dict=1)
			if len(bom__) > 1:
				return {"status":False,"message":f"Multiple BOM's found for Item to Produce - <b>{bom[0].item}</b>"}
			""" End """
	return {"status":True}

@frappe.whitelist()
def get_work_mould_filters():
	try:
		frappe.response.message = frappe.get_single("SPP Settings")
		frappe.response.status = 'success'
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.add_on_work_planning.add_on_work_planning.get_work_mould_filters")
		frappe.response.status = 'failed'
		
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
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.api.generate_barcode",message=frappe.get_traceback())		

@frappe.whitelist()
def submit_workplan(docname,doctype):
	try:
		wp = frappe.get_doc(doctype,docname)
		wp.run_method("validate")
		res = wp.run_method("on_submit_value")
		if res:
			frappe.local.response.status = "success"
		else:
			frappe.local.response.status = "failed"	
	except Exception:
		frappe.local.response.status = "failed"
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.api.submit_workplan",message=frappe.get_traceback())		

