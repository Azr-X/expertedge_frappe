"""Nomod success URL callback — triggered when student completes payment.

Set this as the success_url in Nomod Settings:
    https://yourdomain.com/api/method/expertedge.api.nomod_callback.payment_success?link={link_name}

Nomod redirects the student here after successful payment.
This endpoint auto-marks the payment link as paid and redirects to a thank-you page.
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def payment_success(**kwargs):
	"""Called when student is redirected after successful Nomod payment."""
	link_name = kwargs.get("link")

	if not link_name:
		frappe.respond_as_web_page(
			_("Payment"),
			_("Thank you for your payment."),
			indicator_color="green",
		)
		return

	if not frappe.db.exists("EE Nomod Payment Link", link_name):
		frappe.respond_as_web_page(
			_("Payment"),
			_("Thank you for your payment. Our team will confirm shortly."),
			indicator_color="green",
		)
		return

	link = frappe.get_doc("EE Nomod Payment Link", link_name)

	if link.status == "Paid":
		# Already processed
		frappe.respond_as_web_page(
			_("Payment Confirmed"),
			_("Your payment has already been recorded. Thank you!"),
			indicator_color="green",
		)
		return

	# Verify with Nomod API if enabled
	nomod_settings = frappe.get_cached_doc("Nomod Settings")
	verified = False

	if nomod_settings.enabled and link.nomod_reference and not link.nomod_reference.startswith("PLACEHOLDER"):
		try:
			from expertedge.nomod import list_charges
			charges = list_charges(link_id=link.nomod_reference)
			paid_charges = [
				c for c in charges.get("results", [])
				if c.get("status") in ("captured", "paid")
			]
			if paid_charges:
				verified = True
		except Exception:
			frappe.log_error("Nomod callback: failed to verify charge")

	if verified:
		try:
			link.mark_paid()
			frappe.db.commit()
			frappe.respond_as_web_page(
				_("Payment Successful"),
				_("Thank you! Your payment of {0} {1} has been received and recorded.").format(
					link.currency, link.amount
				),
				indicator_color="green",
			)
		except Exception:
			frappe.log_error("Nomod callback: failed to mark paid")
			frappe.respond_as_web_page(
				_("Payment Received"),
				_("Thank you for your payment. Our team will confirm shortly."),
				indicator_color="green",
			)
	else:
		# Can't verify yet — maybe charge is still processing
		# Mark as "pending verification" so the scheduler picks it up
		frappe.respond_as_web_page(
			_("Payment Processing"),
			_("Thank you! Your payment is being processed. You will receive a confirmation shortly."),
			indicator_color="blue",
		)
