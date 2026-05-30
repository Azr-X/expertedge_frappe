frappe.ui.form.on("EE Lead", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Send Brochure
		if (!frm.doc.converted && frm.doc.status !== "Lost") {
			frm.add_custom_button(__("Send Brochure"), function () {
				frm.call("send_brochure").then(() => frm.reload_doc());
			}, __("Actions"));
		}

		// Request Documents
		if (!frm.doc.converted && frm.doc.status !== "Lost") {
			frm.add_custom_button(__("Request Documents"), function () {
				frm.call("request_documents").then(() => frm.reload_doc());
			}, __("Actions"));
		}

		// Mark Documents Verified
		if (!frm.doc.converted && !frm.doc.documents_verified && frm.doc.status !== "Lost") {
			frm.add_custom_button(__("Mark Documents Verified"), function () {
				frm.call("mark_documents_verified").then(() => frm.reload_doc());
			}, __("Actions"));
		}

		// Convert to Student
		if (frm.doc.status === "Confirmed" && !frm.doc.converted) {
			frm.add_custom_button(__("Convert to Student"), function () {
				frm.call("convert_to_student").then((r) => {
					if (r && r.message) {
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");
		}

		// Mark Lost
		if (!frm.doc.converted && frm.doc.status !== "Lost" && frm.doc.status !== "Converted") {
			frm.add_custom_button(__("Mark Lost"), function () {
				frappe.prompt(
					{ fieldname: "lost_reason", fieldtype: "Small Text", label: "Lost Reason", reqd: 1 },
					function (values) {
						frm.call("mark_lost", { lost_reason: values.lost_reason }).then(() =>
							frm.reload_doc()
						);
					},
					__("Mark Lead as Lost"),
					__("Confirm")
				);
			}, __("Actions"));
		}

		// Show link to student if converted
		if (frm.doc.student) {
			frm.set_intro(
				__('Converted to Student: <a href="/app/ee-student/{0}">{0}</a>', [frm.doc.student]),
				"green"
			);
		}
	},
});
