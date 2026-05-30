"""Nomod payment webhook endpoint — STUB.

When Nomod sends a payment confirmation, this endpoint will:
1. Validate the webhook signature (TBD — depends on Nomod docs).
2. Look up the EE Nomod Payment Link by nomod_reference or name.
3. Call link.mark_paid() to create the Payment Entry and update the student.

Expected Nomod payload (placeholder — fill from actual Nomod API docs):
	{
		"event": "payment.completed",
		"data": {
			"id": "<nomod transaction id>",
			"reference": "<EE-PAY-XXXX>",
			"amount": 200,
			"currency": "AED",
			"status": "completed",
			"paid_at": "2026-05-29T12:00:00Z"
		},
		"signature": "<hmac signature>"
	}

Endpoint: POST /api/method/expertedge.api.nomod_webhook.handle
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle(**kwargs):
	# TODO: Validate webhook signature from Nomod
	# signature = frappe.request.headers.get("X-Nomod-Signature")
	# if not _verify_signature(signature, frappe.request.data):
	#     frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	data = kwargs.get("data") or kwargs
	reference = data.get("reference")
	nomod_id = data.get("id")

	if not reference:
		frappe.throw(_("Missing payment reference"))

	# Find payment link
	if frappe.db.exists("EE Nomod Payment Link", reference):
		link_name = reference
	else:
		link_name = frappe.db.get_value(
			"EE Nomod Payment Link",
			{"nomod_reference": nomod_id or reference},
			"name",
		)

	if not link_name:
		frappe.throw(_("Payment link not found for reference: {0}").format(reference))

	link = frappe.get_doc("EE Nomod Payment Link", link_name)

	if link.status == "Paid":
		return {"status": "already_paid", "link": link_name}

	link.mark_paid()
	return {"status": "ok", "link": link_name, "payment_entry": link.payment_entry}
