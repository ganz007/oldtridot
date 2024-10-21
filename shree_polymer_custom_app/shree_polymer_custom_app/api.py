# Copyright (c) 2022, Tridotstech and contributors
# For license information, please see license.txt
import json
import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import (
	cint,
	date_diff,
	flt,
	get_datetime,
	get_link_to_form,
	getdate,
	nowdate,
	time_diff_in_hours,touch_file
)
import  os

@frappe.whitelist()
def on_item_update(doc,method):
	# frappe.enqueue(item_update, queue='default',doc=doc)
	item_update(doc)

@frappe.whitelist()
def on_batch_update(doc,method):
	if doc.item:
		item_doc = frappe.get_doc("Item",doc.item)
		# frappe.enqueue(item_update, queue='default',doc=item_doc)
		item_update(item_doc)
	if doc.name.startswith("Cutbit_"):
		generate_batch_barcode(doc)

@frappe.whitelist()	
def item_update(doc):
	try:
		
		items_code = "'"+doc.name+"'"
		frappe.db.sql("""DELETE FROM `tabItem Batch Stock Balance` WHERE item_code=%(item_code)s""",{"item_code":doc.name})
		frappe.db.commit()
		item_map = get_item_details()
		bom_items = frappe.db.sql(""" SELECT item_code FROM `tabBOM Item` BI 
								  INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE B.item=%(item)s""",{"item":doc.name},as_dict=1)
		if bom_items:
			items_code+=","
			for x in bom_items:
				frappe.db.sql("""DELETE FROM `tabItem Batch Stock Balance` WHERE item_code=%(item_code)s""",{"item_code":x.item_code})
				frappe.db.commit()
				items_code += "'"+x.item_code+"',"
				c_bom_items = frappe.db.sql(""" SELECT item_code FROM `tabBOM Item` BI 
								  INNER JOIN `tabBOM` B ON BI.parent = B.name WHERE B.item=%(item)s""",{"item":x.item_code},as_dict=1)
				for c in c_bom_items:
					frappe.db.sql("""DELETE FROM `tabItem Batch Stock Balance` WHERE item_code=%(item_code)s""",{"item_code":c.item_code})
					frappe.db.commit()
					items_code += "'"+c.item_code+"',"
			items_code = items_code[:-1]
		iwb_map = get_item_warehouse_batch_map(items_code,float_precision=3)
		data = []
		float_precision = 3
		for item in sorted(iwb_map):
			# if not filters.get("item") or filters.get("item") == item:
			for wh in sorted(iwb_map[item]):
				for batch in sorted(iwb_map[item][wh]):
					qty_dict = iwb_map[item][wh][batch]
					if qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty:
						allow = False
						if qty_dict.bal_qty>0:
							allow = True
						if frappe.db.get_value("Item",item,"allow_negative_stock")==1:
							allow = True
						if allow:
							ibs_doc = frappe.new_doc("Item Batch Stock Balance")
							ibs_doc.item_code=item
							ibs_doc.item_name=item_map[item]["item_name"]
							ibs_doc.description=item_map[item]["description"]
							ibs_doc.warehouse=wh
							ibs_doc.batch_no=batch
							ibs_doc.qty=flt(qty_dict.bal_qty, float_precision)
							ibs_doc.stock_uom=item_map[item]["stock_uom"]
							ibs_doc.save(ignore_permissions=True)
							frappe.db.commit()

	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="Item Batch Stock Balance")
		frappe.db.rollback()
		return {"status":"Failed"}

@frappe.whitelist()
def generate_batchwise_report(doc,method):
	frappe.db.sql(""" UPDATE `tabMaterial Reserved Stock` SET is_consumed=1 WHERE stock_entry_reference=%(stock_entry_reference)s """,{"stock_entry_reference":doc.name})
	# frappe.enqueue(save_generate_batchwise_report, queue='default',doc=doc)
	save_generate_batchwise_report(doc)
	update_se_barcode(doc)


@frappe.whitelist()	
def update_se_barcode(doc):
	allow_save = 0
	if doc.items and doc.stock_entry_type == "Manufacture":
		for x in doc.items:
			if x.t_warehouse and x.spp_batch_number and not x.barcode_text and not x.mix_barcode:
				if frappe.db.get_value("Item",x.item_code,"item_group")=="Compound":
					allow_save = 1
					d_spp_batch_no = get_spp_batch_date(x.item_code)
					bcode_resp = generate_barcode("C_"+d_spp_batch_no)
					x.mix_barcode = x.item_code+"_"+d_spp_batch_no
					x.is_compound=1
					x.barcode_attach = bcode_resp.get("barcode")
					x.barcode_text =bcode_resp.get("barcode_text")
	if allow_save:
		doc.save(ignore_permissions=True)

@frappe.whitelist()	
def save_generate_batchwise_report(doc):
	try:
		items_code = ""
		items = frappe.db.sql(""" SELECT item_code FROM `tabStock Entry Detail` WHERE parent=%(st_name)s GROUP BY item_code""",{"st_name":doc.name},as_dict=1)
		for x in items:
			frappe.db.sql("""DELETE FROM `tabItem Batch Stock Balance` WHERE item_code=%(item_code)s""",{"item_code":x.item_code})
			frappe.db.commit()
			items_code += "'"+x.item_code+"',"
		if items:
			items_code = items_code[:-1]
		item_map = get_item_details()
		if items_code:
			iwb_map = get_item_warehouse_batch_map(items_code,float_precision=3)
			data = []
			float_precision = 3
			for item in sorted(iwb_map):
				# if not filters.get("item") or filters.get("item") == item:
				for wh in sorted(iwb_map[item]):
					for batch in sorted(iwb_map[item][wh]):
						qty_dict = iwb_map[item][wh][batch]
						if qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty:
							allow = False
							if qty_dict.bal_qty>0:
								allow = True
							if frappe.db.get_value("Item",item,"allow_negative_stock")==1:
								allow = True
							if allow:
								ibs_doc = frappe.new_doc("Item Batch Stock Balance")
								ibs_doc.item_code=item
								ibs_doc.item_name=item_map[item]["item_name"]
								ibs_doc.description=item_map[item]["description"]
								ibs_doc.warehouse=wh
								ibs_doc.batch_no=batch
								ibs_doc.qty=flt(qty_dict.bal_qty, float_precision)
								ibs_doc.stock_uom=item_map[item]["stock_uom"]
								ibs_doc.save(ignore_permissions=True)
								frappe.db.commit()

	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(),title="Item Batch Stock Balance")
		frappe.db.rollback()
		return {"status":"Failed"}
def get_conditions(items_code):
	conditions = ""
	conditions += " AND company = 'SPP'"
	conditions += " AND item_code IN ({items_code})".format(items_code=items_code)
	conditions += " AND posting_date <= '%s'" % getdate()
	return conditions
# get all details
def get_stock_ledger_entries(items_code):
	conditions = get_conditions(items_code)
	return frappe.db.sql("""
		select SL.item_code, SL.batch_no, SL.warehouse, SL.posting_date, sum(actual_qty) as actual_qty
		from `tabStock Ledger Entry` SL
		inner join `tabBatch` B ON B.name = SL.batch_no
		where (case when B.expiry_date is not null then B.expiry_date >= CURDATE() else 1=1 end) AND SL.is_cancelled = 0 and SL.docstatus < 2 and ifnull(SL.batch_no, '') != '' %s
		group by voucher_no, batch_no, item_code, warehouse
		order by item_code, warehouse""" %
		conditions, as_dict=1)


def get_item_warehouse_batch_map(items_code,float_precision):
	sle = get_stock_ledger_entries(items_code)
	iwb_map = {}
	from_date = getdate('2021-04-21')
	to_date = getdate()
	for d in sle:
		iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, {})\
			.setdefault(d.batch_no, frappe._dict({
				"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0
			}))
		qty_dict = iwb_map[d.item_code][d.warehouse][d.batch_no]
		if d.posting_date < from_date:
			qty_dict.opening_qty = flt(qty_dict.opening_qty, float_precision) \
				+ flt(d.actual_qty, float_precision)
		elif d.posting_date >= from_date and d.posting_date <= to_date:
			if flt(d.actual_qty) > 0:
				qty_dict.in_qty = flt(qty_dict.in_qty, float_precision) + flt(d.actual_qty, float_precision)
			else:
				qty_dict.out_qty = flt(qty_dict.out_qty, float_precision) \
					+ abs(flt(d.actual_qty, float_precision))

		qty_dict.bal_qty = flt(qty_dict.bal_qty, float_precision) + flt(d.actual_qty, float_precision)

	return iwb_map


def get_item_details():
	item_map = {}
	for d in frappe.db.sql("select name, item_name, description, stock_uom from tabItem", as_dict=1):
		item_map.setdefault(d.name, d)
	return item_map

@frappe.whitelist()
def update_stock_balance():
	item_list = frappe.db.sql(""" SELECT name from `tabItem` WHERE default_bom is not null and name like 'C_%%' and item_group='Compound' and disabled = 0""",as_dict=1)
	for x in item_list:
		doc = frappe.get_doc("Item",x.name)
		# frappe.enqueue(item_update, queue='default',doc=doc)
		item_update(doc)

@frappe.whitelist()
def get_process_based_employess(doctype, txt, searchfield, start, page_len, filters):
	condition=''
	if txt:
		condition += " and (first_name like '%"+txt+"%' OR name like '%"+txt+"%')"
	if filters.get("process"):	
		desgn_list = frappe.db.get_all("SPP Designation Mapping",filters={"spp_process":filters.get("process")},fields=['designation'])
		if desgn_list:
			rl_list = ""
			for x in desgn_list:
				rl_list+="'"+x.designation+"',"
			rl_list = rl_list[:-1]
			return frappe.db.sql('''SELECT name,CONCAT(first_name,' ',last_name) as description  FROM `tabEmployee` WHERE status='Active' AND designation IN({roles}) {condition}'''.format(condition=condition,roles=rl_list))

	return []

@frappe.whitelist()
def generate_batch_barcode(doc):
	if not doc.barcode_attach:
		import code128
		import io
		from PIL import Image, ImageDraw, ImageFont
		barcode_param = barcode_text = "CB_"+doc.item
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
		doc.barcode_attach = "/files/" + barcode_text + ".png"
		doc.barcode_text = barcode_text
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def update_wh_barcode(doc,method):
	if not doc.barcode:
		import code128
		import io
		from PIL import Image, ImageDraw, ImageFont
		barcode_param = barcode_text = str(randomStringDigits(8))
		if frappe.db.get_all("Warehouse",filters={"barcode_text":barcode_text}):
			barcode_param = barcode_text = str(randomStringDigits(8))
			if frappe.db.get_all("Warehouse",filters={"barcode_text":barcode_text}):
				barcode_param = barcode_text = str(randomStringDigits(8))
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
		doc.barcode = "/files/" + barcode_text + ".png"
		doc.barcode_text = barcode_text
		doc.save(ignore_permissions=True)

@frappe.whitelist()
def update_emp_barcode(doc,method):
	if not doc.barcode:
		import code128
		import io
		from PIL import Image, ImageDraw, ImageFont
		barcode_param = barcode_text = str(randomStringDigits(8))
		if frappe.db.get_all("Employee",filters={"barcode_text":barcode_text}):
			barcode_param = barcode_text = str(randomStringDigits(8))
			if frappe.db.get_all("Employee",filters={"barcode_text":barcode_text}):
				barcode_param = barcode_text = str(randomStringDigits(8))
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
		doc.barcode = "/files/" + barcode_text + ".png"
		doc.barcode_text = barcode_text
		doc.save(ignore_permissions=True)

def randomStringDigits(stringLength=6):
	import random
	import string
	lettersAndDigits = string.ascii_uppercase + string.digits
	return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))

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
def get_spp_batch_date(compound=None):
	serial_no = 1
	serial_nos = frappe.db.get_all("SPP Batch Serial",filters={"posted_date":getdate()},fields=['serial_no'],order_by="serial_no DESC")
	if serial_nos:
		serial_no = serial_nos[0].serial_no+1
	month_key = getmonth(str(str(getdate()).split('-')[1]))
	l = len(str(getdate()).split('-')[0])
	compound_key = (str(getdate()).split('-')[0])[l - 2:]+month_key+str(str(getdate()).split('-')[2])+"X"+str(serial_no)
	return compound_key

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

def generate_lot_number(doc,event):
	try:
		if not doc.batch_code:
			production_lot_number = get_spp_batch_date()
			barcode = generate_barcode(production_lot_number)
			query = f" UPDATE `tab{doc.doctype}` SET batch_code='{production_lot_number}',barcode_image_url='{barcode.get('barcode')}' WHERE name='{doc.name}' "
			frappe.db.sql(query)
			frappe.db.commit()
		# update_qty(doc)
	except Exception:
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.api.generate_lot_number",message=frappe.get_traceback())
		frappe.throw("Barcode generation failed..!")

""" By Gopi on 27/03/23 """ 
def get_stock_entry_naming_series(spp_settings,stock_entry_type):
	try:
		if spp_settings and spp_settings.spp_naming_series:
			naming_series = list(filter(lambda x : x.stock_entry_type == stock_entry_type,spp_settings.spp_naming_series))
			if naming_series and naming_series[0].spp_naming_series:
				return True,naming_series[0].spp_naming_series
			else:
				return False,""
		else:
			return False,""
	except Exception:
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.api.get_stock_entry_naming_series",message=frappe.get_traceback())

@frappe.whitelist()
def update_asset_barcode(doc,method):
	try:
		if not doc.barcode:
			spp_settings = frappe.get_single("SPP Settings")
			if not spp_settings.bin_category:
				frappe.throw('Bin Category not mapped in SPP settings..!')
			elif doc.asset_category and spp_settings.bin_category == doc.asset_category:
				import code128
				from PIL import Image, ImageDraw, ImageFont
				barcode_param,barcode_text = None,None
				while True:
					barcode_param = barcode_text = str(randomStringDigits(8))
					if frappe.db.get_all(doc.doctype,filters={"barcode_text":barcode_text}):
						continue
					else:
						break
				barcode_image = code128.image(barcode_param, height=120)
				w, h = barcode_image.size
				margin = 5
				new_h = h +(2*margin) 
				new_image = Image.new( 'RGB', (w, new_h), (255, 255, 255))
				new_image.paste(barcode_image, (0, margin))
				new_image.save(str(frappe.local.site)+'/public/files/{filename}.png'.format(filename=barcode_text), 'PNG')
				doc.barcode = "/files/" + barcode_text + ".png"
				doc.barcode_text = barcode_text
				# doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.api.update_asset_barcode",message=frappe.get_traceback())
		frappe.throw("Barcode generation failed..!")
	
def update_qty(doc):
	try:
		if not doc.total_qty_after_inspection:
			frappe.db.sql(" UPDATE `tabJob Card` SET total_qty_after_inspection = {0} WHERE name = '{1}'".format(doc.total_completed_qty,doc.name))
			frappe.db.commit()
	except Exception:
		frappe.log_error(title="shree_polymer_custom_app.shree_polymer_custom_app.api.update_qty",message=frappe.get_traceback())