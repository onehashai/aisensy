import frappe, json
from frappe import _
from frappe.utils import nowdate, add_to_date
from frappe.email.doctype.notification.notification import Notification, get_context


class AisensyNotification(Notification):
    def validate(self):
       self.validate_aisensy_settings()


    def validate_aisensy_settings(self):
        if self.enabled and self.channel == "WhatsApp":
            # Get enabled Aisensy settings
            enabled_settings = self.get_enabled_aisensy_settings()
            if not enabled_settings:
                frappe.throw(_("Please enable at least one Aisensy setting to send WhatsApp messages"))


    def get_enabled_aisensy_settings(self):
        """Get list of enabled Aisensy Settings"""
        try:
            enabled_settings = frappe.get_all(
                "Aisensy Settings",
                filters={"enabled_name": 1},
                fields=["name", "authentication_token", "enabled_name", "username"]
            )
            return enabled_settings
        except Exception as e:
            frappe.log_error(title='Error fetching Aisensy Settings', message=str(e))
            return []


    def get_active_aisensy_setting(self):
        """Get the first active Aisensy setting"""
        enabled_settings = self.get_enabled_aisensy_settings()
        if enabled_settings:
            # Return the first enabled setting, or you can add logic to select specific one
            return frappe.get_doc("Aisensy Settings", enabled_settings[0].name)
        return None


    def send(self, doc):
        context = get_context(doc)
        context = {"doc": doc, "alert": self, "comments": None}
        if doc.get("_comments"):
            context["comments"] = json.loads(doc.get("_comments"))


        if self.is_standard:
            self.load_standard_properties(context)


        try:
            if self.channel == 'WhatsApp':
                self.send_whatsapp_msg(doc, context)
        except Exception as e:
            frappe.log_error(title='Failed to send Aisensy notification', message=frappe.get_traceback())


        super(AisensyNotification, self).send(doc)


    def send_whatsapp_msg(self, doc, context):
        aisensy_campaign = self.whatsapp_template


        if not aisensy_campaign:
            frappe.msgprint(_("Please select an Aisensy Campaign"))
            return


        campaign = frappe.get_doc("Aisensy Campaign", aisensy_campaign)
        template_parameters = frappe.render_template(self.message, context)


        try:
            params = json.loads(template_parameters) if template_parameters else {}
        except json.JSONDecodeError:
            frappe.throw(_("Invalid JSON format in message parameters"))


        # Handle print format attachments
        for k, v in params.items():
            if v and str(v).strip().lower() in ["print_format", "print format"] and self.attach_print and self.print_format:
                url = frappe.utils.get_url() + "/" + doc.doctype + "/" + doc.name + "?format=" + self.print_format + "&key=" + doc.get_signature()
                params[k] = url


        # Send message using Aisensy
        self.send_aisensy_message(
            doc=doc,
            whatsapp_numbers=self.get_receiver_list(doc, context),
            campaign=campaign,
            template_parameters=params
        )




    def send_aisensy_message(self, doc, whatsapp_numbers, campaign, template_parameters):
        """Send WhatsApp message through Aisensy API"""
        try:
            # Get active Aisensy settings
            aisensy_settings = self.get_active_aisensy_setting()
            if not aisensy_settings:
                frappe.throw(_("No enabled Aisensy settings found"))


            api_key = aisensy_settings.authentication_token
            if not api_key:
                frappe.throw(_("Aisensy API key not found in enabled settings"))


            # Prepare message data
            message_data = self.prepare_message_data(doc, api_key, campaign, template_parameters, whatsapp_numbers)
            
            # Make API call to Aisensy
            response = self.make_aisensy_api_call(message_data)
            
            # Log the message
            self.log_aisensy_message(campaign.campaign_name, whatsapp_numbers, doc.doctype + "/" + doc.name, response)
            
        except Exception as e:
            frappe.log_error(title='Aisensy API Error', message=str(e))
            frappe.throw(_("Failed to send WhatsApp message: {0}").format(str(e)))


    def prepare_message_data(self, doc, api_key, campaign, template_parameters, whatsapp_numbers):
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


        parameters = sorted(self.whatsapp_parameter, key=lambda x: x.parameter)


        for param in parameters:
            fieldvalue = param.field_value
            template_params_list.append(doc.get(fieldvalue))

        frappe.log_error("Template Parameters List: ", template_params_list)

        enabled_settings = self.get_enabled_aisensy_settings()
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
            "attributes": {}
        }
        frappe.log_error("Message Data: ", message_data)
        
        # Add paramsFallbackValue if template parameters exist
        if template_parameters:
            message_data["paramsFallbackValue"] = template_parameters
        
        # Handle media based on campaign template type
        if hasattr(campaign, 'template_type') and campaign.template_type:
            if campaign.template_type.upper() in ["IMAGE", "VIDEO", "FILE"] and hasattr(campaign, 'url') and campaign.url:
                message_data["media"] = {
                    "url": campaign.url
                }
                if hasattr(campaign, 'file_name') and campaign.file_name:
                    message_data["media"]["filename"] = campaign.file_name


        # Handle buttons if campaign has button configuration
        if hasattr(campaign, 'buttons') and campaign.buttons:
            try:
                if isinstance(campaign.buttons, str):
                    message_data["buttons"] = json.loads(campaign.buttons)
                elif isinstance(campaign.buttons, list):
                    message_data["buttons"] = campaign.buttons
            except (json.JSONDecodeError, TypeError):
                frappe.log_error('Invalid buttons format in campaign', campaign.buttons)


        # Handle carousel cards if campaign has carousel configuration
        if hasattr(campaign, 'carousel_cards') and campaign.carousel_cards:
            try:
                if isinstance(campaign.carousel_cards, str):
                    message_data["carouselCards"] = json.loads(campaign.carousel_cards)
                elif isinstance(campaign.carousel_cards, list):
                    message_data["carouselCards"] = campaign.carousel_cards
            except (json.JSONDecodeError, TypeError):
                frappe.log_error('Invalid carousel cards format in campaign', campaign.carousel_cards)


        # Handle location if campaign has location data
        if hasattr(campaign, 'location') and campaign.location:
            try:
                if isinstance(campaign.location, str):
                    message_data["location"] = json.loads(campaign.location)
                elif isinstance(campaign.location, dict):
                    message_data["location"] = campaign.location
            except (json.JSONDecodeError, TypeError):
                frappe.log_error('Invalid location format in campaign', campaign.location)


        return message_data


    def make_aisensy_api_call(self, message_data):
        """Make API call to Aisensy"""
        import requests
        
        headers = {
            "Content-Type": "application/json"
            # Note: No Authorization header needed as apiKey is in the body
        }
        
        # Aisensy API endpoint
        api_url = "https://backend.aisensy.com/campaign/t1/api/v2"


        response = requests.post(
            api_url,
            headers=headers,
            json=message_data,
            timeout=30
        )
        
        if response.status_code != 200:
            frappe.throw(_("Aisensy API Error: {0}").format(response.text))
            
        return response.json()


    def log_aisensy_message(self, campaign_name, numbers, triggered_from, response):
        """Log the Aisensy message"""
        try:
            valid_numbers = []
            invalid_numbers = []
            
            if isinstance(numbers, list):
                valid_numbers = numbers
            else:
                valid_numbers = [numbers]


            response_status = "Success"
            if isinstance(response, dict) and response.get('error'):
                response_status = f"Error: {response.get('error')}"


            # Create log entry
            log_doc = frappe.get_doc({
                "doctype": "Aisensy Message Logs",
                "campaign_name": campaign_name,
                "valid_numbers": "\n".join([str(num) for num in valid_numbers]),
                "invalid_numbers": "\n".join([str(num) for num in invalid_numbers]),
                "triggered_from": triggered_from,
                "status": response_status,
                "created_at": frappe.utils.now(),
                "response_message": json.dumps(response, indent=2)
            })
            log_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(title='Failed to log Aisensy message', message=str(e))