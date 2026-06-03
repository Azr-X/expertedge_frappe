import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, time_diff_in_hours, getdate, nowdate


class EEAttendance(Document):
	def validate(self):
		self.validate_duplicate()

	def validate_duplicate(self):
		if self.is_new():
			existing = frappe.db.exists("EE Attendance", {
				"employee": self.employee,
				"attendance_date": self.attendance_date,
				"name": ["!=", self.name],
			})
			if existing:
				frappe.throw(f"Attendance already exists for {self.employee} on {self.attendance_date}")

	def before_save(self):
		if self.check_out and self.check_in:
			self.total_hours = round(time_diff_in_hours(self.check_out, self.check_in), 2)
			self.status = "Checked Out"

	def on_trash(self):
		frappe.throw("Attendance records cannot be deleted.")


@frappe.whitelist()
def check_in():
	"""Create attendance record for current user."""
	user = frappe.session.user
	today = nowdate()

	existing = frappe.db.get_value("EE Attendance", {
		"employee": user,
		"attendance_date": today,
	}, "name")

	if existing:
		frappe.throw("You have already checked in today.")

	doc = frappe.get_doc({
		"doctype": "EE Attendance",
		"employee": user,
		"attendance_date": today,
		"check_in": now_datetime(),
		"status": "Checked In",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc


@frappe.whitelist()
def check_out():
	"""Check out current user."""
	user = frappe.session.user
	today = nowdate()

	name = frappe.db.get_value("EE Attendance", {
		"employee": user,
		"attendance_date": today,
		"status": "Checked In",
	}, "name")

	if not name:
		frappe.throw("No active check-in found for today.")

	doc = frappe.get_doc("EE Attendance", name)
	doc.check_out = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc


@frappe.whitelist()
def get_today_status():
	"""Get current user's attendance status for today."""
	user = frappe.session.user
	today = nowdate()

	record = frappe.db.get_value("EE Attendance", {
		"employee": user,
		"attendance_date": today,
	}, ["name", "status", "check_in", "check_out", "total_hours"], as_dict=True)

	return record or {}


def auto_checkout_all():
	"""Auto check-out all users who forgot to check out. Called at 11:55 PM."""
	open_records = frappe.get_all("EE Attendance", filters={
		"attendance_date": nowdate(),
		"status": "Checked In",
		"check_out": ["is", "not set"],
	}, pluck="name")

	for name in open_records:
		doc = frappe.get_doc("EE Attendance", name)
		doc.check_out = now_datetime()
		doc.auto_checked_out = 1
		doc.save(ignore_permissions=True)

	if open_records:
		frappe.db.commit()
		frappe.logger().info(f"Auto checked out {len(open_records)} users")
