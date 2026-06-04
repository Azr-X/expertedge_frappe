import uuid

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate, flt


class EEStudent(Document):
	def before_insert(self):
		if not self.web_form_token:
			self.web_form_token = str(uuid.uuid4())[:12]

	def validate(self):
		self._auto_disable_web_edit()
		self._guard_status()
		self._resolve_fees()
		self._compute_net_fee()
		self._compute_aud_amount()
		self._recompute_outstanding()
		if not self.is_new():
			self._ensure_follow_up_todos()

	def _guard_status(self):
		"""Prevent manual status change for statuses that must be set via buttons."""
		if self.is_new():
			return
		db_status = frappe.db.get_value("EE Student", self.name, "status")
		if db_status == self.status:
			return
		guarded = {
			"CMA Registered": ("in_student_cma_registered", "Mark CMA Registered"),
			"Materials Issued": ("in_student_materials_issued", "Issue Materials"),
			"Fully Paid": ("in_student_fully_paid", "Recalculate Payments"),
		}
		if self.status in guarded:
			flag, button = guarded[self.status]
			if not getattr(frappe.flags, flag, False):
				frappe.throw(_("Cannot manually set status to {0}. Use the '{1}' button.").format(self.status, button))

	def _auto_disable_web_edit(self):
		"""Auto-disable web edit after guest submits the form."""
		if frappe.flags.in_web_form and self.allow_web_edit:
			self.allow_web_edit = 0

	def _resolve_fees(self):
		"""Resolve fees from Batch."""
		settings = frappe.get_cached_doc("ExpertEdge Settings")
		self.billing_currency = settings.billing_currency or "AED"

		if self.batch:
			batch = frappe.get_cached_doc("EE Batch", self.batch)
			self.total_fee = batch.total_fee
			if not self.program:
				self.program = batch.program
			if not self.pre_approval_fee:
				self.pre_approval_fee = batch.pre_approval_fee

	def _compute_net_fee(self):
		if self.apply_lumpsum_discount and self.batch:
			batch = frappe.get_cached_doc("EE Batch", self.batch)
			discount_pct = flt(batch.lumpsum_discount_percent)
			self.net_fee = flt(self.total_fee) * (1 - discount_pct / 100)
		else:
			self.net_fee = flt(self.total_fee)

	def _compute_aud_amount(self):
		rate = flt(self.aud_conversion_rate) or 2.65
		self.aud_amount = flt(self.net_fee) / rate if rate > 0 else 0

	def _recompute_outstanding(self):
		self.outstanding = flt(self.net_fee) - flt(self.total_paid)

	def _ensure_follow_up_todos(self):
		for row in (self.call_log or []):
			if row.next_call_on:
				self._ensure_todo(
					row.caller or self.handled_by or self.owner,
					f"Follow-up call for student {self.student_name}",
					row.next_call_on,
				)
		for row in (self.activity_log or []):
			if row.follow_up_on:
				self._ensure_todo(
					row.user or self.handled_by or self.owner,
					f"Follow-up for student {self.student_name}: {row.summary or ''}",
					row.follow_up_on,
				)

	def _ensure_todo(self, allocated_to, description, date):
		existing = frappe.db.exists("ToDo", {
			"reference_type": "EE Student",
			"reference_name": self.name,
			"allocated_to": allocated_to,
			"description": description,
			"status": "Open",
		})
		if not existing:
			frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": allocated_to,
				"reference_type": "EE Student",
				"reference_name": self.name,
				"description": description,
				"date": str(date)[:10] if date else nowdate(),
				"status": "Open",
			}).insert(ignore_permissions=True)

	def _log_system_activity(self, summary):
		self.append("activity_log", {
			"activity_on": now_datetime(),
			"activity_type": "System",
			"user": frappe.session.user,
			"summary": summary,
		})

	@frappe.whitelist()
	def create_customer_and_invoice(self, total_fee=None, apply_discount=None, aud_conversion_rate=None):
		"""Create Customer + submitted Sales Invoice. Idempotent.

		Args:
			total_fee: Override fee amount (from dialog). If None, uses self.net_fee.
			apply_discount: Whether to apply lump-sum discount.
			aud_conversion_rate: AED to AUD conversion rate.
		"""
		if self.sales_invoice:
			return self.sales_invoice

		settings = frappe.get_cached_doc("ExpertEdge Settings")
		if not settings.default_company:
			frappe.throw(_("Default Company not set in ExpertEdge Settings"))
		if not settings.service_item:
			frappe.throw(_("Service Item not set in ExpertEdge Settings"))

		# Update fee on student if provided from dialog
		if total_fee is not None:
			self.total_fee = flt(total_fee)
		if apply_discount is not None:
			self.apply_lumpsum_discount = int(apply_discount)
		if aud_conversion_rate is not None:
			self.aud_conversion_rate = flt(aud_conversion_rate) or 2.65
		self._compute_net_fee()
		self._compute_aud_amount()
		self._recompute_outstanding()

		invoice_amount = flt(self.net_fee)
		if not invoice_amount:
			frappe.throw(_("Fee amount cannot be zero"))

		# Create Customer if needed
		if not self.customer:
			customer = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": self.student_name,
				"customer_type": "Individual",
				"customer_group": "Individual",
				"territory": "All Territories",
			})
			customer.insert(ignore_permissions=True)
			self.customer = customer.name

		# Create Sales Invoice
		si_data = {
			"doctype": "Sales Invoice",
			"customer": self.customer,
			"company": settings.default_company,
			"currency": self.billing_currency or "AED",
			"conversion_rate": 1,
			"items": [{
				"item_code": settings.service_item,
				"qty": 1,
				"rate": invoice_amount,
				"income_account": settings.default_income_account,
			}],
		}
		if settings.default_receivable_account:
			si_data["debit_to"] = settings.default_receivable_account
		si = frappe.get_doc(si_data)
		si.insert(ignore_permissions=True)
		si.submit()

		self.sales_invoice = si.name
		self._log_system_activity(f"Customer {self.customer} and Invoice {si.name} created (AED {invoice_amount})")
		self.save(ignore_permissions=True)
		return si.name

	@frappe.whitelist()
	def create_payment_link(self, purpose, amount, currency=None, remarks=None):
		"""Create a payment link with flexible purpose/amount/currency."""
		self._ensure_invoice_exists()
		link = frappe.get_doc({
			"doctype": "EE Nomod Payment Link",
			"student": self.name,
			"purpose": purpose,
			"amount": flt(amount),
			"currency": currency or self.billing_currency or "AED",
			"sales_invoice": self.sales_invoice,
			"remarks": remarks,
		})
		link.insert(ignore_permissions=True)
		link.generate_nomod_link()
		self._log_system_activity(f"Payment link {link.name} generated — {purpose} {currency or 'AED'} {flt(amount)}")
		self.save(ignore_permissions=True)
		return link.name

	def _ensure_invoice_exists(self):
		if not self.sales_invoice:
			self.create_customer_and_invoice()

	@frappe.whitelist()
	def send_pre_approval_email(self, send_email=True):
		self._send_template_email("pre_approval_email_template", "Pre-approval", send_email)

	@frappe.whitelist()
	def send_receipt_email(self, send_email=True):
		self._send_template_email("payment_receipt_email_template", "Payment receipt", send_email)

	@frappe.whitelist()
	def send_balance_email(self, send_email=True):
		self._send_template_email("balance_payment_email_template", "Balance payment email", send_email)

	@frappe.whitelist()
	def send_welcome_email(self, send_email=True):
		self._send_template_email("welcome_email_template", "Welcome email", send_email)

	def _send_template_email(self, template_field, label, send_email=True):
		send_email = frappe.parse_val(send_email)

		if send_email:
			settings = frappe.get_cached_doc("ExpertEdge Settings")
			template_name = settings.get(template_field)
			if not template_name:
				frappe.throw(_("Email template '{0}' not set in ExpertEdge Settings").format(template_field))

			template = frappe.get_doc("Email Template", template_name)
			message = frappe.render_template(template.response_html or template.response, {"doc": self})
			subject = frappe.render_template(template.subject, {"doc": self})

			frappe.sendmail(
				recipients=[self.email],
				subject=subject,
				message=message,
				reference_doctype="EE Student",
				reference_name=self.name,
			)

		self._log_system_activity(label + (" emailed" if send_email else " marked sent manually"))
		self.save(ignore_permissions=True)

	@frappe.whitelist()
	def mark_cma_registered(self):
		self.cma_registration_status = "Registered"
		self.cma_registered_on = nowdate()
		self.status = "CMA Registered"
		self._log_system_activity("CMA registration confirmed")
		frappe.flags.in_student_cma_registered = True
		try:
			self.save()
		finally:
			frappe.flags.in_student_cma_registered = False

	@frappe.whitelist()
	def issue_materials(self):
		self.materials_issued = 1
		self.materials_issued_on = nowdate()
		self.status = "Materials Issued"
		self._log_system_activity("Materials issued to student")
		frappe.flags.in_student_materials_issued = True
		try:
			self.save()
		finally:
			frappe.flags.in_student_materials_issued = False

	@frappe.whitelist()
	def recalculate_payments(self):
		"""Sum paid payment links, update total_paid and outstanding."""
		total = frappe.db.sql("""
			SELECT COALESCE(SUM(amount), 0)
			FROM `tabEE Nomod Payment Link`
			WHERE student = %s AND status = 'Paid'
		""", self.name)[0][0]

		self.total_paid = flt(total)
		self.outstanding = flt(self.net_fee) - flt(self.total_paid)

		if self.outstanding <= 0:
			self.status = "Fully Paid"
			self._log_system_activity("Fully paid — outstanding cleared")

		frappe.flags.in_student_fully_paid = True
		try:
			self.save(ignore_permissions=True)
		finally:
			frappe.flags.in_student_fully_paid = False

	@frappe.whitelist()
	def generate_web_form_link(self):
		"""Enable web edit and return the shareable link."""
		if not self.web_form_token:
			self.web_form_token = str(uuid.uuid4())[:12]
		self.allow_web_edit = 1
		self._log_system_activity("Web form edit link generated")
		self.save(ignore_permissions=True)
		return f"{frappe.utils.get_url()}/student-details/{self.name}?token={self.web_form_token}"
