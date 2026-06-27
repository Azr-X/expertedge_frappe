"""
Student Portal API — ExpertEdge

All methods are @frappe.whitelist(allow_guest=True).
Auth handled by token check inside each method, not Frappe session.
Next.js calls these server-side via API key auth.
"""

import hashlib
import math
import secrets

import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate, get_datetime, cstr, flt, today


# ─── Password Helpers ───────────────────────────────────────────────

def _hash_password(password):
	salt = secrets.token_hex(16)
	h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
	return f"{salt}:{h.hex()}"


def _verify_password(password, password_hash):
	if not password_hash:
		return False
	parts = password_hash.split(":")
	if len(parts) != 2:
		return False
	salt, stored_hash = parts
	computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
	return secrets.compare_digest(computed.hex(), stored_hash)


def _get_student_by_token(token):
	"""Look up student by auth_token. Returns doc or throws."""
	if not token:
		frappe.throw(_("Invalid or expired token"), frappe.AuthenticationError)
	student_name = frappe.db.get_value("EE Student", {"auth_token": token, "portal_enabled": 1}, "name")
	if not student_name:
		frappe.throw(_("Invalid or expired token"), frappe.AuthenticationError)
	return frappe.get_doc("EE Student", student_name)


def _haversine(lat1, lon1, lat2, lon2):
	R = 6_371_000
	phi1, phi2 = math.radians(lat1), math.radians(lat2)
	dphi = math.radians(lat2 - lat1)
	dlambda = math.radians(lon2 - lon1)
	a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
	return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Auth Methods ────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def login(email, password):
	"""Validate credentials, generate token, return student info."""
	email = cstr(email).strip().lower()
	if not email or not password:
		frappe.throw(_("Email and password are required"))

	student = frappe.db.get_value(
		"EE Student",
		{"email": email, "portal_enabled": 1},
		["name", "student_name", "password_hash", "must_change_password"],
		as_dict=True,
	)
	if not student:
		frappe.throw(_("Invalid email or password"), frappe.AuthenticationError)

	if not _verify_password(password, student.password_hash):
		frappe.throw(_("Invalid email or password"), frappe.AuthenticationError)

	# Generate new auth token
	token = secrets.token_urlsafe(32)
	frappe.db.set_value("EE Student", student.name, "auth_token", token, update_modified=False)
	frappe.db.commit()

	return {
		"token": token,
		"student_id": student.name,
		"name": student.student_name,
		"must_change_password": bool(student.must_change_password),
	}


@frappe.whitelist(allow_guest=True)
def get_student(token):
	"""Return full student data for portal display."""
	student = _get_student_by_token(token)

	# Get batch info
	batch_data = None
	if student.batch:
		batch_data = frappe.db.get_value(
			"EE Batch", student.batch,
			["batch_name", "program", "country", "city", "venue", "start_date",
			 "end_date", "timing", "status"],
			as_dict=True,
		)

	# Get program info
	program_data = None
	if student.program:
		program_data = frappe.db.get_value(
			"EE Program", student.program,
			["program_name", "program_code", "partner", "description"],
			as_dict=True,
		)

	# Today's attendance
	today_attendance = frappe.get_all(
		"EE Student Attendance",
		filters={"student": student.name, "date": today()},
		fields=["name", "check_in_time", "session", "outside_range"],
		order_by="check_in_time asc",
	)

	return {
		"student": {
			"name": student.name,
			"student_name": student.student_name,
			"email": student.email,
			"mobile_no": student.mobile_no,
			"date_of_birth": cstr(student.date_of_birth),
			"nationality": student.nationality,
			"state": student.state,
			"permanent_address": student.permanent_address,
			"pincode": student.pincode,
			"program": student.program,
			"batch": student.batch,
			"status": student.status,
			"must_change_password": bool(student.must_change_password),
		},
		"batch": batch_data,
		"program": program_data,
		"today_attendance": today_attendance,
	}


@frappe.whitelist(allow_guest=True)
def change_password(token, old_password, new_password):
	"""Change student password. Requires old password verification."""
	student = _get_student_by_token(token)

	if not _verify_password(old_password, student.password_hash):
		frappe.throw(_("Invalid current password"), frappe.AuthenticationError)

	if len(new_password) < 6:
		frappe.throw(_("Password must be at least 6 characters"))

	frappe.db.set_value("EE Student", student.name, {
		"password_hash": _hash_password(new_password),
		"must_change_password": 0,
	}, update_modified=False)
	frappe.db.commit()

	return {"success": True}


@frappe.whitelist(allow_guest=True)
def reset_password(email):
	"""Generate random password and email it to the student."""
	email = cstr(email).strip().lower()
	student = frappe.db.get_value(
		"EE Student",
		{"email": email, "portal_enabled": 1},
		["name", "student_name"],
		as_dict=True,
	)
	if not student:
		# Don't reveal if email exists
		return {"success": True}

	new_password = secrets.token_urlsafe(8)
	frappe.db.set_value("EE Student", student.name, {
		"password_hash": _hash_password(new_password),
		"must_change_password": 1,
	}, update_modified=False)
	frappe.db.commit()

	frappe.sendmail(
		recipients=[email],
		subject="ExpertEdge Portal — Password Reset",
		message=f"""
		<p>Hi {student.student_name},</p>
		<p>Your portal password has been reset. Use the following credentials to log in:</p>
		<p><strong>Email:</strong> {email}<br>
		<strong>New Password:</strong> {new_password}</p>
		<p>You will be required to change this password on your next login.</p>
		<p>— ExpertEdge Team</p>
		""",
	)

	return {"success": True}


@frappe.whitelist(allow_guest=True)
def update_profile(token, **kwargs):
	"""Update student profile fields."""
	student = _get_student_by_token(token)
	allowed_fields = ["mobile_no", "date_of_birth", "permanent_address", "state", "pincode", "nationality"]

	updates = {}
	for field in allowed_fields:
		if field in kwargs and kwargs[field]:
			updates[field] = kwargs[field]

	if updates:
		frappe.db.set_value("EE Student", student.name, updates)
		frappe.db.commit()

	return {"success": True}


# ─── Attendance Methods ──────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def check_geofence(token, lat, lng):
	"""Check if student is within geofence of batch venue."""
	student = _get_student_by_token(token)
	if not student.batch:
		frappe.throw(_("No batch assigned"))

	batch = frappe.get_cached_doc("EE Batch", student.batch)

	if not batch.location_lat or not batch.location_lng:
		return {"success": True, "batch_has_location": False, "is_outside_range": False}

	acceptable_range = batch.acceptable_range or 200
	distance = _haversine(flt(lat), flt(lng), flt(batch.location_lat), flt(batch.location_lng))

	return {
		"success": True,
		"batch_has_location": True,
		"is_outside_range": distance > acceptable_range,
		"distance": round(distance, 1),
		"acceptable_range": acceptable_range,
	}


@frappe.whitelist(allow_guest=True)
def check_in(token, lat, lng, accuracy=None, outside_range=0):
	"""Record student attendance check-in."""
	student = _get_student_by_token(token)
	if not student.batch:
		frappe.throw(_("No batch assigned"))

	batch = frappe.get_cached_doc("EE Batch", student.batch)
	now = now_datetime()
	today_str = nowdate()

	# Check max 2 check-ins per day
	existing = frappe.get_all(
		"EE Student Attendance",
		filters={"student": student.name, "date": today_str},
		fields=["name", "session", "check_in_time"],
		order_by="check_in_time desc",
	)

	if len(existing) >= 2:
		frappe.throw(_("Maximum 2 check-ins per day reached"))

	# Cooldown check
	cooldown = batch.check_in_cooldown_minutes or 5
	if existing:
		last_checkin = get_datetime(existing[0].check_in_time)
		diff_minutes = (now - last_checkin).total_seconds() / 60
		if diff_minutes < cooldown:
			frappe.throw(_("Please wait {0} minutes between check-ins").format(cooldown))

	# Determine session
	break_time = cstr(batch.break_time) or "12:00:00"
	current_time = now.strftime("%H:%M:%S")
	session = "First Half" if current_time < break_time else "Second Half"

	# Check duplicate session
	for e in existing:
		if e.session == session:
			frappe.throw(_("Already checked in for {0}").format(session))

	# Create attendance log
	att = frappe.get_doc({
		"doctype": "EE Student Attendance",
		"student": student.name,
		"batch": student.batch,
		"date": today_str,
		"check_in_time": now,
		"session": session,
		"location_lat": flt(lat),
		"location_lng": flt(lng),
		"location_accuracy": flt(accuracy) if accuracy else None,
		"outside_range": int(outside_range),
	})
	att.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"success": True,
		"message": f"Checked in for {session}",
		"check_in_time": cstr(now),
		"session": session,
	}


@frappe.whitelist(allow_guest=True)
def get_attendance_status(token):
	"""Get today's attendance status for student."""
	student = _get_student_by_token(token)

	logs = frappe.get_all(
		"EE Student Attendance",
		filters={"student": student.name, "date": today()},
		fields=["name", "check_in_time", "session", "outside_range",
				"location_lat", "location_lng"],
		order_by="check_in_time asc",
	)

	return {"success": True, "check_ins": logs}


@frappe.whitelist(allow_guest=True)
def get_attendance_history(token, from_date=None, to_date=None):
	"""Get attendance history for student."""
	student = _get_student_by_token(token)

	filters = {"student": student.name}
	if from_date:
		filters["date"] = [">=", from_date]
	if to_date:
		if "date" in filters:
			filters["date"] = ["between", [from_date, to_date]]
		else:
			filters["date"] = ["<=", to_date]

	logs = frappe.get_all(
		"EE Student Attendance",
		filters=filters,
		fields=["name", "date", "check_in_time", "session", "outside_range"],
		order_by="date desc, check_in_time asc",
		limit=100,
	)

	return {"success": True, "history": logs}


# ─── Learn / Course Material Methods ────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_materials(token):
	"""Get all published materials for student's program/batch."""
	student = _get_student_by_token(token)
	if not student.program:
		return {"materials": []}

	filters = {
		"program": student.program,
		"is_published": 1,
	}

	# Get materials for student's batch + materials without specific batch
	materials = frappe.get_all(
		"EE Course Material",
		filters=filters,
		or_filters=[
			{"batch": student.batch},
			{"batch": ["is", "not set"]},
		] if student.batch else [],
		fields=["name", "title", "category", "sequence", "pdf_file",
				"answer_pdf", "answers_unlocked", "description", "batch"],
		order_by="sequence asc, title asc",
	)

	# Strip answer_pdf URL if not unlocked
	for m in materials:
		if not m.answers_unlocked:
			m["answer_pdf"] = None

	return {"materials": materials}


@frappe.whitelist(allow_guest=True)
def get_material_file(token, material_name, file_type="pdf"):
	"""Get file URL for a specific material. file_type: 'pdf' or 'answer'."""
	student = _get_student_by_token(token)

	material = frappe.get_doc("EE Course Material", material_name)

	# Verify student has access
	if material.program != student.program:
		frappe.throw(_("Access denied"))
	if material.batch and material.batch != student.batch:
		frappe.throw(_("Access denied"))
	if not material.is_published:
		frappe.throw(_("Material not available"))

	if file_type == "answer":
		if not material.answers_unlocked:
			frappe.throw(_("Answers are not yet available"))
		return {"url": material.answer_pdf}

	return {"url": material.pdf_file}


# ─── Announcements ───────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_announcements(token):
	"""Get active announcements for student's program/batch."""
	student = _get_student_by_token(token)
	today_str = today()

	filters = {
		"is_published": 1,
		"publish_date": ["<=", today_str],
	}

	announcements = frappe.get_all(
		"EE Announcement",
		filters=filters,
		or_filters=[
			{"expiry_date": [">=", today_str]},
			{"expiry_date": ["is", "not set"]},
		],
		fields=["name", "title", "content", "priority", "publish_date",
				"program", "batch"],
		order_by="priority desc, publish_date desc",
		limit=20,
	)

	# Filter by program/batch relevance
	result = []
	for a in announcements:
		if a.program and a.program != student.program:
			continue
		if a.batch and a.batch != student.batch:
			continue
		result.append(a)

	return {"announcements": result}


# ─── Events ─────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_events(token):
	"""Get upcoming events for student's program/batch."""
	student = _get_student_by_token(token)
	today_str = today()

	events = frappe.get_all(
		"EE Event",
		filters={
			"is_published": 1,
			"event_date": [">=", today_str],
		},
		fields=["name", "title", "event_type", "event_date", "start_time",
				"end_time", "venue", "description", "image", "registration_url",
				"program", "batch"],
		order_by="event_date asc",
		limit=20,
	)

	result = []
	for e in events:
		if e.program and e.program != student.program:
			continue
		if e.batch and e.batch != student.batch:
			continue
		result.append(e)

	return {"events": result}


# ─── CPD Programs ────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_cpd_programs(token):
	"""Get published CPD programs."""
	student = _get_student_by_token(token)

	programs = frappe.get_all(
		"EE CPD Program",
		filters={"is_published": 1},
		fields=["name", "title", "provider", "cpd_hours", "start_date",
				"end_date", "fee", "currency", "description", "image",
				"registration_url", "program"],
		order_by="start_date asc",
	)

	result = []
	for p in programs:
		if p.program and p.program != student.program:
			continue
		result.append(p)

	return {"cpd_programs": result}


# ─── Services ────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_services(token):
	"""Get published services."""
	_get_student_by_token(token)  # verify auth

	services = frappe.get_all(
		"EE Service",
		filters={"is_published": 1},
		fields=["name", "title", "service_type", "fee", "currency",
				"description", "icon", "sequence"],
		order_by="sequence asc, title asc",
	)

	return {"services": services}


# ─── Schedule ────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_schedule(token, from_date=None, to_date=None):
	"""Get schedule entries for student's batch."""
	student = _get_student_by_token(token)
	if not student.batch:
		return {"schedule": []}

	filters = {"batch": student.batch}
	if from_date and to_date:
		filters["date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["date"] = [">=", from_date]
	else:
		# Default: from today onwards
		filters["date"] = [">=", today()]

	entries = frappe.get_all(
		"EE Schedule Entry",
		filters=filters,
		fields=["name", "title", "session_type", "date", "start_time",
				"end_time", "venue", "instructor", "description"],
		order_by="date asc, start_time asc",
		limit=50,
	)

	return {"schedule": entries}


# ─── Admin Helper — Set Portal Password ─────────────────────────────

@frappe.whitelist()
def set_portal_password(student_name, password):
	"""Admin method to set a student's portal password and enable portal."""
	frappe.only_for(["System Manager", "EE Manager"])

	if len(password) < 6:
		frappe.throw(_("Password must be at least 6 characters"))

	frappe.db.set_value("EE Student", student_name, {
		"password_hash": _hash_password(password),
		"portal_enabled": 1,
		"must_change_password": 1,
		"auth_token": None,
	})
	frappe.db.commit()

	return {"success": True}
