frappe.listview_settings['Patient Appointment'] = {
    onload: function(listview) {
        // Skip for administrators and system managers
        if (frappe.user.has_role('Administrator') || frappe.user.has_role('System Manager')) {
            return;
        }
        
        // If user has Physician role (which appears to be used in your system)
        if (frappe.user.has_role('Physician')) {
            // User has practitioner role, get the linked practitioner
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Healthcare Practitioner",
                    filters: {"user_id": frappe.session.user},
                    fieldname: "name"
                },
                callback: function(data) {
                    if (data.message && data.message.name) {
                        console.log("Filtering for practitioner: " + data.message.name);
                        // User is linked to a practitioner, restrict view to their appointments only
                        listview.filter_area.add([[
                            "Patient Appointment", 
                            "practitioner", 
                            "=", 
                            data.message.name
                        ]]);
                        
                        // Prevent removal of this filter
                        listview.filter_area.on("change", function() {
                            const filters = listview.filter_area.get();
                            const hasRequiredFilter = filters.some(filter => 
                                filter[0] === "Patient Appointment" && 
                                filter[1] === "practitioner" && 
                                filter[2] === "=" && 
                                filter[3] === data.message.name
                            );
                            
                            if (!hasRequiredFilter) {
                                // Re-add the filter if it was removed
                                listview.filter_area.add([[
                                    "Patient Appointment", 
                                    "practitioner", 
                                    "=", 
                                    data.message.name
                                ]]);
                            }
                        });
                    } else {
                        console.log("No practitioner found for user with Physician role");
                        frappe.show_alert({
                            message: __("Your user account is not linked to a Healthcare Practitioner record. Please contact your administrator."),
                            indicator: 'red'
                        });
                    }
                }
            });
        }
        // If user has Patient role
        else if (frappe.user.has_role('Patient')) {
            // Handle patient filtering (code as before)
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Patient",
                    filters: {"user_id": frappe.session.user},
                    fieldname: "name"
                },
                callback: function(data) {
                    if (data.message && data.message.name) {
                        // Similar filter logic for patients
                        listview.filter_area.add([[
                            "Patient Appointment", 
                            "patient", 
                            "=", 
                            data.message.name
                        ]]);
                    }
                }
            });
        }
    }
};