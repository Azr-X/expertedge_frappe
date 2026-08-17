import frappe
from frappe.utils import cint


def execute(filters=None):
	filters = filters or {}

	columns = [
		{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "EE Student", "width": 150},
		{"fieldname": "student_name", "label": "Name", "fieldtype": "Data", "width": 180},
		{"fieldname": "batch", "label": "Batch", "fieldtype": "Link", "options": "EE Batch", "width": 140},
		{"fieldname": "program", "label": "Program", "fieldtype": "Link", "options": "EE Program", "width": 140},
		{"fieldname": "required", "label": "Required", "fieldtype": "Int", "width": 90},
		{"fieldname": "submitted", "label": "Submitted", "fieldtype": "Int", "width": 95},
		{"fieldname": "accepted", "label": "Accepted", "fieldtype": "Int", "width": 95},
		{"fieldname": "pending", "label": "Pending", "fieldtype": "Int", "width": 90},
		{"fieldname": "assignment_status", "label": "Status", "fieldtype": "Data", "width": 120},
	]

	conditions = ""
	if filters.get("batch"):
		conditions += " AND s.batch = %(batch)s"
	if filters.get("program"):
		conditions += " AND s.program = %(program)s"

	students = frappe.db.sql("""
		SELECT s.name, s.student_name, s.batch, s.program,
			s.override_assignments_required, s.assignments_required,
			b.assignments_required AS batch_required
		FROM `tabEE Student` s
		LEFT JOIN `tabEE Batch` b ON s.batch = b.name
		WHERE 1=1 {conditions}
		ORDER BY s.batch ASC, s.student_name ASC
	""".format(conditions=conditions), filters, as_dict=True)

	counts = frappe.db.sql("""
		SELECT student, status, COUNT(*) AS cnt
		FROM `tabEE Assignment Submission`
		GROUP BY student, status
	""", as_dict=True)

	tally = {}
	for row in counts:
		tally.setdefault(row.student, {})[row.status] = cint(row.cnt)

	data = []
	for s in students:
		required = (
			cint(s.assignments_required)
			if cint(s.override_assignments_required)
			else cint(s.batch_required)
		)
		by_status = tally.get(s.name, {})
		submitted = (
			by_status.get("Submitted", 0)
			+ by_status.get("Under Review", 0)
			+ by_status.get("Accepted", 0)
		)
		accepted = by_status.get("Accepted", 0)

		if required <= 0:
			status = "Not Required"
		elif accepted >= required:
			status = "Complete"
		else:
			status = "Pending"

		if filters.get("status") and filters["status"] != status:
			continue

		data.append({
			"student": s.name,
			"student_name": s.student_name,
			"batch": s.batch,
			"program": s.program,
			"required": required,
			"submitted": submitted,
			"accepted": accepted,
			"pending": max(required - accepted, 0),
			"assignment_status": status,
		})

	return columns, data
