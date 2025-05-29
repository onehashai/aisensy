frappe.ui.form.on("Notification", {
  aisensy_whatsapp_template: function (frm) {
    frm.set_value("aisensy_whatsapp_parameter", []);
  },
  aisensy_map_fields: function (frm) {
    if (!frm.doc.document_type || !frm.doc.aisensy_whatsapp_template) {
      frappe.msgprint(
        "Please select both Document Type and WhatsApp Template.",
      );
      return;
    }

    frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Aisensy Campaign",
        filters: { campaign_name: frm.doc.aisensy_whatsapp_template },
        fields: [
          "name",
          "no_of_template_params",
          "template_type",
          "template_format",
        ],
        limit_page_length: 1,
      },
      callback: function (r) {
        if (!r.message || r.message.length === 0) {
          frappe.msgprint(
            "No Aisensy Campaign found for the selected WhatsApp Template.",
          );
          return;
        }
        let campaign = r.message[0];

        frappe.model.with_doctype(frm.doc.document_type, function () {
          let fields = frappe.meta
            .get_docfields(frm.doc.document_type)
            .filter(
              (df) =>
                df.fieldtype !== "Section Break" &&
                df.fieldtype !== "Column Break",
            )
            .map((df) => ({
              label: df.label || df.fieldname,
              value: df.fieldname,
            }));

          let dialog_fields = [
            {
              label: "Template Format",
              fieldname: "template_format",
              fieldtype: "Small Text",
              read_only: 1,
              default: campaign.template_format,
              reqd: 1,
            },
          ];

          for (let i = 1; i <= campaign.no_of_template_params; i++) {
            dialog_fields.push({
              label: `Parameter ${i}`,
              fieldname: `param_${i}`,
              fieldtype: "Autocomplete",
              options: fields.map((f) => f.label),
              reqd: 1,
            });
          }

          let d = new frappe.ui.Dialog({
            title: "Map Template Parameters",
            fields: dialog_fields,
            primary_action_label: "Map",
            primary_action(values) {
              for (let i = 1; i <= campaign.no_of_template_params; i++) {
                let selected_label = values[`param_${i}`] || "";

                let selected_field = fields.find(
                  (f) => f.label === selected_label,
                );
                let fieldname = selected_field
                  ? selected_field.value
                  : selected_label;
                let field_label = selected_field
                  ? selected_field.label
                  : selected_label;

                frm.add_child("aisensy_whatsapp_parameter", {
                  parameter: i,
                  value: `${field_label}|${fieldname}`,
                  field_value: fieldname,
                  type: campaign.template_type,
                });
              }
              frm.refresh_field("aisensy_whatsapp_parameter");
              d.hide();
              frappe.msgprint("Parameters mapped successfully!");
            },
          });
          d.show();
        });
      },
    });
  },
});
