import frappe
from frappe.utils import nowdate, add_months, getdate, flt


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
		WHERE s.status IN ('Enrolled', 'Materials Issued')
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
