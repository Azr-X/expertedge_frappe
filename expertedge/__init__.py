__version__ = "0.0.1"

import frappe
from frappe.website.doctype.web_form.web_form import WebForm

_original_has_web_form_permission = WebForm.has_web_form_permission
_original_get_context = WebForm.get_context


def _patched_has_web_form_permission(self, doctype, name, ptype="read"):
	"""Allow token-validated guest access to EE Student web form."""
	if (
		doctype == "EE Student"
		and frappe.session.user == "Guest"
		and frappe.form_dict.get("token")
	):
		token = frappe.form_dict.get("token")
		student = frappe.db.get_value(
			"EE Student", name, ["web_form_token", "allow_web_edit"], as_dict=True
		)
		if student and student.web_form_token == token and student.allow_web_edit:
			return True
	return _original_has_web_form_permission(self, doctype, name, ptype)


def _patched_get_context(self, context):
	"""Skip guest block for token-validated EE Student access."""
	if (
		self.doc_type == "EE Student"
		and frappe.session.user == "Guest"
		and frappe.form_dict.get("name")
		and frappe.form_dict.get("token")
	):
		token = frappe.form_dict.get("token")
		name = frappe.form_dict.get("name")
		student = frappe.db.get_value(
			"EE Student", name, ["web_form_token", "allow_web_edit"], as_dict=True
		)
		if not (student and student.web_form_token == token and student.allow_web_edit):
			frappe.throw("Invalid or expired link", frappe.PermissionError)

		# Bypass the Guest check in original get_context by temporarily setting user
		frappe.session.user = "token-validated-guest"
		try:
			result = _original_get_context(self, context)
		finally:
			frappe.session.user = "Guest"
		return result

	return _original_get_context(self, context)


WebForm.has_web_form_permission = _patched_has_web_form_permission
WebForm.get_context = _patched_get_context
