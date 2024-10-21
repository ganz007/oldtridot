// Copyright (c) 2023, Tridotstech and contributors
// For license information, please see license.txt

frappe.ui.form.on('Blank Bin Inward Entry', {
	refresh:(frm) =>{
		if(frm.doc.docstatus == 1){
			frm.set_df_property("bin_scan_section", "hidden", 1)
		}
		frm.set_df_property("bin_weight_kgs", "hidden", 1)
		frm.set_df_property("gross_weight_kgs", "hidden", 1)
		frm.set_df_property("net_weight_kgs", "hidden", 1)
		if(frm.doc.docstatus == 0){
			$('button[data-fieldname="add"]').attr("disabled","disabled");
		}
	},
	"blank_bin": (frm) => {
		if (frm.doc.blank_bin && frm.doc.blank_bin != undefined) {
				frappe.call({
					method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.blank_bin_inward_entry.blank_bin_inward_entry.validate_bin_barcode',
					args: {
						bar_code: frm.doc.blank_bin,
					},
					freeze: true,
					callback: function (r) {
						if (r.status == "failed") {
							frappe.msgprint(r.message);
							frm.set_value("blank_bin", "");
						}
						else if(r.status == "success"){
							
							if (frm.doc.items && frm.doc.items.length>0) {
								frm.doc.items.map(res =>{
									if (res.bin_code == r.message.name){
										frappe.msgprint(`Scanned Bin <b>${frm.doc.blank_bin}</b> already added.`);
										return
									}
								})
								frm.set_value("blank_bin", "");
								return
							}
							frm.set_df_property("bin_weight_kgs", "hidden", 0)
							frm.set_df_property("gross_weight_kgs", "hidden", 0)
							frm.set_df_property("net_weight_kgs", "hidden", 0)
							frm.set_value("bin_code", r.message.name);
							frm.set_value("bin_weight_kgs", r.message.bin_weight);
							frm.set_value("item", r.message.item);
							frm.set_value("compound_code", r.message.compound_code);
							frm.set_value("spp_batch_number", r.message.spp_batch_number);
							frm.set_value("batch_no", r.message.batch_no);
							// frm.bin_code_array.push(r.message.name)
							$('button[data-fieldname="add"]').removeAttr("disabled");
						}
						else{
							frappe.msgprint("Something went wrong.");
						}
					}
				});	
		}
	},
	"gross_weight_kgs":(frm) =>{
		var net_wt= frm.doc.gross_weight_kgs - frm.doc.bin_weight_kgs
		frm.set_value("net_weight_kgs",net_wt);
	},
	"add":function(frm){
		if(!frm.doc.blank_bin || frm.doc.blank_bin == undefined){
			frappe.msgprint("Please scan the Bin.");
		}
		if(!frm.doc.gross_weight_kgs || frm.doc.gross_weight_kgs == undefined){
			frappe.msgprint("Please enter the Gross Weight.");
		}
		else{
			var row = frappe.model.add_child(frm.doc, "Blank Bin Inward Item", "items");
			row.bin_code = frm.doc.bin_code;
    		row.bin_weight_kgs = frm.doc.bin_weight_kgs;
			row.item = frm.doc.item;
    		row.compound_code = frm.doc.compound_code;
			row.bin_gross_weight = frm.doc.gross_weight_kgs;
			row.bin_net_weight = frm.doc.net_weight_kgs;
			row.spp_batch_number = frm.doc.spp_batch_number;
			row.batch_no = frm.doc.batch_no;
			frm.refresh_field('items');
			frm.set_value("bin_code","");
    		frm.set_value("bin_weight_kgs","");
			frm.set_value("item", "");
			frm.set_value("compound_code", "");
			frm.set_value("gross_weight_kgs","");
    		frm.set_value("net_weight_kgs","");
			frm.set_value("blank_bin","");
			frm.set_value("spp_batch_number","");
			frm.set_value("batch_no","");
			frm.set_df_property("bin_weight_kgs", "hidden", 1)
			frm.set_df_property("gross_weight_kgs", "hidden", 1)
			frm.set_df_property("net_weight_kgs", "hidden", 1)
			$('button[data-fieldname="add"]').attr("disabled","disabled");
		}
	}
});
