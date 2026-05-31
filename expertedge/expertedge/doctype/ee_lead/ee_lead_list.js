frappe.listview_settings["EE Lead"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Sync from Google Sheet"), function () {
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
						listview.refresh();
					}
				},
			});
		});
	},
};
