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
        enabled_settings = aisensy_get_enabled_settings()
        if not enabled_settings:
            frappe.throw(
                _(
                    "Please enable at least one Aisensy setting to send WhatsApp messages"
                )
            )


def aisensy_send(notification_doc, doc):
    context = get_context(doc)
    campaign = notification_doc.aisensy_whatsapp_template
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
            whatsapp_numbers = get_whatsapp_numbers_based_on_trigger(notification_doc, doc, context)
            
            aisensy_send_message(
                notification_doc,
                doc,
                whatsapp_numbers,
                campaign,
            )
    except Exception as e:
        frappe.log_error(
            title="Failed to send Aisensy notification",
            message=frappe.get_traceback(),
        )


def get_whatsapp_numbers_based_on_trigger(notification_doc, doc, context):
    """Get WhatsApp numbers based on trigger conditions"""
    try:
        trigger_for_bill_to_contact = getattr(notification_doc, 'trigger_for_bill_to_contact', 0)
        trigger_for_standard_contact = getattr(notification_doc, 'trigger_for_standard_contact', 0)
        
        whatsapp_numbers = []
        
        if trigger_for_bill_to_contact:
            bill_to_numbers = get_phone_from_customer_address(doc, 'customer_address')
            if bill_to_numbers:
                whatsapp_numbers.extend(bill_to_numbers)
        
        if trigger_for_standard_contact:
            standard_numbers = get_phone_from_customer_address(doc, 'customer_address')
            if standard_numbers:
                whatsapp_numbers.extend(standard_numbers)
        
        if not whatsapp_numbers or (not trigger_for_bill_to_contact and not trigger_for_standard_contact):
            whatsapp_numbers = notification_doc.get_receiver_list(doc, context)
        
        unique_numbers = []
        seen = set()
        for num in whatsapp_numbers:
            if num not in seen:
                unique_numbers.append(num)
                seen.add(num)
        
        return unique_numbers
        
    except Exception as e:
        frappe.log_error(
            title="Error getting WhatsApp numbers based on trigger",
            message=f"Document: {doc.doctype}/{doc.name}, Error: {str(e)}"
        )
        return notification_doc.get_receiver_list(doc, context)


def get_phone_from_customer_address(doc, address_field):
    """Get phone numbers from customer address"""
    phone_numbers = []
    
    try:
        address_name = doc.get(address_field)
        
        if not address_name:
            frappe.log_error(
                title="Address field not found",
                message=f"Field '{address_field}' not found in document {doc.doctype}/{doc.name}"
            )
            return phone_numbers
        
        address_doc = frappe.get_doc("Address", address_name)
        
        phone_fields = ['phone', 'mobile_no', 'fax']
        
        for field in phone_fields:
            phone_value = address_doc.get(field)
            if phone_value:
                cleaned_phone = clean_phone_number(phone_value)
                if cleaned_phone:
                    phone_numbers.append(cleaned_phone)
        
        if phone_numbers:
            frappe.logger().info(f"Found phone numbers from {address_field}: {phone_numbers}")
        else:
            frappe.log_error(
                title="No phone numbers found in address",
                message=f"Address: {address_name}, Document: {doc.doctype}/{doc.name}"
            )
            
    except frappe.DoesNotExistError:
        frappe.log_error(
            title="Address not found",
            message=f"Address '{address_name}' not found for document {doc.doctype}/{doc.name}"
        )
    except Exception as e:
        frappe.log_error(
            title="Error fetching phone from address",
            message=f"Address: {address_name}, Document: {doc.doctype}/{doc.name}, Error: {str(e)}"
        )
    
    return phone_numbers


def clean_phone_number(phone):
    """Clean and validate phone number - handles space-separated formats"""
    if not phone:
        return None
    
    import re
    
    phone_str = str(phone).strip()
    
    cleaned = re.sub(r'[\s\-\.\(\)\[\]]+', '', phone_str)
    cleaned = re.sub(r'[^\d+]', '', cleaned)
    digits_only = re.sub(r'[^\d]', '', cleaned)
    
    if len(digits_only) < 10:
        return None
    
    if cleaned.startswith('+'):
        if len(digits_only) >= 10:
            return cleaned
        else:
            return None
    else:
        if len(digits_only) == 10:
            cleaned = '+91' + digits_only
        elif len(digits_only) == 11:
            if digits_only.startswith('0'):
                cleaned = '+91' + digits_only[1:]
            else:
                cleaned = '+91' + digits_only
        elif len(digits_only) == 12:
            if digits_only.startswith('91'):
                cleaned = '+' + digits_only
            else:
                cleaned = '+91' + digits_only
        elif len(digits_only) == 13:
            if digits_only.startswith('91'):
                cleaned = '+' + digits_only[:12]
            else:
                cleaned = '+91' + digits_only[:10]
        else:
            if len(digits_only) > 13:
                cleaned = '+91' + digits_only[:10]
            else:
                cleaned = '+91' + digits_only
    
    final_digits = re.sub(r'[^\d]', '', cleaned)
    if len(final_digits) < 12:
        return None
    
    return cleaned


def aisensy_send_message(notification_doc, doc, whatsapp_numbers, campaign):
    """Send WhatsApp message through Aisensy API"""
    try:
        if not whatsapp_numbers:
            frappe.msgprint(
                _(
                    "Cannot trigger WhatsApp notification as no contact number is available."
                ).format(doc.doctype, doc.name),
                title=_("WhatsApp Notification Skipped"),
                indicator="orange"
            )
            return
        
        aisensy_settings = aisensy_get_active_setting()
        if not aisensy_settings:
            frappe.throw(_("No enabled Aisensy settings found"))

        api_key = aisensy_settings.authentication_token
        if not api_key:
            frappe.throw(_("Aisensy API key not found in enabled settings"))

        message_data = aisensy_prepare_message_data(
            notification_doc,
            doc,
            api_key,
            campaign,
            whatsapp_numbers,
        )

        response = aisensy_make_api_call(message_data)

        aisensy_log_message(
            campaign,
            whatsapp_numbers,
            doc.doctype + "/" + doc.name,
            response,
        )

    except Exception as e:
        frappe.log_error(title="Aisensy API Error", message=str(e))
        frappe.throw(_("Failed to send WhatsApp message: {0}").format(str(e)))


def aisensy_prepare_message_data(
    notification_doc, doc, api_key, campaign, whatsapp_numbers
):
    """Prepare message data for Aisensy API"""

    if isinstance(whatsapp_numbers, list):
        if len(whatsapp_numbers) == 1:
            destination = str(whatsapp_numbers[0])
        else:
            destination = ",".join([str(num) for num in whatsapp_numbers])
    else:
        destination = str(whatsapp_numbers)

    template_params_list = []

    parameters = sorted(
        notification_doc.aisensy_whatsapp_parameter, key=lambda x: x.parameter
    )

    for param in parameters:
        fieldvalue = param.field_value
        field_data = doc.get(fieldvalue)
        
        # Convert all template parameters to strings
        if field_data is None:
            template_params_list.append("")  # Convert None to empty string
        elif isinstance(field_data, (int, float)):
            template_params_list.append(sanitize_param_text(field_data))
        elif isinstance(field_data, (list, dict)):
            template_params_list.append(json.dumps(field_data))
        else:
            template_params_list.append(sanitize_param_text(field_data))

    enabled_settings = aisensy_get_enabled_settings()
    get_username = frappe.get_doc("Aisensy Settings", enabled_settings[0].name)
    user_name = get_username.username

    message_data = {
        "apiKey": api_key,
        "campaignName": campaign,
        "destination": destination,
        "userName": user_name,
        "templateParams": template_params_list,
        "source": "OneHash-notification",
        "media": {},
        "buttons": [],
        "carouselCards": [],
        "location": {},
        "attributes": {},
    }

    if hasattr(campaign, "template_type") and campaign.template_type:
        if (
            campaign.template_type.upper() in ["IMAGE", "VIDEO", "FILE"]
            and hasattr(campaign, "url")
            and campaign.url
        ):
            message_data["media"] = {"url": campaign.url}
            if hasattr(campaign, "file_name") and campaign.file_name:
                message_data["media"]["filename"] = campaign.file_name

    if hasattr(campaign, "buttons") and campaign.buttons:
        try:
            if isinstance(campaign.buttons, str):
                message_data["buttons"] = json.loads(campaign.buttons)
            elif isinstance(campaign.buttons, list):
                message_data["buttons"] = campaign.buttons
        except (json.JSONDecodeError, TypeError):
            frappe.log_error(
                title="Invalid buttons format in campaign",
                message=f"Campaign: {campaign}, Buttons: {campaign.buttons}"
            )

    if hasattr(campaign, "carousel_cards") and campaign.carousel_cards:
        try:
            if isinstance(campaign.carousel_cards, str):
                message_data["carouselCards"] = json.loads(campaign.carousel_cards)
            elif isinstance(campaign.carousel_cards, list):
                message_data["carouselCards"] = campaign.carousel_cards
        except (json.JSONDecodeError, TypeError):
            frappe.log_error(
                title="Invalid carousel cards format in campaign",
                message=f"Campaign: {campaign}, Carousel cards: {campaign.carousel_cards}"
            )

    if hasattr(campaign, "location") and campaign.location:
        try:
            if isinstance(campaign.location, str):
                message_data["location"] = json.loads(campaign.location)
            elif isinstance(campaign.location, dict):
                message_data["location"] = campaign.location
        except (json.JSONDecodeError, TypeError):
            frappe.log_error(
                title="Invalid location format in campaign",
                message=f"Campaign: {campaign}, Location: {campaign.location}"
            )

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
        except Exception as e:
            frappe.log_error(title="Failed to attach print PDF", message=str(e))
    
    return message_data

def sanitize_param_text(text):
    if not text:
        return ""
    # Remove new-line and tab characters
    text = re.sub(r'[\n\t]', ' ', str(text))
    # Collapse more than 4 spaces to a single space
    text = re.sub(r' {5,}', ' ', text)
    return text.strip()


def aisensy_make_api_call(message_data):
    """Make API call to Aisensy"""
    import requests

    headers = {"Content-Type": "application/json"}
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