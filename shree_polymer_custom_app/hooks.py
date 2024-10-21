from . import __version__ as app_version

app_name = "shree_polymer_custom_app"
app_title = "Shree Polymer Custom App"
app_publisher = "Tridotstech"
app_description = "Shree Polymer Custom App"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@tridotstech.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/shree_polymer_custom_app/css/shree_polymer_custom_app.css"
# app_include_js = "/assets/shree_polymer_custom_app/js/shree_polymer_custom_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/shree_polymer_custom_app/css/shree_polymer_custom_app.css"
# web_include_js = "/assets/shree_polymer_custom_app/js/shree_polymer_custom_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "shree_polymer_custom_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "shree_polymer_custom_app.install.before_install"
# after_install = "shree_polymer_custom_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "shree_polymer_custom_app.uninstall.before_uninstall"
# after_uninstall = "shree_polymer_custom_app.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "shree_polymer_custom_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
fixtures = [
	{
		"doctype": "Stock Entry",
		"filters": [
			["name", "in", [
        	"Stock Entry-sheeting_clip"
			]]
		]
	},
	{
		"doctype": "Quality Inspection",
		"filters": [
			["name", "in", [
        	"Quality Inspection-spp_batch_number",
        	"Quality Inspection-quality_document"
			]]
		]
	},
	{
		"doctype": "Warehouse",
		"filters": [
			["name", "in", [
        	"Warehouse-barcode_section",
        	"Warehouse-barcode",
        	"Warehouse-barcode_text",
        	"Warehouse-customer",
			]]
		]
	},
	{
		"doctype": "Job Card",
		"filters": [
			["name", "in", [
        	"Job Card-moulding","Job Card-press_no","Job Card-operator_code","Job Card-operator_code","Job Card-column_break_72",
			"Job Card-comments","Job Card-batch_code","Job Card-barcode_image_url","Job Card-barcode_text","Job Card-moulding_lot_number",
            "Job Card-total_qty_after_inspection"
			]]
		]
	},
	{
		"doctype": "Stock Entry Detail",
		"filters": [
			["name", "in", [
        	"Stock Entry Detail-deflash_receipt_reference"
			]]
		]
	},
	{
		"doctype": "Delivery Note",
		"filters": [
			["name", "in", [
        	"Delivery Note-operation",
        	"Delivery Note-received_status",
            "Delivery Note-special_instructions",
            "Delivery Note-special_instruction"
			]]
		]
	},
	{
		"doctype": "Delivery Note Item",
		"filters": [
			["name", "in", [
        	"Delivery Note Item-scan_barcode",
        	"Delivery Note Item-spp_batch_no",
        	"Delivery Note Item-is_received",
        	"Delivery Note Item-dc_receipt_no",
        	"Delivery Note Item-dc_receipt_date"
			]]
		]
	},
    {
		"doctype": "Asset",
		"filters": [
			["name", "in", [
        	"Asset-barcode_text","Asset-barcode","Asset-bin_weight"]]
		]
	}

]
doc_events = {
	"Stock Entry": {
		"on_submit": "shree_polymer_custom_app.shree_polymer_custom_app.api.generate_batchwise_report",
		"on_cancel": "shree_polymer_custom_app.shree_polymer_custom_app.api.generate_batchwise_report",
		"on_trash": "shree_polymer_custom_app.shree_polymer_custom_app.api.generate_batchwise_report",
		# "on_update": "shree_polymer_custom_app.shree_polymer_custom_app.api.generate_batchwise_report",
	},
	"Item":{
		"on_update": "shree_polymer_custom_app.shree_polymer_custom_app.api.on_item_update",
	},
	"Batch":{
		"on_update": "shree_polymer_custom_app.shree_polymer_custom_app.api.on_batch_update",
	},
	"Warehouse":{
		"on_update": "shree_polymer_custom_app.shree_polymer_custom_app.api.update_wh_barcode",

	},
	"Employee":{
		"on_update": "shree_polymer_custom_app.shree_polymer_custom_app.api.update_emp_barcode",

	},
	"Job Card":{
		"on_submit":"shree_polymer_custom_app.shree_polymer_custom_app.api.generate_lot_number",
	},
	"Asset":{
		"on_update":"shree_polymer_custom_app.shree_polymer_custom_app.api.update_asset_barcode",
        # "on_update_after_submit":"shree_polymer_custom_app.shree_polymer_custom_app.api.update_asset_barcode"
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"shree_polymer_custom_app.tasks.all"
# 	],
# 	"daily": [
# 		"shree_polymer_custom_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"shree_polymer_custom_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"shree_polymer_custom_app.tasks.weekly"
# 	]
# 	"monthly": [
# 		"shree_polymer_custom_app.tasks.monthly"
# 	]
# 	
	"daily": [
		"shree_polymer_custom_app.shree_polymer_custom_app.api.update_stock_balance",
	]
}

# Testing
# -------

# before_tests = "shree_polymer_custom_app.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "shree_polymer_custom_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "shree_polymer_custom_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"shree_polymer_custom_app.auth.validate"
# ]

# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended only for DocTypes which have limited documents with untranslated names
# For example: Role, Gender, etc.
# translated_search_doctypes = []
