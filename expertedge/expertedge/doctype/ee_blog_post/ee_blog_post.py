import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr
import re


class EEBlogPost(Document):
	def before_save(self):
		if not self.slug and self.title:
			self.slug = self._generate_slug(self.title)

	def _generate_slug(self, title):
		slug = cstr(title).lower().strip()
		slug = re.sub(r"[^\w\s-]", "", slug)
		slug = re.sub(r"[\s_]+", "-", slug)
		slug = re.sub(r"-+", "-", slug).strip("-")
		# Ensure unique
		base = slug
		counter = 1
		while frappe.db.exists("EE Blog Post", {"slug": slug, "name": ["!=", self.name or ""]}):
			slug = f"{base}-{counter}"
			counter += 1
		return slug
