import frappe


def execute(filters=None):
	columns = [
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 200},
		{"fieldname": "count", "label": "Count", "fieldtype": "Int", "width": 120},
		{"fieldname": "percentage", "label": "% of Total", "fieldtype": "Percent", "width": 120},
	]

	statuses = [
		"New", "Contacted", "Brochure Sent", "Docs Requested", "Docs Received",
		"Docs Verified", "Counselling Scheduled", "Counselling Done",
		"Confirmed", "Converted", "Lost",
	]

	total = frappe.db.count("EE Lead") or 1
	data = []

	for status in statuses:
		count = frappe.db.count("EE Lead", {"status": status})
		data.append({
			"status": status,
			"count": count,
			"percentage": (count / total) * 100,
		})

	converted = frappe.db.count("EE Lead", {"status": "Converted"})
	data.append({
		"status": "Conversion Rate",
		"count": converted,
		"percentage": (converted / total) * 100,
	})

	return columns, data
