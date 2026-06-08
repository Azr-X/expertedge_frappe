"""Merge duplicate EE Leads — keep the oldest, absorb data from newer duplicates.

Duplicates identified by email OR normalized mobile (last 9 digits).
For each duplicate group:
  - Primary = oldest by creation date
  - Fill empty fields on primary from duplicates (first non-empty wins)
  - Merge child table rows (call_log, activity_log, documents) into primary
  - Re-link ToDo, Comment, Communication, EE Counselling Session references
  - Add merge note to activity log
  - Delete duplicate leads
"""

import re
import frappe
from frappe.utils import now_datetime


# Data fields that can be filled from duplicates (skip structural/auto fields)
MERGE_FIELDS = [
	"lead_name", "email", "mobile_no", "date_of_birth", "nationality", "state",
	"permanent_address", "pincode", "highest_qualification", "specialization",
	"year_of_qualification", "institution", "years_of_experience",
	"current_designation", "current_employer", "program", "lead_source",
	"campaign", "handled_by", "counsellor", "preferred_batch", "priority",
	"next_action", "next_action_date", "remarks", "sheet_lead_id",
	"counselling_outcome", "latest_session",
]

# Timestamp fields — keep the earliest non-null value
TIMESTAMP_FIELDS = [
	"lead_received_on", "first_contacted_on", "brochure_sent_on",
	"docs_requested_on", "docs_received_on", "docs_verified_on",
	"counselling_done_on", "confirmed_on",
]

# Status priority — higher index = more progressed
STATUS_ORDER = [
	"New", "Contacted", "Brochure Sent", "Docs Requested", "Docs Received",
	"Docs Verified", "Counselling Scheduled", "Counselling Done",
	"Confirmed", "Converted", "Lost",
]


def _normalize_phone(phone_str):
	if not phone_str:
		return ""
	digits = re.sub(r"[^\d]", "", phone_str)
	if digits.startswith("00"):
		digits = digits[2:]
	return digits[-9:] if len(digits) >= 9 else digits


def _find_duplicate_groups():
	"""Find groups of leads that share email or normalized mobile."""
	leads = frappe.get_all(
		"EE Lead",
		fields=["name", "email", "mobile_no", "creation"],
		order_by="creation asc",
		limit_page_length=0,
	)

	# Build lookup maps
	email_map = {}  # email -> [lead_names]
	phone_map = {}  # normalized_phone -> [lead_names]

	for lead in leads:
		if lead.email:
			key = lead.email.strip().lower()
			# Skip placeholder emails
			if not key.endswith("@placeholder.local"):
				email_map.setdefault(key, []).append(lead.name)

		norm = _normalize_phone(lead.mobile_no)
		if norm and len(norm) >= 7:
			phone_map.setdefault(norm, []).append(lead.name)

	# Union-find to merge groups connected by email or phone
	parent = {}

	def find(x):
		while parent.get(x, x) != x:
			parent[x] = parent.get(parent[x], parent[x])
			x = parent[x]
		return x

	def union(a, b):
		ra, rb = find(a), find(b)
		if ra != rb:
			parent[rb] = ra

	for names in email_map.values():
		if len(names) > 1:
			for n in names[1:]:
				union(names[0], n)

	for names in phone_map.values():
		if len(names) > 1:
			for n in names[1:]:
				union(names[0], n)

	# Collect groups
	groups = {}
	all_grouped = set()
	for lead in leads:
		root = find(lead.name)
		if root != lead.name or lead.name in parent:
			groups.setdefault(root, [])
			if root not in [l for l in groups[root]]:
				groups[root].append(root)
			if lead.name not in groups[root]:
				groups[root].append(lead.name)

	# Filter to actual duplicate groups (2+ leads), sorted by creation
	creation_map = {l.name: l.creation for l in leads}
	result = {}
	for root, members in groups.items():
		unique = list(dict.fromkeys(members))
		if len(unique) >= 2:
			unique.sort(key=lambda n: creation_map.get(n, ""))
			result[unique[0]] = unique

	return result


def execute():
	groups = _find_duplicate_groups()

	if not groups:
		frappe.log_error(title="Merge Duplicates", message="No duplicate leads found.")
		return

	merged_count = 0
	deleted_count = 0

	for primary_name, group_names in groups.items():
		duplicates = group_names[1:]  # all except primary

		try:
			primary = frappe.get_doc("EE Lead", primary_name)
			dup_docs = [frappe.get_doc("EE Lead", n) for n in duplicates]

			# 1. Fill empty data fields from duplicates
			for field in MERGE_FIELDS:
				if not primary.get(field):
					for dup in dup_docs:
						val = dup.get(field)
						if val:
							primary.set(field, val)
							break

			# 2. Timestamp fields — keep earliest
			for field in TIMESTAMP_FIELDS:
				vals = [primary.get(field)] + [d.get(field) for d in dup_docs]
				vals = [v for v in vals if v]
				if vals:
					primary.set(field, min(vals))

			# 3. Status — keep most progressed (unless Converted)
			if not primary.converted:
				all_statuses = [primary.status] + [d.status for d in dup_docs]
				best_idx = max(
					STATUS_ORDER.index(s) if s in STATUS_ORDER else 0
					for s in all_statuses
				)
				# Don't auto-set to Converted or Lost from merge
				if best_idx < STATUS_ORDER.index("Converted"):
					primary.status = STATUS_ORDER[best_idx]

			# 4. Merge child tables
			for dup in dup_docs:
				for row in dup.call_log:
					primary.append("call_log", {
						"call_on": row.call_on,
						"caller": row.caller,
						"direction": row.direction,
						"call_result": row.call_result,
						"duration_min": row.duration_min,
						"summary": row.summary,
						"next_call_on": row.next_call_on,
						"recording_url": row.get("recording_url"),
					})

				for row in dup.activity_log:
					primary.append("activity_log", {
						"activity_on": row.activity_on,
						"activity_type": row.activity_type,
						"user": row.user,
						"summary": row.summary,
						"outcome": row.get("outcome"),
						"follow_up_on": row.get("follow_up_on"),
					})

				# Documents — only add if document_type not already present
				existing_doc_types = {r.document_type for r in primary.documents}
				for row in dup.documents:
					if row.document_type not in existing_doc_types:
						primary.append("documents", {
							"document_type": row.document_type,
							"label": row.label,
							"attachment": row.attachment,
							"received": row.received,
							"received_on": row.received_on,
							"verified": row.verified,
							"verified_by": row.verified_by,
							"remarks": row.remarks,
						})
						existing_doc_types.add(row.document_type)
					elif row.attachment:
						# If same doc type exists but primary has no attachment, use dup's
						for prow in primary.documents:
							if prow.document_type == row.document_type and not prow.attachment:
								prow.attachment = row.attachment
								prow.received = row.received or prow.received
								prow.received_on = row.received_on or prow.received_on
								break

			# 5. Add merge activity note
			dup_list = ", ".join(duplicates)
			primary.append("activity_log", {
				"activity_on": now_datetime(),
				"activity_type": "System",
				"user": "Administrator",
				"summary": f"Merged duplicate leads: {dup_list}",
			})

			# 6. documents_verified — set if any dup had it
			if not primary.documents_verified:
				for dup in dup_docs:
					if dup.documents_verified:
						primary.documents_verified = 1
						primary.verified_by = dup.verified_by or primary.verified_by
						break

			# Save primary (bypass status guard)
			primary.flags.ignore_validate = True
			primary.flags.ignore_permissions = True
			primary.save()

			# 7. Re-link references from duplicates to primary
			for dup_name in duplicates:
				_relink_references(dup_name, primary_name)

			# 8. Delete duplicates
			for dup_name in duplicates:
				frappe.delete_doc("EE Lead", dup_name, force=True, ignore_permissions=True)
				deleted_count += 1

			merged_count += 1
			frappe.db.commit()

		except Exception:
			frappe.log_error(
				title=f"Merge duplicate leads error: {primary_name}",
				message=frappe.get_traceback(),
			)
			frappe.db.rollback()

	frappe.log_error(
		title="Merge Duplicate Leads Complete",
		message=f"Merged {merged_count} groups, deleted {deleted_count} duplicate leads.",
	)


def _relink_references(old_name, new_name):
	"""Re-link ToDo, Comment, Communication, Counselling Session from old lead to new."""
	# ToDo
	frappe.db.sql("""
		UPDATE `tabToDo`
		SET reference_name = %(new)s
		WHERE reference_type = 'EE Lead' AND reference_name = %(old)s
	""", {"old": old_name, "new": new_name})

	# Comment
	frappe.db.sql("""
		UPDATE `tabComment`
		SET reference_name = %(new)s
		WHERE reference_doctype = 'EE Lead' AND reference_name = %(old)s
	""", {"old": old_name, "new": new_name})

	# Communication
	frappe.db.sql("""
		UPDATE `tabCommunication`
		SET reference_name = %(new)s
		WHERE reference_doctype = 'EE Lead' AND reference_name = %(old)s
	""", {"old": old_name, "new": new_name})

	# EE Counselling Session
	if frappe.db.table_exists("tabEE Counselling Session"):
		frappe.db.sql("""
			UPDATE `tabEE Counselling Session`
			SET lead = %(new)s
			WHERE lead = %(old)s
		""", {"old": old_name, "new": new_name})

	# Tags
	frappe.db.sql("""
		UPDATE `tabTag Link`
		SET document_name = %(new)s
		WHERE document_type = 'EE Lead' AND document_name = %(old)s
	""", {"old": old_name, "new": new_name})
