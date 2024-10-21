// Copyright (c) 2022, Tridotstech and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["DC Reconciliation"] = {
	"filters": [
		{
			"fieldname": "dc_date",
			"fieldtype": "Date",
			"label": __("Date"),
			"default": ""
		},
		{
			"fieldname": "dc_status",
			"fieldtype": "Select",
			"label": __("Receipt Status"),
			"default": "",
			"options":"\nPending\nPartially Completed\nCompleted"
		},
		{
			"fieldname": "dc_no",
			"fieldtype": "Link",
			"label": __("DC No"),
			"options":"SPP Delivery Challan"

		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"label": __("Item"),
			"options":"Item",
			get_query: function(txt) {
				 return {
	                "query":"shree_polymer_custom_app.shree_polymer_custom_app.report.dc_reconciliation.dc_reconciliation.item_filters",
	                "filters": {
	                    
	                }
	            };
			}

		},
		{
			"fieldname": "spp_batch_number",
			"fieldtype": "Data",
			"label": __("SPP Batch Number"),

		},
		{
			"fieldname": "mixbarcode",
			"fieldtype": "Data",
			"label": __("Mix Barcode"),

		},
	],
	"onload": function(){
		var item_filter = frappe.query_report.get_filter('item_filter');

		
	}
};
