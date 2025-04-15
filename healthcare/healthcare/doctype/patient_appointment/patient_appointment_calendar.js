frappe.views.calendar["Patient Appointment"] = {
    field_map: {
        "start": "start",
        "end": "end",
        "id": "name",
        "title": "title",  // Use the combined title field created in Python
        "allDay": "allDay",
        "eventColor": "color"
    },
    gantt: true,
    filters: [
        {
            "fieldtype": "Link",
            "fieldname": "appointment_type",
            "options": "Appointment Type",
            "label": "Appointment Type"
        },
        {
            "fieldtype": "Select",
            "fieldname": "appointment_for",
            "options": "\nPractitioner\nDepartment\nService Unit",
            "label": "Appointment For"
        },
        {
            "fieldtype": "Link",
            "fieldname": "practitioner",
            "options": "Healthcare Practitioner",
            "label": "Healthcare Practitioner"
        },
        {
            "fieldtype": "Link",
            "fieldname": "department",
            "options": "Medical Department",
            "label": "Department"
        },
        {
            "fieldtype": "Link",
            "fieldname": "service_unit",
            "options": "Healthcare Service Unit",
            "label": "Service Unit"
        },
        {
            "fieldtype": "Check",
            "fieldname": "invoiced",
            "label": "Invoiced"
        },
        {
            "fieldtype": "Select",
            "fieldname": "status",
            "options": "\nScheduled\nOpen\nConfirmed\nChecked In\nChecked Out\nClosed\nCancelled\nNo Show",
            "label": "Status"
        }
    ],
    get_events_method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_events"
};