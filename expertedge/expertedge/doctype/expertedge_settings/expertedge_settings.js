frappe.ui.form.on("ExpertEdge Settings", {
	refresh(frm) {
		if (frm.doc.google_sheet_url) {
			frm.add_custom_button(__("Sync Leads from Sheet"), function () {
				frappe.call({
					method: "expertedge.api.google_sheet_sync.sync_now",
					freeze: true,
					freeze_message: __("Importing leads from Google Sheet..."),
					callback: function (r) {
						if (r.message !== null && r.message !== undefined) {
							frappe.show_alert({
								message: __("{0} new leads imported", [r.message]),
								indicator: "green",
							});
						}
					},
				});
			});
		}

		if (frm.doc.enable_whatsapp_alerts) {
			frm.add_custom_button(__("Test WhatsApp Alert"), function () {
				frappe.call({
					method: "expertedge.whatsapp.test_whatsapp_alert",
					freeze: true,
					freeze_message: __("Sending test message..."),
					callback: function () {
						frappe.show_alert({
							message: __("Test message sent"),
							indicator: "green",
						});
					},
				});
			});
		}
	},
});
