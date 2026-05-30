import frappe
from frappe import _


def create_lead(payload):
	"""Shared normalizer for lead creation from any intake path.

	Args:
		payload (dict): Keys: full_name, email, mobile_no, nationality,
			highest_qualification, years_of_experience, current_designation,
			lead_source, campaign, program.

	Returns:
		str: Name of created/existing EE Lead.

	De-dupe rule: if an open (non-Lost, non-Converted) lead with same email
	or mobile exists, append a comment/activity instead of creating a duplicate.
	"""
	email = (payload.get("email") or "").strip().lower()
	mobile = (payload.get("mobile_no") or "").strip()

	if not email and not mobile:
		frappe.throw(_("Email or Mobile is required to create a lead"))

	# De-dupe check
	filters = {
		"status": ["not in", ["Lost", "Converted"]],
	}
	or_filters = []
	if email:
		or_filters.append({"email": email})
	if mobile:
		or_filters.append({"mobile_no": mobile})

	existing = frappe.get_all(
		"EE Lead",
		filters=filters,
		or_filters=or_filters,
		fields=["name"],
		limit=1,
	)

	if existing:
		lead = frappe.get_doc("EE Lead", existing[0].name)
		lead.append("activity_log", {
			"activity_type": "System",
			"summary": f"Duplicate intake received — source: {payload.get('lead_source', 'Unknown')}",
			"user": frappe.session.user,
		})
		lead.add_comment("Comment", f"Duplicate lead submission from {payload.get('lead_source', 'Unknown')}")
		lead.save(ignore_permissions=True)
		return lead.name

	# Create new lead
	lead = frappe.get_doc({
		"doctype": "EE Lead",
		"lead_name": payload.get("full_name") or payload.get("lead_name"),
		"email": email,
		"mobile_no": mobile,
		"nationality": payload.get("nationality"),
		"highest_qualification": payload.get("highest_qualification"),
		"years_of_experience": payload.get("years_of_experience"),
		"current_designation": payload.get("current_designation"),
		"lead_source": payload.get("lead_source"),
		"campaign": payload.get("campaign"),
		"program": payload.get("program"),
	})
	lead.insert(ignore_permissions=True)
	return lead.name
