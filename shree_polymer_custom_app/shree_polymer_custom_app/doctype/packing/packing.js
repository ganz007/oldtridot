// Copyright (c) 2023, Tridotstech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Packing', {
	refresh: function(frm) {
		if(frm.doc.docstatus == 1){
			frm.set_df_property("scan_section","hidden",1)
		}
		if(!frm.doc.qty_nos){
			frm.set_df_property("qty_nos","hidden",1)
		}
	},
	"scan_lot_no": (frm) => {
		if (frm.doc.scan_lot_no && frm.doc.scan_lot_no != undefined)
			frappe.call({
				method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.packing.packing.validate_lot_barcode',
				args: {
					batch_no: frm.doc.scan_lot_no
				},
				freeze: true,
				callback: function (r) {
					if (r && r.status == "failed") {
						frappe.msgprint(r.message);
						frm.set_value("scan_lot_no", "");
						frm.set_value("product_ref", "");
						frm.set_value("spp_batch_no", "");
						frm.set_value("batch_no", "")
						frm.set_value("qty_nos", 0)	
						frm.set_df_property("qty_nos", "hidden", 1)
					}
					else if (r && r.status == "success") {
						frm.total_nos = 0
						if (frm.doc.items && frm.doc.items.length>0) {
							let flag = false
							frm.doc.items.map(res =>{
								if (res.lot_no == frm.doc.scan_lot_no){
									frm.set_value("scan_lot_no", "");
									flag = true
									frappe.validated = false
									frappe.msgprint(`Scanned lot <b>${frm.doc.scan_lot_no}</b> is already added.`);
									return
								}
								frm.total_nos += res.qty_nos
							})
							if(flag){
								return
							}
						}
						frm.set_df_property("qty_nos", "hidden", 0)
						frm.set_value("product_ref", r.message.item_code)
						frm.set_value("spp_batch_no", r.message.spp_batch_number)
						frm.set_value("batch_no", r.message.batch_no)
						frm.set_value("qty_nos", r.message.qty)
						frm.available_stock = r.message.qty_from_item_batch
					}
					else {
						frappe.msgprint("Something went wrong..!");
					}
				}
			});
	},
	"add": (frm) => {
		if (!frm.doc.scan_lot_no) {
			frappe.msgprint("Please Scan Lot before add.");
			return false;
		}
		if (!frm.doc.qty_nos) {
			frappe.msgprint("Please enter quantity before add.");
			return false;
		}
		if(!frm.available_stock){
			frappe.msgprint("Could not find the available stock.");
			return false;
		}
		else {
			if(frm.available_stock <  parseInt(frm.doc.qty_nos)){
				frappe.validated = false
				frappe.msgprint(`The entered qty <b>${frm.doc.qty_nos}</b> is greater than the avilable stock <b>${frm.available_stock}</b>`)
			}
			else{
				var row = frappe.model.add_child(frm.doc, "Packing Item", "items");
				row.lot_no = frm.doc.scan_lot_no
				row.product_ref = frm.doc.product_ref
				row.qty_nos = frm.doc.qty_nos
				row.batch_no = frm.doc.batch_no
				row.spp_batch_no = frm.doc.spp_batch_no
				frm.refresh_field('items');
				frm.set_value("scan_lot_no", "");
				frm.set_value("product_ref", "");
				frm.set_value("spp_batch_no", "");
				frm.set_value("batch_no", "")
				frm.set_value("qty_nos", 0)	
				frm.set_df_property("qty_nos", "hidden", 1)
			}
		}
	},
});
