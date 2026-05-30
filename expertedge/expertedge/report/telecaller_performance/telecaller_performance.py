import frappe
from frappe.utils import getdate


def execute(filters=None):
	columns = [
		{"fieldname": "caller", "label": "Telecaller", "fieldtype": "Link", "options": "User", "width": 200},
		{"fieldname": "total_calls", "label": "Total Calls", "fieldtype": "Int", "width": 100},
		{"fieldname": "connected", "label": "Connected", "fieldtype": "Int", "width": 100},
		{"fieldname": "connection_rate", "label": "Connection %", "fieldtype": "Percent", "width": 110},
		{"fieldname": "leads_handled", "label": "Leads Handled", "fieldtype": "Int", "width": 120},
		{"fieldname": "contacted_in_sla", "label": "Contacted in SLA", "fieldtype": "Int", "width": 130},
		{"fieldname": "sla_rate", "label": "SLA %", "fieldtype": "Percent", "width": 100},
		{"fieldname": "conversions", "label": "Conversions", "fieldtype": "Int", "width": 100},
		{"fieldname": "conversion_rate", "label": "Conv %", "fieldtype": "Percent", "width": 100},
	]

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	# Call stats from EE Call Log child table
	call_data = frappe.db.sql("""
		SELECT
			cl.caller,
			COUNT(*) as total_calls,
			SUM(CASE WHEN cl.call_result = 'Connected' THEN 1 ELSE 0 END) as connected
		FROM `tabEE Call Log` cl
		JOIN `tabEE Lead` l ON l.name = cl.parent AND cl.parenttype = 'EE Lead'
		WHERE DATE(cl.call_on) BETWEEN %s AND %s
		GROUP BY cl.caller
	""", (from_date, to_date), as_dict=True)

	caller_map = {r.caller: r for r in call_data}

	# Leads handled
	leads_data = frappe.db.sql("""
		SELECT handled_by, COUNT(*) as leads_handled,
			SUM(CASE WHEN status = 'Converted' THEN 1 ELSE 0 END) as conversions
		FROM `tabEE Lead`
		WHERE handled_by IS NOT NULL AND handled_by != ''
		GROUP BY handled_by
	""", as_dict=True)

	leads_map = {r.handled_by: r for r in leads_data}

	# SLA: leads where first_contacted_on is within SLA
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	sla_minutes = settings.first_contact_sla_minutes or 30

	sla_data = frappe.db.sql("""
		SELECT handled_by,
			SUM(CASE WHEN TIMESTAMPDIFF(MINUTE, lead_received_on, first_contacted_on) <= %s THEN 1 ELSE 0 END) as in_sla
		FROM `tabEE Lead`
		WHERE first_contacted_on IS NOT NULL AND handled_by IS NOT NULL
		GROUP BY handled_by
	""", (sla_minutes,), as_dict=True)

	sla_map = {r.handled_by: r.in_sla for r in sla_data}

	all_users = set(list(caller_map.keys()) + list(leads_map.keys()))
	data = []

	for user in sorted(all_users):
		calls = caller_map.get(user, {})
		leads = leads_map.get(user, {})
		total_calls = calls.get("total_calls", 0) if isinstance(calls, dict) else 0
		connected = calls.get("connected", 0) if isinstance(calls, dict) else 0
		leads_handled = leads.get("leads_handled", 0) if isinstance(leads, dict) else 0
		conversions = leads.get("conversions", 0) if isinstance(leads, dict) else 0
		contacted_in_sla = sla_map.get(user, 0)

		data.append({
			"caller": user,
			"total_calls": total_calls,
			"connected": connected,
			"connection_rate": (connected / total_calls * 100) if total_calls else 0,
			"leads_handled": leads_handled,
			"contacted_in_sla": contacted_in_sla,
			"sla_rate": (contacted_in_sla / leads_handled * 100) if leads_handled else 0,
			"conversions": conversions,
			"conversion_rate": (conversions / leads_handled * 100) if leads_handled else 0,
		})

	return columns, data
