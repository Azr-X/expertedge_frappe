"""REST webhook endpoint for ad-platform lead intake (Meta / LinkedIn lead-ads).

Expected payload keys (map your ad platform's fields to these):
	- full_name (or lead_name)
	- email
	- mobile_no (or phone_number)
	- nationality (optional)
	- highest_qualification (optional)
	- years_of_experience (optional)
	- current_designation (optional)
	- lead_source (e.g. "Instagram", "Facebook", "LinkedIn")
	- campaign (optional — ad campaign ID or name)
	- program (optional — EE Program name)

Usage:
	POST /api/method/expertedge.api.lead_webhook.webhook
	Content-Type: application/json
	Body: { "full_name": "...", "email": "...", ... }
"""

import frappe
from expertedge.intake import create_lead


@frappe.whitelist(allow_guest=True)
def webhook(**kwargs):
	# Normalize common field name variations from ad platforms
	payload = {
		"full_name": kwargs.get("full_name") or kwargs.get("lead_name") or kwargs.get("name"),
		"email": kwargs.get("email") or kwargs.get("email_address"),
		"mobile_no": kwargs.get("mobile_no") or kwargs.get("phone_number") or kwargs.get("phone"),
		"nationality": kwargs.get("nationality") or kwargs.get("country"),
		"highest_qualification": kwargs.get("highest_qualification") or kwargs.get("qualification"),
		"years_of_experience": kwargs.get("years_of_experience") or kwargs.get("experience"),
		"current_designation": kwargs.get("current_designation") or kwargs.get("job_title"),
		"lead_source": kwargs.get("lead_source") or kwargs.get("source"),
		"campaign": kwargs.get("campaign") or kwargs.get("campaign_id") or kwargs.get("ad_id"),
		"program": kwargs.get("program"),
	}

	lead_name = create_lead(payload)
	return {"status": "ok", "lead": lead_name}
