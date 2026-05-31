from frappe import _


def get_data():
	return {
		"fieldname": "lead",
		"transactions": [
			{
				"label": _("Counselling"),
				"items": ["EE Counselling Session"],
			},
			{
				"label": _("Conversion"),
				"items": ["EE Student"],
			},
		],
	}
