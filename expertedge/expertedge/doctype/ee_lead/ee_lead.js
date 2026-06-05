frappe.ui.form.on("EE Lead", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.whatsapp.add_button(frm, 'mobile_no');
		_add_follow_up_button(frm);
		_show_last_follow_up(frm);

		const active = !frm.doc.converted && frm.doc.status !== "Lost" && frm.doc.status !== "Converted";

		if (active) {
			frm.add_custom_button(__("Send Brochure"), function () {
				let d = new frappe.ui.Dialog({
					title: __("Send Brochure"),
					primary_action_label: __("Send Email"),
					primary_action: function () {
						d.hide();
						frm.call("send_brochure", { send_email: 1 }).then(() => frm.reload_doc());
					},
					secondary_action_label: __("Manually Sent"),
					secondary_action: function () {
						d.hide();
						frm.call("send_brochure", { send_email: 0 }).then(() => frm.reload_doc());
					},
				});
				d.$body.html(__("How was the brochure sent to {0}?", [frm.doc.email]));
				d.show();
			}, __("Actions"));

			frm.add_custom_button(__("Request Documents"), function () {
				let d = new frappe.ui.Dialog({
					title: __("Request Documents"),
					primary_action_label: __("Send Email"),
					primary_action: function () {
						d.hide();
						frm.call("request_documents", { send_email: 1 }).then(() => frm.reload_doc());
					},
					secondary_action_label: __("Manually Sent"),
					secondary_action: function () {
						d.hide();
						frm.call("request_documents", { send_email: 0 }).then(() => frm.reload_doc());
					},
				});
				d.$body.html(__("How was the document request sent to {0}?", [frm.doc.email]));
				d.show();
			}, __("Actions"));

			frm.add_custom_button(__("Mark Documents Verified"), function () {
				frm.call("mark_documents_verified").then(() => frm.reload_doc());
			}, __("Actions"));

			frm.add_custom_button(__("Confirm Lead"), function () {
				frappe.confirm(
					__("Confirm this lead as Fit and ready for conversion?"),
					function () {
						frm.call("confirm_lead").then(() => frm.reload_doc());
					}
				);
			}, __("Actions"));

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

		// Convert to Student — primary button when Confirmed
		if (frm.doc.status === "Confirmed" && !frm.doc.converted) {
			frm.add_custom_button(__("Convert to Student"), function () {
				frm.call("convert_to_student").then((r) => {
					if (r && r.message) {
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");
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

function _add_follow_up_button(frm) {
	frm.add_custom_button(__("Add Follow Up"), function () {
		var d = new frappe.ui.Dialog({
			title: __("Add Follow Up"),
			fields: [
				{
					fieldname: "summary",
					fieldtype: "Small Text",
					label: "Note",
					reqd: 1,
				},
				{
					fieldname: "follow_up_on",
					fieldtype: "Datetime",
					label: "Follow-up On",
					reqd: 1,
					default: frappe.datetime.add_days(frappe.datetime.now_datetime(), 1),
				},
			],
			primary_action_label: __("Save"),
			primary_action: function (values) {
				d.hide();
				var row = frm.add_child("activity_log", {
					activity_on: frappe.datetime.now_datetime(),
					activity_type: "Follow Up",
					user: frappe.session.user,
					summary: values.summary,
					follow_up_on: values.follow_up_on,
				});
				frm.dirty();
				frm.save().then(() => frm.reload_doc());
			},
		});
		d.show();
	}).addClass("btn-primary");
}

function _show_last_follow_up(frm) {
	if (!frm.doc.activity_log || !frm.doc.activity_log.length) return;

	var follow_ups = frm.doc.activity_log.filter(
		(r) => r.follow_up_on
	).sort((a, b) => new Date(b.follow_up_on) - new Date(a.follow_up_on));

	if (!follow_ups.length) return;

	var last = follow_ups[0];
	var dt = frappe.datetime.str_to_user(last.follow_up_on);
	var is_past = frappe.datetime.get_diff(last.follow_up_on, frappe.datetime.now_datetime()) < 0;
	var color = is_past ? "orange" : "blue";

	frm.set_intro(
		__("Next follow-up: {0} — {1}", [dt, last.summary]),
		color
	);
}
