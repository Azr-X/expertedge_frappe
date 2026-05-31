import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, nowdate


class EELead(Document):
	def before_insert(self):
		self.lead_received_on = now_datetime()
		self._seed_mandatory_documents()
		self._set_default_program()

	def after_insert(self):
		self._create_first_contact_todo()
		self._notify_new_lead()
		self._log_system_activity(f"Lead created via {self.lead_source}")

	def validate(self):
		if not self.handled_by and frappe.session.user != "Guest":
			self.handled_by = frappe.session.user
		self._stamp_first_contact()
		self._ensure_follow_up_todos()

	def _seed_mandatory_documents(self):
		"""Pre-seed document rows from active mandatory EE Document Type records."""
		doc_types = frappe.get_all(
			"EE Document Type",
			filters={"is_mandatory": 1, "is_active": 1, "applies_to": ["in", ["Lead", "Both"]]},
			fields=["document_type", "sort_order"],
			order_by="sort_order asc",
		)
		for dt in doc_types:
			self.append("documents", {"document_type": dt.document_type})

	def _set_default_program(self):
		if not self.program:
			settings = frappe.get_cached_doc("ExpertEdge Settings")
			if settings.default_program:
				self.program = settings.default_program

	def _create_first_contact_todo(self):
		settings = frappe.get_cached_doc("ExpertEdge Settings")
		sla_minutes = settings.first_contact_sla_minutes or 30
		allocated_to = self.handled_by or self.owner
		frappe.get_doc({
			"doctype": "ToDo",
			"allocated_to": allocated_to,
			"reference_type": "EE Lead",
			"reference_name": self.name,
			"description": f"Call new lead {self.lead_name} within {sla_minutes} minutes",
			"date": nowdate(),
			"status": "Open",
		}).insert(ignore_permissions=True)

	def _notify_new_lead(self):
		settings = frappe.get_cached_doc("ExpertEdge Settings")
		sla_minutes = settings.first_contact_sla_minutes or 30
		allocated_to = self.handled_by or self.owner
		frappe.publish_realtime(
			"msgprint",
			{"message": f"New lead {self.lead_name} — call within {sla_minutes} min", "alert": True},
			user=allocated_to,
		)
		self._email_telecaller_new_lead(settings, allocated_to, sla_minutes)

	def _email_telecaller_new_lead(self, settings, allocated_to, sla_minutes):
		"""Send email to telecaller about new lead assignment."""
		template_name = settings.get("new_lead_email_template")

		if template_name:
			template = frappe.get_doc("Email Template", template_name)
			context = {"doc": self, "sla_minutes": sla_minutes}
			message = frappe.render_template(template.response_html or template.response, context)
			subject = frappe.render_template(template.subject, context)
		else:
			subject = f"New Lead Assigned: {self.lead_name}"
			message = (
				f"<p>A new lead has been assigned to you.</p>"
				f"<p><strong>Name:</strong> {self.lead_name}<br>"
				f"<strong>Email:</strong> {self.email or 'N/A'}<br>"
				f"<strong>Mobile:</strong> {self.mobile_no or 'N/A'}<br>"
				f"<strong>Source:</strong> {self.lead_source or 'N/A'}</p>"
				f"<p>Please make first contact within <strong>{sla_minutes} minutes</strong>.</p>"
				f"<p><a href='{frappe.utils.get_url()}/app/ee-lead/{self.name}'>View Lead</a></p>"
			)

		try:
			frappe.sendmail(
				recipients=[allocated_to],
				subject=subject,
				message=message,
				reference_doctype="EE Lead",
				reference_name=self.name,
			)
		except Exception:
			frappe.log_error("Failed to send new lead email to telecaller")

	def _stamp_first_contact(self):
		"""If call_log has rows and first_contacted_on is empty, stamp it."""
		if self.call_log and not self.first_contacted_on:
			earliest = min(get_datetime(row.call_on) for row in self.call_log if row.call_on)
			self.first_contacted_on = earliest
			if self.status == "New":
				self.status = "Contacted"

	def _ensure_follow_up_todos(self):
		"""Create ToDos for call_log.next_call_on and activity_log.follow_up_on."""
		for row in (self.call_log or []):
			if row.next_call_on:
				self._ensure_todo(
					row.caller or self.handled_by or self.owner,
					f"Follow-up call for {self.lead_name}",
					row.next_call_on,
				)
		for row in (self.activity_log or []):
			if row.follow_up_on:
				self._ensure_todo(
					row.user or self.handled_by or self.owner,
					f"Follow-up for {self.lead_name}: {row.summary or ''}",
					row.follow_up_on,
				)

	def _ensure_todo(self, allocated_to, description, date):
		"""Create a ToDo if one doesn't already exist (idempotent)."""
		existing = frappe.db.exists("ToDo", {
			"reference_type": "EE Lead",
			"reference_name": self.name,
			"allocated_to": allocated_to,
			"description": description,
			"status": "Open",
		})
		if not existing:
			frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": allocated_to,
				"reference_type": "EE Lead",
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
	def send_brochure(self):
		settings = frappe.get_cached_doc("ExpertEdge Settings")
		if not settings.brochure_email_template:
			frappe.throw(_("Brochure Email Template not set in ExpertEdge Settings"))

		template = frappe.get_doc("Email Template", settings.brochure_email_template)
		message = frappe.render_template(template.response_html or template.response, {"doc": self})
		subject = frappe.render_template(template.subject, {"doc": self})

		attachments = []
		if settings.default_brochure:
			attachments.append({"file_url": settings.default_brochure})

		frappe.sendmail(
			recipients=[self.email],
			subject=subject,
			message=message,
			attachments=attachments,
			reference_doctype="EE Lead",
			reference_name=self.name,
		)

		self.brochure_sent_on = now_datetime()
		self.status = "Brochure Sent"
		self._log_system_activity("Brochure sent to candidate")
		self.save()

	@frappe.whitelist()
	def request_documents(self):
		settings = frappe.get_cached_doc("ExpertEdge Settings")
		if not settings.doc_request_email_template:
			frappe.throw(_("Document Request Email Template not set in ExpertEdge Settings"))

		template = frappe.get_doc("Email Template", settings.doc_request_email_template)
		message = frappe.render_template(template.response_html or template.response, {"doc": self})
		subject = frappe.render_template(template.subject, {"doc": self})

		frappe.sendmail(
			recipients=[self.email],
			subject=subject,
			message=message,
			reference_doctype="EE Lead",
			reference_name=self.name,
		)

		self.docs_requested_on = now_datetime()
		self.status = "Docs Requested"
		self._log_system_activity("Document request email sent")
		self.save()

	@frappe.whitelist()
	def mark_documents_verified(self):
		for row in self.documents:
			if not row.received or not row.verified:
				frappe.throw(
					_("All document rows must be marked as Received and Verified. "
					  "Row {0} ({1}) is incomplete.").format(row.idx, row.document_type)
				)

		self.documents_verified = 1
		self.verified_by = frappe.session.user
		self.docs_verified_on = now_datetime()
		self.status = "Docs Verified"
		self._log_system_activity("All documents verified")
		self.save()

	@frappe.whitelist()
	def convert_to_student(self):
		if self.converted:
			frappe.throw(_("This lead has already been converted"))
		if self.status != "Confirmed":
			frappe.throw(_("Lead must be in 'Confirmed' status to convert"))

		student = frappe.new_doc("EE Student")
		student.student_name = self.lead_name
		student.email = self.email
		student.mobile_no = self.mobile_no
		student.nationality = self.nationality
		student.highest_qualification = self.highest_qualification
		student.years_of_experience = self.years_of_experience
		student.current_designation = self.current_designation
		student.program = self.program
		student.batch = self.preferred_batch
		student.lead = self.name
		student.counsellor = self.counsellor
		student.handled_by = self.handled_by

		# Copy documents
		for doc_row in self.documents:
			student.append("documents", {
				"document_type": doc_row.document_type,
				"label": doc_row.label,
				"attachment": doc_row.attachment,
				"received": doc_row.received,
				"received_on": doc_row.received_on,
				"verified": doc_row.verified,
				"verified_by": doc_row.verified_by,
				"remarks": doc_row.remarks,
			})

		# Copy call log
		for call_row in self.call_log:
			student.append("call_log", {
				"call_on": call_row.call_on,
				"caller": call_row.caller,
				"direction": call_row.direction,
				"call_result": call_row.call_result,
				"duration_min": call_row.duration_min,
				"summary": call_row.summary,
				"next_call_on": call_row.next_call_on,
				"recording_url": call_row.recording_url,
			})

		# Copy activity log
		for act_row in self.activity_log:
			student.append("activity_log", {
				"activity_on": act_row.activity_on,
				"activity_type": act_row.activity_type,
				"user": act_row.user,
				"summary": act_row.summary,
				"outcome": act_row.outcome,
				"follow_up_on": act_row.follow_up_on,
			})

		student.insert(ignore_permissions=True)

		self.converted = 1
		self.converted_on = now_datetime()
		self.student = student.name
		self.status = "Converted"
		self._log_system_activity(f"Converted to student {student.name}")
		self.save()

		frappe.msgprint(
			_("Student {0} created successfully").format(
				f'<a href="/app/ee-student/{student.name}">{student.name}</a>'
			),
			title=_("Lead Converted"),
			indicator="green",
		)
		return student.name

	@frappe.whitelist()
	def set_status(self, status):
		valid = [
			"Contacted", "Brochure Sent", "Docs Requested", "Docs Received",
			"Docs Verified", "Counselling Scheduled", "Counselling Done", "Confirmed",
		]
		if status not in valid:
			frappe.throw(_("Invalid status transition: {0}").format(status))
		self.status = status
		self._log_system_activity(f"Status changed to {status}")
		self.save()

	@frappe.whitelist()
	def confirm_lead(self):
		self.status = "Confirmed"
		self.confirmed_on = now_datetime()
		self.counselling_outcome = self.counselling_outcome or "Fit \u2013 Confirmed"
		self._log_system_activity("Lead confirmed — ready for conversion")
		self.save()
		frappe.msgprint(_("Lead confirmed. Click 'Convert to Student' to proceed."), indicator="green")

	@frappe.whitelist()
	def mark_lost(self, lost_reason=None):
		if lost_reason:
			self.lost_reason = lost_reason
		self.status = "Lost"
		self._log_system_activity(f"Marked as Lost. Reason: {self.lost_reason or 'Not specified'}")
		self.save()
