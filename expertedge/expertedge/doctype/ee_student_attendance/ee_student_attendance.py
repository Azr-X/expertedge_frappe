import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime, get_datetime, cstr
import math


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
