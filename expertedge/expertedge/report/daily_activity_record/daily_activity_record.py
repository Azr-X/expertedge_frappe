import frappe
from frappe.utils import getdate, get_datetime, time_diff_in_hours, flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "attendance_date", "label": "Date", "fieldtype": "Date", "width": 110},
		{"fieldname": "employee", "label": "User", "fieldtype": "Link", "options": "User", "width": 180},
		{"fieldname": "employee_name", "label": "Full Name", "fieldtype": "Data", "width": 150},
		{"fieldname": "check_in", "label": "Check In", "fieldtype": "Datetime", "width": 170},
		{"fieldname": "check_out", "label": "Check Out", "fieldtype": "Datetime", "width": 170},
		{"fieldname": "total_hours", "label": "Hours Worked", "fieldtype": "Float", "width": 100, "precision": 2},
		{"fieldname": "auto_checked_out", "label": "Auto Out", "fieldtype": "Check", "width": 80},
		{"fieldname": "leads_created", "label": "Leads Created", "fieldtype": "Int", "width": 110},
		{"fieldname": "leads_contacted", "label": "Leads Contacted", "fieldtype": "Int", "width": 120},
		{"fieldname": "students_converted", "label": "Conversions", "fieldtype": "Int", "width": 100},
		{"fieldname": "activities_logged", "label": "Activities", "fieldtype": "Int", "width": 90},
		{"fieldname": "comments_added", "label": "Comments", "fieldtype": "Int", "width": 90},
		{"fieldname": "versions_count", "label": "Changes Made", "fieldtype": "Int", "width": 110},
	]


def get_data(filters):
	conditions = {"attendance_date": ["between", [filters.get("from_date"), filters.get("to_date")]]}
	if filters.get("user"):
		conditions["employee"] = filters.get("user")

	attendance_records = frappe.get_all(
		"EE Attendance",
		filters=conditions,
		fields=["name", "employee", "employee_name", "attendance_date", "check_in",
				"check_out", "total_hours", "auto_checked_out", "status"],
		order_by="attendance_date asc, check_in asc",
	)

	data = []
	for att in attendance_records:
		check_in = att.check_in
		check_out = att.check_out

		# Count leads created by this user during their shift
		lead_filters = {"owner": att.employee, "creation": ["between", [check_in, check_out or frappe.utils.now_datetime()]]}
		leads_created = frappe.db.count("EE Lead", lead_filters)

		# Leads first contacted during shift
		leads_contacted = frappe.db.count("EE Lead", {
			"handled_by": att.employee,
			"first_contacted_on": ["between", [check_in, check_out or frappe.utils.now_datetime()]],
		})

		# Students converted during shift
		students_converted = frappe.db.count("EE Student", {
			"owner": att.employee,
			"creation": ["between", [check_in, check_out or frappe.utils.now_datetime()]],
		})

		# Comments added during shift
		comments_added = frappe.db.count("Comment", {
			"owner": att.employee,
			"comment_type": "Comment",
			"creation": ["between", [check_in, check_out or frappe.utils.now_datetime()]],
		})

		# Version/changes made during shift
		versions_count = frappe.db.count("Version", {
			"owner": att.employee,
			"creation": ["between", [check_in, check_out or frappe.utils.now_datetime()]],
		})

		# Activity log entries (from EE Activity child table — count via SQL)
		activities_logged = frappe.db.sql("""
			SELECT COUNT(*) FROM `tabEE Activity`
			WHERE user = %s AND activity_on BETWEEN %s AND %s
		""", (att.employee, check_in, check_out or frappe.utils.now_datetime()))[0][0]

		data.append({
			"attendance_date": att.attendance_date,
			"employee": att.employee,
			"employee_name": att.employee_name,
			"check_in": att.check_in,
			"check_out": att.check_out,
			"total_hours": att.total_hours,
			"auto_checked_out": att.auto_checked_out,
			"leads_created": leads_created,
			"leads_contacted": leads_contacted,
			"students_converted": students_converted,
			"activities_logged": activities_logged,
			"comments_added": comments_added,
			"versions_count": versions_count,
		})

	return data
