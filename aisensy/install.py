import frappe
from aisensy.app_config import APP_TITLE


def after_install():
    try:
        add_app_to_whatsapp_apps()
        add_custom_fields_to_notification()
    except Exception as e:
        frappe.log_error(f"Error occured after installing {APP_TITLE} app:", e)


def add_app_to_whatsapp_apps():
    try:
        field = frappe.db.get_list(
            "Custom Field",
            ["*"],
            {"dt": "Notification", "fieldname": "custom_whatsapp_app"},
        )[0]

        options = field.get("options", "").split("\n")

        if APP_TITLE not in options:
            options.append(APP_TITLE)
            frappe.db.set_value(
                "Custom Field", field.name, "options", "\n".join(options)
            )
            frappe.db.commit()
    except IndexError:
        raise Exception("Notification field custom_whatsapp_app not present.")


def add_custom_fields_to_notification():
    custom_fields = [
        {
            "depends_on": 'eval: (doc.channel == "WhatsApp") && (doc.custom_whatsapp_app == "Aisensy")',
            "description": "Preffered to use pre-approved template.",
            "dt": "Notification",
            "fieldname": "aisensy_whatsapp_template",
            "fieldtype": "Link",
            "insert_after": "custom_whatsapp_app",
            "label": "WhatsApp Template",
            "mandatory_depends_on": 'eval: (doc.channel == "WhatsApp") && (doc.custom_whatsapp_app == "Aisensy")',
            "module": "Aisensy",
            "name": "Notification-aisensy_whatsapp_template",
            "options": "Aisensy Campaign",
        },
        {
            "depends_on": 'eval: (doc.custom_whatsapp_app == "Aisensy") && doc.aisensy_whatsapp_template',
            "dt": "Notification",
            "fieldname": "aisensy_map_fields",
            "fieldtype": "Button",
            "insert_after": "send_to_all_assignees",
            "label": "Map Fields",
            "module": "Aisensy",
            "name": "Notification-aisensy_map_fields",
        },
        {
            "depends_on": 'eval: (doc.channel == "WhatsApp") && (doc.custom_whatsapp_app == "Aisensy")',
            "dt": "Notification",
            "fieldname": "aisensy_whatsapp_parameter",
            "fieldtype": "Table",
            "insert_after": "recipients",
            "label": "WhatsApp Parameter",
            "module": "Aisensy",
            "name": "Notification-aisensy_whatsapp_parameter",
            "options": "WhatsApp Parameter",
        },
        {
            "dt": "Notification",
            "fieldname": "trigger_for_bill_to_contact",
            "fieldtype": "Check",
            "label": "Trigger for Bill To Contact",
            "module": "Aisensy",
            "name": "Notification-trigger_for_bill_to_contact",
            "insert_after": "module",
        },
        {
            "dt": "Notification",
            "fieldname": "trigger_for_standard_contact",
            "fieldtype": "Check",
            "label": "Trigger for Standard Contact",
            "module": "Aisensy",
            "name": "Notification-trigger_for_standard_contact",
            "insert_after": "trigger_for_bill_to_contact",
        },
    ]

    for field in custom_fields:
        if not frappe.db.exists(
            "Custom Field", {"dt": "Notification", "fieldname": field["fieldname"]}
        ):
            new_field = frappe.get_doc({"doctype": "Custom Field", **field})
            new_field.insert()
            frappe.db.commit()
