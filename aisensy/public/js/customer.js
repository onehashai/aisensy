var html;

frappe.ui.form.on('Customer', {
    
    refresh: async function (frm) {
        // var cas=await frappe.db.count('Aisensy Settings', {'enabled_name': 1})
        // let aisensy_enabled_name = await frappe.db.get_single_value('Aisensy Settings', 'enabled_name');
        
        // console.log(cas)
        // if (cas>0) {
            
            frm.add_custom_button("Send Whatsapp Message", async function () {
                whatsapp_dialog(frm)
           }, __('<img src="https://aisensy.wpenginepowered.com/wp-content/uploads/2021/02/Untitled.png" height="35px" width="60px">'));
            
            frm.add_custom_button(__('Get Whatsapp Logs'), function () {
                frappe.set_route('List', 'Aisensy Message Logs', { });
            }, __('<img src="https://aisensy.wpenginepowered.com/wp-content/uploads/2021/02/Untitled.png" height="35px" width="60px">'));

            
        // }

    }
    
    
//--------------------------------------------------------------------------------------------
});

//
async function whatsapp_dialog(frm){

    var temp = frm.doc;
        var mobileNumbers = [];
        var mobileNumber=''
        for (var prop in temp) {
        if (frappe.meta.has_field(frm.doc.doctype, prop) && frappe.meta.get_field(frm.doc.doctype, prop).options === 'Phone'){
            // console.log(temp[prop])
            
            if((temp[prop]).length===10)
            {
                mobileNumber = '+91'+temp[prop];
            }
            else if((temp[prop]).length===12){
                mobileNumber = '+'+temp[prop];
            }
            else {
                mobileNumber = temp[prop];
            }
            if (!mobileNumbers.includes(mobileNumber)) {
                
                    await mobileNumbers.push(mobileNumber)
                
            }
        }
        }
        
        var lname=await frm.doc.first_name ? await frm.doc.first_name: await frm.doc.customer_name;

        let d = new frappe.ui.Dialog({
            'title': 'Send Message',
            'fields': [
                {
                    'fieldname': 'select_account',
                    'label': 'Select Account',
                    'fieldtype': 'Link',
                    'reqd': 1,
                    'options':'Aisensy Settings',
                    'get_query': function() {
                        return {
                            'filters': [
                                ['Aisensy Settings', 'enabled_name', '=', 1]
                            ]
                        };
                    }
                },
                {
                    'fieldname': 'customer_name',
                    'label': 'Customer Name',
                    'fieldtype': 'Data',
                    'reqd': 1,
                    'default': lname,
                },
                {
                    'fieldname': 'customer_numbers',
                    'label': 'Customer Number',
                    'fieldtype': 'MultiSelect',
                    'options': mobileNumbers,
                    'reqd': 1,
                    'description': 'Format: +917888187242, +17888187242,',
                },
                // {
                //     'fieldname': 'lead_source',
                //     'label': 'Source of Lead',
                //     'fieldtype': 'Data',
                //     'reqd': 0,
                // },
                
                {
                    'fieldname': 'campaign_name',
                    'label': 'Campaign Name',
                    'fieldtype': 'Link',
                    'options': 'Aisensy Campaign',
                    'reqd': 1,
                    'onchange': async function(dialog){
                        let save=this;
                       
                        await frappe.call({
                            method: 'frappe.client.get',
                            args: {
                                doctype: 'Aisensy Campaign',
                                filters: { 'name': this.value }
                            },
                            callback: function (r) {
                                // console.log("Response from frappe.call:", r);
                        
                                if (r && r.message && typeof r.message === 'object') {
                                    var campaign = r.message;
                                    // console.log(campaign);
                                    var template_format = campaign.template_format;
                                    var template_footer = campaign.template_footer;
                                    d.set_value('template_message', template_format + template_footer);
                                    d.set_value('no_of_template_params', campaign.no_of_template_params);
                                    d.set_value('template_type',campaign.template_type);
                                    d.set_value('file_name',campaign.file_name);
                                    d.set_value('url',campaign.url);
                                    var options = [];
                                    for (var i = 1; i <= campaign.no_of_template_params; i++) {
                                        options.push('{{'+i.toString()+'}}');
                                    }
                                    
                                    d.set_value('parameters',options);
                                } else {
                                    console.error("Unexpected response from frappe.call:", r);
                                }
                                
                            },
                            error: function (err) {
                                console.error("Error in frappe.call:", err);
                            }
                        });
                        
                        
                    }
                },
                {
                    'fieldname': 'template_type',
                    'label': 'Template Type',
                    'fieldtype': 'Select',
                    'reqd': 0,
                    'read_only': 1,
                    'options': ['TEXT','IMAGE','VIDEO','FILE']
                },
                {
                    'fieldname': 'template_message',
                    'label': 'Template Message',
                    'fieldtype': 'Text',
                    'reqd': 0,
                    'read_only':1
                },
                {
                    'fieldname': 'no_of_template_params',
                    'label': 'Number of Template Params / Sample Values',
                    'fieldtype': 'Int',
                    'reqd': 0,
                    'read_only': 1
                },
                {
                    'fieldname': 'parameters',
                    'label': 'Parameters',
                    'fieldtype': 'Small Text',
                    'reqd': 0,
                    'description': 'Format: Param 1,Param 2,Param 3'
                },
                {
                    'fieldname': 'file_name',
                    'label': 'File Name',
                    'fieldtype': 'Data',
                    'reqd': 0
                },
                {
                    'fieldname': 'url',
                    'label': 'Media URL',
                    'fieldtype': 'Small Text',
                    'reqd': 0
                },

            ],
            'primary_action_label': 'Submit',
            'primary_action': async function () {

                let values = this.get_values();
                if ((values.template_type == "IMAGE" || values.template_type == "VIDEO" || values.template_type == "FILE") && (values.url == undefined || values.url == '' || values.url == null || values.file_name == undefined || values.file_name == '' || values.file_name == null))
                {
                    frappe.msgprint("Please upload Media: "+values.template_type)
                    return
                }
                
                var atoken = await frappe.db.get_value('Aisensy Settings', values.select_account, 'authentication_token');
                var authentication_token= atoken.message.authentication_token;
                // console.log(authentication_token);
                let base_url = 'https://backend.aisensy.com/campaign/t1/api';

                let campaign;
                await frappe.call({
                    method: 'frappe.client.get',
                    args: {
                        doctype: 'Aisensy Campaign',
                        filters: { 'name': values.campaign_name }
                    },
                    callback: function (r) {
                       campaign=r.message;
                    }
                });
                let contact_numbers = [];
                let number = '';
                for (let i = 0; i < values.customer_numbers.length; i++) {
                    if (values.customer_numbers[i] == ',') {
                        contact_numbers.push(number)
                        number = '';
                        continue;
                    }
                    else if (values.customer_numbers[i] == ' ')
                    {
                        continue;
                    }
                    number += values.customer_numbers[i];
                }
                if (number!= ''){
                    contact_numbers.push(number)
                }
                let invalid_numbers='',valid_numbers=''
                let message_invalid='',message_valid=''
                if(contact_numbers.length==0){
                    frappe.msgprint("Please add any contact Number or check the format for adding numbers.")
                }
                for(let i=0;i<contact_numbers.length;i++){
                    let data = {
                        "apiKey": authentication_token,
                        "campaignName": values.campaign_name,
                        "userName": values.customer_name,
                        "destination": contact_numbers[i]
                    }
                    if (values.lead_source != undefined && values.lead_source != '' && values.lead_source !=null)
                    {
                        data.source=values.lead_source;
                    }
                    if (values.url != undefined && values.url != '' && values.url !=null)
                    {
                        if (values.file_name != undefined && values.file_name != '' && values.file_name!=null)
                        {
                            data.media = {
                                "url": values.url,
                                "filename": values.file_name
                            };
                        }
                    }
                    let template_params=[];
                    let value='';
                    for(let i=0;i<values.parameters.length;i++)
                    {
                        if(values.parameters[i]==',')
                        {
                            template_params.push(value)
                            value='';
                            continue;
                        }
                        value+=values.parameters[i];
                    }
                    if(value!=''){
                        template_params.push(value)
                    }
                    if (template_params != 'undefined' && template_params != '') {
                        data.templateParams = template_params;
                    }
                    
                    await fetch(base_url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',

                        },
                        body: JSON.stringify(data)
                    }).then(async response =>{
                        
                        if(response.status==200){
                            if (valid_numbers == '') {
                                valid_numbers += contact_numbers[i];
                            }
                            else
                                valid_numbers += ', ' + contact_numbers[i];
                            let message = 'Message moved to sent state, check Aisensy dashboard to for further status. Note: The message may be moved to Failed State, check the dashboard for reasons.';
                            message_valid=message
                            frappe.msgprint('For [' + contact_numbers[i]+'], Status 200 : '+ message)
                            return response.ok;
                        }
                        else if(response.status==401){
                            let message = "Enter valid API Key";
                            message_invalid = message
                            frappe.msgprint(message)
                        }
                        return await  response.json();
                    }).then(async response => {
                        if(response==true)
                        {
                            return;
                        }
                        
                        let message = 'Message not sent, ' + response.errorMessage;
                        if(response.errorMessage=="Invalid Number")
                        {
                            if(invalid_numbers==''){
                                invalid_numbers+=contact_numbers[i];
                            }
                            else
                            invalid_numbers+=', '+contact_numbers[i];

                            frappe.msgprint('For [' + contact_numbers[i] + '], Status ' + response.errorCode + " " + ': '+message)
                        }
                        else{
                        message_invalid = message
                        frappe.msgprint('For [' + contact_numbers[i] + '], Status ' + response.errorCode + " " + ': '+message)
                        }
                    });
                }
                
                let message=''
                if(message_valid.length!=0)
                {
                    message=message_valid
                }
                else if(message_invalid.length!=0)
                {
                    message=message_invalid
                }
                else
                {
                    message="Please add valid numbers."
                }
                
                let message_logs = {
                    "doctype": "Aisensy Message Logs",
                    "triggered_from": "Customer Form",
                    "response_message": message,
                    "created_at": frappe.datetime.now_datetime(),
                    "campaign_name": values.campaign_name,
                    "invalid_numbers": invalid_numbers,
                    "valid_numbers": valid_numbers
                };
               
                frappe.db.insert(message_logs);
                this.hide();
            }
        }).show();
        d.show();
}
