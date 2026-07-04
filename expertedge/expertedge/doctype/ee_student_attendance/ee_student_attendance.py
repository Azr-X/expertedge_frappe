import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime, get_datetime, cstr
import math
from datetime import datetime
import pytz


class EEStudentAttendance(Document):
	def validate(self):
		if not self.session:
			self.determine_session()

	def determine_session(self):
		"""Auto-determine session based on batch break_time."""
		batch = frappe.get_cached_doc("EE Batch", self.batch)
		break_time = batch.break_time or "12:00:00"
		check_time = get_datetime(self.check_in_time).strftime("%H:%M:%S")
		self.session = "First Half" if check_time < break_time else "Second Half"


def haversine_distance(lat1, lon1, lat2, lon2):
	"""Distance in meters between two GPS coordinates."""
	R = 6_371_000
	phi1, phi2 = math.radians(lat1), math.radians(lat2)
	dphi = math.radians(lat2 - lat1)
	dlambda = math.radians(lon2 - lon1)
	a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
	return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@frappe.whitelist()
def bulk_mark_attendance(student_ids, date, session, check_in_time, timezone):
	"""Create EE Student Attendance records for multiple students at once."""
	if isinstance(student_ids, str):
		student_ids = frappe.parse_json(student_ids)

	# Build full datetime in the chosen timezone, then convert to system timezone
	tz = pytz.timezone(timezone)
	naive_dt = datetime.strptime(f"{date} {check_in_time}", "%Y-%m-%d %H:%M:%S")
	local_dt = tz.localize(naive_dt)
	system_tz = pytz.timezone(frappe.utils.get_system_timezone())
	system_dt = local_dt.astimezone(system_tz)

	created = 0
	skipped = 0

	for student_id in student_ids:
		# Skip if attendance already exists for this student + date + session
		exists = frappe.db.exists("EE Student Attendance", {
			"student": student_id,
			"date": date,
			"session": session,
		})
		if exists:
			skipped += 1
			continue

		student = frappe.get_cached_doc("EE Student", student_id)
		if not student.batch:
			frappe.throw(_("Student {0} has no batch assigned. Please assign a batch first.").format(student_id))
		doc = frappe.get_doc({
			"doctype": "EE Student Attendance",
			"student": student_id,
			"batch": student.batch,
			"date": date,
			"session": session,
			"check_in_time": system_dt.strftime("%Y-%m-%d %H:%M:%S"),
			"location_lat": 0,
			"location_lng": 0,
		})
		doc.insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()
	return {"created": created, "skipped": skipped}
