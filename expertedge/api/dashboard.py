import frappe
from frappe.utils import nowdate, add_months, getdate, flt, pretty_date


@frappe.whitelist()
def get_leads_by_source():
	"""Lead count grouped by source — for donut chart."""
	data = frappe.db.sql("""
		SELECT ls.source_name as label, COUNT(l.name) as value
		FROM `tabEE Lead` l
		JOIN `tabEE Lead Source` ls ON ls.name = l.lead_source
		GROUP BY l.lead_source
		ORDER BY value DESC
	""", as_dict=True)
	return data


@frappe.whitelist()
def get_conversion_funnel():
	"""Count per lead status — for funnel/bar chart."""
	statuses = [
		"New", "Contacted", "Brochure Sent", "Docs Requested", "Docs Received",
		"Docs Verified", "Counselling Scheduled", "Counselling Done",
		"Confirmed", "Converted", "Lost",
	]
	data = []
	for s in statuses:
		count = frappe.db.count("EE Lead", {"status": s})
		data.append({"status": s, "count": count})
	return data


@frappe.whitelist()
def get_payments_by_month():
	"""Sum of paid payment link amounts by month — last 6 months."""
	six_months_ago = add_months(getdate(nowdate()), -6)
	data = frappe.db.sql("""
		SELECT
			DATE_FORMAT(paid_on, '%%Y-%%m') as month,
			SUM(amount) as total
		FROM `tabEE Nomod Payment Link`
		WHERE status = 'Paid' AND paid_on >= %s
		GROUP BY DATE_FORMAT(paid_on, '%%Y-%%m')
		ORDER BY month
	""", six_months_ago, as_dict=True)
	return data


@frappe.whitelist()
def get_enrollments_by_batch():
	"""Student count grouped by batch."""
	data = frappe.db.sql("""
		SELECT
			COALESCE(b.batch_name, 'Unassigned') as batch,
			COUNT(s.name) as count
		FROM `tabEE Student` s
		LEFT JOIN `tabEE Batch` b ON b.name = s.batch
		WHERE s.status NOT IN ('Dropped')
		GROUP BY s.batch
		ORDER BY count DESC
	""", as_dict=True)
	return data


@frappe.whitelist()
def get_dashboard_stats():
	"""Quick stats for number cards."""
	today = nowdate()
	return {
		"new_leads_today": frappe.db.count("EE Lead", {
			"creation": [">=", today],
			"creation": ["<=", today + " 23:59:59"],
		}),
		"calls_today": frappe.db.sql("""
			SELECT COUNT(*) FROM `tabEE Call Log`
			WHERE DATE(call_on) = %s
		""", today)[0][0],
		"leads_in_counselling": frappe.db.count("EE Lead", {
			"status": ["in", ["Counselling Scheduled", "Counselling Done"]],
		}),
		"pending_pre_approval": frappe.db.count("EE Student", {
			"status": "Pre-Approval Pending",
		}),
		"pending_balance": frappe.db.count("EE Student", {
			"status": "Balance Pending",
		}),
		"enrolled_this_month": frappe.db.sql("""
			SELECT COUNT(*) FROM `tabEE Student`
			WHERE status IN ('Enrolled', 'Materials Issued')
			AND MONTH(creation) = MONTH(CURDATE())
			AND YEAR(creation) = YEAR(CURDATE())
		""")[0][0],
	}


@frappe.whitelist()
def get_recent_activity():
	"""Recent updates across leads and students — last 15 items."""
	activities = []

	# Recent lead status changes
	leads = frappe.db.sql("""
		SELECT name, lead_name, status, modified, modified_by
		FROM `tabEE Lead`
		ORDER BY modified DESC
		LIMIT 10
	""", as_dict=True)
	for l in leads:
		activities.append({
			"time": l.modified,
			"ago": pretty_date(l.modified),
			"icon": "lead" if l.status not in ("Converted", "Lost") else ("check" if l.status == "Converted" else "close"),
			"color": _status_color(l.status),
			"text": f"{l.lead_name}",
			"detail": l.status,
			"route": f"/app/ee-lead/{l.name}",
			"user": l.modified_by,
		})

	# Recent student updates
	students = frappe.db.sql("""
		SELECT name, student_name, status, modified, modified_by
		FROM `tabEE Student`
		ORDER BY modified DESC
		LIMIT 10
	""", as_dict=True)
	for s in students:
		activities.append({
			"time": s.modified,
			"ago": pretty_date(s.modified),
			"icon": "student",
			"color": _status_color(s.status),
			"text": f"{s.student_name}",
			"detail": s.status,
			"route": f"/app/ee-student/{s.name}",
			"user": s.modified_by,
		})

	# Recent payments
	payments = frappe.db.sql("""
		SELECT pl.name, pl.candidate_name, pl.status, pl.amount, pl.currency, pl.modified
		FROM `tabEE Nomod Payment Link` pl
		WHERE pl.status = 'Paid'
		ORDER BY pl.modified DESC
		LIMIT 5
	""", as_dict=True)
	for p in payments:
		activities.append({
			"time": p.modified,
			"ago": pretty_date(p.modified),
			"icon": "payment",
			"color": "green",
			"text": f"{p.candidate_name}",
			"detail": f"Paid {p.currency} {flt(p.amount):,.0f}",
			"route": f"/app/ee-nomod-payment-link/{p.name}",
			"user": "",
		})

	# Sort by time descending, take top 15
	activities.sort(key=lambda x: x["time"], reverse=True)
	return activities[:15]


@frappe.whitelist()
def get_payment_links_summary():
	"""Payment links grouped by status with amounts."""
	data = frappe.db.sql("""
		SELECT
			status,
			COUNT(*) as count,
			COALESCE(SUM(amount), 0) as total_amount,
			currency
		FROM `tabEE Nomod Payment Link`
		GROUP BY status, currency
		ORDER BY FIELD(status, 'Generated', 'Sent', 'Paid', 'Draft', 'Expired', 'Cancelled')
	""", as_dict=True)

	# Recent payment links (last 10)
	recent = frappe.db.sql("""
		SELECT name, candidate_name, purpose, amount, currency, status, modified
		FROM `tabEE Nomod Payment Link`
		ORDER BY modified DESC
		LIMIT 10
	""", as_dict=True)
	for r in recent:
		r["ago"] = pretty_date(r["modified"])

	return {"summary": data, "recent": recent}


def _status_color(status):
	colors = {
		"New": "red", "Contacted": "blue", "Brochure Sent": "blue",
		"Docs Requested": "orange", "Docs Received": "orange",
		"Docs Verified": "cyan", "Counselling Scheduled": "purple",
		"Counselling Done": "purple", "Confirmed": "green",
		"Converted": "green", "Lost": "grey",
		"Pre-Approval Pending": "red", "Pre-Approval Paid": "blue",
		"CMA Registration": "orange", "CMA Registered": "cyan",
		"Balance Pending": "orange", "Fully Paid": "green",
		"Enrolled": "green", "Materials Issued": "green", "Dropped": "grey",
	}
	return colors.get(status, "grey")
