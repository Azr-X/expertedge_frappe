import frappe
from frappe.utils import getdate, add_days


@frappe.whitelist()
def get_attendance_data(from_date, to_date, batch):
	students = frappe.get_all(
		"EE Student",
		filters={"batch": batch},
		fields=["name", "student_name"],
		order_by="student_name asc",
	)

	if not students:
		return {"students": [], "attendance": {}}

	student_ids = [s.name for s in students]

	records = frappe.get_all(
		"EE Student Attendance",
		filters={
			"student": ["in", student_ids],
			"date": ["between", [from_date, to_date]],
		},
		fields=["student", "date", "session"],
	)

	# Build lookup: "student_id|date|session" -> "present"
	attendance = {}
	for r in records:
		key = f"{r.student}|{str(r.date)}|{r.session}"
		attendance[key] = "present"

	# Fill absent for dates that have at least one attendance record (class happened)
	# Collect dates where class happened per session
	class_dates = {}
	for r in records:
		session_key = f"{str(r.date)}|{r.session}"
		class_dates[session_key] = True

	# Mark absent for students missing on class dates
	for student in students:
		for session_key in class_dates:
			date_str, session = session_key.rsplit("|", 1)
			key = f"{student.name}|{date_str}|{session}"
			if key not in attendance:
				attendance[key] = "absent"

	return {"students": students, "attendance": attendance}
