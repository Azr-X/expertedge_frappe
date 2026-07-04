frappe.listview_settings["EE Student"] = {
	onload(listview) {
		listview.page.add_action_item(__("Mark Attendance"), () => {
			const selected = listview.get_checked_items();
			if (!selected.length) {
				frappe.throw(__("Please select at least one student."));
			}
			show_attendance_dialog(selected);
		});
	},
};

function show_attendance_dialog(students) {
	// Build student list HTML
	const student_list = students
		.map((s) => `<li>${s.student_name || s.name}</li>`)
		.join("");

	const tz_options = Intl.supportedValuesOf
		? Intl.supportedValuesOf("timeZone")
		: ["Asia/Kolkata", "Asia/Dubai", "Asia/Riyadh", "UTC"];
	const browser_tz =
		Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata";

	const d = new frappe.ui.Dialog({
		title: __("Mark Student Attendance"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "student_list_html",
				options: `<div class="mb-3">
					<strong>${students.length} Student(s) Selected:</strong>
					<ul class="mt-1" style="max-height:120px;overflow-y:auto;margin-bottom:0">${student_list}</ul>
				</div>`,
			},
			{
				fieldtype: "Section Break",
				label: __("Attendance Details"),
			},
			{
				fieldtype: "Date",
				fieldname: "date",
				label: __("Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldtype: "Column Break",
			},
			{
				fieldtype: "Select",
				fieldname: "session",
				label: __("Session"),
				reqd: 1,
				options: ["First Half", "Second Half"],
				default: "First Half",
			},
			{
				fieldtype: "Section Break",
				label: __("Time & Timezone"),
			},
			{
				fieldtype: "Time",
				fieldname: "check_in_time",
				label: __("Check-in Time"),
				reqd: 1,
				default: frappe.datetime.now_time(),
			},
			{
				fieldtype: "Column Break",
			},
			{
				fieldtype: "Autocomplete",
				fieldname: "timezone",
				label: __("Timezone"),
				reqd: 1,
				options: tz_options,
				default: browser_tz,
			},
		],
		primary_action_label: __("Mark Attendance"),
		primary_action(values) {
			const student_ids = students.map((s) => s.name);
			d.disable_primary_action();
			frappe.xcall(
				"expertedge.expertedge.doctype.ee_student_attendance.ee_student_attendance.bulk_mark_attendance",
				{
					student_ids: student_ids,
					date: values.date,
					session: values.session,
					check_in_time: values.check_in_time,
					timezone: values.timezone,
				}
			).then((result) => {
				d.hide();
				frappe.msgprint({
					title: __("Attendance Marked"),
					message: __(
						"{0} attendance record(s) created. {1} skipped (already exist).",
						[result.created, result.skipped]
					),
					indicator: "green",
				});
			}).catch(() => {
				d.enable_primary_action();
			});
		},
	});

	d.show();
}
