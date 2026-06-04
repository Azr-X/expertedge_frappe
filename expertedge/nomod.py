"""Nomod API client for ExpertEdge.

Documented endpoints only:
- POST /v1/links — create payment link
- POST /v1/checkout — create checkout session

API Reference: https://nomod.com/docs/api-reference/introduction
Base URL: https://api.nomod.com/v1
Auth: X-API-KEY header

Webhooks (Svix-based):
- charge.completed, charge.authorised, charge.failed, etc.
- Signature: HMAC-SHA256 via svix-id, svix-timestamp, svix-signature headers
"""

import frappe
from frappe import _
import requests
from frappe.utils import add_days, nowdate


class NomodAPIError(Exception):
	def __init__(self, status_code, message, error_code=None):
		self.status_code = status_code
		self.error_code = error_code
		super().__init__(message)


def get_settings():
	"""Get Nomod Settings singleton."""
	return frappe.get_cached_doc("Nomod Settings")


def _get_headers():
	settings = get_settings()
	api_key = settings.get_api_key()
	if not api_key:
		frappe.throw(_("Nomod API Key not configured. Go to Nomod Settings."))
	return {
		"X-API-KEY": api_key,
		"Content-Type": "application/json",
	}


def _request(method, path, data=None, params=None):
	"""Make an authenticated request to the Nomod API."""
	settings = get_settings()
	url = f"{settings.get_base_url()}/{path.lstrip('/')}"
	headers = _get_headers()

	try:
		response = requests.request(
			method=method,
			url=url,
			json=data,
			params=params,
			headers=headers,
			timeout=30,
		)
	except requests.exceptions.RequestException as e:
		frappe.throw(_("Nomod API connection error: {0}").format(str(e)))

	if response.status_code in (200, 201):
		return response.json()

	try:
		error_data = response.json()
		error_msg = error_data.get("detail") or error_data.get("message") or str(error_data)
		error_code = error_data.get("code")
	except Exception:
		error_msg = response.text
		error_code = None

	raise NomodAPIError(
		status_code=response.status_code,
		message=f"Nomod API error ({response.status_code}): {error_msg}",
		error_code=error_code,
	)


def create_link(amount, currency, title=None, note=None, reference=None,
                success_url=None, failure_url=None, expiry_date=None):
	"""Create a Nomod payment link.

	Documented: POST /v1/links
	https://nomod.com/docs/api-reference/generate-link
	"""
	settings = get_settings()

	data = {
		"currency": currency or settings.default_currency or "AED",
		"items": [{
			"name": title or "Payment",
			"amount": str(amount),
			"quantity": 1,
		}],
		"allow_service_fee": bool(settings.allow_service_fee),
		"allow_tabby": bool(settings.allow_tabby),
		"allow_tamara": bool(settings.allow_tamara),
	}

	if title:
		data["title"] = title[:50]
	if note:
		data["note"] = note[:280]

	redirect_success = success_url or settings.default_success_url
	redirect_failure = failure_url or settings.default_failure_url
	if redirect_success:
		data["success_url"] = redirect_success
	if redirect_failure:
		data["failure_url"] = redirect_failure

	if expiry_date:
		data["expiry_date"] = str(expiry_date)
	elif settings.payment_expiry_days:
		data["expiry_date"] = str(add_days(nowdate(), settings.payment_expiry_days))

	return _request("POST", "links", data=data)


def verify_webhook_signature(payload, headers):
	"""Verify Nomod/Svix webhook signature.

	Args:
		payload: Raw request body (bytes)
		headers: Dict with svix-id, svix-timestamp, svix-signature

	Returns:
		True if signature valid, False otherwise
	"""
	import hmac
	import hashlib
	import base64
	import time

	settings = get_settings()
	secret = settings.get_password("webhook_secret") if settings.webhook_secret else None
	if not secret:
		frappe.log_error("Nomod webhook: no webhook_secret configured")
		return False

	svix_id = headers.get("svix-id")
	svix_timestamp = headers.get("svix-timestamp")
	svix_signature = headers.get("svix-signature")

	if not all([svix_id, svix_timestamp, svix_signature]):
		return False

	# Reject if timestamp older than 5 minutes
	try:
		ts = int(svix_timestamp)
		if abs(time.time() - ts) > 300:
			frappe.log_error("Nomod webhook: timestamp too old/new")
			return False
	except (ValueError, TypeError):
		return False

	# Compute expected signature
	# Secret format: "whsec_<base64>" — strip prefix
	secret_part = secret.split("_", 1)[1] if "_" in secret else secret
	secret_bytes = base64.b64decode(secret_part)

	signed_content = f"{svix_id}.{svix_timestamp}.{payload.decode('utf-8')}"
	expected = base64.b64encode(
		hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
	).decode("utf-8")

	# svix-signature can have multiple sigs: "v1,sig1 v1,sig2"
	for sig in svix_signature.split(" "):
		sig_value = sig.split(",", 1)[1] if "," in sig else sig
		if hmac.compare_digest(expected, sig_value):
			return True

	return False
