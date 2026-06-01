__version__ = "0.0.1"

# Patch frappe_s3_attachment for Cloudflare R2 support
try:
	from expertedge.r2_storage import patch_s3_for_r2  # noqa: F401
except Exception:
	pass
