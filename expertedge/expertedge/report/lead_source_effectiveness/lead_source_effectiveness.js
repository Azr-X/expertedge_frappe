frappe.query_reports["Lead Source Effectiveness"] = {
	filters: [
		{
			fieldname: "batch",
			label: __("Batch"),
			fieldtype: "Link",
			options: "EE Batch",
		},
		{
			fieldname: "program",
			label: __("Program"),
			fieldtype: "Link",
			options: "EE Program",
		},
	],
};
