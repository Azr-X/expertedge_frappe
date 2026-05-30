import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, flt


class EENomodPaymentLink(Document):
	@frappe.whitelist()
	def generate_nomod_link(self):
		"""Generate a Nomod payment link.

		STUB FOR NOW — real Nomod API integration comes later.

		Integration contract:
		    POST to {Settings.nomod_api_base_url}/payment-links
		    Headers: Authorization: Bearer {Settings.nomod_api_key}
		    Body: {amount, currency, reference=self.name, description, customer_email}
		    Response: {id -> nomod_reference, url -> payment_link_url}
		"""
		settings = frappe.get_cached_doc("ExpertEdge Settings")

		# Compute service fee
		if not self.service_fee:
			fee_pct = flt(settings.nomod_service_fee_percent)
			if fee_pct:
				self.service_fee = flt(self.amount) * fee_pct / 100

		self.total_chargeable = flt(self.amount) + flt(self.service_fee)

		# TODO(Nomod API): POST to {Settings.nomod_api_base_url}/payment-links
		# headers: Authorization: Bearer {Settings.nomod_api_key}
		# body: {amount, currency, reference=self.name, description, customer_email}
		# response: {id -> nomod_reference, url -> payment_link_url}
		# Replace the placeholder below with the real call.
		self.payment_link_url = f"https://pay.nomod.com/PLACEHOLDER/{self.name}"
		self.nomod_reference = f"PLACEHOLDER-{self.name}"

		self.generated_on = now_datetime()
		self.status = "Generated"
		self.save(ignore_permissions=True)

	@frappe.whitelist()
	def mark_paid(self):
		"""Mark payment as received and create Payment Entry.

		Later this becomes a Nomod webhook handler instead of a manual button.
		"""
		if self.status == "Paid":
			frappe.throw(_("This payment link is already marked as Paid"))

		settings = frappe.get_cached_doc("ExpertEdge Settings")
		student = frappe.get_doc("EE Student", self.student)

		if not student.sales_invoice:
			frappe.throw(_("Student has no Sales Invoice. Create Customer & Invoice first."))

		if not settings.deposit_account:
			frappe.throw(_("AED Deposit Account not set in ExpertEdge Settings"))

		si = frappe.get_doc("Sales Invoice", student.sales_invoice)

		# Create Payment Entry — amount in AED, deposit to AED account
		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": student.customer,
			"company": si.company,
			"paid_from": si.debit_to,
			"paid_to": settings.deposit_account,
			"paid_amount": flt(self.amount),
			"received_amount": flt(self.amount),  # ERPNext recalculates with exchange rate
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,  # ERPNext will fetch actual exchange rate
			"reference_no": self.nomod_reference or self.name,
			"reference_date": now_datetime(),
			"references": [{
				"reference_doctype": "Sales Invoice",
				"reference_name": student.sales_invoice,
				"allocated_amount": flt(self.amount),
			}],
		})
		pe.insert(ignore_permissions=True)
		pe.submit()

		self.payment_entry = pe.name
		self.paid_on = now_datetime()
		self.status = "Paid"
		self.save(ignore_permissions=True)

		# Update student
		if self.purpose == "Pre-Approval" and student.status == "Pre-Approval Pending":
			student.status = "Pre-Approval Paid"
			student.append("activity_log", {
				"activity_on": now_datetime(),
				"activity_type": "Payment",
				"user": frappe.session.user,
				"summary": f"Pre-approval payment received via {self.name}",
			})
			student.save(ignore_permissions=True)

			# Trigger receipt email
			try:
				student.send_receipt_email()
			except Exception:
				frappe.log_error("Failed to send receipt email after pre-approval payment")

		student.recalculate_payments()
