// Project Shape. With a project: the section table and the curve. Without: the portfolio.

frappe.query_reports["FC Project Shape"] = {
	filters: [
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
			get_query: () => ({ filters: { fc_boq: ["is", "set"] } }),
		},
		{
			fieldname: "as_at",
			label: __("As At"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "periodicity",
			label: __("Curve By"),
			fieldtype: "Select",
			options: ["Weekly", "Monthly"],
			default: "Weekly",
			depends_on: "eval:doc.project",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;
		if (data.bold) value = `<b>${value}</b>`;
		if (column.fieldname === "health" && data.health) {
			const colour = { Green: "green", Amber: "orange", Red: "red" }[data.health] || "grey";
			value = `<span class="indicator-pill ${colour}">${frappe.utils.escape_html(data.health)}</span>`;
		}
		if (["cost_variance", "schedule_variance", "variance_at_completion"].includes(column.fieldname)) {
			if (flt(data[column.fieldname]) < 0) value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		if (["cpi", "spi"].includes(column.fieldname) && data[column.fieldname] != null) {
			const ratio = flt(data[column.fieldname]);
			if (ratio && ratio < 0.9) value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},

	onload(report) {
		report.page.add_inner_button(__("Dashboard"), () => {
			const project = report.get_filter_value("project");
			frappe.set_route("fc-project-dashboard", project ? { project } : {});
		});
	},
};
