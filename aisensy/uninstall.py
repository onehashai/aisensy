import frappe
from aisensy.app_config import APP_TITLE


def after_uninstall():
    try:
        remove_app_to_whatsapp_apps()
    except Exception as e:
        frappe.log_error(f"Error occured after uninstalling {APP_TITLE} app:", e)


def remove_app_to_whatsapp_apps():
    try:
        field = frappe.db.get_list(
            "Custom Field",
            ["*"],
            {"dt": "Notification", "fieldname": "custom_whatsapp_app"},
        )[0]

        options = field.options.split("\n")
        if APP_TITLE in options:
            new_options = [option for option in options if option != APP_TITLE]
            frappe.db.set_value(
                "Custom Field", field.name, "options", "\n".join(new_options)
            )
            frappe.db.commit()
    except IndexError:
        raise Exception("Clientside app is not installed.")
