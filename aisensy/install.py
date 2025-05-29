import frappe
from aisensy.app_config import APP_TITLE


def after_install():
    add_app_to_whatsapp_apps()


def add_app_to_whatsapp_apps():
    field = frappe.db.get_list(
        "Custom Field",
        ["*"],
        {"dt": "Notification", "fieldname": "custom_whatsapp_app"},
    )[0]

    if not field.options:
        field.options = ""

    if APP_TITLE not in field.options:
        new_options = field.options + f"\n{APP_TITLE}"
        frappe.db.set_value("Custom Field", field.name, "options", new_options)
        frappe.db.commit()
