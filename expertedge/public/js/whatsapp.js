frappe.provide('frappe.whatsapp');

frappe.whatsapp._clean = function(number, country_code) {
	let cleaned = number.replace(/\D/g, '');
	country_code = country_code || '91';

	// Strip leading + or 0
	if (cleaned.startsWith('0')) {
		cleaned = cleaned.substring(1);
	}

	// 10 digits = Indian local, prepend country code
	if (cleaned.length === 10) {
		cleaned = country_code + cleaned;
	}

	return cleaned;
};

frappe.whatsapp._suggest_format = function(raw, cleaned) {
	// Return user-friendly suggestion
	if (cleaned.length < 10) {
		return __('Number too short ({0} digits). Expected format: +91 9876543210', [cleaned.length]);
	}
	if (cleaned.length > 15) {
		return __('Number too long ({0} digits). Expected format: +91 9876543210', [cleaned.length]);
	}
	return null;
};

/**
 * Open WhatsApp chat. If number invalid, show dialog to correct it.
 */
frappe.whatsapp.open_chat = function(number, opts) {
	opts = opts || {};

	if (!number) {
		frappe.msgprint(__('No contact number provided'));
		return;
	}

	let cleaned = frappe.whatsapp._clean(number, opts.country_code);
	let issue = frappe.whatsapp._suggest_format(number, cleaned);

	if (issue) {
		// Show correction dialog
		frappe.whatsapp._correction_dialog(number, cleaned, issue, opts);
		return;
	}

	frappe.whatsapp._launch(cleaned, opts.message);
};

frappe.whatsapp._launch = function(cleaned, message) {
	let url = 'https://wa.me/' + cleaned;
	if (message) {
		url += '?text=' + encodeURIComponent(message);
	}
	window.open(url, '_blank');
};

frappe.whatsapp._correction_dialog = function(raw, cleaned, issue, opts) {
	let d = new frappe.ui.Dialog({
		title: __('Fix Phone Number'),
		fields: [
			{
				fieldtype: 'HTML',
				options: '<p class="text-muted">' + issue + '</p>'
			},
			{
				fieldname: 'number',
				fieldtype: 'Data',
				label: __('Corrected Number'),
				default: raw,
				reqd: 1,
				description: __('Include country code, e.g. +91 9876543210')
			}
		],
		primary_action_label: __('Open WhatsApp'),
		primary_action: function(values) {
			let re_cleaned = frappe.whatsapp._clean(values.number, opts.country_code);
			let re_issue = frappe.whatsapp._suggest_format(values.number, re_cleaned);

			if (re_issue) {
				frappe.msgprint(re_issue);
				return;
			}

			d.hide();
			frappe.whatsapp._launch(re_cleaned, opts.message);
		}
	});
	d.show();
};

/**
 * Add WhatsApp Chat button to form. Always visible, validates on click.
 */
frappe.whatsapp.add_button = function(frm, field, opts) {
	opts = opts || {};
	frm.add_custom_button(__('WhatsApp Chat'), function() {
		frappe.whatsapp.open_chat(frm.doc[field], opts);
	}).addClass('btn-success');
};
