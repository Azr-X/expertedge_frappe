frappe.ui.form.on("EE Student", {
	refresh(frm) {
		if (frm.is_new()) return;

		frappe.whatsapp.add_button(frm, 'mobile_no');
		_add_follow_up_button(frm);
		_show_last_follow_up(frm);

		if (frm.doc.status !== "Dropped") {
			// Create Customer & Invoice — dialog with fee input
			if (!frm.doc.sales_invoice) {
				frm.add_custom_button(__("Create Customer & Invoice"), function () {
					_show_invoice_dialog(frm);
				}, __("Billing"));
			}

			// Create Payment Link
			frm.add_custom_button(__("Create Payment Link"), function () {
				if (!frm.doc.sales_invoice) {
					_show_invoice_dialog(frm, true);
					return;
				}
				_show_payment_link_dialog(frm);
			}, __("Billing"));

			// Email buttons (Send Email / Manually Sent dialog)
			function email_action_dialog(title, method, email) {
				let d = new frappe.ui.Dialog({
					title: __(title),
					primary_action_label: __("Send Email"),
					primary_action: function () {
						d.hide();
						frm.call(method, { send_email: 1 }).then(() => frm.reload_doc());
					},
					secondary_action_label: __("Manually Sent"),
					secondary_action: function () {
						d.hide();
						frm.call(method, { send_email: 0 }).then(() => frm.reload_doc());
					},
				});
				d.$body.html(__("How was this communicated to {0}?", [email]));
				d.show();
			}

			frm.add_custom_button(__("Send Pre-Approval Email"), function () {
				email_action_dialog("Pre-Approval", "send_pre_approval_email", frm.doc.email);
			}, __("Email"));

			frm.add_custom_button(__("Send Receipt"), function () {
				email_action_dialog("Payment Receipt", "send_receipt_email", frm.doc.email);
			}, __("Email"));

			frm.add_custom_button(__("Send Balance Email"), function () {
				email_action_dialog("Balance Payment", "send_balance_email", frm.doc.email);
			}, __("Email"));

			frm.add_custom_button(__("Send Welcome Email"), function () {
				email_action_dialog("Welcome Email", "send_welcome_email", frm.doc.email);
			}, __("Email"));

			// Mark CMA Registered
			frm.add_custom_button(__("Mark CMA Registered"), function () {
				frm.call("mark_cma_registered").then(() => frm.reload_doc());
			}, __("Actions"));

			// Issue Materials
			frm.add_custom_button(__("Issue Materials"), function () {
				frm.call("issue_materials").then(() => frm.reload_doc());
			}, __("Actions"));
		}

		// Generate Web Form Link
		frm.add_custom_button(__("Generate Web Form Link"), function () {
			frm.call("generate_web_form_link").then((r) => {
				if (r && r.message) {
					frm.reload_doc();
					frappe.msgprint({
						title: __("Student Details Link"),
						indicator: "green",
						message: __("Share this link with the student via WhatsApp:<br><br><code>{0}</code><br><br><button class='btn btn-xs btn-default' onclick='navigator.clipboard.writeText(\"{0}\");frappe.show_alert(\"Copied!\")'>Copy Link</button>", [r.message]),
					});
				}
			});
		}, __("Actions"));

		// Show lead link
		if (frm.doc.lead) {
			frm.set_intro(
				__('Converted from Lead: <a href="/app/ee-lead/{0}">{0}</a>', [frm.doc.lead]),
				"blue"
			);
		}

		// Dashboard connections — Customer, Sales Invoice, Payment Entries
		if (frm.doc.customer) {
			frm.dashboard.add_indicator(
				__('<a href="/app/customer/{0}">{0}</a>', [frm.doc.customer]),
				"blue"
			);
		}
		if (frm.doc.sales_invoice) {
			frm.dashboard.add_indicator(
				__('<a href="/app/sales-invoice/{0}">Invoice: {0}</a>', [frm.doc.sales_invoice]),
				"green"
			);
		}
		// Show payment entries from linked payment links
		if (!frm.is_new()) {
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "EE Nomod Payment Link",
					filters: { student: frm.doc.name, status: "Paid" },
					fields: ["name", "payment_entry", "amount", "purpose"],
				},
				async: false,
				callback: function (r) {
					if (r.message) {
						r.message.forEach(function (link) {
							if (link.payment_entry) {
								frm.dashboard.add_indicator(
									__('<a href="/app/payment-entry/{0}">PE: {0} ({1} {2})</a>',
										[link.payment_entry, link.purpose, link.amount]),
									"orange"
								);
							}
						});
					}
				},
			});
		}
	},
});

function _show_invoice_dialog(frm, open_payment_link_after) {
	// Compute default AUD from existing fee if available
	var existing_rate = frm.doc.aud_conversion_rate || 2.65;
	var existing_aed = frm.doc.net_fee || frm.doc.total_fee || 0;
	var default_aud = existing_aed && existing_rate > 0 ? existing_aed / existing_rate : 1320;

	var d = new frappe.ui.Dialog({
		title: __("Create Customer & Sales Invoice"),
		fields: [
			{
				fieldname: "aud_amount",
				fieldtype: "Currency",
				label: "Program Fee (AUD)",
				default: default_aud,
				reqd: 1,
				description: "Enter the fee in AUD. AED amount will be computed.",
			},
			{
				fieldname: "aud_conversion_rate",
				fieldtype: "Float",
				label: "AUD → AED Conversion Rate",
				default: existing_rate,
				precision: 4,
				reqd: 1,
				description: "1 AUD = X AED",
			},
			{
				fieldname: "total_fee",
				fieldtype: "Currency",
				label: "Total Fee (AED)",
				read_only: 1,
				description: "Auto-calculated: AUD × Rate",
			},
			{
				fieldname: "apply_lumpsum_discount",
				fieldtype: "Check",
				label: "Apply Lump-sum Discount (5%)",
				default: frm.doc.apply_lumpsum_discount || 0,
			},
			{
				fieldname: "net_fee_display",
				fieldtype: "Currency",
				label: "Net Invoice Amount (AED)",
				read_only: 1,
				bold: 1,
			},
		],
		primary_action_label: __("Create"),
		primary_action: function (values) {
			d.hide();
			frm.call("create_customer_and_invoice", {
				total_fee: d.get_value("total_fee"),
				apply_discount: values.apply_lumpsum_discount,
				aud_conversion_rate: values.aud_conversion_rate,
			}).then(() => {
				frm.reload_doc();
				if (open_payment_link_after) {
					frappe.show_alert({
						message: __("Invoice created. Now create the payment link."),
						indicator: "green",
					});
				}
			});
		},
	});

	function recalc() {
		var aud = d.get_value("aud_amount") || 0;
		var rate = d.get_value("aud_conversion_rate") || 2.65;
		var aed = flt(aud * rate, 2);
		d.set_value("total_fee", aed);

		var disc = d.get_value("apply_lumpsum_discount");
		var net = disc ? flt(aed * 0.95, 2) : aed;
		d.set_value("net_fee_display", net);
	}
	d.fields_dict.aud_amount.$input.on("change", recalc);
	d.fields_dict.aud_conversion_rate.$input.on("change", recalc);
	d.fields_dict.apply_lumpsum_discount.$input.on("change", recalc);

	// Fetch latest AUD→AED rate from Currency Exchange
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Currency Exchange",
			filters: { from_currency: "AUD", to_currency: "AED" },
			fields: ["exchange_rate"],
			order_by: "date desc",
			limit_page_length: 1,
		},
		async: false,
		callback: function (r) {
			if (r.message && r.message.length) {
				d.set_value("aud_conversion_rate", r.message[0].exchange_rate);
			}
		},
	});

	recalc();
	recalc();
	d.show();
}

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

function _show_payment_link_dialog(frm) {
	var d = new frappe.ui.Dialog({
		title: __("Create Payment Link"),
		fields: [
			{
				fieldname: "purpose",
				fieldtype: "Select",
				label: "Purpose",
				options: "Pre-Approval\nBalance\nPartial\nFull Payment\nOther",
				default: frm.doc.status === "Pre-Approval Pending" ? "Pre-Approval" : "Balance",
				reqd: 1,
			},
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: "Amount",
				default: frm.doc.status === "Pre-Approval Pending"
					? frm.doc.pre_approval_fee
					: frm.doc.outstanding,
				reqd: 1,
			},
			{
				fieldname: "currency",
				fieldtype: "Link",
				label: "Currency",
				options: "Currency",
				default: frm.doc.billing_currency || "AED",
				reqd: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: "Remarks",
			},
		],
		primary_action_label: __("Generate"),
		primary_action: function (values) {
			d.hide();
			frm.call("create_payment_link", values).then((r) => {
				if (r && r.message) {
					frappe.msgprint(
						__("Payment link created: <a href='/app/ee-nomod-payment-link/{0}'>{0}</a>", [r.message])
					);
					frm.reload_doc();
				}
			});
		},
	});
	d.fields_dict.purpose.$input.on("change", function () {
		var purpose = d.get_value("purpose");
		if (purpose === "Pre-Approval") {
			d.set_value("amount", frm.doc.pre_approval_fee || 200);
		} else if (purpose === "Balance") {
			d.set_value("amount", frm.doc.outstanding || 0);
		} else if (purpose === "Full Payment") {
			d.set_value("amount", frm.doc.net_fee || 0);
		}
	});
	d.show();
}
