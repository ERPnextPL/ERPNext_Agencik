from . import __version__ as app_version

app_name = "agencik"
app_title = "Agencik"
app_publisher = "Jan"
app_description = "app"
app_email = "swiatek-jan@wp.pl"
app_license = "mit"

# def before_insert(doc, method):
#     if doc.doctype == "add_creater_policy":
#         doc.user = frappe.session.user



doc_events = {
    "Sales Person": {
        "before_insert": "agencik.overrides.add_creater_policy.before_insert",
        "before_save": "agencik.overrides.add_creater_policy.before_save",
        "set_current_user": "agencik.overrides.add_creater_policy.set_current_user",
        "validate": "agencik.overrides.sales_person_controller.validate_item"
    },
    "Insurance Policy": {
        # "validate": "agencik.overrides.walidation_company_number.length_company",
        "validate": "agencik.policy.doctype.insurance_policy.insurance_policy_controller.length_company",
        # "after_insert": "agencik.policy.doctype.insurance_policy.insurance_policy.after_insert",
        # "on_update": "agencik.policy.doctype.insurance_policy.insurance_policy.on_update",
        # "on_trash": "agencik.policy.idoctype.nsurance_policy.policy_ocr.on_policy_trash",
    }


}

# permission_query_conditions = {
#     "Insurance Policy": "agencik.policy.doctype.insurance_policy.policy_ocr.get_permission_query_conditions",
# }
fixtures = [
    {"dt": "Client Script", "filters": [["name", "in", ["Insurance Policy"]]]},
]

doctype_js = {
    "Insurance Policy": "doctype/insurance_policy/insurance_policy.js"
}




# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "agencik",
# 		"logo": "/assets/agencik/logo.png",
# 		"title": "Agencik",
# 		"route": "/agencik",
# 		"has_permission": "agencik.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/agencik/css/agencik.css"
# app_include_js = "/assets/agencik/js/agencik.js"

# include js, css files in header of web template
# web_include_css = "/assets/agencik/css/agencik.css"
# web_include_js = "/assets/agencik/js/agencik.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "agencik/public/scss/website"

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

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "agencik/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "agencik.utils.jinja_methods",
# 	"filters": "agencik.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "agencik.install.before_install"
# after_install = "agencik.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "agencik.uninstall.before_uninstall"
# after_uninstall = "agencik.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "agencik.utils.before_app_install"
# after_app_install = "agencik.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "agencik.utils.before_app_uninstall"
# after_app_uninstall = "agencik.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "agencik.notifications.get_notification_config"

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

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"agencik.tasks.all"
# 	],
# 	"daily": [
# 		"agencik.tasks.daily"
# 	],
# 	"hourly": [
# 		"agencik.tasks.hourly"
# 	],
# 	"weekly": [
# 		"agencik.tasks.weekly"
# 	],
# 	"monthly": [
# 		"agencik.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "agencik.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "agencik.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "agencik.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["agencik.utils.before_request"]
# after_request = ["agencik.utils.after_request"]

# Job Events
# ----------
# before_job = ["agencik.utils.before_job"]
# after_job = ["agencik.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"agencik.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

