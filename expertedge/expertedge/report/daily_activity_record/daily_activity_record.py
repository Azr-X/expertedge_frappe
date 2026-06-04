import frappe
from frappe.utils import getdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 110},
		{"fieldname": "user", "label": "User", "fieldtype": "Link", "options": "User", "width": 180},
		{"fieldname": "full_name", "label": "Full Name", "fieldtype": "Data", "width": 150},
		{"fieldname": "check_in", "label": "Check In", "fieldtype": "Time", "width": 90},
		{"fieldname": "check_out", "label": "Check Out", "fieldtype": "Time", "width": 90},
		{"fieldname": "total_hours", "label": "Hours", "fieldtype": "Float", "width": 80, "precision": 1},
		{"fieldname": "leads_created", "label": "Leads Created", "fieldtype": "Int", "width": 110},
		{"fieldname": "leads_contacted", "label": "Leads Contacted", "fieldtype": "Int", "width": 120},
		{"fieldname": "students_converted", "label": "Conversions", "fieldtype": "Int", "width": 100},
		{"fieldname": "counselling_sessions", "label": "Counselling", "fieldtype": "Int", "width": 100},
		{"fieldname": "calls_made", "label": "Calls", "fieldtype": "Int", "width": 80},
		{"fieldname": "payment_links", "label": "Pay Links", "fieldtype": "Int", "width": 90},
		{"fieldname": "comments_added", "label": "Comments", "fieldtype": "Int", "width": 90},
		{"fieldname": "versions_count", "label": "Changes", "fieldtype": "Int", "width": 90},
	]


def get_data(filters):
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	user_filter = filters.get("user")

	users = get_active_users(from_date, to_date, user_filter)
	attendance_map = get_attendance_map(from_date, to_date, user_filter)

	# Merge attendance users into active users
	for user, dates in attendance_map.items():
		users.setdefault(user, set()).update(dates)

	data = []
	for user, dates in users.items():
		full_name = frappe.db.get_value("User", user, "full_name") or user
		for date in sorted(dates):
			day_start = f"{date} 00:00:00"
			day_end = f"{date} 23:59:59"

			row = {
				"date": date,
				"user": user,
				"full_name": full_name,
			}

			# Attendance
			att = attendance_map.get(user, {}).get(date)
			if att:
				row["check_in"] = str(att["check_in"].time()) if att.get("check_in") else None
				row["check_out"] = str(att["check_out"].time()) if att.get("check_out") else None
				row["total_hours"] = att.get("total_hours") or 0
			else:
				row["check_in"] = None
				row["check_out"] = None
				row["total_hours"] = 0

			row["leads_created"] = frappe.db.count("EE Lead", {
				"owner": user,
				"creation": ["between", [day_start, day_end]],
			})

			row["leads_contacted"] = frappe.db.count("EE Lead", {
				"handled_by": user,
				"first_contacted_on": ["between", [day_start, day_end]],
			})

			row["students_converted"] = frappe.db.count("EE Student", {
				"owner": user,
				"creation": ["between", [day_start, day_end]],
			})

			# Counselling sessions conducted
			row["counselling_sessions"] = frappe.db.count("EE Counselling Session", {
				"counsellor": user,
				"conducted_on": ["between", [day_start, day_end]],
			})

			# Call logs
			row["calls_made"] = frappe.db.count("EE Call Log", {
				"caller": user,
				"call_on": ["between", [day_start, day_end]],
			})

			# Payment links generated
			row["payment_links"] = frappe.db.count("EE Nomod Payment Link", {
				"owner": user,
				"creation": ["between", [day_start, day_end]],
			})

			row["comments_added"] = frappe.db.count("Comment", {
				"owner": user,
				"comment_type": "Comment",
				"creation": ["between", [day_start, day_end]],
			})

			row["versions_count"] = frappe.db.count("Version", {
				"owner": user,
				"creation": ["between", [day_start, day_end]],
			})

			# Skip completely empty rows (no attendance, no activity)
			has_activity = any([
				row.get("check_in"),
				row["leads_created"], row["leads_contacted"],
				row["students_converted"], row["counselling_sessions"],
				row["calls_made"], row["payment_links"],
				row["comments_added"], row["versions_count"],
			])
			if not has_activity:
				continue

			data.append(row)

	data.sort(key=lambda r: (r["date"], r["user"]))
	return data


def get_attendance_map(from_date, to_date, user_filter=None):
	"""Return {user: {date: attendance_dict}}."""
	filters = {"attendance_date": ["between", [from_date, to_date]]}
	if user_filter:
		filters["employee"] = user_filter

	records = frappe.get_all(
		"EE Attendance",
		filters=filters,
		fields=["employee", "attendance_date", "check_in", "check_out", "total_hours"],
	)

	att_map = {}
	for r in records:
		att_map.setdefault(r.employee, {})[r.attendance_date] = {
			"check_in": r.check_in,
			"check_out": r.check_out,
			"total_hours": r.total_hours,
		}
	return att_map


def get_active_users(from_date, to_date, user_filter=None):
	"""Find all users who did anything in the date range."""
	users = {}
	day_start = f"{from_date} 00:00:00"
	day_end = f"{to_date} 23:59:59"

	sources = [
		("EE Lead", "owner", "creation"),
		("EE Lead", "handled_by", "first_contacted_on"),
		("EE Student", "owner", "creation"),
		("EE Counselling Session", "counsellor", "conducted_on"),
		("EE Call Log", "caller", "call_on"),
		("EE Nomod Payment Link", "owner", "creation"),
		("Comment", "owner", "creation"),
		("Version", "owner", "creation"),
	]

	for doctype, user_field, date_field in sources:
		filters = {date_field: ["between", [day_start, day_end]]}
		if user_filter:
			filters[user_field] = user_filter

		try:
			records = frappe.get_all(
				doctype,
				filters=filters,
				fields=[user_field, date_field],
				limit_page_length=0,
			)
		except Exception:
			continue

		for r in records:
			u = r.get(user_field)
			d = r.get(date_field)
			if u and d:
				users.setdefault(u, set()).add(getdate(d))

	return users
