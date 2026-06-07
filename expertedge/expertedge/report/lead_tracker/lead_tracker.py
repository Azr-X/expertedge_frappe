import frappe
from frappe.utils import getdate, formatdate
from collections import OrderedDict


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "label", "label": "Lead", "fieldtype": "Data", "width": 300},
		{"fieldname": "count", "label": "Count", "fieldtype": "Int", "width": 80},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 130},
		{"fieldname": "handled_by", "label": "Handled By", "fieldtype": "Data", "width": 160},
		{"fieldname": "latest_notes", "label": "Latest Call Notes", "fieldtype": "Data", "width": 350},
	]


def get_data(filters):
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	source_filter = filters.get("lead_source")

	conditions = {
		"lead_received_on": ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]],
	}
	if source_filter:
		conditions["lead_source"] = source_filter

	leads = frappe.get_all(
		"EE Lead",
		filters=conditions,
		fields=[
			"name", "lead_name", "lead_source", "status",
			"handled_by", "lead_received_on",
		],
		order_by="lead_received_on asc",
		limit_page_length=0,
	)

	# Get latest call log summary for all leads in one query
	latest_notes = get_latest_call_notes([l.name for l in leads])

	# Group by date -> source
	tree = OrderedDict()
	for lead in leads:
		date_key = str(getdate(lead.lead_received_on))
		source_key = lead.lead_source or "Unknown"
		tree.setdefault(date_key, OrderedDict())
		tree[date_key].setdefault(source_key, [])
		tree[date_key][source_key].append(lead)

	data = []
	for date_key in sorted(tree.keys()):
		date_label = formatdate(date_key)
		date_count = sum(len(v) for v in tree[date_key].values())
		data.append({
			"label": date_label,
			"count": date_count,
			"status": "",
			"handled_by": "",
			"latest_notes": "",
			"indent": 0,
		})

		for source_key in sorted(tree[date_key].keys()):
			source_leads = tree[date_key][source_key]
			data.append({
				"label": source_key,
				"count": len(source_leads),
				"source": source_key,
				"status": "",
				"handled_by": "",
				"latest_notes": "",
				"indent": 1,
			})

			for lead in source_leads:
				handled_by_name = ""
				if lead.handled_by:
					handled_by_name = frappe.db.get_value("User", lead.handled_by, "full_name") or lead.handled_by

				data.append({
					"label": f"{lead.name}: {lead.lead_name}",
					"count": "",
						"status": lead.status,
					"handled_by": handled_by_name,
					"latest_notes": latest_notes.get(lead.name, ""),
					"indent": 2,
				})

	return data


def get_latest_call_notes(lead_names):
	"""Get the latest call log summary for each lead in bulk."""
	if not lead_names:
		return {}

	# EE Call Log is child table of EE Lead, parent field = "parent"
	logs = frappe.db.sql("""
		SELECT parent, summary
		FROM `tabEE Call Log`
		WHERE parent IN %(leads)s
		ORDER BY call_on DESC, idx DESC
	""", {"leads": lead_names}, as_dict=True)

	result = {}
	for log in logs:
		if log.parent not in result and log.summary:
			result[log.parent] = log.summary

	return result
