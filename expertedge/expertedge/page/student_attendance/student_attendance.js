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

	function do_refresh() {
		render_heatmap(
			from_ctrl.get_value(),
			to_ctrl.get_value(),
			batch_ctrl.get_value(),
			page.main.find("#chk-absent-only").is(":checked"),
			page
		);
	}

	page.main.find("#btn-refresh").on("click", do_refresh);
	page.main.find("#chk-absent-only").on("change", do_refresh);
};

function render_heatmap(from_date, to_date, batch, absent_only, page) {
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

		// Compute total sessions (class dates only)
		var total_sessions = data.total_sessions || 0;

		// Pre-compute per-student stats
		var student_stats = data.students.map(function (student) {
			var attended = 0;
			var missed = 0;
			dates.forEach(function (d) {
				["First Half", "Second Half"].forEach(function (session) {
					var key = student.name + "|" + d + "|" + session;
					var status = data.attendance[key];
					if (status === "present") attended++;
					else if (status === "absent") missed++;
				});
			});
			return {
				student: student,
				attended: attended,
				missed: missed,
				pct: total_sessions > 0 ? Math.round((attended / total_sessions) * 100) : 0,
			};
		});

		// Filter if absent_only
		var filtered = absent_only
			? student_stats.filter(function (s) { return s.missed > 0; })
			: student_stats;

		if (!filtered.length) {
			container.html('<p class="text-muted">No students to display.</p>');
			return;
		}

		// Build header
		var html = '<div class="heatmap-wrapper"><table class="heatmap-table"><thead><tr>';
		html += '<th class="student-name-col">Student</th>';
		html += '<th>Attendance %</th>';
		dates.forEach(function (d) {
			var dt = new Date(d);
			var day = day_names[dt.getDay()];
			html +=
				'<th><div class="date-header"><div class="day-name">' +
				day +
				"</div>" +
				frappe.datetime.str_to_user(d).split("-").slice(1).join("/") +
				"</div></th>";
		});
		html += "</tr></thead><tbody>";

		// Build rows
		filtered.forEach(function (row) {
			var student = row.student;
			var pct_cls = row.pct >= 75 ? "green" : row.pct >= 50 ? "orange" : "red";

			html += "<tr>";
			html +=
				'<td class="student-name-cell">' +
				frappe.utils.escape_html(student.student_name) +
				"</td>";

			html +=
				'<td style="white-space:nowrap;font-weight:600;text-align:center">' +
				'<span class="indicator-pill ' + pct_cls + '">' +
				row.attended + "/" + total_sessions +
				" (" + row.pct + "%)</span></td>";

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
