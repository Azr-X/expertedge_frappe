import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate


class EECounsellingSession(Document):
	def on_update(self):
		self._update_lead_from_outcome()

	def _update_lead_from_outcome(self):
		if not self.lead or not self.outcome:
			return

		lead = frappe.get_doc("EE Lead", self.lead)
		lead.latest_session = self.name

		if self.outcome == "Fit \u2013 Confirmed":
			lead.counselling_outcome = "Fit \u2013 Confirmed"
			lead.counselling_done_on = self.conducted_on or now_datetime()
			lead.status = "Confirmed"
			lead.confirmed_on = now_datetime()
			lead.append("activity_log", {
				"activity_on": now_datetime(),
				"activity_type": "System",
				"user": frappe.session.user,
				"summary": f"Counselling session {self.name}: Fit \u2013 Confirmed",
			})
			lead.save(ignore_permissions=True)

			# Create ToDo for conversion
			frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": lead.handled_by or lead.owner,
				"reference_type": "EE Lead",
				"reference_name": lead.name,
				"description": f"Convert {lead.lead_name} to Student & send pre-approval",
				"date": nowdate(),
				"status": "Open",
			}).insert(ignore_permissions=True)

		elif self.outcome == "Not Fit":
			lead.counselling_outcome = "Not Fit"
			lead.counselling_done_on = self.conducted_on or now_datetime()
			lead.append("activity_log", {
				"activity_on": now_datetime(),
				"activity_type": "System",
				"user": frappe.session.user,
				"summary": f"Counselling session {self.name}: Not Fit",
			})
			lead.save(ignore_permissions=True)

			# Notify — don't auto-lose
			frappe.publish_realtime(
				"msgprint",
				{
					"message": f"Lead {lead.lead_name} assessed as Not Fit. Consider marking as Lost.",
					"alert": True,
				},
				user=lead.handled_by or lead.owner,
			)

		else:
			# Reschedule / No Show / Fit – Considering
			lead.counselling_outcome = self.outcome
			if self.conducted_on:
				lead.counselling_done_on = self.conducted_on
			lead.append("activity_log", {
				"activity_on": now_datetime(),
				"activity_type": "System",
				"user": frappe.session.user,
				"summary": f"Counselling session {self.name}: {self.outcome}",
			})
			lead.save(ignore_permissions=True)
