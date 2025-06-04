// Copyright (c) 2022, healthcare and contributors
// For license information, please see license.txt
// {% include "healthcare/public/js/service_request.js" %}  - Commented by Amit Kumar on 2023-10-04

frappe.ui.form.on('Medication Request', {
    refresh: function(frm) {
        frm.set_query("status", function () {
			return {
				"filters": {
					"code_system": "Medication Request Status",
				}
			};
		});
	},

})