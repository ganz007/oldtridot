// Copyright (c) 2023, Tridotstech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Inspection Entry', {
	refresh: (frm) => {
		if (frm.doc.docstatus == 1) {
			frm.set_df_property("scan_production_lot", "hidden", 1)
			frm.set_df_property("type_of_defect", "hidden", 1)
			frm.set_df_property("rejected_qty", "hidden", 1)
			frm.set_df_property("add", "hidden", 1)
		}
	},
	"inspection_type":frm =>{
		if(frm.doc.inspection_type && frm.doc.inspection_type == "Incoming Inspection"){
			frm.set_df_property("total_inspected_qty","read_only",0)
			frm.set_df_property("total_inspected_qty","hidden",0)
		}
		else{
			frm.set_df_property("total_inspected_qty","read_only",1)
		}
	},
	"scan_inspector": function(frm) {
		if(frm.doc.scan_inspector && frm.doc.scan_inspector != undefined){
			frappe.call({
				method:'shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.validate_inspector_barcode',
				args:{
					"b__code":frm.doc.scan_inspector,
					inspection_type:frm.doc.inspection_type
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
						frm.set_value("scan_inspector", "");
					}
					else{
						frappe.msgprint("Somthing went wrong.");
						frm.set_value("scan_inspector", "");
					}
				}
			})
		}
	},
	"scan_production_lot": (frm) => {
		if (frm.doc.scan_production_lot && frm.doc.scan_production_lot != undefined)
			frappe.call({
				method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.inspection_entry.inspection_entry.validate_lot_number',
				args: {
					batch_no: frm.doc.scan_production_lot,
					docname: frm.doc.name,
					inspection_type:frm.doc.inspection_type
				},
				freeze: true,
				callback: function (r) {
					if (r && r.message && r.message.status == "Failed") {
						frappe.msgprint(r.message.message);
						frm.set_value("scan_production_lot", "");
					}
					else if (r && r.message && r.message.status == "Success") {
						if (frm.doc.inspection_type == "Lot Inspection" || frm.doc.inspection_type == "Line Inspection"){
							frm.set_value("product_ref_no", r.message.message.production_item)
							frm.set_value("lot_no", r.message.message.batch_code)
							frm.set_value("operator_name", r.message.message.employee)
							frm.set_value("scan_production_lot", "")
							frm.set_value("batch_no", r.message.message.batch_no)
							frm.set_value("spp_batch_number", r.message.message.spp_batch_no)
							frm.set_value("machine_no", r.message.message.workstation)
							// frm.set_value("total_inspected_qty", r.message.message.total_completed_qty)
							// frm.set_value("total_inspected_qty", r.message.message.total_qty_after_inspection)
							frm.set_value("total_inspected_qty", r.message.message.qty_from_item_batch)
							frm.one_no_qty_equal_kgs = r.message.message.one_no_qty_equal_kgs
						}
						else if(frm.doc.inspection_type == "Incoming Inspection" || frm.doc.inspection_type == "Patrol Inspection" || frm.doc.inspection_type == "Final Inspection"){
							frm.set_value("product_ref_no", r.message.message.production_item)
							frm.set_value("lot_no", r.message.message.batch_code)
							frm.set_value("operator_name", r.message.message.employee)
							frm.set_value("scan_production_lot", "")
							frm.set_value("batch_no", r.message.message.batch_no)
							frm.set_value("machine_no", r.message.message.workstation)
							// frm.set_value("total_inspected_qty_nos", r.message.message.total_completed_qty)
							frm.set_value("total_inspected_qty_nos", r.message.message.qty_from_item_batch)
						}
					}
					else {
						frappe.msgprint("Something went wrong.");
					}
				}
			});
	},
	"add": function (frm) {
		if (!frm.doc.product_ref_no || frm.doc.product_ref_no == undefined) {
			frappe.msgprint("Product reference no is missing.");
			return
		}
		if (!frm.doc.type_of_defect || frm.doc.type_of_defect == undefined) {
			frappe.msgprint("Please select type of defect.");
			return
		}
		if (!frm.doc.rejected_qty || frm.doc.rejected_qty == undefined) {
			frappe.msgprint("Please enter the rejected qty.");
			return
		}
		if (!frm.doc.machine_no || frm.doc.machine_no == undefined) {
			frappe.msgprint("Please enter the machine number.");
			return
		}
		if (!frm.doc.lot_no || frm.doc.lot_no == undefined) {
			frappe.msgprint("Please enter the lot number.");
			return
		}
		if (!frm.doc.inspector_code || frm.doc.inspector_code == undefined) {
			frappe.msgprint("Please Scan the Inspector.");
			return
		}
		if((frm.doc.inspection_type == "Lot Inspection" || frm.doc.inspection_type == "Line Inspection") && (!frm.one_no_qty_equal_kgs || frm.one_no_qty_equal_kgs == undefined)){
			frappe.msgprint("UOM coversion factor value not found.");
			return 
		}
		else {
			if(frm.doc.inspection_type == "Lot Inspection" || frm.doc.inspection_type == "Line Inspection"){
				let cur_rejected_qty = frm.one_no_qty_equal_kgs *  frm.doc.rejected_qty
				if ((frm.doc.total_inspected_qty ? frm.doc.total_inspected_qty : 0) > (cur_rejected_qty + (frm.doc.total_rejected_qty_kg ? frm.doc.total_rejected_qty_kg : 0))) {
					var row = frappe.model.add_child(frm.doc, "Inspection Entry Item", "items");
					row.product_ref_no = frm.doc.product_ref_no;
					row.lot_no = frm.doc.lot_no;
					row.type_of_defect = frm.doc.type_of_defect;
					row.rejected_qty = frm.doc.rejected_qty;
					row.rejected_qty_kg = cur_rejected_qty;
					row.operator_name = frm.doc.operator_name;
					row.machine_no = frm.doc.machine_no;
					row.inspector_name = frm.doc.inspector_name
					row.inspector_code = frm.doc.inspector_code
					row.batch_no = frm.doc.batch_no
					frm.refresh_field('items');
					frm.set_value("type_of_defect", "FLOW-(FL)");
					frm.set_value("rejected_qty", 0);
					if (frm.doc.items) {
						var r_qty = 0;
						var r_qty_kgs = 0;
						for (var i = 0; i < frm.doc.items.length; i++) {
							r_qty += frm.doc.items[i].rejected_qty
							r_qty_kgs += frm.doc.items[i].rejected_qty_kg
						}
						frm.set_value("total_rejected_qty", r_qty)
						frm.set_value("total_rejected_qty_kg", r_qty_kgs)
						var r_qty_per = (r_qty_kgs / frm.doc.total_inspected_qty) * 100
						frm.set_value("total_rejected_qty_in_percentage", r_qty_per)
					}
				}
				else {
					frappe.msgprint("Total <b>Rejected Quantity</b> should be less than the <b>Total Inspected Quantity</b>.");
					}
			}
			else if(frm.doc.inspection_type == "Incoming Inspection" || frm.doc.inspection_type == "Patrol Inspection" || frm.doc.inspection_type == "Final Inspection"){
				if ((frm.doc.total_inspected_qty_nos ? frm.doc.total_inspected_qty_nos : 0) > ((frm.doc.rejected_qty ? frm.doc.rejected_qty : 0) + (frm.doc.total_rejected_qty ? frm.doc.total_rejected_qty : 0))) {
					var row = frappe.model.add_child(frm.doc, "Inspection Entry Item", "items");
					row.product_ref_no = frm.doc.product_ref_no;
					row.lot_no = frm.doc.lot_no;
					row.type_of_defect = frm.doc.type_of_defect;
					row.rejected_qty = frm.doc.rejected_qty;
					row.operator_name = frm.doc.operator_name;
					row.machine_no = frm.doc.machine_no;
					row.inspector_name = frm.doc.inspector_name
					row.inspector_code = frm.doc.inspector_code
					row.batch_no = frm.doc.batch_no
					frm.refresh_field('items');
					frm.set_value("type_of_defect", "FLOW-(FL)");
					frm.set_value("rejected_qty", 0);
					if (frm.doc.items) {
						var r_qty = 0;
						for (var i = 0; i < frm.doc.items.length; i++) {
							r_qty += frm.doc.items[i].rejected_qty
						}
						frm.set_value("total_rejected_qty", r_qty)
						var r_qty_per = (r_qty / frm.doc.total_inspected_qty_nos) * 100
						frm.set_value("total_rejected_qty_in_percentage", r_qty_per)
					}
				}
				else {
					frappe.msgprint("Total <b>Rejected Quantity</b> should be less than the <b>Total Inspected Quantity</b>.");
					}
			}
		}
	}
});
