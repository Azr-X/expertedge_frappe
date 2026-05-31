"""Nomod API client for ExpertEdge.

API Reference: https://nomod.com/docs/api-reference/introduction
Base URL: https://api.nomod.com/v1
Auth: X-API-KEY header
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

	# Handle errors
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

	Args:
		amount: Payment amount (decimal string or number)
		currency: ISO 4217 currency code (e.g. AED)
		title: Link display name (max 50 chars)
		note: Description (max 280 chars)
		reference: Internal reference (stored in item SKU)
		success_url: Redirect after successful payment
		failure_url: Redirect after failed payment
		expiry_date: Auto-expire date (YYYY-MM-DD)

	Returns:
		dict: Nomod link object with id, url, reference_id, etc.
	"""
	settings = get_settings()

	data = {
		"currency": currency or settings.default_currency or "AED",
		"items": [{
			"name": title or "Payment",
			"amount": str(amount),
			"quantity": 1,
			"sku": reference or "",
		}],
		"allow_service_fee": bool(settings.allow_service_fee),
		"allow_tabby": bool(settings.allow_tabby),
		"allow_tamara": bool(settings.allow_tamara),
	}

	if title:
		data["title"] = title[:50]
	if note:
		data["note"] = note[:280]

	# Success/failure URLs
	redirect_success = success_url or settings.default_success_url
	redirect_failure = failure_url or settings.default_failure_url
	if redirect_success:
		data["success_url"] = redirect_success
	if redirect_failure:
		data["failure_url"] = redirect_failure

	# Expiry
	if expiry_date:
		data["expiry_date"] = str(expiry_date)
	elif settings.payment_expiry_days:
		data["expiry_date"] = str(add_days(nowdate(), settings.payment_expiry_days))

	return _request("POST", "links", data=data)


def get_link(link_id):
	"""Retrieve a Nomod link by ID.

	Args:
		link_id: UUID of the Nomod link

	Returns:
		dict: Nomod link object
	"""
	return _request("GET", f"links/{link_id}")


def list_links(currency=None, status=None, page=1, page_size=20, search=None):
	"""List Nomod payment links.

	Returns:
		dict: {count, next, previous, results: [...]}
	"""
	params = {"page": page, "page_size": page_size}
	if currency:
		params["currency"] = currency
	if status:
		params["status"] = status
	if search:
		params["search"] = search
	return _request("GET", "links", params=params)


def delete_link(link_id):
	"""Delete/disable a Nomod link."""
	return _request("DELETE", f"links/{link_id}")


def get_charge(charge_id):
	"""Retrieve a charge (completed payment) by ID.

	Args:
		charge_id: UUID of the charge

	Returns:
		dict: Charge object with status, amount, payment_method, etc.
	"""
	return _request("GET", f"charges/{charge_id}")


def list_charges(link_id=None, status=None, currency=None, page=1, page_size=20):
	"""List charges, optionally filtered by link_id.

	Args:
		link_id: Filter charges for a specific link
		status: Filter by charge status
		currency: Filter by currency
		page: Page number
		page_size: Results per page

	Returns:
		dict: {count, next, previous, results: [...]}
	"""
	params = {"page": page, "page_size": page_size}
	if link_id:
		params["link_id"] = link_id
	if status:
		params["status"] = status
	if currency:
		params["currency"] = currency
	return _request("GET", "charges", params=params)


def refund_charge(charge_id, amount=None):
	"""Refund a charge (full or partial).

	Args:
		charge_id: UUID of the charge to refund
		amount: Partial refund amount (omit for full refund)

	Returns:
		dict: Refund result
	"""
	data = {}
	if amount is not None:
		data["amount"] = str(amount)
	return _request("POST", f"charges/{charge_id}/refund", data=data)
