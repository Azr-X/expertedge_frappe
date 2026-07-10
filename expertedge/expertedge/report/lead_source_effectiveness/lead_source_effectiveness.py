import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"fieldname": "lead_source", "label": "Lead Source", "fieldtype": "Data", "width": 200},
		{"fieldname": "total_leads", "label": "Total Leads", "fieldtype": "Int", "width": 130},
		{"fieldname": "total_students", "label": "Total Students", "fieldtype": "Int", "width": 140},
		{"fieldname": "effectiveness", "label": "Effectiveness %", "fieldtype": "Percent", "width": 140},
	]

	conditions = ""
	student_conditions = ""
	if filters.get("batch"):
		student_conditions += " AND s.batch = %(batch)s"
	if filters.get("program"):
		conditions += " AND l.program = %(program)s"
		student_conditions += " AND s.program = %(program)s"

	lead_counts = frappe.db.sql("""
		SELECT IFNULL(l.lead_source, 'Unknown') as lead_source, COUNT(*) as total_leads
		FROM `tabEE Lead` l
		WHERE 1=1 {conditions}
		GROUP BY IFNULL(l.lead_source, 'Unknown')
	""".format(conditions=conditions), filters, as_dict=True)

	lead_map = {r.lead_source: r.total_leads for r in lead_counts}

	student_counts = frappe.db.sql("""
		SELECT IFNULL(l.lead_source, 'Unknown') as lead_source, COUNT(*) as total_students
		FROM `tabEE Student` s
		LEFT JOIN `tabEE Lead` l ON s.lead = l.name
		WHERE s.lead IS NOT NULL AND s.lead != ''
			{student_conditions}
		GROUP BY IFNULL(l.lead_source, 'Unknown')
	""".format(student_conditions=student_conditions), filters, as_dict=True)

	student_map = {r.lead_source: r.total_students for r in student_counts}

	# Count students without a lead link
	direct = frappe.db.sql("""
		SELECT COUNT(*) as cnt FROM `tabEE Student` s
		WHERE (s.lead IS NULL OR s.lead = '') {student_conditions}
	""".format(student_conditions=student_conditions), filters)[0][0]
	if direct:
		student_map["Direct (No Lead)"] = direct

	all_sources = set(lead_map.keys()) | set(student_map.keys())
	data = []
	for source in sorted(all_sources):
		leads = lead_map.get(source, 0)
		students = student_map.get(source, 0)
		effectiveness = (students / leads * 100) if leads else (100.0 if students else 0)
		data.append({
			"lead_source": source,
			"total_leads": leads,
			"total_students": students,
			"effectiveness": flt(effectiveness, 1),
		})

	data.sort(key=lambda x: x["total_students"], reverse=True)

	chart = {
		"data": {
			"labels": [d["lead_source"] for d in data],
			"datasets": [
				{"name": "Leads", "values": [d["total_leads"] for d in data]},
				{"name": "Students", "values": [d["total_students"] for d in data]},
			],
		},
		"type": "bar",
	} if data else None

	return columns, data, None, chart
