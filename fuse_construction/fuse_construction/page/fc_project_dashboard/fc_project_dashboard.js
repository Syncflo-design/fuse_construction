// Construction dashboard — one job on one screen.
//
// Layout after epcforge's project dashboard (MIT, Invento Software Limited); charts are
// Frappe's own (frappe.Chart), so nothing is fetched from a CDN. Every number comes from
// fuse_construction.dashboard, which reads the same engine as Project Shape.

frappe.pages['fc-project-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({ parent: wrapper, title: 'Construction Dashboard', single_column: true });
	wrapper.fcDashboard = new FCDashboard(page);
};

// Opened again from Project Shape or a project form with a project chosen: show that one.
frappe.pages['fc-project-dashboard'].on_page_show = function (wrapper) {
	var project = (frappe.route_options && frappe.route_options.project) || null;
	frappe.route_options = null;
	if (wrapper.fcDashboard && project) wrapper.fcDashboard.set_project(project);
};

function fcd_escape(value) {
	return frappe.utils.escape_html(value == null ? '' : String(value));
}

function fcd_money(value) {
	return fcd_escape(format_currency(flt(value)));
}

function fcd_ratio(value) {
	return value == null ? '—' : flt(value).toFixed(2);
}

function FCDashboard(page) {
	var self = this;
	this.page = page;
	this.$body = $('<div class="fcd"></div>').appendTo(page.body);
	this.project_field = page.add_field({
		label: 'Project',
		fieldtype: 'Link',
		options: 'Project',
		fieldname: 'project',
		get_query: function () { return { filters: { fc_boq: ['is', 'set'] } }; },
		change: function () {
			var value = self.project_field.get_value();
			if (value && value !== self.project) self.load(value);
		}
	});
	this.period_field = page.add_field({
		label: 'Curve',
		fieldtype: 'Select',
		options: ['Weekly', 'Monthly'],
		default: 'Weekly',
		fieldname: 'periodicity',
		change: function () { if (self.project) self.load(self.project); }
	});
	page.add_inner_button('Refresh', function () { if (self.project) self.load(self.project); });
	page.add_inner_button('Project Shape', function () {
		frappe.set_route('query-report', 'FC Project Shape', self.project ? { project: self.project } : {});
	});

	var start = (frappe.route_options && frappe.route_options.project) || null;
	frappe.route_options = null;
	if (start) {
		this.set_project(start);
	} else {
		frappe.xcall('fuse_construction.dashboard.projects').then(function (rows) {
			if (rows.length) self.set_project(rows[0].project);
			else self.$body.html('<div class="text-muted" style="padding:40px;text-align:center">No awarded jobs yet. Award a BOQ to see it here.</div>');
		});
	}
}

FCDashboard.prototype.set_project = function (project) {
	this.project_field.set_value(project);
	this.load(project);
};

FCDashboard.prototype.load = function (project) {
	var self = this;
	this.project = project;
	this.$body.html('<div class="text-muted" style="padding:40px;text-align:center">Loading…</div>');
	frappe.xcall('fuse_construction.dashboard.get_data', {
		project: project,
		periodicity: this.period_field.get_value() || 'Weekly'
	}).then(function (data) { self.render(data); });
};

function fcd_card(label, value, tone) {
	var colour = { green: 'var(--green-600)', red: 'var(--red-600)', amber: 'var(--orange-600)', blue: 'var(--blue-600)' }[tone] || 'var(--text-color)';
	return '<div class="fcd-card"><div class="fcd-label">' + fcd_escape(label) + '</div>' +
		'<div class="fcd-value" style="color:' + colour + '">' + value + '</div></div>';
}

function fcd_bar(percent) {
	var p = Math.max(0, Math.min(100, flt(percent)));
	return '<div class="fcd-bar"><span style="width:' + p + '%"></span></div>';
}

FCDashboard.prototype.render = function (data) {
	if (!data.awarded) {
		this.$body.html('<div class="text-muted" style="padding:40px;text-align:center">This project has no awarded BOQ.</div>');
		return;
	}
	var t = data.total;
	var tone = { Green: 'green', Amber: 'amber', Red: 'red' }[t.health];
	var html = [];

	html.push('<div class="fcd-head"><h3>' + fcd_escape(data.title) + '</h3><div class="text-muted">' +
		fcd_escape([data.project_key, data.contract_model, data.customer].filter(Boolean).join(' · ')) +
		' · <a href="/app/fc-boq/' + encodeURIComponent(data.boq) + '">' + fcd_escape(data.boq) + '</a></div></div>');

	html.push('<div class="fcd-grid">',
		fcd_card('Contract value', fcd_money(t.contract_value), 'blue'),
		fcd_card('Budget at completion', fcd_money(t.budget)),
		fcd_card('Committed + actual', fcd_money(t.committed + t.actual), t.committed + t.actual > t.budget ? 'red' : 'green'),
		fcd_card('% complete', flt(t.percent_complete).toFixed(1) + '%'),
		fcd_card('Earned value', fcd_money(t.earned_value), t.cost_variance >= 0 ? 'green' : 'red'),
		fcd_card('CPI · SPI', fcd_ratio(t.cpi) + ' · ' + fcd_ratio(t.spi), tone),
		fcd_card('Forecast at completion', fcd_money(t.forecast), t.forecast > t.budget ? 'red' : 'green'),
		fcd_card('Health', fcd_escape(t.health) + ' · ' + fcd_escape(t.schedule_status), tone),
	'</div>');

	html.push('<div class="fcd-panel"><h4>Project shape</h4><div data-curve="1"></div></div>');

	html.push('<div class="fcd-panel"><h4>By section</h4><table class="table table-sm fcd-table"><thead><tr>' +
		'<th>Section</th><th class="text-right">Budget</th><th class="text-right">Committed</th><th class="text-right">Actual</th>' +
		'<th style="width:140px">% complete</th><th class="text-right">EV</th><th class="text-right">CPI</th><th class="text-right">Forecast</th></tr></thead><tbody>' +
		data.sections.map(function (s) {
			return '<tr><td>' + fcd_escape(s.boq_group) + '</td><td class="text-right">' + fcd_money(s.budget) + '</td>' +
				'<td class="text-right">' + fcd_money(s.committed) + '</td><td class="text-right">' + fcd_money(s.actual) + '</td>' +
				'<td>' + fcd_bar(s.percent_complete) + '<small>' + flt(s.percent_complete).toFixed(0) + '%</small></td>' +
				'<td class="text-right">' + fcd_money(s.earned_value) + '</td>' +
				'<td class="text-right"' + (s.cpi != null && s.cpi < 0.9 ? ' style="color:var(--red-600)"' : '') + '>' + fcd_ratio(s.cpi) + '</td>' +
				'<td class="text-right">' + fcd_money(s.forecast) + '</td></tr>';
		}).join('') + '</tbody></table></div>');

	html.push('<div class="fcd-two">');
	html.push('<div class="fcd-panel"><h4>Cost by type</h4><div data-types="1"></div></div>');
	html.push('<div class="fcd-panel"><h4>Phase progress</h4>' + data.phases.map(function (p) {
		return '<div class="fcd-phase"><div>' + fcd_escape(p.phase) + ' <small class="text-muted">' + fcd_money(p.amount) + '</small></div>' +
			fcd_bar(p.percent) + '<small>' + flt(p.percent).toFixed(0) + '%</small></div>';
	}).join('') + '</div>');
	html.push('</div>');

	html.push('<div class="fcd-two">');
	html.push('<div class="fcd-panel"><h4>Subcontracts</h4>' + (data.subcontracts.length ? '<table class="table table-sm fcd-table"><thead><tr>' +
		'<th>Subcontract</th><th class="text-right">Value</th><th style="width:120px">Certified</th><th class="text-right">Retention held</th></tr></thead><tbody>' +
		data.subcontracts.map(function (s) {
			return '<tr><td><a href="/app/fc-subcontract/' + encodeURIComponent(s.name) + '">' + fcd_escape(s.title) + '</a><br><small class="text-muted">' +
				fcd_escape(s.supplier_name) + ' · ' + fcd_escape(s.status) + '</small></td><td class="text-right">' + fcd_money(s.subcontract_value) + '</td>' +
				'<td>' + fcd_bar(s.percent_certified) + '<small>' + flt(s.percent_certified).toFixed(0) + '%</small></td>' +
				'<td class="text-right">' + fcd_money(s.retention_outstanding) + '</td></tr>';
		}).join('') + '</tbody></table>' : '<div class="text-muted">No subcontracts yet.</div>') + '</div>');

	if (data.client) {
		var c = data.client;
		html.push('<div class="fcd-panel"><h4>Client</h4>' +
			'<div class="fcd-kv"><span>Valued to date</span><b>' + fcd_money(c.valued_to_date) + '</b></div>' +
			'<div class="fcd-kv"><span>Of contract</span><b>' + (c.contract_value ? (c.valued_to_date / c.contract_value * 100).toFixed(1) : '0') + '%</b></div>' +
			'<div class="fcd-kv"><span>Retention held by client</span><b>' + fcd_money(c.retention_held) + '</b></div>' +
			'<div class="fcd-kv"><span>Advance not yet recovered</span><b>' + fcd_money(c.advance_outstanding) + '</b></div>' +
			(c.next_milestone ? '<div class="fcd-kv"><span>Next milestone</span><b>' + fcd_escape(c.next_milestone.milestone) + ' · ' +
				fcd_money(c.next_milestone.amount) + '</b></div>' : '') +
			(c.overdue_milestones.length ? '<div class="fcd-kv" style="color:var(--red-600)"><span>Overdue milestones</span><b>' +
				fcd_escape(c.overdue_milestones.join(', ')) + '</b></div>' : '') +
			'</div>');
	}
	html.push('</div>');

	if (data.procurement.length) {
		html.push('<div class="fcd-panel"><h4>Procurement coverage</h4><table class="table table-sm fcd-table"><thead><tr>' +
			'<th>Material</th><th class="text-right">BOQ qty</th><th>Requested</th><th>Ordered</th><th>Received</th></tr></thead><tbody>' +
			data.procurement.map(function (p) {
				return '<tr><td>' + fcd_escape(p.description) + '<br><small class="text-muted">' + fcd_escape(p.item_code) + ' · ' + fcd_escape(p.section) + '</small></td>' +
					'<td class="text-right">' + flt(p.qty) + ' ' + fcd_escape(p.uom || '') + '</td>' +
					['requested', 'ordered', 'received'].map(function (k) {
						return '<td>' + fcd_bar(p[k]) + '<small>' + flt(p[k]).toFixed(0) + '%</small></td>';
					}).join('') + '</tr>';
			}).join('') + '</tbody></table></div>');
	}

	this.$body.html(this.styles() + html.join('\n'));

	if (data.curve && data.curve.labels && data.curve.labels.length) {
		new frappe.Chart(this.$body.find('[data-curve]').get(0), {
			data: { labels: data.curve.labels, datasets: data.curve.datasets },
			type: 'line',
			height: 280,
			colors: ['#94A3B8', '#007E45', '#B91C1C', '#D97706'],
			lineOptions: { hideDots: 1, regionFill: 0 },
			axisOptions: { xIsSeries: 1 }
		});
	} else {
		this.$body.find('[data-curve]').html('<div class="text-muted">Nothing to draw yet — the job has not started.</div>');
	}

	if (data.cost_by_type.length) {
		new frappe.Chart(this.$body.find('[data-types]').get(0), {
			data: {
				labels: data.cost_by_type.map(function (r) { return r.type; }),
				datasets: [
					{ name: 'Budget', values: data.cost_by_type.map(function (r) { return r.budget; }) },
					{ name: 'Actual', values: data.cost_by_type.map(function (r) { return r.actual; }) }
				]
			},
			type: 'bar',
			height: 240,
			colors: ['#94A3B8', '#007E45']
		});
	}
};

FCDashboard.prototype.styles = function () {
	return [
		'<style>',
		'.fcd { padding: 8px 0 32px; }',
		'.fcd-head h3 { margin: 0; }',
		'.fcd-head { margin-bottom: 16px; }',
		'.fcd-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }',
		'@media (max-width: 900px) { .fcd-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }',
		'.fcd-card, .fcd-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px; }',
		'.fcd-panel { margin-bottom: 16px; overflow-x: auto; }',
		'.fcd-panel h4 { margin: 0 0 10px; font-size: 15px; }',
		'.fcd-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .03em; }',
		'.fcd-value { font-size: 20px; font-weight: 700; margin-top: 4px; }',
		'.fcd-two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }',
		'@media (max-width: 900px) { .fcd-two { grid-template-columns: 1fr; } }',
		'.fcd-bar { height: 8px; border-radius: 4px; background: var(--gray-200, #E2E8F0); overflow: hidden; }',
		'.fcd-bar span { display: block; height: 100%; background: var(--green-600, #007E45); }',
		'.fcd-phase { margin-bottom: 10px; }',
		'.fcd-kv { display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--border-color); }',
		'.fcd-table td, .fcd-table th { vertical-align: middle; }',
		'</style>'
	].join('\n');
};
