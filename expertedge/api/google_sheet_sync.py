import frappe
from frappe import _


@frappe.whitelist()
def sync_now():
	"""Pull new leads from Google Sheet into EE Lead. Manual trigger."""
	from expertedge.google_sheets import sync_leads_from_sheet

	count = sync_leads_from_sheet()
	frappe.msgprint(_(f"{count} new leads imported from Google Sheet"), indicator="green")
	return count
