import frappe
from frappe.utils import getdate


def execute(filters=None):
	columns = [
		{"fieldname": "call_on", "label": "Date/Time", "fieldtype": "Datetime", "width": 160},
		{"fieldname": "caller", "label": "Called By", "fieldtype": "Link", "options": "User", "width": 180},
		{"fieldname": "parent_type", "label": "Source", "fieldtype": "Data", "width": 100},
		{"fieldname": "parent", "label": "Record", "fieldtype": "Dynamic Link", "options": "parent_type", "width": 160},
		{"fieldname": "candidate", "label": "Candidate", "fieldtype": "Data", "width": 180},
		{"fieldname": "direction", "label": "Direction", "fieldtype": "Data", "width": 90},
		{"fieldname": "call_result", "label": "Result", "fieldtype": "Data", "width": 140},
		{"fieldname": "duration_min", "label": "Duration", "fieldtype": "Float", "width": 80},
		{"fieldname": "summary", "label": "Notes", "fieldtype": "Data", "width": 250},
	]

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	conditions = "WHERE DATE(cl.call_on) BETWEEN %(from_date)s AND %(to_date)s"
	params = {"from_date": from_date, "to_date": to_date}

	if filters.get("call_result"):
		conditions += " AND cl.call_result = %(call_result)s"
		params["call_result"] = filters["call_result"]

	data = frappe.db.sql(f"""
		SELECT
			cl.call_on, cl.caller, cl.parenttype as parent_type, cl.parent,
			COALESCE(l.lead_name, s.student_name) as candidate,
			cl.direction, cl.call_result, cl.duration_min, cl.summary
		FROM `tabEE Call Log` cl
		LEFT JOIN `tabEE Lead` l ON l.name = cl.parent AND cl.parenttype = 'EE Lead'
		LEFT JOIN `tabEE Student` s ON s.name = cl.parent AND cl.parenttype = 'EE Student'
		{conditions}
		ORDER BY cl.call_on DESC
	""", params, as_dict=True)

	return columns, data
