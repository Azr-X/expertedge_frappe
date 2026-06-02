"""Cloudflare R2 / S3-compatible file storage for ExpertEdge.

Uploads file attachments to R2, serves private files via signed URLs.
Config lives in ExpertEdge Settings. No third-party app needed.
"""
import datetime
import mimetypes
import os
import random
import re
import string

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

import frappe


def _get_r2_settings():
	"""Read R2 config from ExpertEdge Settings."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	return {
		"endpoint_url": settings.get("r2_endpoint_url"),
		"bucket": settings.get("r2_bucket"),
		"access_key": settings.get("r2_access_key"),
		"secret_key": settings.get_password("r2_secret_key", raise_exception=False) or "",
		"folder": settings.get("r2_folder") or "",
		"signed_url_expiry": settings.get("r2_signed_url_expiry") or 3600,
	}


def _get_client(cfg):
	"""Create boto3 S3 client for R2."""
	return boto3.client(
		"s3",
		endpoint_url=cfg["endpoint_url"],
		aws_access_key_id=cfg["access_key"],
		aws_secret_access_key=cfg["secret_key"],
		region_name="auto",
		config=BotoConfig(signature_version="s3v4"),
	)


def _strip_special_chars(name):
	return re.sub(r"[^0-9a-zA-Z._-]", "", name)


def _generate_key(file_name, parent_doctype, folder):
	"""Generate S3 key: folder/YYYY/MM/DD/DocType/RAND_filename"""
	file_name = _strip_special_chars(file_name.replace(" ", "_"))
	rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
	now = datetime.datetime.now()
	parts = [now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"), parent_doctype, f"{rand}_{file_name}"]
	if folder:
		parts.insert(0, folder)
	return "/".join(parts)


def _detect_mime(file_path, file_name):
	"""Detect MIME type — try python-magic, fallback to mimetypes."""
	try:
		import magic
		return magic.from_file(file_path, mime=True)
	except (ImportError, Exception):
		guessed, _ = mimetypes.guess_type(file_name)
		return guessed or "application/octet-stream"


# --- Hooks ---

def file_upload_to_r2(doc, method=None):
	"""Hook: File.after_insert — upload to R2, update URL, delete local."""
	cfg = _get_r2_settings()
	if not cfg["endpoint_url"] or not cfg["bucket"]:
		return

	# Skip doctypes that shouldn't go to R2
	ignore_list = frappe.local.conf.get("ignore_s3_upload_for_doctype") or ["Data Import"]
	parent_doctype = doc.attached_to_doctype or "File"
	if parent_doctype in ignore_list:
		return

	path = doc.file_url
	if not path or path.startswith("http") or path.startswith("/api/method/"):
		return

	site_path = frappe.utils.get_site_path()
	if doc.is_private:
		file_path = site_path + path
	else:
		file_path = site_path + "/public" + path

	if not os.path.exists(file_path):
		return

	try:
		client = _get_client(cfg)
		key = _generate_key(doc.file_name, parent_doctype, cfg["folder"])
		content_type = _detect_mime(file_path, doc.file_name)

		extra_args = {
			"ContentType": content_type,
			"Metadata": {"ContentType": content_type, "file_name": doc.file_name},
		}
		if not doc.is_private:
			extra_args["ACL"] = "public-read"

		client.upload_file(file_path, cfg["bucket"], key, ExtraArgs=extra_args)

		# Build URL
		if doc.is_private:
			file_url = "/api/method/expertedge.r2_storage.generate_file?key={}&file_name={}".format(
				key, doc.file_name
			)
		else:
			file_url = "{}/{}/{}".format(cfg["endpoint_url"].rstrip("/"), cfg["bucket"], key)

		# Update DB and remove local
		os.remove(file_path)
		frappe.db.sql(
			"""UPDATE `tabFile` SET file_url=%s, folder=%s, old_parent=%s, content_hash=%s WHERE name=%s""",
			(file_url, "Home/Attachments", "Home/Attachments", key, doc.name),
		)
		doc.file_url = file_url

		if parent_doctype and frappe.get_meta(parent_doctype).get("image_field"):
			frappe.db.set_value(parent_doctype, doc.attached_to_name, frappe.get_meta(parent_doctype).get("image_field"), file_url)

		frappe.db.commit()

	except Exception:
		frappe.log_error(title=f"R2 upload failed: {doc.file_name}", message=frappe.get_traceback())


def delete_from_r2(doc, method=None):
	"""Hook: File.on_trash — delete from R2."""
	cfg = _get_r2_settings()
	if not cfg["endpoint_url"] or not cfg["bucket"]:
		return

	key = doc.content_hash
	if not key:
		return

	try:
		client = _get_client(cfg)
		client.delete_object(Bucket=cfg["bucket"], Key=key)
	except ClientError:
		frappe.log_error(title=f"R2 delete failed: {key}")
	except Exception:
		pass


@frappe.whitelist(allow_guest=True)
def generate_file(key=None, file_name=None):
	"""Serve private files via signed URL redirect."""
	if not key:
		frappe.local.response["body"] = "Key not found."
		return

	cfg = _get_r2_settings()
	client = _get_client(cfg)

	params = {"Bucket": cfg["bucket"], "Key": key}
	if file_name:
		params["ResponseContentDisposition"] = f"filename={file_name}"

	signed_url = client.generate_presigned_url(
		"get_object",
		Params=params,
		ExpiresIn=cfg["signed_url_expiry"],
	)

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = signed_url


@frappe.whitelist()
def migrate_existing_files():
	"""Migrate all local files to R2."""
	cfg = _get_r2_settings()
	if not cfg["endpoint_url"] or not cfg["bucket"]:
		frappe.throw("R2 not configured in ExpertEdge Settings")

	files = frappe.get_all("File", fields=["name", "file_url"])
	migrated = 0
	for f in files:
		if f.file_url and not f.file_url.startswith("http") and not f.file_url.startswith("/api/method/"):
			try:
				doc = frappe.get_doc("File", f.name)
				file_upload_to_r2(doc)
				migrated += 1
			except Exception:
				frappe.log_error(title=f"R2 migration failed: {f.name}")

	return migrated
