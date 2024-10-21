// Copyright (c) 2023, Tridotstech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Blank Bin Rejection Entry', {
	"scan_inspector": function(frm) {
		if(frm.doc.scan_inspector && frm.doc.scan_inspector != undefined){
			frappe.call({
				method:'shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_rejection_entry.blank_bin_rejection_entry.validate_inspector_barcode',
				args:{
					"b__code":frm.doc.scan_inspector
				},
				freeze:true,
				callback:(r) =>{
					if(r && r.status=="failed"){
						frappe.msgprint(r.message);
						frm.set_value("scan_inspector", "");
					}
					else if(r && r.status=="success"){
						frm.set_value("inspector_name",r.message.employee_name);
						frm.set_value("inspector_code",r.message.name);
					}
					else{
						frappe.msgprint("Somthing went wrong.");
						frm.set_value("scan_inspector", "");
					}
				}
			})
		}
	},
	"scan_bin": (frm) => {
		if (frm.doc.scan_bin && frm.doc.scan_bin != undefined) {
				frappe.call({
					method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_rejection_entry.blank_bin_rejection_entry.validate_bin_barcode',
					args: {
						bar_code: frm.doc.scan_bin,
					},
					freeze: true,
					callback: function (r) {
						if (r.status == "failed") {
							frappe.msgprint(r.message);
							frm.set_value("scan_bin", "");
						}
						else if(r.status == "success"){
							// frm.set_value("quantity", r.message.qty);
							frm.set_value("item", r.message.item);
							frm.set_value("compound_code", r.message.compound_code);
							frm.set_value("bin_code", r.message.name);
							frm.set_value("bin_weight", r.message.bin_weight);
							
						}
						 
					}
				});	
		}
	},
	"gross_weight": (frm) => {
		if(frm.doc.gross_weight && frm.doc.gross_weight>0){
			frm.set_value("quantity", (frm.doc.gross_weight-frm.doc.bin_weight));
		}
	}
});
