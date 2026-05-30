frappe.ui.form.on("EE Student", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Create Customer & Invoice
		if (!frm.doc.sales_invoice) {
			frm.add_custom_button(__("Create Customer & Invoice"), function () {
				frm.call("create_customer_and_invoice").then(() => frm.reload_doc());
			}, __("Billing"));
		}

		// Generate Pre-Approval Link
		if (frm.doc.status === "Pre-Approval Pending") {
			frm.add_custom_button(__("Generate Pre-Approval Link"), function () {
				frm.call("generate_pre_approval_link").then((r) => {
					if (r && r.message) {
						frappe.msgprint(__("Payment link created: {0}", [r.message]));
						frm.reload_doc();
					}
				});
			}, __("Billing"));
		}

		// Generate Balance Link
		if (["Balance Pending", "CMA Registered"].includes(frm.doc.status) && frm.doc.outstanding > 0) {
			frm.add_custom_button(__("Generate Balance Link"), function () {
				frm.call("generate_balance_link").then((r) => {
					if (r && r.message) {
						frappe.msgprint(__("Balance link created: {0}", [r.message]));
						frm.reload_doc();
					}
				});
			}, __("Billing"));
		}

		// Email buttons
		if (frm.doc.status !== "Dropped") {
			frm.add_custom_button(__("Send Pre-Approval Email"), function () {
				frm.call("send_pre_approval_email").then(() => frm.reload_doc());
			}, __("Email"));

			frm.add_custom_button(__("Send Receipt"), function () {
				frm.call("send_receipt_email").then(() => frm.reload_doc());
			}, __("Email"));

			frm.add_custom_button(__("Send Balance Email"), function () {
				frm.call("send_balance_email").then(() => frm.reload_doc());
			}, __("Email"));

			frm.add_custom_button(__("Send Welcome Email"), function () {
				frm.call("send_welcome_email").then(() => frm.reload_doc());
			}, __("Email"));
		}

		// Mark CMA Registered
		if (["Pre-Approval Paid", "CMA Registration"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Mark CMA Registered"), function () {
				frm.call("mark_cma_registered").then(() => frm.reload_doc());
			}, __("Actions"));
		}

		// Issue Materials
		if (frm.doc.status === "Enrolled") {
			frm.add_custom_button(__("Issue Materials"), function () {
				frm.call("issue_materials").then(() => frm.reload_doc());
			}, __("Actions"));
		}

		// Show lead link
		if (frm.doc.lead) {
			frm.set_intro(
				__('Converted from Lead: <a href="/app/ee-lead/{0}">{0}</a>', [frm.doc.lead]),
				"blue"
			);
		}
	},
});
