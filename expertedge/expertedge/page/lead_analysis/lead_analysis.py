import frappe
from frappe.utils import getdate


@frappe.whitelist()
def get_lead_data(from_date, to_date):
	leads = frappe.get_all(
		"EE Lead",
		filters={
			"lead_received_on": ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]],
		},
		fields=[
			"name", "lead_name", "lead_source", "status",
			"handled_by", "lead_received_on",
		],
		order_by="lead_received_on desc",
		limit_page_length=0,
	)

	lead_names = [l.name for l in leads]
	notes_map = get_latest_call_notes(lead_names)
	user_names = get_user_full_names(set(l.handled_by for l in leads if l.handled_by))

	result = []
	for lead in leads:
		result.append({
			"name": lead.name,
			"lead_name": lead.lead_name,
			"lead_source": lead.lead_source or "Unknown",
			"status": lead.status,
			"handled_by": lead.handled_by,
			"handled_by_name": user_names.get(lead.handled_by, ""),
			"lead_date": str(getdate(lead.lead_received_on)),
			"latest_notes": notes_map.get(lead.name, ""),
		})

	return result


def get_latest_call_notes(lead_names):
	if not lead_names:
		return {}

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


def get_user_full_names(users):
	if not users:
		return {}
	result = {}
	for user in users:
		result[user] = frappe.db.get_value("User", user, "full_name") or user
	return result


@frappe.whitelist()
def get_lead_detail(lead_name):
	lead = frappe.get_doc("EE Lead", lead_name)
	user_names = get_user_full_names(
		set(filter(None, [lead.handled_by, lead.counsellor] + [r.caller for r in lead.call_log]))
	)

	call_logs = []
	for row in sorted(lead.call_log, key=lambda r: r.call_on or "", reverse=True):
		call_logs.append({
			"call_on": str(row.call_on) if row.call_on else "",
			"caller": user_names.get(row.caller, row.caller or ""),
			"direction": row.direction,
			"call_result": row.call_result,
			"duration_min": row.duration_min,
			"summary": row.summary,
			"next_call_on": str(row.next_call_on) if row.next_call_on else "",
		})

	return {
		"name": lead.name,
		"lead_name": lead.lead_name,
		"email": lead.email,
		"mobile_no": lead.mobile_no,
		"status": lead.status,
		"lead_source": lead.lead_source,
		"handled_by": user_names.get(lead.handled_by, lead.handled_by or ""),
		"counsellor": user_names.get(lead.counsellor, lead.counsellor or ""),
		"nationality": lead.nationality,
		"program": lead.program,
		"preferred_batch": lead.preferred_batch,
		"priority": lead.priority,
		"remarks": lead.remarks,
		"next_action": lead.next_action,
		"next_action_date": str(lead.next_action_date) if lead.next_action_date else "",
		"lead_received_on": str(lead.lead_received_on) if lead.lead_received_on else "",
		"first_contacted_on": str(lead.first_contacted_on) if lead.first_contacted_on else "",
		"call_logs": call_logs,
	}
