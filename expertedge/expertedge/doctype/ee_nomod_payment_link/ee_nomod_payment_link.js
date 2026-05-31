frappe.ui.form.on("EE Nomod Payment Link", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Generate Link
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Generate Link"), function () {
				frm.call("generate_nomod_link").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}

		if (["Generated", "Sent"].includes(frm.doc.status)) {
			// Check Payment Status (polls Nomod API)
			if (frm.doc.nomod_reference && !frm.doc.nomod_reference.startsWith("PLACEHOLDER")) {
				frm.add_custom_button(__("Check Payment Status"), function () {
					frm.call("check_payment_status").then((r) => {
						if (r && r.message && r.message.paid) {
							frappe.confirm(
								__("Payment confirmed by Nomod. Mark as Paid and create Payment Entry?"),
								function () {
									frm.call("mark_paid").then(() => frm.reload_doc());
								}
							);
						}
					});
				}, __("Actions"));
			}

			// Mark as Paid (manual)
			frm.add_custom_button(__("Mark as Paid"), function () {
				frappe.confirm(
					__("Confirm payment of {0} {1} received?", [frm.doc.currency, frm.doc.amount]),
					function () {
						frm.call("mark_paid").then(() => frm.reload_doc());
					}
				);
			}, __("Actions"));
		}

		// Copy link button
		if (frm.doc.payment_link_url && ["Generated", "Sent"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Copy Link"), function () {
				frappe.utils.copy_to_clipboard(frm.doc.payment_link_url);
				frappe.show_alert({message: __("Payment link copied!"), indicator: "green"});
			});

			// Email Payment Link
			frm.add_custom_button(__("Email Payment Link"), function () {
				frappe.confirm(
					__("Email payment link ({0} {1}) to student?", [frm.doc.currency, frm.doc.amount]),
					function () {
						frm.call("email_payment_link").then(() => {
							frm.reload_doc();
							frappe.show_alert({message: __("Payment link emailed to student"), indicator: "green"});
						});
					}
				);
			}, __("Actions"));
		}
	},
});
