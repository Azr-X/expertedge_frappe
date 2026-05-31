import frappe
from frappe.model.document import Document


class NomodSettings(Document):
	def get_api_key(self):
		"""Return the active API key based on test_mode setting."""
		if self.test_mode:
			return self.get_password("test_api_key")
		return self.get_password("api_key")

	def get_base_url(self):
		return (self.api_base_url or "https://api.nomod.com/v1").rstrip("/")
