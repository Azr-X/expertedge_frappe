from frappe import _


def get_data():
	return {
		"fieldname": "student",
		"transactions": [
			{
				"label": _("Payments"),
				"items": ["EE Nomod Payment Link"],
			},
		],
	}
