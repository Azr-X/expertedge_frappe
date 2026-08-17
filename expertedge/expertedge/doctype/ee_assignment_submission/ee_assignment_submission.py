import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime


# Statuses that count as "the student has handed something in"
SUBMITTED_STATUSES = ("Submitted", "Under Review", "Accepted")

# Slots always offered in the portal, even when nothing is formally required.
# Whether a student needs to submit depends on their experience, so the call is
# left to them — the portal shows the slots and they upload if applicable.
DEFAULT_ASSIGNMENT_SLOTS = 2


class EEAssignmentSubmission(Document):
	def validate(self):
		if cint(self.sequence) < 1:
			frappe.throw(_("Assignment No. must be 1 or greater"))

		self.validate_slot()
		self.validate_duplicate()

		if not self.submitted_on:
			self.submitted_on = now_datetime()

		if self.has_value_changed("status") and self.status in ("Accepted", "Resubmit Required"):
			self.reviewed_by = frappe.session.user
			self.reviewed_on = now_datetime()

	def validate_slot(self):
		slots = get_slot_count(self.student)
		if cint(self.sequence) > slots:
			frappe.throw(
				_("Assignment No. {0} exceeds the {1} assignment slot(s) available for this student.").format(
					self.sequence, slots
				)
			)

	def validate_duplicate(self):
		existing = frappe.db.get_value(
			"EE Assignment Submission",
			{
				"student": self.student,
				"sequence": cint(self.sequence),
				"name": ("!=", self.name or ""),
			},
			"name",
		)
		if existing:
			frappe.throw(
				_("Assignment No. {0} is already submitted for this student ({1}). Edit that record to resubmit.").format(
					self.sequence, existing
				)
			)

	def on_update(self):
		update_student_progress(self.student)

	def on_trash(self):
		self._student_to_refresh = self.student

	def after_delete(self):
		update_student_progress(getattr(self, "_student_to_refresh", None) or self.student)


def get_slot_count(student):
	"""How many upload slots the portal offers this student.

	Never fewer than the default — the requirement depends on the student's
	experience, so the slots are always visible and submitting is their call.
	"""
	return max(get_required_count(student), DEFAULT_ASSIGNMENT_SLOTS)


def get_required_count(student):
	"""How many assignments this student is formally expected to submit.

	Used for reporting and progress display only; it does not block uploads.

	The batch default applies unless the student carries an explicit override
	(override_assignments_required = 1), which may legitimately be 0 for students
	exempt from the requirement.
	"""
	row = frappe.db.get_value(
		"EE Student",
		student,
		["override_assignments_required", "assignments_required", "batch"],
		as_dict=True,
	)
	if not row:
		return 0
	if cint(row.override_assignments_required):
		return cint(row.assignments_required)
	if row.batch:
		return cint(frappe.db.get_value("EE Batch", row.batch, "assignments_required"))
	return 0


def update_student_progress(student):
	"""Recompute the assignment rollup fields on EE Student."""
	if not student or not frappe.db.exists("EE Student", student):
		return

	required = get_required_count(student)

	rows = frappe.get_all(
		"EE Assignment Submission",
		filters={"student": student},
		fields=["status"],
	)
	submitted = len([r for r in rows if r.status in SUBMITTED_STATUSES])
	accepted = len([r for r in rows if r.status == "Accepted"])

	if required <= 0:
		status = "Not Required"
	elif accepted >= required:
		status = "Complete"
	else:
		status = "Pending"

	frappe.db.set_value(
		"EE Student",
		student,
		{
			"assignments_submitted": submitted,
			"assignments_accepted": accepted,
			"assignments_status": status,
		},
		update_modified=False,
	)
