frappe.ui.form.on("EE Nomod Payment Link", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Generate Link
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Generate Link"), function () {
				frm.call("generate_nomod_link").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}

		// Mark as Paid
		if (["Generated", "Sent"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Mark as Paid"), function () {
				frappe.confirm(
					__("Confirm payment of {0} {1} received?", [frm.doc.currency, frm.doc.amount]),
					function () {
						frm.call("mark_paid").then(() => frm.reload_doc());
					}
				);
			}, __("Actions"));
		}
	},
});
