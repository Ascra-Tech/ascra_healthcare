frappe.views.calendar["Patient Appointment"] = {
    field_map: {
        "start": "start",
        "end": "end",
        "id": "name",
        "title": "patient",
        "allDay": "allDay",
        "eventColor": "color"
    },
    gantt: true,
    get_events_method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_events"
};

// Add this to a file that loads after calendar.js
$(document).on('app_ready', function() {
    // Check if we're on the Patient Appointment Calendar page
    if (frappe.get_route()[0] === 'List' && frappe.get_route()[1] === 'Patient Appointment' && frappe.get_route()[2] === 'Calendar') {
        // Override the default event click handler
        if (frappe.views.calendar['Patient Appointment']) {
            const originalClick = frappe.views.calendar['Patient Appointment'].on_event_click;
            
            frappe.views.calendar['Patient Appointment'].on_event_click = function(event) {
                // Get the appointment details
                frappe.db.get_doc('Patient Appointment', event.name)
                    .then(doc => {
                        frappe.msgprint({
                            title: __('Appointment Details'),
                            indicator: 'blue',
                            message: `
                                <div style="min-width: 300px;">
                                    <p><b>Patient:</b> ${doc.patient_name || doc.patient}</p>
                                    <p><b>Type:</b> ${doc.appointment_type || 'N/A'}</p>
                                    <p><b>Date & Time:</b> ${frappe.datetime.str_to_user(doc.appointment_date)} ${doc.appointment_time || ''}</p>
                                    <p><b>Duration:</b> ${doc.duration || '15'} minutes</p>
                                    <p><b>Practitioner:</b> ${doc.practitioner_name || doc.practitioner || 'N/A'}</p>
                                    <p><b>Status:</b> ${doc.status || 'N/A'}</p>
                                    <p><b>Invoice:</b> ${doc.invoiced ? 'Invoiced' : 'Not Invoiced'}</p>
                                    ${doc.notes ? `<p><b>Notes:</b> ${doc.notes}</p>` : ''}
                                    <div style="margin-top: 10px;">
                                        <button class="btn btn-sm btn-primary" 
                                                onclick="frappe.set_route('Form', 'Patient Appointment', '${doc.name}')">
                                            View Full Details
                                        </button>
                                    </div>
                                </div>
                            `
                        });
                    });
            };
        }
    }
});