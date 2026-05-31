import frappe
from frappe import _
from frappe.utils import cint


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_lead(lead_name, email, phone, country, program, phone_code="+91", state=None, message=None, source=None):
	"""Guest API for website lead/contact forms.

	POST /api/method/expertedge.api.create_lead
	"""
	_rate_limit()

	# Sanitize inputs
	lead_name = (lead_name or "").strip()
	email = (email or "").strip().lower()
	phone = (phone or "").strip()
	phone_code = (phone_code or "+91").strip()
	country = (country or "").strip()
	program = (program or "").strip()
	state = (state or "").strip() or None
	message = (message or "").strip() or None
	source = (source or "Website").strip()

	# Validate required fields
	if not lead_name or len(lead_name) < 2:
		frappe.throw(_("Name is required (min 2 characters)"), frappe.ValidationError)
	if not email or "@" not in email:
		frappe.throw(_("Valid email is required"), frappe.ValidationError)
	if not phone or len(phone) < 7:
		frappe.throw(_("Valid phone number is required"), frappe.ValidationError)
	if not country:
		frappe.throw(_("Country is required"), frappe.ValidationError)
	if not program:
		frappe.throw(_("Program is required"), frappe.ValidationError)

	# Resolve program name to EE Program (form sends display name like "CMA ANZ")
	program_doc = frappe.db.get_value("EE Program", {"program_name": program}, "name")
	if not program_doc:
		# Try exact match on name field
		program_doc = frappe.db.exists("EE Program", program)

	# Resolve country name to Country link
	country_doc = frappe.db.get_value("Country", {"name": country}, "name")
	if not country_doc:
		country_doc = frappe.db.get_value("Country", {"country_name": country}, "name")

	# Resolve lead source
	lead_source = frappe.db.exists("EE Lead Source", source) or "Website"

	# Check duplicate: same email + same program = return existing
	existing = frappe.db.get_value(
		"EE Lead",
		{"email": email, "program": program_doc} if program_doc else {"email": email},
		"name",
	)
	if existing:
		return {"status": "ok", "lead": existing, "duplicate": True}

	# Build mobile number with country code
	mobile = f"{phone_code}{phone}" if not phone.startswith("+") else phone

	lead = frappe.get_doc({
		"doctype": "EE Lead",
		"lead_name": lead_name,
		"email": email,
		"mobile_no": mobile,
		"nationality": country_doc,
		"state": state,
		"program": program_doc,
		"lead_source": lead_source,
		"remarks": message,
		"handled_by": None,
	})
	lead.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "ok", "lead": lead.name, "duplicate": False}


def _rate_limit():
	"""Simple rate limit: max 10 leads per IP per hour."""
	ip = frappe.local.request_ip
	cache_key = f"website_lead_ratelimit:{ip}"
	count = cint(frappe.cache.get_value(cache_key))
	if count >= 10:
		frappe.throw(_("Too many submissions. Please try again later."), frappe.RateLimitExceededError)
	frappe.cache.set_value(cache_key, count + 1, expires_in_sec=3600)
