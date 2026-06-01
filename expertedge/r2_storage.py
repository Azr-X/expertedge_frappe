"""Monkey-patch frappe_s3_attachment to support Cloudflare R2 (custom endpoint_url).

Loaded at app startup via hooks.py boot_session.
Survives updates to the frappe_s3_attachment app.
"""
import frappe


def patch_s3_for_r2():
	"""Patch S3Operations.__init__ to inject endpoint_url from site_config."""
	try:
		from frappe_s3_attachment.controller import S3Operations
	except ImportError:
		return

	_original_init = S3Operations.__init__

	def _patched_init(self):
		_original_init(self)
		endpoint_url = frappe.local.conf.get("s3_endpoint_url")
		if endpoint_url and hasattr(self, "S3_CLIENT"):
			import boto3
			from botocore.client import Config
			kwargs = {
				"region_name": self.s3_settings_doc.region_name,
				"endpoint_url": endpoint_url,
				"config": Config(signature_version="s3v4"),
			}
			if self.s3_settings_doc.aws_key and self.s3_settings_doc.aws_secret:
				kwargs["aws_access_key_id"] = self.s3_settings_doc.aws_key
				kwargs["aws_secret_access_key"] = self.s3_settings_doc.aws_secret
			self.S3_CLIENT = boto3.client("s3", **kwargs)

	S3Operations.__init__ = _patched_init


# Apply patch on import
patch_s3_for_r2()
