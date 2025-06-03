import frappe
import json
from aisensy.app_config import APP_TITLE
from frappe.email.doctype.notification.notification import get_context
from frappe import utils, _


def aisensy_validate(notification_doc):
    if (
        notification_doc.enabled
        and notification_doc.channel == "WhatsApp"
        and notification_doc.custom_whatsapp_app == APP_TITLE
    ):
        # Get enabled Aisensy settings
        enabled_settings = aisensy_get_enabled_settings()
        if not enabled_settings:
            frappe.throw(
                _(
                    "Please enable at least one Aisensy setting to send WhatsApp messages"
                )
            )


def aisensy_send(notification_doc, doc):
    context = get_context(doc)
    context = {"doc": doc, "alert": notification_doc, "comments": None}
    if doc.get("_comments"):
        context["comments"] = json.loads(doc.get("_comments"))

    if notification_doc.is_standard:
        notification_doc.load_standard_properties(context)

    try:
        if (
            notification_doc.channel == "WhatsApp"
            and notification_doc.custom_whatsapp_app == APP_TITLE
        ):
            aisensy_send_whatsapp_msg(notification_doc, doc, context)
    except Exception as e:
        frappe.log_error(
            title="Failed to send Aisensy notification",
            message=frappe.get_traceback(),
        )


def aisensy_send_whatsapp_msg(notification_doc, doc, context):
    aisensy_campaign = notification_doc.aisensy_whatsapp_template

    if not aisensy_campaign:
        frappe.msgprint(_("Please select an Aisensy Campaign"))
        return

    campaign = frappe.get_doc("Aisensy Campaign", aisensy_campaign)
    template_parameters = frappe.render_template(notification_doc.message, context)

    try:
        params = json.loads(template_parameters) if template_parameters else {}
    except json.JSONDecodeError:
        frappe.throw(_("Invalid JSON format in message parameters"))

    # Handle print format attachments
    for k, v in params.items():
        if (
            v
            and str(v).strip().lower() in ["print_format", "print format"]
            and notification_doc.attach_print
            and notification_doc.print_format
        ):
            url = (
                utils.get_url()
                + "/"
                + doc.doctype
                + "/"
                + doc.name
                + "?format="
                + notification_doc.print_format
                + "&key="
                + doc.get_signature()
            )
            params[k] = url

    # Send message using Aisensy
    aisensy_send_message(
        notification_doc,
        doc=doc,
        whatsapp_numbers=notification_doc.get_receiver_list(doc, context),
        campaign=campaign,
        template_parameters=params,
    )


def aisensy_send_message(
    notification_doc, doc, whatsapp_numbers, campaign, template_parameters
):
    """Send WhatsApp message through Aisensy API"""
    try:
        # Get active Aisensy settings
        aisensy_settings = aisensy_get_active_setting()
        if not aisensy_settings:
            frappe.throw(_("No enabled Aisensy settings found"))

        api_key = aisensy_settings.authentication_token
        if not api_key:
            frappe.throw(_("Aisensy API key not found in enabled settings"))

        # Prepare message data
        message_data = aisensy_prepare_message_data(
            notification_doc,
            doc,
            api_key,
            campaign,
            template_parameters,
            whatsapp_numbers,
        )

        # Make API call to Aisensy
        response = aisensy_make_api_call(message_data)

        # Log the message
        aisensy_log_message(
            campaign.campaign_name,
            whatsapp_numbers,
            doc.doctype + "/" + doc.name,
            response,
        )

    except Exception as e:
        frappe.log_error(title="Aisensy API Error", message=str(e))
        frappe.throw(_("Failed to send WhatsApp message: {0}").format(str(e)))


def aisensy_prepare_message_data(
    notification_doc, doc, api_key, campaign, template_parameters, whatsapp_numbers
):
    """Prepare message data for Aisensy API matching the curl format"""

    # Convert single number to string, multiple numbers to comma-separated string
    if isinstance(whatsapp_numbers, list):
        if len(whatsapp_numbers) == 1:
            destination = str(whatsapp_numbers[0])
        else:
            destination = ",".join([str(num) for num in whatsapp_numbers])
    else:
        destination = str(whatsapp_numbers)

    # Prepare template parameters as a list of values
    template_params_list = []

    parameters = sorted(
        notification_doc.aisensy_whatsapp_parameter, key=lambda x: x.parameter
    )

    for param in parameters:
        fieldvalue = param.field_value
        template_params_list.append(doc.get(fieldvalue))

    frappe.log_error("Template Parameters List: ", template_params_list)

    enabled_settings = aisensy_get_enabled_settings()
    get_username = frappe.get_doc("Aisensy Settings", enabled_settings[0].name)
    user_name = get_username.username

    # Base message data structure matching the curl example
    message_data = {
        "apiKey": api_key,
        "campaignName": campaign.campaign_name,
        "destination": destination,
        "userName": user_name,
        "templateParams": template_params_list,
        "source": "frappe-notification",
        "media": {},
        "buttons": [],
        "carouselCards": [],
        "location": {},
        "attributes": {},
    }
    frappe.log_error("Message Data: ", message_data)

    # Add paramsFallbackValue if template parameters exist
    if template_parameters:
        message_data["paramsFallbackValue"] = template_parameters

    # Handle media based on campaign template type
    if hasattr(campaign, "template_type") and campaign.template_type:
        if (
            campaign.template_type.upper() in ["IMAGE", "VIDEO", "FILE"]
            and hasattr(campaign, "url")
            and campaign.url
        ):
            message_data["media"] = {"url": campaign.url}
            if hasattr(campaign, "file_name") and campaign.file_name:
                message_data["media"]["filename"] = campaign.file_name

    # Handle buttons if campaign has button configuration
    if hasattr(campaign, "buttons") and campaign.buttons:
        try:
            if isinstance(campaign.buttons, str):
                message_data["buttons"] = json.loads(campaign.buttons)
            elif isinstance(campaign.buttons, list):
                message_data["buttons"] = campaign.buttons
        except (json.JSONDecodeError, TypeError):
            frappe.log_error("Invalid buttons format in campaign", campaign.buttons)

    # Handle carousel cards if campaign has carousel configuration
    if hasattr(campaign, "carousel_cards") and campaign.carousel_cards:
        try:
            if isinstance(campaign.carousel_cards, str):
                message_data["carouselCards"] = json.loads(campaign.carousel_cards)
            elif isinstance(campaign.carousel_cards, list):
                message_data["carouselCards"] = campaign.carousel_cards
        except (json.JSONDecodeError, TypeError):
            frappe.log_error(
                "Invalid carousel cards format in campaign", campaign.carousel_cards
            )

    # Handle location if campaign has location data
    if hasattr(campaign, "location") and campaign.location:
        try:
            if isinstance(campaign.location, str):
                message_data["location"] = json.loads(campaign.location)
            elif isinstance(campaign.location, dict):
                message_data["location"] = campaign.location
        except (json.JSONDecodeError, TypeError):
            frappe.log_error("Invalid location format in campaign", campaign.location)

    if getattr(notification_doc, "attach_print", False) and getattr(
        notification_doc, "print_format", None
    ):
        try:
            pdf_content = frappe.get_print(
                doc.doctype,
                doc.name,
                print_format=notification_doc.print_format,
                as_pdf=True,
            )
            filename = f"{doc.name}.pdf"

            file_doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": filename,
                    "is_private": 0,
                    "content": pdf_content,
                }
            )
            file_doc.save(ignore_permissions=True)
            public_url = file_doc.file_url
            full_url = utils.get_url(public_url)

            message_data["media"] = {"url": full_url, "filename": filename}
            frappe.log_error("PDF attached to WhatsApp message", full_url)
        except Exception as e:
            frappe.log_error("Failed to attach print PDF", str(e))
    return message_data


def aisensy_make_api_call(message_data):
    """Make API call to Aisensy"""
    import requests

    headers = {
        "Content-Type": "application/json"
        # Note: No Authorization header needed as apiKey is in the body
    }

    # Aisensy API endpoint
    api_url = "https://backend.aisensy.com/campaign/t1/api/v2"

    response = requests.post(api_url, headers=headers, json=message_data, timeout=30)

    if response.status_code != 200:
        frappe.throw(_("Aisensy API Error: {0}").format(response.text))

    return response.json()


def aisensy_get_enabled_settings():
    """Get list of enabled Aisensy Settings"""
    try:
        enabled_settings = frappe.get_all(
            "Aisensy Settings",
            filters={"enabled_name": 1},
            fields=["name", "authentication_token", "enabled_name", "username"],
        )
        return enabled_settings
    except Exception as e:
        frappe.log_error(title="Error fetching Aisensy Settings", message=str(e))
        return []


def aisensy_get_active_setting():
    """Get the first active Aisensy setting"""
    enabled_settings = aisensy_get_enabled_settings()
    if enabled_settings:
        # Return the first enabled setting, or you can add logic to select specific one
        return frappe.get_doc("Aisensy Settings", enabled_settings[0].name)
    return None


def aisensy_log_message(campaign_name, numbers, triggered_from, response):
    """Log the Aisensy message"""
    try:
        valid_numbers = []
        invalid_numbers = []

        if isinstance(numbers, list):
            valid_numbers = numbers
        else:
            valid_numbers = [numbers]

        response_status = "Success"
        if isinstance(response, dict) and response.get("error"):
            response_status = f"Error: {response.get('error')}"

        # Create log entry
        log_doc = frappe.get_doc(
            {
                "doctype": "Aisensy Message Logs",
                "campaign_name": campaign_name,
                "valid_numbers": "\n".join([str(num) for num in valid_numbers]),
                "invalid_numbers": "\n".join([str(num) for num in invalid_numbers]),
                "triggered_from": triggered_from,
                "status": response_status,
                "created_at": utils.now(),
                "response_message": json.dumps(response, indent=2),
            }
        )
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()

    except Exception as e:
        frappe.log_error(title="Failed to log Aisensy message", message=str(e))
