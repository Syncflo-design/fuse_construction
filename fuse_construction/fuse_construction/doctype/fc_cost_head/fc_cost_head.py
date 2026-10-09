from frappe.utils.nestedset import NestedSet


class FCCostHead(NestedSet):
	nsm_parent_field = "parent_fc_cost_head"
