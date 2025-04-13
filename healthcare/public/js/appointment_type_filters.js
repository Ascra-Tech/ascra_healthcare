// appointment_type_filters.js
// Dynamic filtering module for Patient Appointment
// This file handles the filtering of service units, practitioners, and departments
// based on the selected appointment type's "allow_booking_for" setting

frappe.provide('healthcare.appointment_filters');

healthcare.appointment_filters = {
    
    // Setup filter for the appropriate field based on appointment_for
    setupFilters: function(frm) {
        if (frm.doc.appointment_for == 'Service Unit') {
            this.setupServiceUnitFilter(frm);
        } else if (frm.doc.appointment_for == 'Practitioner') {
            this.setupPractitionerFilter(frm);
        } else if (frm.doc.appointment_for == 'Department') {
            this.setupDepartmentFilter(frm);
        }
    },
    
    // Function to handle appointment type selection
    handleAppointmentType: function(frm) {
        if (!frm.doc.appointment_type) {
            return;
        }
        
        if (frm.doc.appointment_for && frm.doc[frappe.scrub(frm.doc.appointment_for)]) {
            frm.events.set_payment_details(frm);
        }
        
        // Get the allow_booking_for value for the selected appointment type
        frappe.db.get_value('Appointment Type', frm.doc.appointment_type, 'allow_booking_for', (r) => {
            if (r && r.allow_booking_for) {
                // Set the appointment_for field based on the allow_booking_for value
                frm.set_value('appointment_for', r.allow_booking_for);
                
                // Clear the respective fields based on appointment_for
                if (r.allow_booking_for == 'Practitioner') {
                    frm.set_value('practitioner', '');
                    frm.set_value('service_unit', '');
                    frm.set_value('department', '');
                    // Setup filter for practitioner
                    this.setupPractitionerFilter(frm);
                } else if (r.allow_booking_for == 'Department') {
                    frm.set_value('practitioner', '');
                    frm.set_value('service_unit', '');
                    frm.set_value('department', '');
                    // Setup filter for department
                    this.setupDepartmentFilter(frm);
                } else if (r.allow_booking_for == 'Service Unit') {
                    frm.set_value('practitioner', '');
                    frm.set_value('service_unit', '');
                    frm.set_value('department', '');
                    // Setup filter for service unit
                    this.setupServiceUnitFilter(frm);
                }
            }
        });
    },
    
    // Function to setup service unit filter based on appointment type
    setupServiceUnitFilter: function(frm) {
        if (!frm.doc.appointment_type || !frm.doc.company) {
            return;
        }
        
        // Set up a dynamic query for the service unit field
        // Note: Updated to use the new module path
        frm.set_query('service_unit', function() {
            return {
                query: "healthcare.healthcare.doctype.patient_appointment.appointment_type_queries.get_service_units_by_appointment_type",
                filters: {
                    'appointment_type': frm.doc.appointment_type,
                    'company': frm.doc.company
                }
            };
        });
        
        // Update field help text
        frm.get_field('service_unit').set_description(
            __('Showing service units associated with appointment type {0}', [frm.doc.appointment_type.bold()])
        );
    },
    
    // Function to setup practitioner filter based on appointment type
    setupPractitionerFilter: function(frm) {
        if (!frm.doc.appointment_type) {
            return;
        }
        
        // Set up a dynamic query for the practitioner field
        // Note: Updated to use the new module path
        frm.set_query('practitioner', function() {
            return {
                query: "healthcare.healthcare.doctype.patient_appointment.appointment_type_queries.get_practitioners_by_appointment_type",
                filters: {
                    'appointment_type': frm.doc.appointment_type
                }
            };
        });
        
        // Update field help text
        frm.get_field('practitioner').set_description(
            __('Showing practitioners associated with appointment type {0}', [frm.doc.appointment_type.bold()])
        );
    },
    
    // Function to setup department filter based on appointment type
    setupDepartmentFilter: function(frm) {
        if (!frm.doc.appointment_type) {
            return;
        }
        
        // Set up a dynamic query for the department field
        // Note: Updated to use the new module path
        frm.set_query('department', function() {
            return {
                query: "healthcare.healthcare.doctype.patient_appointment.appointment_type_queries.get_departments_by_appointment_type",
                filters: {
                    'appointment_type': frm.doc.appointment_type
                }
            };
        });
        
        // Update field help text
        frm.get_field('department').set_description(
            __('Showing departments associated with appointment type {0}', [frm.doc.appointment_type.bold()])
        );
    }
};

// Event handlers to be added to Patient Appointment form
frappe.ui.form.on('Patient Appointment', {
    // On form refresh
    refresh: function(frm) {
        healthcare.appointment_filters.setupFilters(frm);
    },
    
    // When appointment type changes
    appointment_type: function(frm) {
        healthcare.appointment_filters.handleAppointmentType(frm);
    },
    
    // When appointment_for field changes
    appointment_for: function(frm) {
        if (frm.doc.appointment_for && frm.doc.appointment_type) {
            healthcare.appointment_filters.setupFilters(frm);
        }
    },
    
    // When company changes (for service unit filter)
    company: function(frm) {
        if (frm.doc.appointment_for == 'Service Unit' && frm.doc.appointment_type) {
            healthcare.appointment_filters.setupServiceUnitFilter(frm);
        }
    }
});