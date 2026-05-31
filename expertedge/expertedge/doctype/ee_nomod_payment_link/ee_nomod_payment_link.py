import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, flt


class EENomodPaymentLink(Document):
	@frappe.whitelist()
	def generate_nomod_link(self):
		"""Generate a Nomod payment link — real API or placeholder."""
		self.total_chargeable = flt(self.amount) + flt(self.service_fee)

		nomod_settings = frappe.get_cached_doc("Nomod Settings")

		if nomod_settings.enabled:
			self._generate_via_api(nomod_settings)
		else:
			self._generate_placeholder()

		self.generated_on = now_datetime()
		self.status = "Generated"
		self.save(ignore_permissions=True)

	def _generate_via_api(self, nomod_settings):
		"""Call Nomod API to create a real payment link."""
		from expertedge.nomod import create_link, NomodAPIError

		student = frappe.get_doc("EE Student", self.student)
		title = f"{self.purpose} — {student.student_name}"
		note = f"Student: {student.student_name} | Ref: {self.name}"

		# Build success callback URL
		site_url = frappe.utils.get_url()
		success_url = f"{site_url}/api/method/expertedge.api.nomod_callback.payment_success?link={self.name}"

		try:
			result = create_link(
				amount=flt(self.amount),
				currency=self.currency or nomod_settings.default_currency or "AED",
				title=title,
				note=note,
				reference=self.name,
				success_url=success_url,
			)

			self.nomod_reference = result.get("id", "")
			self.payment_link_url = result.get("url", "")

			if not self.payment_link_url:
				frappe.throw(_("Nomod API returned no payment URL"))

		except NomodAPIError as e:
			frappe.log_error(
				title="Nomod API Error",
				message=f"Link: {self.name}\nError: {str(e)}"
			)
			frappe.throw(_("Nomod API error: {0}").format(str(e)))

	def _generate_placeholder(self):
		"""Generate a placeholder link when Nomod integration is disabled."""
		self.payment_link_url = f"https://pay.nomod.com/PLACEHOLDER/{self.name}"
		self.nomod_reference = f"PLACEHOLDER-{self.name}"

	@frappe.whitelist()
	def check_payment_status(self):
		"""Check if this link has been paid via Nomod API (poll charges)."""
		nomod_settings = frappe.get_cached_doc("Nomod Settings")
		if not nomod_settings.enabled or not self.nomod_reference:
			frappe.throw(_("Nomod integration not enabled or no reference ID"))

		if self.nomod_reference.startswith("PLACEHOLDER"):
			frappe.throw(_("Cannot check status on placeholder links"))

		from expertedge.nomod import list_charges

		charges = list_charges(link_id=self.nomod_reference)
		paid_charges = [
			c for c in charges.get("results", [])
			if c.get("status") in ("captured", "paid")
		]

		if paid_charges:
			charge = paid_charges[0]
			frappe.msgprint(
				_("Payment found! Charge {0} — {1} {2}").format(
					charge.get("reference_id"),
					charge.get("currency"),
					charge.get("total"),
				),
				indicator="green",
			)
			return {"paid": True, "charge": charge}

		frappe.msgprint(_("No payment found yet for this link."), indicator="orange")
		return {"paid": False}

	@frappe.whitelist()
	def email_payment_link(self):
		"""Email payment link to the student using configured template."""
		if not self.payment_link_url:
			frappe.throw(_("No payment link URL. Generate the link first."))

		settings = frappe.get_cached_doc("ExpertEdge Settings")
		template_name = settings.get("payment_link_email_template")

		student = frappe.get_doc("EE Student", self.student)

		if template_name:
			template = frappe.get_doc("Email Template", template_name)
			context = {"doc": student, "link": self}
			message = frappe.render_template(template.response_html or template.response, context)
			subject = frappe.render_template(template.subject, context)
		else:
			subject = f"Payment Link — {self.purpose}"
			message = (
				f"<p>Dear {student.student_name},</p>"
				f"<p>Please use the following link to make your payment of "
				f"{self.currency} {flt(self.amount):,.2f} ({self.purpose}):</p>"
				f"<p><a href='{self.payment_link_url}'>{self.payment_link_url}</a></p>"
				f"<p>Thank you.</p>"
			)

		frappe.sendmail(
			recipients=[student.email],
			subject=subject,
			message=message,
			reference_doctype="EE Nomod Payment Link",
			reference_name=self.name,
		)

		self.status = "Sent"
		self.sent_on = now_datetime()
		self.save(ignore_permissions=True)

	@frappe.whitelist()
	def mark_paid(self):
		"""Mark payment as received and create Payment Entry."""
		if self.status == "Paid":
			frappe.throw(_("This payment link is already marked as Paid"))

		settings = frappe.get_cached_doc("ExpertEdge Settings")
		student = frappe.get_doc("EE Student", self.student)

		if not student.sales_invoice:
			frappe.throw(_("Student has no Sales Invoice. Create Customer & Invoice first."))

		if not settings.deposit_account:
			frappe.throw(_("AED Deposit Account not set in ExpertEdge Settings"))

		si = frappe.get_doc("Sales Invoice", student.sales_invoice)

		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": student.customer,
			"company": si.company,
			"paid_from": si.debit_to,
			"paid_to": settings.deposit_account,
			"paid_amount": flt(self.amount),
			"received_amount": flt(self.amount),
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
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

		# Update student status
		if self.purpose == "Pre-Approval" and student.status == "Pre-Approval Pending":
			student.status = "Pre-Approval Paid"
			student.append("activity_log", {
				"activity_on": now_datetime(),
				"activity_type": "Payment",
				"user": frappe.session.user,
				"summary": f"Pre-approval payment received via {self.name}",
			})
			student.save(ignore_permissions=True)

			try:
				student.send_receipt_email()
			except Exception:
				frappe.log_error("Failed to send receipt email after pre-approval payment")

		student.recalculate_payments()
