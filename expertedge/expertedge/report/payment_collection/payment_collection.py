import frappe
from frappe.utils import flt, date_diff, nowdate


def execute(filters=None):
	columns = [
		{"fieldname": "student", "label": "Student", "fieldtype": "Link", "options": "EE Student", "width": 150},
		{"fieldname": "student_name", "label": "Name", "fieldtype": "Data", "width": 180},
		{"fieldname": "batch", "label": "Batch", "fieldtype": "Link", "options": "EE Batch", "width": 180},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 130},
		{"fieldname": "net_fee", "label": "Net Fee (AED)", "fieldtype": "Currency", "width": 120},
		{"fieldname": "total_paid", "label": "Total Paid (AED)", "fieldtype": "Currency", "width": 130},
		{"fieldname": "outstanding", "label": "Outstanding (AED)", "fieldtype": "Currency", "width": 130},
		{"fieldname": "days_since_creation", "label": "Days Since Start", "fieldtype": "Int", "width": 120},
	]

	students = frappe.get_all(
		"EE Student",
		fields=["name", "student_name", "batch", "status", "net_fee", "total_paid", "outstanding", "creation"],
		order_by="outstanding desc",
	)

	data = []
	for s in students:
		data.append({
			"student": s.name,
			"student_name": s.student_name,
			"batch": s.batch,
			"status": s.status,
			"net_fee": flt(s.net_fee),
			"total_paid": flt(s.total_paid),
			"outstanding": flt(s.outstanding),
			"days_since_creation": date_diff(nowdate(), s.creation),
		})

	return columns, data
