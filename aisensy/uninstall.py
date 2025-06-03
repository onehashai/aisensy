import frappe
from aisensy.app_config import APP_TITLE


def after_uninstall():
    try:
        remove_app_to_whatsapp_apps()
    except Exception as e:
        frappe.log_error(f"Error occured after uninstalling {APP_TITLE} app:", e)


def remove_app_to_whatsapp_apps():
    if frappe.db.exists("WhatsApp App", APP_TITLE):
        frappe.get_doc("WhatsApp App", APP_TITLE).delete()
        frappe.db.commit()
