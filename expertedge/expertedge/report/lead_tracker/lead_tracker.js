frappe.query_reports["Lead Tracker"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "lead_source",
			label: __("Lead Source"),
			fieldtype: "Link",
			options: "EE Lead Source",
		},
	],
	tree: true,
	name_field: "label",
	parent_field: "parent_label",
	initial_depth: 1,
};
