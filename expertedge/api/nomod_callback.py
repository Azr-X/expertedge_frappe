"""Nomod success URL callback — triggered when student completes payment.

The success_url is set when creating the Nomod link:
    https://yourdomain.com/api/method/expertedge.api.nomod_callback.payment_success?link={link_name}

Nomod redirects the student here after payment. This does NOT confirm payment —
only the webhook (charge.completed) confirms actual payment. This page just
shows the student a thank-you message.
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def payment_success(**kwargs):
	"""Called when student is redirected after Nomod payment."""
	# Log all params Nomod sends — remove after confirming
	frappe.log_error(
		title="Nomod callback params",
		message=f"kwargs: {kwargs}\nquery_string: {frappe.request.query_string}\nfull_url: {frappe.request.url}"
	)

	link_name = kwargs.get("link")

	if not link_name or not frappe.db.exists("EE Nomod Payment Link", link_name):
		frappe.respond_as_web_page(
			_("Payment"),
			_("Thank you for your payment. Our team will confirm shortly."),
			indicator_color="green",
		)
		return

	link = frappe.get_doc("EE Nomod Payment Link", link_name)

	if link.status == "Paid":
		frappe.respond_as_web_page(
			_("Payment Confirmed"),
			_("Your payment has already been recorded. Thank you!"),
			indicator_color="green",
		)
		return

	# Payment not yet confirmed via webhook — show processing message
	frappe.respond_as_web_page(
		_("Payment Processing"),
		_("Thank you! Your payment is being processed. You will receive a confirmation shortly."),
		indicator_color="blue",
	)
