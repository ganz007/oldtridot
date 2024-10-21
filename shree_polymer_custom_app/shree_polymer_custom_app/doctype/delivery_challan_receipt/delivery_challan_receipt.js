// Copyright (c) 2022, Tridotstech and contributors
// For license information, please see license.txt
var scanned_batches = [];
frappe.ui.form.on('Delivery Challan Receipt', {
	refresh: function(frm) {
		if(frm.doc.batches){
			for (var i = 0; i < frm.doc.batches.length; i++) {
				scanned_batches.push(frm.doc.batches[i].scan_barcode);
			}
		}
		var process_type = "Transfer Batches to Mixing Center";
		frm.set_query("hld_warehouse", function() {
            return {
                "query":"shree_polymer_custom_app.shree_polymer_custom_app.doctype.material_transfer.material_transfer.get_minxing_t_warehouses",
                "filters": {
                     "type":process_type
                }
            };
        });
	},
	"is_internal_mixing":function(frm){
		if(frm.doc.is_internal_mixing==1){
			frm.set_value("source_warehouse","U3-Store - SPP INDIA");
			frm.set_df_property("source_warehouse", "read_only", 1);
			frm.refresh_field('source_warehouse');
		}
		else{
			frm.set_value("source_warehouse","");
			// frm.set_df_property("source_warehouse", "read_only", 0);
			frm.refresh_field('source_warehouse');


		}

	},
	enter_manually:function(frm){
		if(frm.doc.dc_items){
			scanned_batches = [];
			for(var k=0;k<frm.doc.dc_items.length;k++){
					scanned_batches.push(frm.doc.dc_items[k].scan_barcode)
				}
		}
		if(frm.doc.enter_manually==1){
			setTimeout(function(){
		 $('input[data-fieldname="manual_scan_spp_batch_number"]').change(function(){
		 		if(frm.doc.manual_scan_spp_batch_number!="undefined" && frm.doc.manual_scan_spp_batch_number!="" ){
			if(scanned_batches.indexOf(frm.doc.manual_scan_spp_batch_number)==-1){
					frappe.call({
		                method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.delivery_challan_receipt.delivery_challan_receipt.validate_barcode',
		                args: {
		                    batch_no: frm.doc.manual_scan_spp_batch_number,
		                    warehouse:frm.doc.source_warehouse,
		                    is_internal_mixing:frm.doc.is_internal_mixing

		                },
		                freeze: true,
		                callback: function(r) {
		                	if(r.message.status=="Success"){
		                		var st_details = r.message.stock;
		                		var allow_warehouse = 1;
		                		if(frm.doc.source_warehouse){
		                			if(! (frm.doc.source_warehouse == st_details[0].warehouse)){
		                				allow_warehouse = 0
		                			}
		                		}
		                		else{
									frm.set_value("source_warehouse",st_details[0].warehouse);
		                		}
		                		if(allow_warehouse==1){
			                		var row = frappe.model.add_child(frm.doc, "DC Item", "dc_items");
			                		row.item_code = st_details[0].item_code;
			                		row.item_name = st_details[0].item_code;
			                		row.spp_batch_no = st_details[0].spp_batch_no;
			                		row.batch_no = st_details[0].batch_no;
			                		row.dc_no = st_details[0].dc_no;
			                		row.operation = st_details[0].operation;
			                		row.qty = st_details[0].qty;
			                		row.qty_uom = st_details[0].qty_uom;
			                		row.scan_barcode = st_details[0].scan_barcode;
			                		if(st_details[0].bom_item!=undefined && st_details[0].bom_item!=""){
			                			row.item_to_manufacture = st_details[0].bom_item;
			                		}
			                		frm.refresh_field('dc_items');
			                		frm.set_value("manual_scan_spp_batch_number","")
			                		scanned_batches.push(st_details[0].manual_scan_spp_batch_number)
			                	}
			                	else{
			                		frappe.msgprint("Source Warehouse should same.");

			                	}
		                	}
		                	else{
								frappe.msgprint(r.message.message);
								frm.set_value("manual_scan_spp_batch_number","")
		                	}
		                }
		            });
			}

		}
		 })
		},1000);
	 }
	},
	"scan_barcode":function(frm){
		if(frm.doc.dc_items){
			scanned_batches = [];
			for(var k=0;k<frm.doc.dc_items.length;k++){
					scanned_batches.push(frm.doc.dc_items[k].scan_barcode)
				}
		}
		if(frm.doc.scan_barcode!="undefined" && frm.doc.scan_barcode!="" ){
			if(scanned_batches.indexOf(frm.doc.scan_barcode)==-1){
					frappe.call({
		                method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.delivery_challan_receipt.delivery_challan_receipt.validate_barcode',
		                args: {
		                    batch_no: frm.doc.scan_barcode,
		                    warehouse:frm.doc.source_warehouse,
		                    is_internal_mixing:frm.doc.is_internal_mixing
		                    
		                },
		                freeze: true,
		                callback: function(r) {
		                	if(r.message.status=="Success"){
		                		var st_details = r.message.stock;
		                		var allow_warehouse = 1;
		                		if(frm.doc.source_warehouse){
		                			if(! (frm.doc.source_warehouse == st_details[0].warehouse)){
		                				allow_warehouse = 0
		                			}
		                		}
		                		else{
									frm.set_value("source_warehouse",st_details[0].warehouse);
		                		}
		                		if(allow_warehouse==1){
			                		var row = frappe.model.add_child(frm.doc, "DC Item", "dc_items");
			                		row.item_code = st_details[0].item_code;
			                		row.item_name = st_details[0].item_code;
			                		row.spp_batch_no = st_details[0].spp_batch_no;
			                		row.batch_no = st_details[0].batch_no;
			                		row.dc_no = st_details[0].dc_no;
			                		row.operation = st_details[0].operation;
			                		row.qty = st_details[0].qty;
			                		row.qty_uom = st_details[0].qty_uom;
			                		row.scan_barcode = st_details[0].scan_barcode;
			                		if(st_details[0].bom_item!=undefined && st_details[0].bom_item!=""){
			                			row.item_to_manufacture = st_details[0].bom_item;
			                		}

			                		frm.refresh_field('dc_items');
			                		frm.set_value("scan_barcode","")
			                		scanned_batches.push(st_details[0].scan_barcode)
			                	}
			                	else{
			                		frappe.msgprint("Source Warehouse should same.");

			                	}
		                	}
		                	else{
								frappe.msgprint(r.message.message);
								frm.set_value("scan_barcode","")
		                	}
		                }
		            });
			}

		}
	},
	"hld_item":function(frm){
		if(frm.doc.hld_warehouse){
			if(frm.doc.hld_item){
			frappe.call({
		                method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.delivery_challan_receipt.delivery_challan_receipt.get_batch_items',
		                args: {
		                    item_code: frm.doc.hld_item,
		                    warehouse:frm.doc.hld_warehouse
		                },
		                freeze: true,
		                callback: function(r) {
							if(r && r.message && r.message.status == "success"){
								if(r.message.message.length>0){
									for(var i=0;i<r.message.message.length;i++){
										var row = frappe.model.add_child(frm.doc, "Mixing Center Holding Item", "hld_items");
										row.item_code = r.message.message[i].item_code;
										row.item_name = r.message.message[i].item_code;
										row.spp_batch_no = r.message.message[i].spp_batch_no;
										row.batch_no = r.message.message[i].batch_no;
										row.qty = r.message.message[i].qty;
										row.qty_uom = r.message.message[i].qty_uom;
										row.mix_barcode = r.message.message[i].scan_barcode;
									}
									frm.refresh_field('hld_items');
								}
								else{
									frappe.msgprint("No items found in the warehouse "+frm.doc.hld_warehouse);
								}
							}
							else if(r && r.message && r.message.status == "failed"){
								frappe.msgprint(r.message.message);
							}
		                }
		            });
			}
		}
		else{
			frappe.msgprint("Please select the source warehouse");

		}
	},
	"hld_barcode":function(frm){
		if(frm.doc.hld_items){
			scanned_batches = [];
			for(var k=0;k<frm.doc.hld_items.length;k++){
					scanned_batches.push(frm.doc.hld_items[k].mix_barcode)
				}
		}
		if(frm.doc.hld_barcode!="undefined" && frm.doc.hld_barcode!="" ){
			if(scanned_batches.indexOf(frm.doc.hld_barcode)==-1){
					frappe.call({
		                method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.delivery_challan_receipt.delivery_challan_receipt.validate_barcode',
		                args: {
		                    batch_no: frm.doc.hld_barcode,
		                    warehouse:frm.doc.hld_warehouse
		                },
		                freeze: true,
		                callback: function(r) {
		                	if(r.message.status=="Success"){
		                		var st_details = r.message.stock;
		                		var allow_warehouse = 1;
		                		if(frm.doc.hld_warehouse){
		                			if(! (frm.doc.hld_warehouse == st_details[0].warehouse)){
		                				allow_warehouse = 0
		                			}
		                		}
		                		else{
									frm.set_value("hld_warehouse",st_details[0].warehouse);
		                		}
		                		if(allow_warehouse==1){
			                		var row = frappe.model.add_child(frm.doc, "Mixing Center Holding Item", "hld_items");
			                		row.item_code = st_details[0].item_code;
			                		row.item_name = st_details[0].item_name;
			                		row.spp_batch_no = st_details[0].spp_batch_no;
			                		row.batch_no = st_details[0].batch_no;
			                		row.dc_no = st_details[0].dc_no;
			                		row.operation = st_details[0].operation;
			                		row.qty = st_details[0].qty;
			                		row.qty_uom = st_details[0].qty_uom;
			                		row.mix_barcode = st_details[0].scan_barcode;
			                		frm.refresh_field('hld_items');
			                		frm.set_value("hld_barcode","")
			                		scanned_batches.push(st_details[0].scan_barcode)
			                	}
			                	else{
			                		frappe.msgprint("Source Warehouse should same.");

			                	}
		                	}
		                	else{
								frappe.msgprint(r.message.message);
								frm.set_value("hld_barcode","")
		                	}
		                }
		            });
			}
			else{
				frm.set_value("hld_barcode","")
			}

		}
	},
	"hld_manual_barcode":function(frm){
		
		$('input[data-fieldname="hld_manual_barcode"]').change(function(){
		if(frm.doc.hld_manual_barcode!="undefined" && frm.doc.hld_manual_barcode!="" ){
			if(frm.doc.hld_items){
				scanned_batches = [];
				for(var k=0;k<frm.doc.hld_items.length;k++){
						scanned_batches.push(frm.doc.hld_items[k].mix_barcode)
					}
			}
			if(scanned_batches.indexOf(frm.doc.hld_manual_barcode)==-1){
					frappe.call({
		                method: 'shree_polymer_custom_app.shree_polymer_custom_app.doctype.delivery_challan_receipt.delivery_challan_receipt.validate_barcode',
		                args: {
		                    batch_no: frm.doc.hld_manual_barcode,
		                    warehouse:frm.doc.hld_warehouse
		                },
		                freeze: true,
		                callback: function(r) {
		                	if(r.message.status=="Success"){
		                		var st_details = r.message.stock;
		                		var allow_warehouse = 1;
		                		if(frm.doc.hld_warehouse){
		                			if(! (frm.doc.hld_warehouse == st_details[0].warehouse)){
		                				allow_warehouse = 0
		                			}
		                		}
		                		else{
									frm.set_value("hld_warehouse",st_details[0].warehouse);
		                		}
		                		if(allow_warehouse==1){
			                		var row = frappe.model.add_child(frm.doc, "Mixing Center Holding Item", "hld_items");
			                		row.item_code = st_details[0].item_code;
			                		row.item_name = st_details[0].item_name;
			                		row.spp_batch_no = st_details[0].spp_batch_no;
			                		row.batch_no = st_details[0].batch_no;
			                		row.dc_no = st_details[0].dc_no;
			                		row.operation = st_details[0].operation;
			                		row.qty = st_details[0].qty;
			                		row.qty_uom = st_details[0].qty_uom;
			                		row.mix_barcode = st_details[0].scan_barcode;
			                		frm.refresh_field('hld_items');
			                		frm.set_value("hld_manual_barcode","")
			                		scanned_batches.push(st_details[0].scan_barcode)
			                	}
			                	else{
			                		frappe.msgprint("Source Warehouse should same.");

			                	}
		                	}
		                	else{
								frappe.msgprint(r.message.message);
								frm.set_value("hld_manual_barcode","")
		                	}
		                }
		            });
			}
			else{
				frm.set_value("hld_manual_barcode","")
			}

		}
		});
	},

});
