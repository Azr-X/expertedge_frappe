frappe.ui.form.on("EE Attendance", {
	refresh(frm) {
		// Disable delete button
		frm.disable_delete();

		if (frm.doc.status === "Checked In" && !frm.doc.check_out) {
			frm.add_custom_button(__("Check Out"), function () {
				frappe.call({
					method: "expertedge.expertedge.doctype.ee_attendance.ee_attendance.check_out",
					callback(r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({ message: "Checked out successfully", indicator: "green" });
						}
					},
				});
			}).addClass("btn-primary");
		}
	},
});
