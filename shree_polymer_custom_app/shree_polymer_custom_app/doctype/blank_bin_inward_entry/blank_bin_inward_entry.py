# Copyright (c) 2023, Tridotstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, duration_to_seconds, flt,add_to_date, update_progress_bar,format_time, formatdate, getdate, nowdate,now


class BlankBinInwardEntry(Document):
	def validate(self):
		if self.items:
			for item in self.items:
				if not item.bin_gross_weight:
					frappe.throw(f"Enter the gross weight for the item {item.item} in row {item.idx}.")
		else:
			frappe.throw("Please add items before save.")

	def on_submit(self):
		make_stock_entry(self)

def make_stock_entry(self):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.purpose = "Repack" if self.move_to_cut_bit_warehouse else "Material Transfer"
		stock_entry.company = "SPP"
		stock_entry.naming_series = "MAT-STE-.YYYY.-"
		stock_entry.stock_entry_type = "Repack" if self.move_to_cut_bit_warehouse else "Material Transfer"
		stock_entry.from_warehouse = spp_settings.unit_2_warehouse
		stock_entry.to_warehouse = spp_settings.target_warehouse if not self.move_to_cut_bit_warehouse else spp_settings.default_cut_bit_warehouse
		for x in self.items:
			from shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_inward_entry.blank_bin_inward_entry import get_spp_batch_date
			d_spp_batch_no = get_spp_batch_date(x.get("compound_code"))
			stock_entry.append("items",{
				"item_code":x.get("item"),
				"s_warehouse":spp_settings.unit_2_warehouse,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"transfer_qty":x.get("bin_net_weight"),
				"qty":x.get("bin_net_weight"),
				})
			bcode_resp = generate_barcode("C_"+d_spp_batch_no)
			if self.move_to_cut_bit_warehouse == 0:
				stock_entry.append("items",{
					"item_code":x.get("item"),
					"t_warehouse":spp_settings.default_blanking_warehouse,
					"stock_uom": "Kg",
					"uom": "Kg",
					"conversion_factor_uom":1,
					"is_finished_item":1,
					"transfer_qty":x.get("bin_net_weight"),
					"qty":x.get("bin_net_weight"),
					"batch_no":x.get("batch_no"),
					"spp_batch_number":x.get("spp_batch_number"),
					"barcode_text":x.get("item")+"_"+x.get("spp_batch_number"),
					"mix_barcode":x.get("item")+"_"+x.get("spp_batch_number")
					})
			else:
				r_batchno = ""
				ct_batch = "Cutbit_"+x.get("compound_code")
				cb_batch = frappe.db.get_all("Batch",filters={"batch_id":ct_batch})
				if cb_batch:
					r_batchno = "Cutbit_"+x.get("compound_code")
				stock_entry.append("items",{
				"item_code":x.get("compound_code"),
				"t_warehouse":spp_settings.target_warehouse if not self.move_to_cut_bit_warehouse else spp_settings.default_cut_bit_warehouse,
				"stock_uom": "Kg",
				"uom": "Kg",
				"conversion_factor_uom":1,
				"is_finished_item":1,
				"transfer_qty":x.get("bin_net_weight"),
				"batch_no":r_batchno,
				"qty":x.get("bin_net_weight"),
				"spp_batch_number":d_spp_batch_no,
				"is_compound":1,
				"barcode_text":"CB_"+x.get("compound_code"),
				"mix_barcode":x.get("compound_code")+"_"+d_spp_batch_no if not self.move_to_cut_bit_warehouse else "CB_"+x.get("compound_code")
				})
		stock_entry.insert()
		sub_entry = frappe.get_doc("Stock Entry",stock_entry.name)
		sub_entry.docstatus=1
		sub_entry.save(ignore_permissions=True)
		frappe.db.set_value(self.doctype,self.name,"stock_entry_reference",stock_entry.name)
		frappe.db.commit()
		for x in self.items:
			serial_no = 1
			serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
			if serial_nos:
				serial_no = serial_nos[0].serial_no+1
			sl_no = frappe.new_doc("SPP Batch Serial")
			sl_no.posted_date = getdate()
			sl_no.compound_code = x.get("compound_code")
			sl_no.serial_no = serial_no
			sl_no.insert()
		
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_inward_entry.blank_bin_inward_entry.make_stock_entry")
		frappe.db.rollback()
		
@frappe.whitelist()
def validate_bin_barcode(bar_code):
	try:
		spp_settings = frappe.get_single("SPP Settings")
		bl_bin = frappe.db.sql(""" SELECT BB.bin_weight,BB.name,IBM.compound as item,IBM.is_retired,IBM.qty,IBM.spp_batch_number FROM `tabBlanking Bin` BB INNER JOIN `tabItem Bin Mapping` IBM ON BB.name=IBM.blanking_bin 
								   WHERE barcode_text=%(barcode_text)s order by IBM.creation desc""",{"barcode_text":bar_code},as_dict=1)
		if bl_bin:
			if bl_bin[0].is_retired == 1:
				frappe.response.status = 'failed'
				frappe.response.message = "No item found in Scanned Bin."
			else:
				""" Check Bom mapped and get compound """
				stock_status = check_default_bom(bl_bin[0].item,bl_bin[0])
				if stock_status.get('status') == "success":
					s_query = "SELECT I.item_code,I.item_name,I.description,I.batch_no,SD.spp_batch_number,SD.mix_barcode,\
						I.stock_uom as uom,I.qty FROM `tabItem Batch Stock Balance` I\
						 INNER JOIN `tabBatch` B ON I.batch_no = B.name \
						 INNER JOIN  `tabStock Entry Detail` SD ON SD.batch_no = B.name\
						 INNER JOIN `tabStock Entry` SE ON SE.name = SD.parent \
						 WHERE SE.bom_no ='{bom_no}'AND SE.stock_entry_type='Manufacture' AND\
						 I.warehouse ='{warehouse}' AND B.expiry_date>=curdate() ORDER BY SE.creation DESC LIMIT 1".format(bom_no=stock_status.get("bom"),warehouse=spp_settings.default_blanking_warehouse)
					st_entry = frappe.db.sql(s_query,as_dict=1)
					if st_entry:
						bl_bin[0].spp_batch_number = st_entry[0].spp_batch_number
						bl_bin[0].batch_no = st_entry[0].batch_no
						frappe.response.message = bl_bin[0]
						frappe.response.status = 'success'
					else:
						frappe.response.status = 'failed'
						frappe.response.message = "No Stock."
				else:
					frappe.response.message = stock_status.get('message')
					frappe.response.status = stock_status.get('status')
		else:
			frappe.response.status = 'failed'
			frappe.response.message = "Scanned Bin <b>"+bar_code+"</b> not exist."
	except Exception:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_inward_entry.blank_bin_inward_entry.validate_bin_barcode")
		frappe.response.status = 'failed'
		frappe.response.message = "Something went wrong."
	
def check_default_bom(item,bl_entry):
	try:
		bom = validate_bom(item)
		if bom.get("status"):
			bl_entry.compound_code = bom.get("bom").item_code
			return {"status":"success","message":bl_entry,"bom":bom.get("bom").name}
		else:
			return {"status":"failed","message":"BOM is not found."}
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_inward_entry.blank_bin_inward_entry.check_stock_entry")

def validate_bom(item_code):
	bom = frappe.db.sql(""" SELECT B.name,BI.item_code FROM `tabBOM Item` BI INNER JOIN `tabBOM` B ON BI.parent = B.name INNER JOIN `tabItem` I ON I.name=B.item  WHERE B.item=%(item_code)s AND B.is_active=1 AND I.default_bom=B.name """,{"item_code":item_code},as_dict=1)
	if bom:
		return {"status":True,"bom":bom[0]}
	return {"status":False}


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