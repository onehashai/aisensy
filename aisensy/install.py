import frappe
from aisensy.app_config import APP_TITLE


def after_install():
    try:
        add_app_to_whatsapp_apps()
    except Exception as e:
        frappe.log_error(f"Error occured after installing {APP_TITLE} app:", e)


def add_app_to_whatsapp_apps():
    if not frappe.db.exists("WhatsApp App", APP_TITLE):
        frappe.get_doc({"doctype": "WhatsApp App", "app_name": APP_TITLE}).insert()
        frappe.db.commit()
