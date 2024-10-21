// Copyright (c) 2023, Tridotstech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lot Resource Tagging', {
	"scan_lot_no": (frm) => {
		if (frm.doc.scan_lot_no && frm.doc.scan_lot_no != undefined)
		frappe.call({
			method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.lot_resource_tagging.lot_resource_tagging.validate_lot_number',
			args: {
				barcode: frm.doc.scan_lot_no,
				docname:frm.doc.name,
				operation_type:frm.doc.operation_type
			},
			freeze: true,
			callback: function (r) {
				if (r.status == "failed") {
					frappe.msgprint(r.message);
					frm.set_value("scan_lot_no", "");
				}
				else if(r.status == "success"){
					frm.set_value("job_card", r.message.name);
					frm.set_value("product_ref", r.message.production_item);
				}
				else{
					frappe.msgprint("Something went wrong.");
					frm.set_value("scan_lot_no", "");
				}
			}
		});	
	},
	"scan_operator": function(frm) {
		if(frm.doc.scan_operator && frm.doc.scan_operator != undefined){
			frappe.call({
				method:'shree_polymer_custom_app.shree_polymer_custom_app.doctype.lot_resource_tagging.lot_resource_tagging.validate_inspector_barcode',
				args:{
					"b__code":frm.doc.scan_operator
				},
				freeze:true,
				callback:(r) =>{
					if(r && r.status=="failed"){
						frappe.msgprint(r.message);
						frm.set_value("scan_operator", "");
					}
					else if(r && r.status=="success"){
						frm.set_value("operator_name",r.message.employee_name);
						frm.set_value("operator_id",r.message.name);
					}
					else{
						frappe.msgprint("Somthing went wrong.");
						frm.set_value("scan_operator", "");
					}
				}
			})
		}
	},
});
