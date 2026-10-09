from frappe.utils.nestedset import NestedSet


class FCBOQGroup(NestedSet):
	nsm_parent_field = "parent_fc_boq_group"
