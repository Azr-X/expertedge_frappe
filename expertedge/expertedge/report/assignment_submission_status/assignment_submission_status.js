frappe.query_reports["Assignment Submission Status"] = {
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
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nNot Required\nPending\nComplete",
		},
	],
};
