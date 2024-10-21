# Copyright (c) 2022, Tridotstech and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
from frappe import _
def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_columns(filters):
	columns =  [
		_("Sl No") + ":Data",
		_("DC Date") + ":Date:120",
		_("DC No") + ":Link/SPP Delivery Challan:250",
		_("Compound REF") + ":Link/Item:120",
		_("Batch Code") + ":Data:120",
		_("Mix Barcode") + ":Data:120",
		_("Quantity") + ":Float:120",
		_("Receipt Status") + ":Data:120",
		_("Receipt DC No") + ":Data:250",
		_("Receipt Date") + ":Date:120",
		_("Receipt Quantity") + ":Float:120",
		]
	return columns

@frappe.whitelist()
def item_filters(doctype, txt, searchfield, start, page_len, filters):
	search_condition = ""
	if txt:
		search_condition = " AND name like '%"+txt+"%'"
	query = "SELECT name as value,Concat(item_name,',',item_group,description) as description FROM `tabItem` WHERE disabled=0 AND item_group IN('Compound','Batch')  {condition} ORDER BY modified DESC".format(condition=search_condition)
	linked_docs = frappe.db.sql(query)
	return linked_docs


def get_data(filters):
	conditions = " "
	if filters.get("dc_date"):
		conditions += " AND DATE(DC.creation) = '"+filters.get("dc_date")+"'"
	if filters.get("dc_status"):
		conditions += " AND DC.status = '"+filters.get("dc_status")+"'"
	if filters.get("dc_no"):
		conditions += " AND DC.name = '"+filters.get("dc_no")+"'"
	if filters.get("item"):
		conditions += " AND DCI.item_code = '"+filters.get("item")+"'"
	if filters.get("spp_batch_number"):
		conditions += " AND DCI.spp_batch_no like '%"+filters.get("spp_batch_number")+"%'"
	if filters.get("mixbarcode"):
		conditions += " AND DCI.scan_barcode like '%"+filters.get("mixbarcode")+"%'"

	query = "SELECT ROW_NUMBER() OVER(ORDER BY DC.creation DESC) AS row_num  ,DATE(DC.creation),DC.name,\
			DCI.item_code,DCI.spp_batch_no,DCI.scan_barcode,DCI.qty,\
			CASE \
				WHEN DCI.is_received = 1 THEN 'Received'\
				ELSE  'Not  Received'\
			END as r_status,\
			CASE \
				WHEN DCI.is_received = 1 THEN (SELECT DCR.parent FROM `tabDC Item` DCR WHERE DCR.operation = DC.operation AND DCR.scan_barcode = DCI.scan_barcode AND DCR.item_code = DCI.item_code LIMIT 1)\
				ELSE  ''\
			END as dcr_name,\
			CASE \
				WHEN DCI.is_received = 1 THEN (SELECT DATE(DCR.creation) FROM `tabDC Item` DCR WHERE DCR.operation = DC.operation AND DCR.scan_barcode = DCI.scan_barcode AND DCR.item_code = DCI.item_code LIMIT 1)\
				ELSE  ''\
			END as dcr_date,\
			CASE \
				WHEN DCI.is_received = 1 THEN (SELECT DCR.qty FROM `tabDC Item` DCR WHERE DCR.operation = DC.operation AND DCR.scan_barcode = DCI.scan_barcode AND DCR.item_code = DCI.item_code LIMIT 1)\
				ELSE  ''\
			END as dcr_qty\
			FROM `tabSPP Delivery Challan` DC\
			INNER JOIN `tabMixing Center Items` DCI ON DC.name = DCI.parent\
			LEFT JOIN `tabDC Item` DCR ON DCR.scan_barcode = DCI.scan_barcode AND DCR.item_code = DCI.item_code\
			WHERE DCI.qty> 0 {conditions} ORDER BY DC.creation DESC\
			".format(conditions=conditions)
	return frappe.db.sql(query, as_list=1)
	




