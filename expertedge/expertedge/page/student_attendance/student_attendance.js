frappe.pages["student-attendance"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Student Attendance",
		single_column: true,
	});

	page.main.html(frappe.render_template("student_attendance"));

	var from_ctrl = frappe.ui.form.make_control({
		df: {
			fieldname: "from_date",
			fieldtype: "Date",
			label: "From Date",
			reqd: 1,
		},
		parent: page.main.find("#from-date-filter"),
		render_input: true,
	});
	from_ctrl.set_value(frappe.datetime.month_start());

	var to_ctrl = frappe.ui.form.make_control({
		df: {
			fieldname: "to_date",
			fieldtype: "Date",
			label: "To Date",
			reqd: 1,
		},
		parent: page.main.find("#to-date-filter"),
		render_input: true,
	});
	to_ctrl.set_value(frappe.datetime.get_today());

	var batch_ctrl = frappe.ui.form.make_control({
		df: {
			fieldname: "batch",
			fieldtype: "Link",
			label: "Batch",
			options: "EE Batch",
			reqd: 1,
		},
		parent: page.main.find("#batch-filter"),
		render_input: true,
	});

	page.main.find("#btn-refresh").on("click", function () {
		render_heatmap(
			from_ctrl.get_value(),
			to_ctrl.get_value(),
			batch_ctrl.get_value(),
			page
		);
	});
};

function render_heatmap(from_date, to_date, batch, page) {
	if (!from_date || !to_date || !batch) {
		frappe.show_alert({ message: __("Please select all filters"), indicator: "orange" });
		return;
	}

	frappe.xcall(
		"expertedge.expertedge.page.student_attendance.student_attendance.get_attendance_data",
		{ from_date, to_date, batch }
	).then(function (data) {
		var container = page.main.find("#heatmap-container");

		if (!data.students.length) {
			container.html('<p class="text-muted">No students found in this batch.</p>');
			return;
		}

		var dates = get_date_range(from_date, to_date);
		var day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

		// Build header
		var html = '<div class="heatmap-wrapper"><table class="heatmap-table"><thead><tr>';
		html += '<th class="student-name-col">Student</th>';
		dates.forEach(function (d) {
			var dt = new Date(d);
			var day = day_names[dt.getDay()];
			var label = frappe.datetime.str_to_user(d).replace(/^\d{4}-/, "");
			html +=
				'<th><div class="date-header"><div class="day-name">' +
				day +
				"</div>" +
				frappe.datetime.str_to_user(d).split("-").slice(1).join("/") +
				"</div></th>";
		});
		html += "</tr></thead><tbody>";

		// Build rows
		data.students.forEach(function (student) {
			html += "<tr>";
			html +=
				'<td class="student-name-cell">' +
				frappe.utils.escape_html(student.student_name) +
				"</td>";

			dates.forEach(function (d) {
				var key = student.name + "|" + d;
				var first = data.attendance[key + "|First Half"];
				var second = data.attendance[key + "|Second Half"];

				html += '<td><div class="session-pair">';
				html += build_cell(first, student.name, d, "First Half");
				html += build_cell(second, student.name, d, "Second Half");
				html += "</div></td>";
			});

			html += "</tr>";
		});

		html += "</tbody></table></div>";
		container.html(html);
	});
}

function build_cell(status, student, date, session) {
	var cls = status === "present" ? "present" : status === "absent" ? "absent" : "no-class";
	var title = session + (status === "present" ? " - Present" : status === "absent" ? " - Absent" : " - No Record");
	return '<span class="att-cell ' + cls + '" title="' + date + " " + title + '"></span>';
}

function get_date_range(from_date, to_date) {
	var dates = [];
	var current = frappe.datetime.str_to_obj(from_date);
	var end = frappe.datetime.str_to_obj(to_date);
	while (current <= end) {
		dates.push(frappe.datetime.obj_to_str(current));
		current.setDate(current.getDate() + 1);
	}
	return dates;
}
