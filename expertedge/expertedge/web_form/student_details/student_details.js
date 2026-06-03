frappe.ready(function() {
	// Pass token from URL to all API calls so server can validate
	var token = frappe.utils.get_url_arg("token");
	if (token) {
		// Inject token into frappe.call so accept/get_form_data receive it
		var original_call = frappe.call;
		frappe.call = function(opts) {
			if (opts && opts.args) {
				opts.args.token = token;
			}
			return original_call.apply(this, arguments);
		};
	}
});
