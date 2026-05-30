app_name = "expertedge"
app_title = "Expertedge"
app_publisher = "ashar"
app_description = "expertedge customizations"
app_email = "azr.shamz@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

fixtures = [
	{
		"dt": "EE Lead Source",
		"filters": [["source_name", "in", ["Instagram", "Facebook", "LinkedIn", "Referral", "Website"]]],
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
]

# Scheduled Tasks
scheduler_events = {
	"hourly": [
		"expertedge.tasks.check_first_contact_sla",
		"expertedge.tasks.check_doc_sla",
		"expertedge.tasks.check_payment_sla",
	],
}
