frappe.ui.form.on("EE Batch", {
	refresh(frm) {
		if (frm.is_new()) return;

		// Capture venue location button
		frm.add_custom_button(__("Capture Venue Location"), function () {
			if (!navigator.geolocation) {
				frappe.msgprint(__("Your browser does not support geolocation."));
				return;
			}

			frappe.show_alert({ message: __("Getting GPS location..."), indicator: "blue" });

			navigator.geolocation.getCurrentPosition(
				function (pos) {
					frm.set_value("location_lat", pos.coords.latitude);
					frm.set_value("location_lng", pos.coords.longitude);
					frm.dirty();
					frappe.show_alert({
						message: __("Location captured: {0}, {1} (accuracy: {2}m)", [
							pos.coords.latitude.toFixed(6),
							pos.coords.longitude.toFixed(6),
							Math.round(pos.coords.accuracy),
						]),
						indicator: "green",
					});
					_show_map(frm);
				},
				function (err) {
					var msg = "Could not get location.";
					if (err.code === 1) msg = "Location access denied. Enable GPS in browser settings.";
					if (err.code === 2) msg = "Location unavailable.";
					if (err.code === 3) msg = "Location request timed out.";
					frappe.msgprint(__(msg));
				},
				{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
			);
		}, __("Attendance"));

		// Set location manually via Google Maps link
		frm.add_custom_button(__("Set Location from Coordinates"), function () {
			var d = new frappe.ui.Dialog({
				title: __("Set Venue Coordinates"),
				fields: [
					{
						fieldname: "coords",
						fieldtype: "Data",
						label: "Coordinates",
						description: "Paste lat,lng (e.g. 25.276987,55.296249) or a Google Maps URL",
						reqd: 1,
					},
				],
				primary_action_label: __("Set"),
				primary_action: function (values) {
					var input = values.coords.trim();
					var lat, lng;

					// Try Google Maps URL patterns
					var gm = input.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
					if (gm) {
						lat = parseFloat(gm[1]);
						lng = parseFloat(gm[2]);
					} else {
						// Try "lat, lng" format
						var parts = input.split(",").map(function (s) { return parseFloat(s.trim()); });
						if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
							lat = parts[0];
							lng = parts[1];
						}
					}

					if (lat && lng && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
						frm.set_value("location_lat", lat);
						frm.set_value("location_lng", lng);
						frm.dirty();
						d.hide();
						frappe.show_alert({ message: __("Location set: {0}, {1}", [lat.toFixed(6), lng.toFixed(6)]), indicator: "green" });
						_show_map(frm);
					} else {
						frappe.msgprint(__("Could not parse coordinates. Use format: 25.276987,55.296249"));
					}
				},
			});
			d.show();
		}, __("Attendance"));

		// Show map if location exists
		if (frm.doc.location_lat && frm.doc.location_lng) {
			_show_map(frm);
		}
	},
});

function _show_map(frm) {
	if (!frm.doc.location_lat || !frm.doc.location_lng) return;

	var lat = frm.doc.location_lat;
	var lng = frm.doc.location_lng;
	var range = frm.doc.acceptable_range || 200;

	var html = '<div style="margin-top:8px;">'
		+ '<a href="https://www.google.com/maps?q=' + lat + ',' + lng + '" target="_blank" '
		+ 'style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;background:#f0f4f8;border:1px solid #d5dae1;border-radius:8px;text-decoration:none;color:#333;font-size:13px;">'
		+ '📍 <span>' + lat.toFixed(6) + ', ' + lng.toFixed(6) + '</span>'
		+ '<span style="color:#888;font-size:11px;">(' + range + 'm geofence)</span>'
		+ '<span style="color:#1a73e8;font-size:12px;">Open in Maps ↗</span>'
		+ '</a></div>';

	// Use the section below the geofence fields
	if (frm.fields_dict.acceptable_range) {
		$(frm.fields_dict.acceptable_range.wrapper).find(".ee-map-link").remove();
		$(frm.fields_dict.acceptable_range.wrapper).append('<div class="ee-map-link">' + html + '</div>');
	}
}
