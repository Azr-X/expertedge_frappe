import frappe


def get_email_recipients(email_type):
	"""Get configured recipients for an email type from ExpertEdge Settings."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	recipients = []
	for row in (settings.email_recipients or []):
		if row.email_type == email_type:
			recipients.append(row.user)
	return recipients
