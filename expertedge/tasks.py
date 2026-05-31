import frappe
from frappe.utils import now_datetime, add_to_date, nowdate


def sync_google_sheet_leads():
	"""Pull new leads from Google Sheet every 15 minutes."""
	try:
		from expertedge.google_sheets import sync_leads_from_sheet
		count = sync_leads_from_sheet()
		if count:
			frappe.logger().info(f"Google Sheet sync: {count} new leads imported")
	except Exception:
		frappe.log_error("Google Sheet lead sync failed")


def check_first_contact_sla():
	"""Leads in New/Contacted past first_contact_sla_minutes with no first_contacted_on."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	sla_minutes = settings.first_contact_sla_minutes or 30
	cutoff = add_to_date(now_datetime(), minutes=-sla_minutes)

	leads = frappe.get_all(
		"EE Lead",
		filters={
			"status": ["in", ["New", "Contacted"]],
			"first_contacted_on": ["is", "not set"],
			"lead_received_on": ["<", cutoff],
			"converted": 0,
		},
		fields=["name", "lead_name", "handled_by", "owner"],
	)

	for lead in leads:
		allocated_to = lead.handled_by or lead.owner
		_ensure_sla_todo(
			"EE Lead",
			lead.name,
			allocated_to,
			f"SLA BREACH: Lead {lead.lead_name} not contacted within {sla_minutes} min",
		)


def check_doc_sla():
	"""Leads in Docs Requested past doc_turnaround_sla_hours."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	sla_hours = settings.doc_turnaround_sla_hours or 48
	cutoff = add_to_date(now_datetime(), hours=-sla_hours)

	leads = frappe.get_all(
		"EE Lead",
		filters={
			"status": "Docs Requested",
			"docs_requested_on": ["<", cutoff],
			"docs_received_on": ["is", "not set"],
			"converted": 0,
		},
		fields=["name", "lead_name", "handled_by", "owner"],
	)

	for lead in leads:
		allocated_to = lead.handled_by or lead.owner
		_ensure_sla_todo(
			"EE Lead",
			lead.name,
			allocated_to,
			f"SLA: Documents not received for {lead.lead_name} — follow up",
		)


def check_payment_sla():
	"""Students in Pre-Approval Pending or Balance Pending past SLA."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")

	# Pre-approval SLA
	pa_hours = settings.post_counselling_payment_sla_hours or 24
	pa_cutoff = add_to_date(now_datetime(), hours=-pa_hours)

	students = frappe.get_all(
		"EE Student",
		filters={
			"status": "Pre-Approval Pending",
			"creation": ["<", pa_cutoff],
		},
		fields=["name", "student_name", "handled_by", "owner"],
	)

	for s in students:
		allocated_to = s.handled_by or s.owner
		_ensure_sla_todo(
			"EE Student",
			s.name,
			allocated_to,
			f"SLA: Pre-approval pending for {s.student_name} — follow up",
		)

	# Balance payment SLA
	fp_days = settings.full_payment_sla_days or 7
	fp_cutoff = add_to_date(now_datetime(), days=-fp_days)

	students = frappe.get_all(
		"EE Student",
		filters={
			"status": "Balance Pending",
			"creation": ["<", fp_cutoff],
		},
		fields=["name", "student_name", "handled_by", "owner"],
	)

	for s in students:
		allocated_to = s.handled_by or s.owner
		_ensure_sla_todo(
			"EE Student",
			s.name,
			allocated_to,
			f"SLA: Balance payment pending for {s.student_name} — follow up",
		)


def check_nomod_payments():
	"""Poll Nomod API for paid charges on open payment links.

	Only checks links that:
	- Are in Generated/Sent status
	- Were generated more than 30 min ago (give callback time to fire first)
	- Have a real nomod_reference (not placeholder)
	- Nomod integration is enabled
	"""
	nomod_settings = frappe.get_cached_doc("Nomod Settings")
	if not nomod_settings.enabled:
		return

	cutoff = add_to_date(now_datetime(), minutes=-30)

	open_links = frappe.get_all(
		"EE Nomod Payment Link",
		filters={
			"status": ["in", ["Generated", "Sent"]],
			"generated_on": ["<", cutoff],
			"nomod_reference": ["not like", "PLACEHOLDER%"],
		},
		fields=["name", "nomod_reference"],
	)

	if not open_links:
		return

	from expertedge.nomod import list_charges, NomodAPIError

	for link_doc in open_links:
		try:
			charges = list_charges(link_id=link_doc.nomod_reference)
			paid_charges = [
				c for c in charges.get("results", [])
				if c.get("status") in ("captured", "paid")
			]

			if paid_charges:
				link = frappe.get_doc("EE Nomod Payment Link", link_doc.name)
				link.mark_paid()
				frappe.db.commit()
				frappe.logger().info(f"Nomod auto-paid: {link_doc.name}")

		except NomodAPIError as e:
			frappe.log_error(
				title=f"Nomod poll error: {link_doc.name}",
				message=str(e),
			)
		except Exception as e:
			frappe.log_error(
				title=f"Nomod poll error: {link_doc.name}",
				message=str(e),
			)


def _ensure_sla_todo(doctype, docname, allocated_to, description):
	"""Create a ToDo if an open one with same description doesn't exist (idempotent)."""
	existing = frappe.db.exists("ToDo", {
		"reference_type": doctype,
		"reference_name": docname,
		"allocated_to": allocated_to,
		"description": description,
		"status": "Open",
	})
	if not existing:
		frappe.get_doc({
			"doctype": "ToDo",
			"allocated_to": allocated_to,
			"reference_type": doctype,
			"reference_name": docname,
			"description": description,
			"date": nowdate(),
			"status": "Open",
		}).insert(ignore_permissions=True)
