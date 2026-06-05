frappe.ui.form.on("EE Lead", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.whatsapp.add_button(frm, 'mobile_no');
		_add_follow_up_button(frm);
		_show_last_follow_up(frm);

		const active = !frm.doc.converted && frm.doc.status !== "Lost" && frm.doc.status !== "Converted";

		if (active) {
			frm.add_custom_button(__("Send Brochure"), function () {
				_email_with_field_check(frm, {
					title: "Send Brochure",
					method: "send_brochure",
					fields: [
						{ fieldname: "email", label: "Email", fieldtype: "Data", options: "Email" },
						{ fieldname: "preferred_batch", label: "Preferred Batch", fieldtype: "Link", options: "EE Batch" },
					],
				});
			}, __("Actions"));

			frm.add_custom_button(__("Request Documents"), function () {
				_email_with_field_check(frm, {
					title: "Request Documents",
					method: "request_documents",
					fields: [
						{ fieldname: "email", label: "Email", fieldtype: "Data", options: "Email" },
					],
				});
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
			title: __("Log Call / Follow Up"),
			fields: [
				{
					fieldname: "direction",
					fieldtype: "Select",
					label: "Direction",
					options: "Outbound\nInbound",
					default: "Outbound",
					reqd: 1,
				},
				{
					fieldname: "call_result",
					fieldtype: "Select",
					label: "Result",
					options: "Connected\nNo Answer\nBusy\nSwitched Off\nNot Reachable\nWrong Number\nCall Back Later\nInterested\nNot Interested\nFollow-up Scheduled",
					reqd: 1,
				},
				{
					fieldname: "duration_min",
					fieldtype: "Float",
					label: "Duration (min)",
				},
				{
					fieldname: "summary",
					fieldtype: "Small Text",
					label: "Notes",
				},
				{
					fieldname: "next_call_on",
					fieldtype: "Datetime",
					label: "Next Call On",
					default: frappe.datetime.add_days(frappe.datetime.now_datetime(), 1),
				},
			],
			primary_action_label: __("Save"),
			primary_action: function (values) {
				d.hide();
				frm.add_child("call_log", {
					call_on: frappe.datetime.now_datetime(),
					caller: frappe.session.user,
					direction: values.direction,
					call_result: values.call_result,
					duration_min: values.duration_min,
					summary: values.summary,
					next_call_on: values.next_call_on,
				});
				frm.dirty();
				frm.save().then(() => frm.reload_doc());
			},
		});
		d.show();
	}).addClass("btn-primary");
}

function _show_last_follow_up(frm) {
	if (!frm.doc.call_log || !frm.doc.call_log.length) return;

	var with_next = frm.doc.call_log.filter(
		(r) => r.next_call_on
	).sort((a, b) => new Date(b.next_call_on) - new Date(a.next_call_on));

	if (!with_next.length) return;

	var last = with_next[0];
	var dt = frappe.datetime.str_to_user(last.next_call_on);
	var is_past = frappe.datetime.get_diff(last.next_call_on, frappe.datetime.now_datetime()) < 0;
	var color = is_past ? "orange" : "blue";
	var label = is_past ? "Overdue follow-up" : "Next follow-up";

	frm.set_intro(
		__("{0}: {1} — {2} ({3})", [label, dt, last.summary || "", last.call_result]),
		color
	);
}

function _email_with_field_check(frm, opts) {
	var missing = [];
	for (var f of opts.fields) {
		if (!frm.doc[f.fieldname]) {
			missing.push({
				fieldname: f.fieldname,
				fieldtype: f.fieldtype || "Data",
				label: f.label,
				options: f.options,
				reqd: 1,
			});
		}
	}

	if (missing.length) {
		var d = new frappe.ui.Dialog({
			title: __(opts.title + " — Fill Required Fields"),
			fields: missing,
			primary_action_label: __("Save & Continue"),
			primary_action: function (values) {
				d.hide();
				for (var key in values) {
					frm.set_value(key, values[key]);
				}
				frm.save().then(() => {
					_show_send_dialog(frm, opts);
				});
			},
		});
		d.show();
		return;
	}

	_show_send_dialog(frm, opts);
}

function _show_send_dialog(frm, opts) {
	var d = new frappe.ui.Dialog({
		title: __(opts.title),
		primary_action_label: __("Send Email"),
		primary_action: function () {
			d.hide();
			frm.call(opts.method, { send_email: 1 }).then(() => frm.reload_doc());
		},
		secondary_action_label: __("Manually Sent"),
		secondary_action: function () {
			d.hide();
			frm.call(opts.method, { send_email: 0 }).then(() => frm.reload_doc());
		},
	});
	d.$body.html(__("Send {0} to {1}?", [opts.title, frm.doc.email]));
	d.show();
}
