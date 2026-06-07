frappe.pages["lead-analysis"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Lead Analysis",
		single_column: true,
	});

	page.main.html(frappe.render_template("lead_analysis"));

	var state = {
		from_date: frappe.datetime.month_start(),
		to_date: frappe.datetime.get_today(),
		selected_date: null,
		selected_source: null,
		selected_lead: null,
		selected_status: null,
		all_leads: [],
	};

	// Date filters
	var from_ctrl = frappe.ui.form.make_control({
		df: { fieldname: "from_date", fieldtype: "Date", label: "From Date", default: state.from_date, reqd: 1 },
		parent: page.main.find("#from-date-filter"),
		render_input: true,
	});
	from_ctrl.set_value(state.from_date);

	var to_ctrl = frappe.ui.form.make_control({
		df: { fieldname: "to_date", fieldtype: "Date", label: "To Date", default: state.to_date, reqd: 1 },
		parent: page.main.find("#to-date-filter"),
		render_input: true,
	});
	to_ctrl.set_value(state.to_date);

	var status_ctrl = frappe.ui.form.make_control({
		df: {
			fieldname: "status",
			fieldtype: "Select",
			label: "Status",
			options: "\nNew\nContacted\nBrochure Sent\nDocs Requested\nDocs Received\nDocs Verified\nCounselling Scheduled\nCounselling Done\nConfirmed\nConverted\nLost",
		},
		parent: page.main.find("#status-filter"),
		render_input: true,
	});
	status_ctrl.$input.on("change", function () {
		state.selected_status = status_ctrl.get_value();
		render_all();
	});

	page.main.find("#btn-refresh").on("click", function () {
		state.from_date = from_ctrl.get_value();
		state.to_date = to_ctrl.get_value();
		state.selected_date = null;
		state.selected_source = null;
		state.selected_status = status_ctrl.get_value();
		fetch_data();
	});

	page.main.find("#btn-clear").on("click", function () {
		state.selected_date = null;
		state.selected_source = null;
		render_all();
	});

	function fetch_data() {
		frappe.call({
			method: "expertedge.expertedge.page.lead_analysis.lead_analysis.get_lead_data",
			args: { from_date: state.from_date, to_date: state.to_date },
			freeze: true,
			callback: function (r) {
				state.all_leads = r.message || [];
				render_all();
			},
		});
	}

	function render_all() {
		render_date_slicer();
		render_source_slicer();
		render_leads_table();
		update_filter_tags();
	}

	function apply_status_filter(leads) {
		if (state.selected_status) {
			return leads.filter((l) => l.status === state.selected_status);
		}
		return leads;
	}

	function get_filtered_leads() {
		var leads = apply_status_filter(state.all_leads);
		if (state.selected_date) {
			leads = leads.filter((l) => l.lead_date === state.selected_date);
		}
		if (state.selected_source) {
			leads = leads.filter((l) => l.lead_source === state.selected_source);
		}
		return leads;
	}

	function get_date_filtered_leads() {
		var leads = apply_status_filter(state.all_leads);
		if (state.selected_date) {
			leads = leads.filter((l) => l.lead_date === state.selected_date);
		}
		return leads;
	}

	function get_source_filtered_leads() {
		var leads = apply_status_filter(state.all_leads);
		if (state.selected_source) {
			leads = leads.filter((l) => l.lead_source === state.selected_source);
		}
		return leads;
	}

	function render_date_slicer() {
		var leads = get_source_filtered_leads();
		var date_map = {};
		leads.forEach(function (l) {
			date_map[l.lead_date] = (date_map[l.lead_date] || 0) + 1;
		});

		var dates = Object.keys(date_map).sort();
		var total = dates.reduce((s, d) => s + date_map[d], 0);

		var rows = dates
			.map(function (d) {
				var cls = state.selected_date === d ? "selected" : "";
				return `<tr class="${cls}" data-date="${d}">
				<td>${frappe.datetime.str_to_user(d)}</td>
				<td style="text-align:right">${date_map[d]}</td>
			</tr>`;
			})
			.join("");

		var html = `<div class="slicer-card">
			<table>
				<thead><tr><th>Date</th><th style="text-align:right">Leads (${total})</th></tr></thead>
				<tbody>${rows || '<tr><td colspan="2" class="text-muted text-center">No data</td></tr>'}</tbody>
			</table>
		</div>`;

		var $el = page.main.find("#date-slicer").html(html);
		$el.find("tr[data-date]").on("click", function () {
			var d = $(this).data("date");
			state.selected_date = state.selected_date === d ? null : d;
			render_all();
		});
	}

	function render_source_slicer() {
		var leads = get_date_filtered_leads();
		var source_map = {};
		leads.forEach(function (l) {
			var src = l.lead_source || "Unknown";
			source_map[src] = (source_map[src] || 0) + 1;
		});

		var sources = Object.keys(source_map).sort();
		var total = sources.reduce((s, k) => s + source_map[k], 0);

		var rows = sources
			.map(function (src) {
				var cls = state.selected_source === src ? "selected" : "";
				return `<tr class="${cls}" data-source="${frappe.utils.escape_html(src)}">
				<td>${frappe.utils.escape_html(src)}</td>
				<td style="text-align:right">${source_map[src]}</td>
			</tr>`;
			})
			.join("");

		var html = `<div class="slicer-card">
			<table>
				<thead><tr><th>Source</th><th style="text-align:right">Leads (${total})</th></tr></thead>
				<tbody>${rows || '<tr><td colspan="2" class="text-muted text-center">No data</td></tr>'}</tbody>
			</table>
		</div>`;

		var $el = page.main.find("#source-slicer").html(html);
		$el.find("tr[data-source]").on("click", function () {
			var src = $(this).data("source");
			state.selected_source = state.selected_source === src ? null : src;
			render_all();
		});
	}

	function render_leads_table() {
		var leads = get_filtered_leads();

		var rows = leads
			.map(function (l) {
				var status_color = get_status_color(l.status);
				var cls = state.selected_lead === l.name ? "selected" : "";
				return `<tr class="${cls}" data-lead="${l.name}">
				<td>${frappe.utils.escape_html(l.lead_name)}</td>
				<td>${frappe.datetime.str_to_user(l.lead_date)}</td>
				<td>${frappe.utils.escape_html(l.lead_source || "")}</td>
				<td><span class="indicator-pill ${status_color}">${frappe.utils.escape_html(l.status || "")}</span></td>
				<td>${frappe.utils.escape_html(l.handled_by_name || "")}</td>
				<td>${frappe.utils.escape_html(l.latest_notes || "")}</td>
			</tr>`;
			})
			.join("");

		var html = `<div class="leads-card">
			<table>
				<thead><tr>
					<th>Lead Name</th>
					<th>Date</th>
					<th>Source</th>
					<th>Status</th>
					<th>Handled By</th>
					<th>Latest Notes</th>
				</tr></thead>
				<tbody>${rows || '<tr><td colspan="6" class="text-muted text-center">No leads found</td></tr>'}</tbody>
			</table>
			<div style="padding:8px 12px;font-size:12px;color:var(--text-muted);">${leads.length} leads</div>
		</div>`;

		var $el = page.main.find("#leads-table").html(html);
		$el.find("tr[data-lead]").on("click", function () {
			var lead_name = $(this).data("lead");
			if (state.selected_lead === lead_name) {
				state.selected_lead = null;
				page.main.find("#lead-detail").hide();
				$el.find("tr.selected").removeClass("selected");
			} else {
				state.selected_lead = lead_name;
				$el.find("tr.selected").removeClass("selected");
				$(this).addClass("selected");
				fetch_lead_detail(lead_name);
			}
		});
	}

	function fetch_lead_detail(lead_name) {
		frappe.call({
			method: "expertedge.expertedge.page.lead_analysis.lead_analysis.get_lead_detail",
			args: { lead_name: lead_name },
			callback: function (r) {
				if (r.message) {
					render_lead_detail(r.message);
				}
			},
		});
	}

	function render_lead_detail(d) {
		var status_color = get_status_color(d.status);

		var detail_rows = [
			["Status", `<span class="indicator-pill ${status_color}">${frappe.utils.escape_html(d.status || "")}</span>`],
			["Email", d.email || ""],
			["Mobile", d.mobile_no || ""],
			["Source", d.lead_source || ""],
			["Handled By", d.handled_by || ""],
			["Counsellor", d.counsellor || ""],
			["Program", d.program || ""],
			["Batch", d.preferred_batch || ""],
			["Nationality", d.nationality || ""],
			["Priority", d.priority || ""],
			["Received", d.lead_received_on ? frappe.datetime.str_to_user(d.lead_received_on) : ""],
			["1st Contact", d.first_contacted_on ? frappe.datetime.str_to_user(d.first_contacted_on) : ""],
			["Next Action", d.next_action || ""],
			["Remarks", d.remarks || ""],
		].filter(function (r) { return r[1]; })
		 .map(function (r) {
			return `<div class="detail-row">
				<div class="label">${r[0]}</div>
				<div class="value">${r[1]}</div>
			</div>`;
		}).join("");

		var call_entries = (d.call_logs || []).map(function (c) {
			var dt = c.call_on ? frappe.datetime.str_to_user(c.call_on) : "";
			var result_color = c.call_result === "Connected" || c.call_result === "Interested" ? "green" : "orange";
			return `<div class="call-entry">
				<div class="call-meta">
					${dt} &middot; ${frappe.utils.escape_html(c.caller || "")} &middot;
					${frappe.utils.escape_html(c.direction || "")} &middot;
					<span class="indicator-pill ${result_color} sm">${frappe.utils.escape_html(c.call_result || "")}</span>
					${c.duration_min ? " &middot; " + c.duration_min + " min" : ""}
				</div>
				${c.summary ? '<div class="call-notes">' + frappe.utils.escape_html(c.summary) + '</div>' : ''}
				${c.next_call_on ? '<div class="call-meta" style="margin-top:2px;">Next: ' + frappe.datetime.str_to_user(c.next_call_on) + '</div>' : ''}
			</div>`;
		}).join("");

		var html = `<div class="detail-card">
			<div class="detail-header">
				<h6>${frappe.utils.escape_html(d.lead_name)}</h6>
				<a href="/app/ee-lead/${d.name}" class="btn btn-xs btn-default">Open</a>
			</div>
			<div class="detail-body">
				${detail_rows}
			</div>
			${d.call_logs && d.call_logs.length ? '<div class="call-log-section"><h6>Call Log (' + d.call_logs.length + ')</h6>' + call_entries + '</div>' : ''}
		</div>`;

		page.main.find("#lead-detail").html(html).show();
	}

	function update_filter_tags() {
		var tags = [];
		if (state.selected_date) {
			tags.push(`<span class="filter-tag">Date: ${frappe.datetime.str_to_user(state.selected_date)}</span>`);
		}
		if (state.selected_source) {
			tags.push(`<span class="filter-tag">Source: ${state.selected_source}</span>`);
		}
		var $filters = page.main.find("#active-filters");
		var $clear = page.main.find("#btn-clear");
		if (tags.length) {
			$filters.show().find("#filter-tags").html(tags.join(""));
			$clear.show();
		} else {
			$filters.hide();
			$clear.hide();
		}
	}

	function get_status_color(status) {
		var map = {
			New: "blue",
			Contacted: "orange",
			"Brochure Sent": "orange",
			"Docs Requested": "yellow",
			"Docs Received": "yellow",
			"Docs Verified": "purple",
			"Counselling Scheduled": "purple",
			"Counselling Done": "purple",
			Confirmed: "green",
			Converted: "green",
			Lost: "red",
		};
		return map[status] || "grey";
	}

	// Initial load
	fetch_data();
};
