app_name = "expertedge"
app_title = "Expertedge"
app_publisher = "ashar"
app_description = "expertedge customizations"
app_email = "azr.shamz@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

app_include_css = "/assets/expertedge/css/expertedge.css"

fixtures = [
	{
		"dt": "EE Lead Source",
		"filters": [["source_name", "in", ["Instagram", "Facebook", "LinkedIn", "Referral", "Website", "Contact Form"]]],
	},
	{
		"dt": "EE Document Type",
		"filters": [["document_type", "in", ["Resume / CV", "Degree Certificate", "Transcript"]]],
	},
	{
		"dt": "Role",
		"filters": [["name", "in", ["EE Telecaller", "EE Academic Counsellor", "EE Finance", "EE Manager"]]],
	},
	{
		"dt": "Email Template",
		"filters": [["name", "like", "EE -%"]],
	},
	{
		"dt": "Web Form",
		"filters": [["name", "=", "program-enquiry"]],
	},
	{
		"dt": "Custom HTML Block",
		"filters": [["name", "like", "EE -%"]],
	},
	{
		"dt": "Custom DocPerm",
		"filters": [["role", "in", ["EE Telecaller", "EE Academic Counsellor", "EE Finance", "EE Manager"]]],
	},
]

# Cloudflare R2 file storage
doc_events = {
	"File": {
		"after_insert": "expertedge.r2_storage.file_upload_to_r2",
		"on_trash": "expertedge.r2_storage.delete_from_r2",
	},
}

# Scheduled Tasks
scheduler_events = {
	"cron": {
		"*/15 * * * *": [
			"expertedge.tasks.sync_google_sheet_leads",
		],
	},
	"hourly": [
		"expertedge.tasks.check_first_contact_sla",
		"expertedge.tasks.check_doc_sla",
		"expertedge.tasks.check_payment_sla",
		"expertedge.tasks.check_nomod_payments",
	],
}
