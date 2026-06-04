"""Nomod webhook endpoint — receives Svix-signed payment notifications.

Webhook events handled:
- charge.completed: payment captured, mark link as paid
- charge.authorised: funds reserved (logged, not acted on)
- charge.failed: payment declined (logged)

Endpoint: POST /api/method/expertedge.api.nomod_webhook.handle

Nomod webhook payload:
{
    "type": "charge.completed",
    "eventId": "<unique event id>",
    "objectId": "<charge id>",
    "data": {
        "created": "<timestamp>",
        "currency": "AED",
        "customer": {...},
        ...
    }
}

Headers: svix-id, svix-timestamp, svix-signature
"""

import frappe
from frappe import _
import json


@frappe.whitelist(allow_guest=True)
def handle(**kwargs):
	# Get raw body and headers for signature verification
	raw_body = frappe.request.get_data()
	headers = {
		"svix-id": frappe.request.headers.get("svix-id"),
		"svix-timestamp": frappe.request.headers.get("svix-timestamp"),
		"svix-signature": frappe.request.headers.get("svix-signature"),
	}

	# Verify signature
	from expertedge.nomod import verify_webhook_signature
	if not verify_webhook_signature(raw_body, headers):
		frappe.log_error("Nomod webhook: invalid signature", "Nomod Webhook")
		frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	# Parse payload
	try:
		payload = json.loads(raw_body)
	except json.JSONDecodeError:
		frappe.throw(_("Invalid JSON payload"))

	event_type = payload.get("type")
	event_id = payload.get("eventId")
	charge_id = payload.get("objectId")
	data = payload.get("data", {})

	frappe.logger().info(f"Nomod webhook: {event_type} | event={event_id} | charge={charge_id}")

	if event_type == "charge.completed":
		return _handle_charge_completed(charge_id, data)
	elif event_type == "charge.authorised":
		frappe.log_error(
			title="Nomod: charge authorised",
			message=f"Charge {charge_id} authorised. Awaiting capture.\n{json.dumps(data, indent=2)}"
		)
		return {"status": "noted"}
	elif event_type == "charge.failed":
		frappe.log_error(
			title="Nomod: charge failed",
			message=f"Charge {charge_id} failed.\n{json.dumps(data, indent=2)}"
		)
		return {"status": "noted"}
	else:
		frappe.logger().info(f"Nomod webhook: unhandled event type {event_type}")
		return {"status": "ignored"}


def _handle_charge_completed(charge_id, data):
	"""Process a completed charge — find matching payment link and mark paid."""
	# Try to find payment link by nomod_reference (link ID from create_link response)
	# The charge's data may contain reference info linking back to our payment link
	currency = data.get("currency")
	amount = data.get("amount") if "amount" in data else None

	# Look up by nomod_reference or by matching charge metadata
	# Nomod links have a reference_id — charges are tied to links
	link_name = None

	# Strategy 1: check custom_fields or metadata in charge data for our reference
	custom_fields = data.get("customFields") or data.get("custom_fields") or {}
	if isinstance(custom_fields, list):
		for cf in custom_fields:
			if cf.get("label") == "reference" or cf.get("name") == "reference":
				ref = cf.get("value")
				if ref and frappe.db.exists("EE Nomod Payment Link", ref):
					link_name = ref
					break

	# Strategy 2: search by nomod_reference matching charge_id's parent link
	if not link_name and charge_id:
		link_name = frappe.db.get_value(
			"EE Nomod Payment Link",
			{"nomod_reference": charge_id},
			"name",
		)

	# Strategy 3: match by amount + currency for recent unpaid links (last resort)
	if not link_name and amount and currency:
		link_name = frappe.db.get_value(
			"EE Nomod Payment Link",
			{
				"status": ["in", ["Generated", "Sent"]],
				"amount": amount,
				"currency": currency,
			},
			"name",
			order_by="creation desc",
		)

	if not link_name:
		frappe.log_error(
			title="Nomod webhook: no matching payment link",
			message=f"charge_id={charge_id}\n{json.dumps(data, indent=2)}"
		)
		return {"status": "no_match", "charge_id": charge_id}

	link = frappe.get_doc("EE Nomod Payment Link", link_name)

	if link.status == "Paid":
		return {"status": "already_paid", "link": link_name}

	link.mark_paid()
	frappe.db.commit()
	return {"status": "ok", "link": link_name, "payment_entry": link.payment_entry}
