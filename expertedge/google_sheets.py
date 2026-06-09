import frappe
from frappe.utils import get_datetime
import csv
import io
import re
import requests


PLATFORM_MAP = {
	"ig": "Instagram",
	"fb": "Facebook",
	"in": "LinkedIn",
	"instagram": "Instagram",
	"facebook": "Facebook",
	"linkedin": "LinkedIn",
}

EXPERIENCE_MAP = {
	"below_5_years": 3,
	"5_to_10_years": 7,
	"10_to_15_years": 12,
	"above_15_years": 18,
	"15+_years": 18,
}


def _extract_sheet_id(url):
	"""Extract spreadsheet ID from Google Sheets URL."""
	match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url or "")
	if not match:
		frappe.throw("Invalid Google Sheet URL in ExpertEdge Settings")
	return match.group(1)


def _get_gid(url):
	"""Extract gid from URL if present, default 0."""
	match = re.search(r"gid=(\d+)", url or "")
	return match.group(1) if match else "0"


def _fetch_sheet_csv(sheet_url):
	"""Fetch public Google Sheet as CSV. No auth needed for public sheets."""
	sheet_id = _extract_sheet_id(sheet_url)
	gid = _get_gid(sheet_url)
	csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

	resp = requests.get(csv_url, timeout=30)
	resp.raise_for_status()
	resp.encoding = "utf-8"
	return resp.text


def _clean_phone(phone_str):
	"""Strip 'p:' prefix and clean phone number."""
	if not phone_str:
		return ""
	phone = phone_str.strip()
	if phone.startswith("p:"):
		phone = phone[2:]
	return phone.strip()


def _normalize_phone(phone_str):
	"""Normalize phone to digits-only for dedup comparison.

	Strips +, spaces, dashes, parens, leading 00. Returns last 9 digits
	which are the subscriber number (works for most GCC/Indian numbers).
	"""
	if not phone_str:
		return ""
	digits = re.sub(r"[^\d]", "", phone_str)
	if digits.startswith("00"):
		digits = digits[2:]
	# Last 9 digits = subscriber number (avoids country code mismatches)
	return digits[-9:] if len(digits) >= 9 else digits


def _map_platform(platform_str):
	"""Map platform code to EE Lead Source name."""
	return PLATFORM_MAP.get((platform_str or "").lower().strip(), platform_str or "")


def _map_experience(exp_str):
	"""Map experience string to approximate years."""
	return EXPERIENCE_MAP.get((exp_str or "").lower().strip(), 0)


def _lead_exists(sheet_lead_id=None, email=None, mobile_no=None):
	"""Check if lead already exists by email, normalized mobile, or sheet_lead_id.

	Email and phone checked FIRST — these are the real identity.
	sheet_lead_id is a fallback for leads with placeholder emails and no phone.
	"""
	# Email check — case-insensitive via LIKE or LOWER
	if email and not email.startswith("noemail-"):
		existing = frappe.db.sql(
			"SELECT name FROM `tabEE Lead` WHERE LOWER(email) = %s LIMIT 1",
			email.lower(),
		)
		if existing:
			return existing[0][0]

	# Phone check — normalized (last 9 digits)
	if mobile_no:
		norm = _normalize_phone(mobile_no)
		if norm and len(norm) >= 7:
			# Exact match first (fast)
			existing = frappe.db.get_value("EE Lead", {"mobile_no": mobile_no}, "name")
			if existing:
				return existing
			# Normalized scan
			all_leads = frappe.get_all(
				"EE Lead",
				filters={"mobile_no": ["is", "set"]},
				fields=["name", "mobile_no"],
				limit_page_length=0,
			)
			for lead in all_leads:
				if _normalize_phone(lead.mobile_no) == norm:
					return lead.name

	# sheet_lead_id fallback
	if sheet_lead_id:
		existing = frappe.db.exists("EE Lead", {"sheet_lead_id": sheet_lead_id})
		if existing:
			return existing

	return None


def _ensure_lead_source(source_name):
	"""Create EE Lead Source if it doesn't exist."""
	if not source_name:
		return None
	if not frappe.db.exists("EE Lead Source", {"source_name": source_name}):
		frappe.get_doc({
			"doctype": "EE Lead Source",
			"source_name": source_name,
		}).insert(ignore_permissions=True)
	return source_name


def sync_leads_from_sheet():
	"""Pull new leads from Google Sheet into EE Lead.

	Returns count of new leads created.
	"""
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	if not settings.google_sheet_url:
		return 0

	csv_text = _fetch_sheet_csv(settings.google_sheet_url)
	reader = csv.DictReader(io.StringIO(csv_text))

	created = 0
	for row in reader:
		try:
			sheet_lead_id = (row.get("id") or "").strip()
			email = (row.get("email") or "").strip().lower()
			phone = _clean_phone(row.get("phone_number"))
			full_name = (row.get("full_name") or "").strip()

			if not full_name or not (email or phone):
				continue

			# Dedup check
			if _lead_exists(sheet_lead_id, email, phone):
				continue

			platform = _map_platform(row.get("platform"))
			lead_source = _ensure_lead_source(platform or "Google Sheet")

			# Parse experience
			exp_col = None
			for key in row:
				if "experience" in key.lower():
					exp_col = key
					break
			years_exp = _map_experience(row.get(exp_col)) if exp_col else 0

			# Parse planning/intent
			intent_col = None
			for key in row:
				if "planning" in key.lower() or "started" in key.lower():
					intent_col = key
					break
			intent = (row.get(intent_col) or "").replace("_", " ").strip() if intent_col else ""

			# Campaign info
			campaign_name = row.get("campaign_name", "")
			ad_name = row.get("ad_name", "")
			campaign_str = f"{campaign_name}"
			if ad_name and ad_name != campaign_name:
				campaign_str += f" / {ad_name}"

			# Country
			country_code = (row.get("country") or "").strip()
			city = (row.get("city") or "").strip()
			nationality = _resolve_country(country_code)

			# Created time
			created_time = row.get("created_time", "")
			lead_received_on = None
			if created_time:
				try:
					lead_received_on = get_datetime(created_time)
				except Exception:
					pass

			lead = frappe.new_doc("EE Lead")
			lead.lead_name = full_name
			lead.email = email or f"noemail-{sheet_lead_id}@placeholder.local"
			lead.mobile_no = phone
			lead.lead_source = lead_source
			lead.campaign = campaign_str.strip()
			lead.nationality = nationality
			lead.years_of_experience = years_exp
			lead.sheet_lead_id = sheet_lead_id

			if intent:
				lead.next_action = f"Intent: {intent}"

			if city:
				lead.current_designation = city  # Reuse field for city until dedicated field exists

			if lead_received_on:
				lead.lead_received_on = lead_received_on

			frappe.flags.skip_duplicate_lead_throw = True
			try:
				lead.insert(ignore_permissions=True)
			finally:
				frappe.flags.skip_duplicate_lead_throw = False
			frappe.db.commit()
			created += 1

		except frappe.DuplicateEntryError:
			# Silently skip — duplicate caught by EE Lead before_insert
			frappe.db.rollback()
		except Exception:
			frappe.log_error(
				title=f"Google Sheet lead import error: {row.get('id', 'unknown')}",
				message=frappe.get_traceback(),
			)
			frappe.db.rollback()

	return created


def _resolve_country(code):
	"""Resolve 2-letter country code to Country doctype name."""
	if not code or len(code) != 2:
		return None
	code = code.upper()
	# Common mappings
	country_name = frappe.db.get_value("Country", {"code": code.lower()}, "name")
	return country_name
