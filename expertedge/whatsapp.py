import frappe
import requests
from frappe import _


def send_lead_alert(lead_doc):
	"""Send WhatsApp alert for new lead. Called from EE Lead.after_insert."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")

	if not settings.enable_whatsapp_alerts:
		return

	if not settings.whatsapp_recipients:
		return

	api_key = settings.get_password("whatsapp_api_key")
	if not api_key:
		frappe.log_error("WhatsApp alert skipped: no API key configured", "WhatsApp Alert")
		return

	template_id = settings.whatsapp_template_id or "supportmessage_002"

	message_text = "New Lead: {name}, {phone}, {program}, {source}".format(
		name=lead_doc.lead_name or "Unknown",
		phone=lead_doc.mobile_no or "N/A",
		program=lead_doc.program or "N/A",
		source=lead_doc.lead_source or "N/A",
	)

	for row in settings.whatsapp_recipients:
		phone = (row.phone or "").strip().replace("+", "").replace(" ", "")
		if not phone:
			continue
		try:
			_send_zoko_template(api_key, phone, template_id, [message_text])
		except Exception:
			frappe.log_error(
				f"WhatsApp alert failed for {phone}",
				"WhatsApp Alert",
			)


def send_test_alert(recipient_phone):
	"""Send a test WhatsApp message. Called from Settings UI."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")
	api_key = settings.get_password("whatsapp_api_key")

	if not api_key:
		frappe.throw(_("Zoko API Key not configured in ExpertEdge Settings"))

	template_id = settings.whatsapp_template_id or "supportmessage_002"
	phone = (recipient_phone or "").strip().replace("+", "").replace(" ", "")

	if not phone:
		frappe.throw(_("No phone number provided"))

	_send_zoko_template(api_key, phone, template_id, ["Test alert from ExpertEdge. Setup working!"])


def _send_zoko_template(api_key, recipient, template_id, template_args):
	"""Send a WhatsApp template message via Zoko API."""
	payload = {
		"channel": "whatsapp",
		"recipient": recipient,
		"type": "template",
		"templateId": template_id,
		"templateArgs": template_args,
	}

	resp = requests.post(
		"https://chat.zoko.io/v2/message",
		json=payload,
		headers={
			"apikey": api_key,
			"Content-Type": "application/json",
			"Accept": "application/json",
		},
		timeout=10,
	)

	if resp.status_code not in (200, 201, 202):
		frappe.log_error(
			f"Zoko API error {resp.status_code}: {resp.text}",
			"WhatsApp Alert",
		)
		frappe.throw(_("Zoko API error: {0}").format(resp.text))

	return resp.json()


@frappe.whitelist()
def test_whatsapp_alert():
	"""Whitelisted method for test button in Settings."""
	settings = frappe.get_cached_doc("ExpertEdge Settings")

	if not settings.whatsapp_recipients:
		frappe.throw(_("Add at least one recipient in the WhatsApp Recipients table"))

	first_phone = settings.whatsapp_recipients[0].phone
	send_test_alert(first_phone)
	frappe.msgprint(_("Test message sent to {0}").format(first_phone), indicator="green")
