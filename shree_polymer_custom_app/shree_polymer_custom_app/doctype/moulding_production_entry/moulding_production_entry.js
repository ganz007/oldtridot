// Copyright (c) 2023, Tridotstech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Moulding Production Entry', {
	refresh: function(frm) {
		frm.set_query("employee", function() {
	        return {
	        	"query":"shree_polymer_custom_app.shree_polymer_custom_app.api.get_process_based_employess",
	            "filters": {
	                "process":"Moulding"
	            }
	        }
	    });
	},
	"scan_lot_number": (frm) => {
		if (frm.doc.scan_lot_number && frm.doc.scan_lot_number != undefined) {
			 frappe.call({
				method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.moulding_production_entry.moulding_production_entry.validate_lot_number',
				args: {
					batch_no: frm.doc.scan_lot_number
				},
				freeze: true,
				callback: function (r) {
					if(r.message.status=="Failed"){
						frappe.msgprint(r.message.message)
					}
					else{
						frm.set_value("job_card",r.message.message.job_card)
						frm.set_value("spp_batch_number",r.message.message.spp_batch_number)
						frm.set_value("batch_no",r.message.message.batch_no__)
					}

				}
			});
		}
	},
	"operator": (frm) => {
		if (frm.doc.operator && frm.doc.operator != undefined) {
			 frappe.call({
				method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.moulding_production_entry.moulding_production_entry.validate_operator',
				args: {
					operator: frm.doc.operator
				},
				freeze: true,
				callback: function (r) {
					if(r.message.status=="Failed"){
						frappe.msgprint(r.message.message)
					}
					else{
						frm.set_value("employee",r.message.message)
					}

				}
			});
		}
	},
	"scan_bin": (frm) => {
		if (frm.doc.scan_bin && frm.doc.scan_bin != undefined) {
			if(frm.doc.job_card){
				frappe.call({
					method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.moulding_production_entry.moulding_production_entry.validate_bin',
					args: {
						batch_no: frm.doc.scan_bin,
						job_card:frm.doc.job_card
					},
					freeze: true,
					callback: function (r) {
						if(r.message.status=="Failed"){
							frappe.msgprint(r.message.message)
						}
						else{
							frm.set_value("bin_weight",r.message.bin_weight)
							frm.set_value("bin_code",r.message.blanking_bin)
							frm.set_value("bin_name",r.message.asset_name)
						}
					}
				});
			}
			else{
				frappe.msgprint("Please Scan Lot No. before scan Bin")
			}
		}
	},
	"weight_of_balance_bin":function(frm){
		frappe.call({
				method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.moulding_production_entry.moulding_production_entry.validate_bin_weight',
				args: {
					weight: frm.doc.weight_of_balance_bin,
					bin:frm.doc.bin_code,
					bin_Weight:frm.doc.bin_weight
				},
				freeze: true,
				callback: function (r) {
					if(r.message.status=="Failed"){
						frappe.msgprint(r.message.message);
						frm.set_value("net_weight",0);
						frm.set_value("weight_of_balance_bin",0);

					}
					else{
						var net_wt= frm.doc.weight_of_balance_bin - frm.doc.bin_weight
						frm.set_value("net_weight",net_wt);
					}

				}
			});
		
	},
});
