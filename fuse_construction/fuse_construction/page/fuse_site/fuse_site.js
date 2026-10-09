// Fuse Construction — the Site screen, for a phone.
//
// A second front door onto the same records the desk uses. Every action goes through
// fuse_construction/site.py, which saves an ordinary document — crew timesheet, task,
// daily report, material request, purchase receipt — so the phone and the desk share one
// path and one set of rules.
//
// Mounted inside page.body (a jQuery object in v16 — CoWork_Helper gotcha
// 2026-05-10-frappe-v16-page-api-drift). HTML is built as string arrays joined with "\n",
// and everything that came from the server goes through fs_escape.

frappe.pages['fuse-site'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({ parent: wrapper, title: 'Site', single_column: true });

	var BUILD_MARKER = 'v0.1.0-2026-10-08';
	console.log('Fuse Site loaded:', BUILD_MARKER);

	if (!document.getElementById('fuse-site-stylesheet')) {
		var link = document.createElement('link');
		link.id = 'fuse-site-stylesheet';
		link.rel = 'stylesheet';
		link.href = '/assets/fuse_construction/css/fuse_site.css?v=' + encodeURIComponent(BUILD_MARKER);
		document.head.appendChild(link);
	}

	wrapper.fuseSite = window.fuseSite = new FuseSite(page);
};

frappe.pages['fuse-site'].on_page_show = function (wrapper) {
	// Back on the screen from somewhere else. Refresh the counts on the home screen, but
	// never throw away a crew sheet or a report someone is half-way through.
	if (wrapper.fuseSite && wrapper.fuseSite.screen === 'home') wrapper.fuseSite.reload();
};

// ---------------------------------------------------------------------------

function fs_escape(value) {
	return frappe.utils.escape_html(value == null ? '' : String(value));
}

function fs_num(value) {
	var n = flt(value);
	return String(parseFloat(n.toFixed(2)));
}

function fs_recall(key) {
	try {
		return localStorage.getItem('fuse_site:' + key) || '';
	} catch (e) {
		return '';
	}
}

function fs_remember(key, value) {
	try {
		localStorage.setItem('fuse_site:' + key, value || '');
	} catch (e) {
		// Private browsing. Remembering is a convenience, not a requirement.
	}
}

// Lucide, one stroke weight. Never emoji: they cannot take a colour from the stylesheet and
// render differently on every phone. Every icon sits beside text, so all are aria-hidden.
var FS_ICONS = {
	back: 'M19 12H5M12 19l-7-7 7-7',
	crew: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
	approve: 'M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4 12 14.01l-3-3',
	progress: 'M22 12h-4l-3 9L9 3l-3 9H2',
	report: 'M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM8 12h8M8 16h5',
	request: 'M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0',
	receive: 'M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z',
	work: 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z',
	tick: 'M20 6 9 17l-5-5',
	camera: 'M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
	warn: 'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01'
};

function fs_icon(name) {
	return '<svg class="fs-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="' +
		FS_ICONS[name] + '"></path></svg>';
}

var FS_WEATHER = ['Clear', 'Partly Cloudy', 'Overcast', 'Rain', 'Heavy Rain', 'Wind', 'Storm', 'Extreme Heat'];

// ---------------------------------------------------------------------------

function FuseSite(page) {
	this.page = page;
	this.context = null;
	this.screen = 'home';
	this.project = fs_recall('project');
	this.$root = $('<div class="fs-root"></div>').appendTo(page.body);
	this.reload();
}

FuseSite.prototype.call = function (method, args) {
	return frappe.xcall('fuse_construction.site.' + method, args || {});
};

FuseSite.prototype.reload = function () {
	var self = this;
	this.call('context').then(function (context) {
		self.context = context;
		var known = (context.projects || []).some(function (p) { return p.name === self.project; });
		if (!known) self.project = '';
		if (self.screen === 'home') self.home();
	});
};

FuseSite.prototype.render = function (html, bar) {
	this.$root.html(html + (bar ? '<div class="fs-bar"><div class="fs-bar-inner">' + bar + '</div></div>' : ''));
	window.scrollTo(0, 0);
};

FuseSite.prototype.header = function (title, subtitle) {
	return [
		'<div class="fs-head">',
		'  <button class="fs-back" data-back="1" aria-label="Back">' + fs_icon('back') + '</button>',
		'  <div><div class="fs-title">' + fs_escape(title) + '</div>',
		'  <div class="fs-sub">' + fs_escape(subtitle || '') + '</div></div>',
		'</div>'
	].join('\n');
};

FuseSite.prototype.bind_back = function () {
	var self = this;
	this.$root.find('[data-back]').on('click', function () { self.home(); });
};

FuseSite.prototype.project_name = function () {
	var self = this;
	var match = (this.context && this.context.projects || []).filter(function (p) { return p.name === self.project; })[0];
	return match ? (match.project_name || match.name) : '';
};

FuseSite.prototype.done = function (title, lines, again) {
	var self = this;
	this.screen = 'done';
	this.render([
		'<div class="fs-done">',
		'  <div class="fs-tile-mark">' + fs_icon('tick') + '</div>',
		'  <h3>' + fs_escape(title) + '</h3>',
		(lines || []).map(function (line) { return '<div class="fs-sub">' + fs_escape(line) + '</div>'; }).join('\n'),
		'</div>'
	].join('\n'), [
		again ? '<button class="fs-btn" data-again="1">' + fs_escape(again.label) + '</button>' : '',
		'<button class="fs-btn fs-btn-go" data-home="1">Done</button>'
	].join(''));
	this.$root.find('[data-home]').on('click', function () { self.home(); self.reload(); });
	if (again) this.$root.find('[data-again]').on('click', function () { again.go.call(self); });
};

// ---------------------------------------------------------------------------
// Home
// ---------------------------------------------------------------------------

function fs_tile(go, icon, title, blurb, badge) {
	return [
		'<button class="fs-tile" data-go="' + go + '">',
		'  <span class="fs-tile-mark">' + fs_icon(icon) + '</span>',
		'  <span><span class="fs-tile-title">' + fs_escape(title) + '</span>',
		'  <span class="fs-tile-sub">' + fs_escape(blurb) + '</span></span>',
		badge ? '  <span class="fs-badge" aria-label="' + badge + ' waiting">' + badge + '</span>' : '',
		'</button>'
	].join('\n');
}

FuseSite.prototype.home = function () {
	var self = this;
	this.screen = 'home';
	var context = this.context || {};
	var options = ['<option value="">Choose the project…</option>'].concat((context.projects || []).map(function (p) {
		return '<option value="' + fs_escape(p.name) + '"' + (p.name === self.project ? ' selected' : '') + '>' +
			fs_escape(p.project_name || p.name) + '</option>';
	}));

	var tiles = [
		fs_tile('crew', 'crew', 'Crew time', 'Book today\'s crew against a section'),
		context.approver ? fs_tile('approve', 'approve', 'Approve time', 'Crew sheets waiting for you', context.pending) : '',
		fs_tile('progress', 'progress', 'Progress', 'Move a section\'s % complete'),
		fs_tile('report', 'report', 'Daily report', 'Weather, work done, photos, sign-off'),
		fs_tile('request', 'request', 'Material request', 'Ask the buyer for what site needs'),
		fs_tile('receive', 'receive', 'Receive delivery', 'Book a delivery in against an order'),
		context.site_work_page ? fs_tile('work', 'work', 'Site work', 'Tasks found on site, and your own time') : ''
	];

	this.render([
		'<div class="fs-project">',
		'  <label for="fs-project">Project</label>',
		'  <select id="fs-project" class="fs-select" data-project="1">' + options.join('') + '</select>',
		'</div>',
		'<div class="fs-menu">' + tiles.join('\n') + '</div>'
	].join('\n'));

	this.$root.find('[data-project]').on('change', function () {
		self.project = $(this).val();
		fs_remember('project', self.project);
	});

	this.$root.find('[data-go]').on('click', function () {
		var go = $(this).data('go');
		var needs_project = ['crew', 'progress', 'report', 'request', 'receive'].indexOf(go) !== -1;
		if (needs_project && !self.project) {
			frappe.show_alert({ message: 'Choose the project first.', indicator: 'orange' });
			self.$root.find('[data-project]').focus();
			return;
		}
		if (go === 'crew') self.crew();
		else if (go === 'approve') self.approvals();
		else if (go === 'progress') self.progress();
		else if (go === 'report') self.report();
		else if (go === 'request') self.request();
		else if (go === 'receive') self.receive();
		else if (go === 'work') frappe.set_route(context.site_work_page);
	});
};

// ---------------------------------------------------------------------------
// Crew time
// ---------------------------------------------------------------------------

FuseSite.prototype.crew = function () {
	var self = this;
	this.screen = 'crew';
	this.render(this.header('Crew time', this.project_name()) + '<div class="fs-empty">Loading the crew…</div>');
	this.bind_back();

	Promise.all([this.call('crew', { project: this.project }), this.call('sections', { project: this.project })])
		.then(function (results) {
			var context = self.context || {};
			self.crew_state = {
				workers: results[0].workers || [],
				previous: results[0].previous || [],
				previous_date: results[0].previous_date,
				sections: results[1] || [],
				date: frappe.datetime.get_today(),
				task: fs_recall('task:' + self.project),
				normal: flt(context.standard_day_hours) || 8,
				overtime: 0,
				picked: {},
				search: ''
			};
			var known = self.crew_state.sections.some(function (s) { return s.name === self.crew_state.task; });
			if (!known) self.crew_state.task = self.crew_state.sections[0] ? self.crew_state.sections[0].name : '';
			self.draw_crew();
		});
};

FuseSite.prototype.section_options = function (sections, selected, blank) {
	return (blank ? ['<option value="">' + fs_escape(blank) + '</option>'] : []).concat(sections.map(function (s) {
		return '<option value="' + fs_escape(s.name) + '"' + (s.name === selected ? ' selected' : '') + '>' +
			fs_escape(s.subject) + '</option>';
	})).join('');
};

FuseSite.prototype.draw_crew = function () {
	var self = this;
	var state = this.crew_state;
	var context = this.context || {};
	var picked = Object.keys(state.picked).length;

	var html = [
		this.header('Crew time', this.project_name()),
		'<div class="fs-pair">',
		'  <div class="fs-field"><label for="fs-date">Date</label>',
		'    <input id="fs-date" class="fs-input" type="date" data-date="1" value="' + fs_escape(state.date) + '"></div>',
		'  <div class="fs-field"><label for="fs-task">Section</label>',
		'    <select id="fs-task" class="fs-select" data-task="1">' + this.section_options(state.sections, state.task) + '</select></div>',
		'</div>',
		'<div class="fs-pair">',
		'  <div class="fs-field"><label for="fs-normal">Hours each</label>',
		'    <input id="fs-normal" class="fs-input" type="number" inputmode="decimal" min="0" step="0.5" data-normal="1" value="' + fs_num(state.normal) + '"></div>',
		'  <div class="fs-field"><label for="fs-ot">Overtime each</label>',
		'    <input id="fs-ot" class="fs-input" type="number" inputmode="decimal" min="0" step="0.5" data-ot="1" value="' + fs_num(state.overtime) + '"></div>',
		'</div>',
		context.auto_overtime
			? '<div class="fs-hint">Hours past ' + fs_num(context.standard_day_hours) + ' in a day become overtime by themselves.</div>'
			: '',
		state.previous.length
			? '<div class="fs-field" style="margin-top:12px"><button class="fs-btn" style="width:100%" data-same="1">Same crew as ' +
				fs_escape(frappe.datetime.str_to_user(state.previous_date)) + ' (' + state.previous.length + ')</button></div>'
			: '',
		'<div class="fs-field" style="margin-top:12px"><label for="fs-find">Workers</label>',
		'  <input id="fs-find" class="fs-input" type="search" placeholder="Find a worker" data-find="1" value="' + fs_escape(state.search) + '"></div>',
		'<div class="fs-list" data-workers="1"></div>'
	].join('\n');

	var bar = '<button class="fs-btn fs-btn-go" data-send="1"' + (picked ? '' : ' disabled') + '>' +
		(picked ? 'Send ' + picked + ' for approval' : 'Tick the crew') + '</button>';
	this.render(html, bar);
	this.bind_back();
	this.paint_workers();

	this.$root.find('[data-date]').on('change', function () { state.date = $(this).val(); });
	this.$root.find('[data-task]').on('change', function () {
		state.task = $(this).val();
		fs_remember('task:' + self.project, state.task);
		self.paint_workers();
	});
	this.$root.find('[data-normal]').on('input', function () { state.normal = flt($(this).val()); self.paint_workers(); });
	this.$root.find('[data-ot]').on('input', function () { state.overtime = flt($(this).val()); self.paint_workers(); });
	var timer = null;
	this.$root.find('[data-find]').on('input', function () {
		var value = $(this).val();
		clearTimeout(timer);
		timer = setTimeout(function () { state.search = value; self.paint_workers(); }, 150);
	});
	this.$root.find('[data-same]').on('click', function () {
		state.previous.forEach(function (row) {
			state.picked[row.employee] = { custom: false };
		});
		self.draw_crew();
	});
	this.$root.find('[data-send]').on('click', function () { self.send_crew(); });
};

FuseSite.prototype.paint_workers = function () {
	var self = this;
	var state = this.crew_state;
	var term = (state.search || '').toLowerCase();
	var sections = {};
	state.sections.forEach(function (s) { sections[s.name] = s.subject; });

	var rows = state.workers.filter(function (w) {
		return !term || [w.employee_name, w.name, w.designation, w.fc_trade].join(' ').toLowerCase().indexOf(term) !== -1;
	}).map(function (w) {
		var pick = state.picked[w.name];
		var hours = '';
		if (pick) {
			var normal = pick.custom ? pick.normal : state.normal;
			var ot = pick.custom ? pick.overtime : state.overtime;
			var where = pick.custom && pick.task && pick.task !== state.task ? ' · ' + (sections[pick.task] || pick.task) : '';
			hours = '<button class="fs-chip" data-hours="' + fs_escape(w.name) + '">' + fs_num(normal) + ' h' +
				(flt(ot) ? ' + ' + fs_num(ot) + ' OT' : '') + fs_escape(where) + '</button>';
		}
		return [
			'<div class="fs-row' + (pick ? ' fs-on' : '') + '" data-worker="' + fs_escape(w.name) + '" role="checkbox" aria-checked="' + (pick ? 'true' : 'false') + '" tabindex="0">',
			'  <span class="fs-check">' + fs_icon('tick') + '</span>',
			'  <span class="fs-row-main"><span class="fs-row-title">' + fs_escape(w.employee_name || w.name) + '</span>',
			'  <span class="fs-row-sub">' + fs_escape([w.fc_trade || w.designation, w.fc_worker_type].filter(Boolean).join(' · ')) + '</span></span>',
			hours,
			'</div>'
		].join('\n');
	});
	this.$root.find('[data-workers]').html(rows.join('\n') || '<div class="fs-empty">No workers match.</div>');

	this.$root.find('[data-worker]').on('click keydown', function (e) {
		if (e.type === 'keydown' && e.key !== ' ' && e.key !== 'Enter') return;
		if ($(e.target).closest('[data-hours]').length) return;
		e.preventDefault();
		var id = $(this).data('worker');
		if (state.picked[id]) delete state.picked[id];
		else state.picked[id] = { custom: false };
		self.draw_crew();
	});
	this.$root.find('[data-hours]').on('click', function (e) {
		e.stopPropagation();
		self.worker_hours($(this).data('hours'));
	});
};

FuseSite.prototype.worker_hours = function (employee) {
	var self = this;
	var state = this.crew_state;
	var pick = state.picked[employee];
	var worker = state.workers.filter(function (w) { return w.name === employee; })[0] || {};
	var dialog = new frappe.ui.Dialog({
		title: worker.employee_name || employee,
		fields: [
			{ fieldname: 'normal', fieldtype: 'Float', label: 'Hours', default: pick.custom ? pick.normal : state.normal },
			{ fieldname: 'overtime', fieldtype: 'Float', label: 'Overtime', default: pick.custom ? pick.overtime : state.overtime },
			{
				fieldname: 'task', fieldtype: 'Select', label: 'Section',
				options: state.sections.map(function (s) { return { value: s.name, label: s.subject }; }),
				default: pick.custom && pick.task ? pick.task : state.task
			}
		],
		primary_action_label: 'Set',
		primary_action: function (values) {
			state.picked[employee] = { custom: true, normal: flt(values.normal), overtime: flt(values.overtime), task: values.task };
			dialog.hide();
			self.draw_crew();
		},
		secondary_action_label: 'Same as the crew',
		secondary_action: function () {
			state.picked[employee] = { custom: false };
			dialog.hide();
			self.draw_crew();
		}
	});
	dialog.show();
};

FuseSite.prototype.send_crew = function () {
	var self = this;
	var state = this.crew_state;
	if (!state.task) {
		frappe.show_alert({ message: 'Choose the section.', indicator: 'orange' });
		return;
	}
	var rows = Object.keys(state.picked).map(function (employee) {
		var pick = state.picked[employee];
		return {
			employee: employee,
			task: pick.custom && pick.task ? pick.task : state.task,
			normal_hours: pick.custom ? pick.normal : state.normal,
			overtime_hours: pick.custom ? pick.overtime : state.overtime,
			activity_type: null
		};
	});
	var $send = this.$root.find('[data-send]').prop('disabled', true).text('Sending…');
	this.call('book_crew', {
		project: this.project,
		work_date: state.date,
		task: state.task,
		rows: JSON.stringify(rows)
	}).then(function (r) {
		self.done('Sent for approval', [
			r.workers + ' workers · ' + fs_num(r.hours) + ' hours' + (flt(r.overtime) ? ' (' + fs_num(r.overtime) + ' overtime)' : ''),
			r.name
		], { label: 'Book another crew', go: self.crew });
	}).catch(function () {
		$send.prop('disabled', false).text('Send ' + rows.length + ' for approval');
	});
};

// ---------------------------------------------------------------------------
// Approve time
// ---------------------------------------------------------------------------

FuseSite.prototype.approvals = function () {
	var self = this;
	this.screen = 'approve';
	this.render(this.header('Approve time', 'Crew sheets waiting') + '<div class="fs-empty">Loading…</div>');
	this.bind_back();

	this.call('pending').then(function (sheets) {
		if (!sheets.length) {
			self.render(self.header('Approve time', 'Crew sheets waiting') +
				'<div class="fs-empty">Nothing is waiting for approval.</div>');
			self.bind_back();
			return;
		}
		var cards = sheets.map(function (sheet) {
			var rows = (sheet.rows || []).map(function (row) {
				return '<tr><td>' + fs_escape(row.employee_name) + '<div class="fs-sub">' + fs_escape(row.section) + '</div></td>' +
					'<td class="fs-num">' + fs_num(row.normal_hours) + ' h' + (flt(row.overtime_hours) ? ' + ' + fs_num(row.overtime_hours) : '') + '</td></tr>';
			}).join('');
			return [
				'<div class="fs-card" data-sheet="' + fs_escape(sheet.name) + '">',
				'  <h4>' + fs_escape(sheet.project_name) + '</h4>',
				'  <div class="fs-sub">' + fs_escape(frappe.datetime.str_to_user(sheet.work_date)) + ' · booked by ' + fs_escape(sheet.booked_by) + '</div>',
				'  <div style="margin-top:6px"><b>' + sheet.total_workers + ' workers · ' + fs_num(sheet.total_hours) + ' h</b>' +
					(flt(sheet.total_overtime_hours) ? ' (' + fs_num(sheet.total_overtime_hours) + ' overtime)' : '') +
					' · ' + fs_escape(format_currency(sheet.total_cost)) + '</div>',
				'  <table class="fs-table">' + rows + '</table>',
				'  <div class="fs-actions">',
				'    <button class="fs-btn fs-btn-warn" data-back-sheet="' + fs_escape(sheet.name) + '">Send back</button>',
				'    <button class="fs-btn fs-btn-go" data-approve="' + fs_escape(sheet.name) + '">Approve</button>',
				'  </div>',
				'</div>'
			].join('\n');
		});
		self.render(self.header('Approve time', sheets.length + ' waiting') + cards.join('\n'));
		self.bind_back();

		self.$root.find('[data-approve]').on('click', function () {
			var name = $(this).data('approve');
			$(this).prop('disabled', true).text('Approving…');
			self.call('approve', { name: name }).then(function () {
				frappe.show_alert({ message: 'Approved. Labour is on the job.', indicator: 'green' });
				self.approvals();
			}).catch(function () { self.approvals(); });
		});
		self.$root.find('[data-back-sheet]').on('click', function () {
			var name = $(this).data('back-sheet');
			frappe.prompt(
				[{ fieldname: 'reason', fieldtype: 'Small Text', label: 'What needs fixing?', reqd: 1 }],
				function (values) {
					self.call('send_back', { name: name, reason: values.reason }).then(function () {
						frappe.show_alert({ message: 'Sent back to the foreman.', indicator: 'orange' });
						self.approvals();
					});
				},
				'Send back',
				'Send back'
			);
		});
	});
};

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

FuseSite.prototype.progress = function () {
	var self = this;
	this.screen = 'progress';
	this.render(this.header('Progress', this.project_name()) + '<div class="fs-empty">Loading…</div>');
	this.bind_back();

	this.call('sections', { project: this.project }).then(function (sections) {
		var rows = sections.map(function (s) {
			var pct = Math.round(flt(s.progress));
			return [
				'<div class="fs-row" data-section="' + fs_escape(s.name) + '" role="button" tabindex="0">',
				'  <span class="fs-row-main"><span class="fs-row-title">' + fs_escape(s.subject) + '</span>',
				'  <span class="fs-row-sub">' + fs_escape(s.status) + '</span>',
				'  <div class="fs-progress" aria-hidden="true"><span style="width:' + Math.min(pct, 100) + '%"></span></div></span>',
				'  <span class="fs-chip">' + pct + '%</span>',
				'</div>'
			].join('\n');
		});
		self.render(self.header('Progress', self.project_name()) +
			'<div class="fs-list">' + (rows.join('\n') || '<div class="fs-empty">No sections on this project.</div>') + '</div>');
		self.bind_back();
		self.$root.find('[data-section]').on('click keydown', function (e) {
			if (e.type === 'keydown' && e.key !== ' ' && e.key !== 'Enter') return;
			var task = $(this).data('section');
			var section = sections.filter(function (s) { return s.name === task; })[0];
			self.set_progress(section);
		});
	});
};

FuseSite.prototype.set_progress = function (section) {
	var self = this;
	var dialog = new frappe.ui.Dialog({
		title: section.subject,
		fields: [
			{ fieldname: 'percent', fieldtype: 'Percent', label: '% complete', default: flt(section.progress), reqd: 1 },
			{ fieldname: 'hint', fieldtype: 'HTML', options: '<div class="text-muted small">How much of this section is done, all of it, as of today.</div>' }
		],
		primary_action_label: 'Save',
		primary_action: function (values) {
			save(values.percent, null);
		},
		secondary_action_label: 'Section complete',
		secondary_action: function () {
			save(100, 'Completed');
		}
	});
	function save(percent, status) {
		self.call('set_progress', { task: section.name, percent: percent, status: status }).then(function (r) {
			dialog.hide();
			frappe.show_alert({ message: section.subject + ': ' + Math.round(r.progress) + '%', indicator: 'green' });
			self.progress();
		});
	}
	dialog.show();
};

// ---------------------------------------------------------------------------
// Daily report
// ---------------------------------------------------------------------------

FuseSite.prototype.report = function () {
	var self = this;
	this.screen = 'report';
	this.render(this.header('Daily report', this.project_name()) + '<div class="fs-empty">Loading…</div>');
	this.bind_back();

	Promise.all([this.call('daily_report', { project: this.project }), this.call('sections', { project: this.project })])
		.then(function (results) {
			self.report_doc = results[0];
			self.report_sections = results[1] || [];
			['activities', 'plant', 'materials', 'photos'].forEach(function (table) {
				self.report_doc[table] = self.report_doc[table] || [];
			});
			if (!self.report_doc.activities.length) self.report_doc.activities.push({});
			self.draw_report();
		});
};

FuseSite.prototype.draw_report = function () {
	var self = this;
	var doc = this.report_doc;
	var sections = this.report_sections;
	// Always one blank "work done" to type into; empty ones are dropped when saving.
	if (!doc.activities.length) doc.activities.push({});

	var weather = FS_WEATHER.map(function (w) {
		return '<button class="fs-chip' + (doc.weather === w ? ' fs-on' : '') + '" data-weather="' + fs_escape(w) + '">' + fs_escape(w) + '</button>';
	}).join('');

	var activities = doc.activities.map(function (row, i) {
		return [
			'<div class="fs-card" data-activity="' + i + '">',
			'  <div class="fs-field"><label>Section</label><select class="fs-select" data-a-task="' + i + '">' +
				self.section_options(sections, row.task, 'General') + '</select></div>',
			'  <div class="fs-field"><label>Work done</label><textarea class="fs-textarea" data-a-desc="' + i + '">' + fs_escape(row.description) + '</textarea></div>',
			'  <div class="fs-pair">',
			'    <div class="fs-field"><label>Section % complete</label><input class="fs-input" type="number" inputmode="decimal" min="0" max="100" data-a-pct="' + i + '" value="' + (row.percent_complete == null ? '' : fs_num(row.percent_complete)) + '"></div>',
			'    <div class="fs-field"><label>Crew</label><input class="fs-input" type="number" inputmode="numeric" min="0" data-a-crew="' + i + '" value="' + (row.crew_size || '') + '"></div>',
			'  </div>',
			'</div>'
		].join('\n');
	}).join('\n');

	var plant = doc.plant.map(function (row, i) {
		return [
			'<div class="fs-card">',
			'  <div class="fs-field"><label>Plant / equipment</label><input class="fs-input" data-p-name="' + i + '" value="' + fs_escape(row.plant) + '"></div>',
			'  <div class="fs-pair">',
			'    <div class="fs-field"><label>Hours</label><input class="fs-input" type="number" inputmode="decimal" data-p-hours="' + i + '" value="' + (row.hours || '') + '"></div>',
			'    <div class="fs-field"><label>Status</label><select class="fs-select" data-p-status="' + i + '">' +
				['Working', 'Standing', 'Breakdown'].map(function (s) {
					return '<option' + ((row.status || 'Working') === s ? ' selected' : '') + '>' + s + '</option>';
				}).join('') + '</select></div>',
			'  </div>',
			'</div>'
		].join('\n');
	}).join('\n');

	var photos = doc.photos.map(function (row, i) {
		return '<div class="fs-photo"><img src="' + fs_escape(row.photo) + '" alt="' + fs_escape(row.caption || 'Site photo') + '">' +
			'<button data-unphoto="' + i + '" aria-label="Remove photo">×</button></div>';
	}).join('');

	var html = [
		this.header('Daily report', this.project_name() + ' · ' + frappe.datetime.str_to_user(doc.report_date)),
		'<div class="fs-field"><label>Weather</label><div class="fs-chips">' + weather + '</div></div>',
		'<div class="fs-pair">',
		'  <div class="fs-field"><label for="fs-temp">Temperature °C</label><input id="fs-temp" class="fs-input" type="number" inputmode="decimal" data-r="temperature_c" value="' + (doc.temperature_c == null ? '' : fs_num(doc.temperature_c)) + '"></div>',
		'  <div class="fs-field"><label for="fs-cond">Site</label><select id="fs-cond" class="fs-select" data-r="site_condition">' +
			['', 'Workable', 'Partly Workable', 'Not Workable'].map(function (s) {
				return '<option' + ((doc.site_condition || '') === s ? ' selected' : '') + '>' + s + '</option>';
			}).join('') + '</select></div>',
		'</div>',
		'<div class="fs-pair">',
		'  <div class="fs-field"><label for="fs-labour">Labour on site</label><input id="fs-labour" class="fs-input" type="number" inputmode="numeric" data-r="labour_count" value="' + (doc.labour_count || '') + '"></div>',
		'  <div class="fs-field"><label for="fs-lost">Hours lost</label><input id="fs-lost" class="fs-input" type="number" inputmode="decimal" data-r="lost_hours" value="' + (doc.lost_hours || '') + '"></div>',
		'</div>',
		'<h4 style="margin:16px 0 8px">Work done</h4>', activities,
		'<button class="fs-btn" style="width:100%;margin-bottom:12px" data-add="activities">+ Add work done</button>',
		'<h4 style="margin:16px 0 8px">Plant on site</h4>', plant,
		'<button class="fs-btn" style="width:100%;margin-bottom:12px" data-add="plant">+ Add plant</button>',
		'<div class="fs-field"><label for="fs-issues">Issues and delays</label><textarea id="fs-issues" class="fs-textarea" data-r="issues">' + fs_escape(doc.issues) + '</textarea></div>',
		'<div class="fs-field"><label for="fs-safety">Safety and incidents</label><textarea id="fs-safety" class="fs-textarea" data-r="safety">' + fs_escape(doc.safety) + '</textarea></div>',
		'<h4 style="margin:16px 0 8px">Photos</h4>',
		'<div class="fs-photos">' + photos + '</div>',
		'<label class="fs-btn" style="width:100%;margin:10px 0 12px">' + fs_icon('camera') + ' Take a photo',
		'  <input class="fs-sr-only" type="file" accept="image/*" capture="environment" multiple data-camera="1"></label>',
		'<h4 style="margin:16px 0 8px">Sign off</h4>',
		'<canvas class="fs-signature" data-sign="1" aria-label="Signature pad"></canvas>',
		'<button class="fs-btn" style="margin-top:8px" data-clear-sign="1">Clear signature</button>'
	].join('\n');
	var bar = '<button class="fs-btn" data-save-report="1">Save</button>' +
		'<button class="fs-btn fs-btn-go" data-sign-report="1">Sign and submit</button>';
	this.render(html, bar);
	this.bind_back();
	this.signature_pad();

	this.$root.find('[data-weather]').on('click', function () {
		self.gather_report();
		doc.weather = $(this).data('weather');
		self.draw_report();
	});
	this.$root.find('[data-add]').on('click', function () {
		self.gather_report();
		doc[$(this).data('add')].push({});
		self.draw_report();
	});
	this.$root.find('[data-unphoto]').on('click', function () {
		self.gather_report();
		doc.photos.splice(flt($(this).data('unphoto')), 1);
		self.draw_report();
	});
	this.$root.find('[data-camera]').on('change', function () { self.upload_photos(this.files); });
	this.$root.find('[data-save-report]').on('click', function () { self.save_report(false); });
	this.$root.find('[data-sign-report]').on('click', function () { self.save_report(true); });
};

FuseSite.prototype.gather_report = function () {
	var doc = this.report_doc;
	var $root = this.$root;
	$root.find('[data-r]').each(function () { doc[$(this).data('r')] = $(this).val(); });
	doc.activities.forEach(function (row, i) {
		row.task = $root.find('[data-a-task="' + i + '"]').val() || null;
		row.description = $root.find('[data-a-desc="' + i + '"]').val();
		var pct = $root.find('[data-a-pct="' + i + '"]').val();
		row.percent_complete = pct === '' ? null : flt(pct);
		row.crew_size = cint($root.find('[data-a-crew="' + i + '"]').val());
	});
	doc.plant.forEach(function (row, i) {
		row.plant = $root.find('[data-p-name="' + i + '"]').val();
		row.hours = flt($root.find('[data-p-hours="' + i + '"]').val());
		row.status = $root.find('[data-p-status="' + i + '"]').val();
	});
	// Rows nobody filled in are not sent: an empty "work done" is not a record of anything.
	doc.activities = doc.activities.filter(function (row) { return (row.description || '').trim(); });
	doc.plant = doc.plant.filter(function (row) { return (row.plant || '').trim(); });
	return doc;
};

FuseSite.prototype.upload_photos = function (files) {
	var self = this;
	var doc = this.gather_report();
	var uploads = Array.prototype.map.call(files || [], function (file) {
		var form = new FormData();
		form.append('file', file, file.name);
		form.append('is_private', '1');
		form.append('doctype', 'FC Daily Site Report');
		form.append('docname', doc.name);
		form.append('optimize', '1');
		return fetch('/api/method/upload_file', {
			method: 'POST',
			headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token, Accept: 'application/json' },
			body: form
		}).then(function (response) {
			if (!response.ok) throw new Error('Upload failed (' + response.status + ')');
			return response.json();
		}).then(function (body) {
			doc.photos.push({ photo: body.message.file_url, caption: '' });
		});
	});
	frappe.show_alert({ message: 'Uploading ' + uploads.length + ' photo' + (uploads.length === 1 ? '' : 's') + '…', indicator: 'blue' });
	Promise.all(uploads).then(function () {
		self.draw_report();
	}).catch(function (error) {
		frappe.msgprint({ title: 'Photo not uploaded', message: fs_escape(error.message), indicator: 'red' });
		self.draw_report();
	});
};

FuseSite.prototype.signature_pad = function () {
	var canvas = this.$root.find('[data-sign]').get(0);
	if (!canvas) return;
	var ratio = window.devicePixelRatio || 1;
	canvas.width = canvas.offsetWidth * ratio;
	canvas.height = canvas.offsetHeight * ratio;
	var ctx = canvas.getContext('2d');
	ctx.scale(ratio, ratio);
	ctx.lineWidth = 2.5;
	ctx.lineCap = 'round';
	ctx.strokeStyle = '#0F172A';
	var drawing = false;
	var self = this;
	this.signed = false;

	function point(e) {
		var rect = canvas.getBoundingClientRect();
		return { x: e.clientX - rect.left, y: e.clientY - rect.top };
	}
	canvas.addEventListener('pointerdown', function (e) {
		drawing = true;
		canvas.setPointerCapture(e.pointerId);
		var p = point(e);
		ctx.beginPath();
		ctx.moveTo(p.x, p.y);
	});
	canvas.addEventListener('pointermove', function (e) {
		if (!drawing) return;
		var p = point(e);
		ctx.lineTo(p.x, p.y);
		ctx.stroke();
		self.signed = true;
	});
	['pointerup', 'pointercancel', 'pointerleave'].forEach(function (name) {
		canvas.addEventListener(name, function () { drawing = false; });
	});
	this.$root.find('[data-clear-sign]').on('click', function () {
		ctx.clearRect(0, 0, canvas.width, canvas.height);
		self.signed = false;
	});
};

FuseSite.prototype.save_report = function (sign) {
	var self = this;
	var doc = this.gather_report();
	var signature = null;
	if (sign) {
		if (!this.signed) {
			frappe.show_alert({ message: 'Sign the report first.', indicator: 'orange' });
			return;
		}
		if (this.context && this.context.require_photo && !doc.photos.length) {
			frappe.show_alert({ message: 'This site asks for at least one photo.', indicator: 'orange' });
			return;
		}
		signature = this.$root.find('[data-sign]').get(0).toDataURL('image/png');
	}
	var data = {};
	['weather', 'temperature_c', 'site_condition', 'labour_count', 'lost_hours', 'issues', 'safety'].forEach(function (f) {
		data[f] = doc[f] === '' ? null : doc[f];
	});
	data.activities = doc.activities;
	data.plant = doc.plant;
	data.photos = doc.photos;
	this.call('save_daily_report', { name: doc.name, data: JSON.stringify(data), sign: signature }).then(function (r) {
		if (r.docstatus === 1) {
			self.done('Report signed off', [doc.name]);
		} else {
			frappe.show_alert({ message: 'Saved.', indicator: 'green' });
		}
	});
};

// ---------------------------------------------------------------------------
// Material request
// ---------------------------------------------------------------------------

FuseSite.prototype.request = function () {
	var self = this;
	this.screen = 'request';
	this.call('sections', { project: this.project }).then(function (sections) {
		self.request_state = { lines: [], sections: sections, task: '', required: frappe.datetime.add_days(frappe.datetime.get_today(), 3) };
		self.draw_request();
	});
};

FuseSite.prototype.draw_request = function () {
	var self = this;
	var state = this.request_state;
	var lines = state.lines.map(function (line, i) {
		return [
			'<div class="fs-row">',
			'  <span class="fs-row-main"><span class="fs-row-title">' + fs_escape(line.item_name || line.item_code) + '</span>',
			'  <span class="fs-row-sub">' + fs_escape(line.item_code) + '</span></span>',
			'  <input class="fs-input" style="width:96px" type="number" inputmode="decimal" min="0" data-qty="' + i + '" value="' + fs_num(line.qty) + '" aria-label="Quantity">',
			'  <span class="fs-sub">' + fs_escape(line.uom) + '</span>',
			'  <button class="fs-chip" data-drop="' + i + '" aria-label="Remove">×</button>',
			'</div>'
		].join('\n');
	}).join('\n');

	this.render([
		this.header('Material request', this.project_name()),
		'<div class="fs-pair">',
		'  <div class="fs-field"><label for="fs-rtask">Section</label><select id="fs-rtask" class="fs-select" data-rtask="1">' +
			this.section_options(state.sections, state.task, 'Whole project') + '</select></div>',
		'  <div class="fs-field"><label for="fs-rdate">Needed by</label><input id="fs-rdate" class="fs-input" type="date" data-rdate="1" value="' + fs_escape(state.required) + '"></div>',
		'</div>',
		'<div class="fs-field"><label for="fs-item">Add an item</label><input id="fs-item" class="fs-input" type="search" placeholder="Search items" data-item="1"></div>',
		'<div class="fs-list" data-matches="1"></div>',
		'<h4 style="margin:16px 0 8px">Requested</h4>',
		'<div class="fs-list">' + (lines || '<div class="fs-empty">Nothing yet.</div>') + '</div>'
	].join('\n'), '<button class="fs-btn fs-btn-go" data-send-request="1"' + (state.lines.length ? '' : ' disabled') + '>Send request</button>');
	this.bind_back();

	this.$root.find('[data-rtask]').on('change', function () { state.task = $(this).val(); });
	this.$root.find('[data-rdate]').on('change', function () { state.required = $(this).val(); });
	this.$root.find('[data-qty]').on('input', function () { state.lines[cint($(this).data('qty'))].qty = flt($(this).val()); });
	this.$root.find('[data-drop]').on('click', function () { state.lines.splice(cint($(this).data('drop')), 1); self.draw_request(); });
	var timer = null;
	this.$root.find('[data-item]').on('input', function () {
		var term = $(this).val();
		clearTimeout(timer);
		timer = setTimeout(function () {
			if (!term) { self.$root.find('[data-matches]').html(''); return; }
			self.call('items', { search: term }).then(function (items) {
				self.$root.find('[data-matches]').html(items.map(function (item, i) {
					return '<div class="fs-row" data-pick="' + i + '" role="button" tabindex="0"><span class="fs-row-main"><span class="fs-row-title">' +
						fs_escape(item.item_name) + '</span><span class="fs-row-sub">' + fs_escape(item.name) + '</span></span></div>';
				}).join('') || '<div class="fs-empty">No items match.</div>');
				self.$root.find('[data-pick]').on('click', function () {
					var item = items[cint($(this).data('pick'))];
					state.lines.push({ item_code: item.name, item_name: item.item_name, uom: item.stock_uom, qty: 1 });
					self.draw_request();
				});
			});
		}, 300);
	});
	this.$root.find('[data-send-request]').on('click', function () {
		$(this).prop('disabled', true).text('Sending…');
		self.call('material_request', {
			project: self.project,
			lines: JSON.stringify(state.lines),
			task: state.task || null,
			required_by: state.required
		}).then(function (r) {
			self.done(r.submitted ? 'Request sent' : 'Request saved as a draft', [r.name], { label: 'Another request', go: self.request });
		}).catch(function () { self.draw_request(); });
	});
};

// ---------------------------------------------------------------------------
// Receive delivery
// ---------------------------------------------------------------------------

FuseSite.prototype.receive = function () {
	var self = this;
	var context = this.context || {};
	// Where Fuse Manufacturing's receiving screen is installed it is THE way goods come in —
	// it posts the receipt to Intacct. Two receiving screens would be two rules.
	if (context.receiving_page) {
		frappe.set_route(context.receiving_page);
		return;
	}
	this.screen = 'receive';
	this.render(this.header('Receive delivery', this.project_name()) + '<div class="fs-empty">Loading orders…</div>');
	this.bind_back();
	this.call('open_orders', { project: this.project }).then(function (orders) {
		var rows = orders.map(function (o) {
			return '<div class="fs-row" data-order="' + fs_escape(o.name) + '" role="button" tabindex="0"><span class="fs-row-main">' +
				'<span class="fs-row-title">' + fs_escape(o.supplier_name || o.supplier) + '</span>' +
				'<span class="fs-row-sub">' + fs_escape(o.name) + ' · ' + fs_escape(frappe.datetime.str_to_user(o.transaction_date)) + '</span></span></div>';
		}).join('\n');
		self.render(self.header('Receive delivery', self.project_name()) +
			'<div class="fs-list">' + (rows || '<div class="fs-empty">Nothing is waiting to be delivered to this project.</div>') + '</div>');
		self.bind_back();
		self.$root.find('[data-order]').on('click', function () { self.receive_order($(this).data('order')); });
	});
};

FuseSite.prototype.receive_order = function (order) {
	var self = this;
	this.call('order_lines', { purchase_order: order }).then(function (lines) {
		var rows = lines.filter(function (l) { return l.outstanding > 0; }).map(function (line) {
			return [
				'<div class="fs-row">',
				'  <span class="fs-row-main"><span class="fs-row-title">' + fs_escape(line.item_name) + '</span>',
				'  <span class="fs-row-sub">' + fs_num(line.outstanding) + ' ' + fs_escape(line.uom) + ' still to come</span></span>',
				'  <input class="fs-input" style="width:96px" type="number" inputmode="decimal" min="0" data-line="' + fs_escape(line.name) + '" value="' + fs_num(line.outstanding) + '" aria-label="Received">',
				'</div>'
			].join('\n');
		}).join('\n');
		self.render(self.header('Receive delivery', order) + '<div class="fs-list">' + rows + '</div>',
			'<button class="fs-btn fs-btn-go" data-book="1">Book it in</button>');
		self.$root.find('[data-back]').off('click').on('click', function () { self.receive(); });
		self.$root.find('[data-book]').on('click', function () {
			var picked = [];
			self.$root.find('[data-line]').each(function () {
				if (flt($(this).val()) > 0) picked.push({ name: $(this).data('line'), qty: flt($(this).val()) });
			});
			if (!picked.length) {
				frappe.show_alert({ message: 'Enter what arrived.', indicator: 'orange' });
				return;
			}
			$(this).prop('disabled', true).text('Booking…');
			self.call('receive', { purchase_order: order, lines: JSON.stringify(picked) }).then(function (r) {
				self.done('Delivery booked in', [r.name], { label: 'Another delivery', go: self.receive });
			}).catch(function () { self.receive_order(order); });
		});
	});
};
