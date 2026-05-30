import frappe


def execute(filters=None):
	columns = [
		{"fieldname": "counsellor", "label": "Counsellor", "fieldtype": "Link", "options": "User", "width": 200},
		{"fieldname": "sessions", "label": "Sessions Done", "fieldtype": "Int", "width": 120},
		{"fieldname": "fit_confirmed", "label": "Fit-Confirmed", "fieldtype": "Int", "width": 120},
		{"fieldname": "fit_rate", "label": "Fit-Confirmed %", "fieldtype": "Percent", "width": 130},
		{"fieldname": "enrollments", "label": "Enrollments", "fieldtype": "Int", "width": 120},
	]

	session_data = frappe.db.sql("""
		SELECT
			counsellor,
			COUNT(*) as sessions,
			SUM(CASE WHEN outcome = 'Fit – Confirmed' THEN 1 ELSE 0 END) as fit_confirmed
		FROM `tabEE Counselling Session`
		WHERE outcome IS NOT NULL AND outcome != ''
		GROUP BY counsellor
	""", as_dict=True)

	enrollment_data = frappe.db.sql("""
		SELECT counsellor, COUNT(*) as enrollments
		FROM `tabEE Student`
		WHERE status IN ('Enrolled', 'Materials Issued')
		GROUP BY counsellor
	""", as_dict=True)

	enrollment_map = {r.counsellor: r.enrollments for r in enrollment_data}

	data = []
	for row in session_data:
		data.append({
			"counsellor": row.counsellor,
			"sessions": row.sessions,
			"fit_confirmed": row.fit_confirmed,
			"fit_rate": (row.fit_confirmed / row.sessions * 100) if row.sessions else 0,
			"enrollments": enrollment_map.get(row.counsellor, 0),
		})

	return columns, data
