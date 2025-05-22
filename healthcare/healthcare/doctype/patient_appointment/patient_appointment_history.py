# patient_appointment_history.py
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import format_datetime, get_datetime, format_date, format_time


@frappe.whitelist()
def get_patient_appointment_history(patient):
    """
    Get comprehensive appointment history for a patient with all relevant details
    
    Args:
        patient (str): Patient ID
        
    Returns:
        dict: Contains appointment history and summary statistics
    """
    if not patient:
        frappe.throw(_("Patient is required"))
    
    # Validate patient exists
    if not frappe.db.exists("Patient", patient):
        frappe.throw(_("Patient {0} does not exist").format(patient))
    
    # Get appointment history with all details
    appointments = frappe.db.sql("""
        SELECT 
            pa.name,
            pa.appointment_date,
            pa.appointment_time,
            pa.appointment_datetime,
            pa.status,
            pa.appointment_type,
            pa.appointment_for,
            pa.practitioner,
            pa.practitioner_name,
            pa.department,
            pa.service_unit,
            pa.duration,
            pa.invoiced,
            pa.paid_amount,
            pa.ref_sales_invoice,
            pa.notes,
            pa.creation,
            pa.modified,
            pa.company,
            pa.referring_practitioner,
            pa.procedure_template,
            pa.therapy_type,
            pa.google_meet_link,
            at.color as appointment_type_color,
            at.default_duration as type_default_duration,
            md.department as department_name,
            hsu.healthcare_service_unit_name as service_unit_name,
            hp.practitioner_name as referring_practitioner_name
        FROM 
            `tabPatient Appointment` pa
        LEFT JOIN 
            `tabAppointment Type` at ON pa.appointment_type = at.name
        LEFT JOIN 
            `tabMedical Department` md ON pa.department = md.name
        LEFT JOIN 
            `tabHealthcare Service Unit` hsu ON pa.service_unit = hsu.name
        LEFT JOIN 
            `tabHealthcare Practitioner` hp ON pa.referring_practitioner = hp.name
        WHERE 
            pa.patient = %s
            AND pa.docstatus < 2
        ORDER BY 
            pa.appointment_date DESC, 
            pa.appointment_time DESC,
            pa.creation DESC
    """, (patient,), as_dict=True)
    
    # Process appointments to add computed fields
    processed_appointments = []
    stats = {
        'total_appointments': len(appointments),
        'completed_appointments': 0,
        'cancelled_appointments': 0,
        'upcoming_appointments': 0,
        'total_paid': 0,
        'practitioner_appointments': 0,
        'department_appointments': 0,
        'service_unit_appointments': 0
    }
    
    today = frappe.utils.getdate()
    
    for appointment in appointments:
        # Determine primary provider based on appointment_for
        if appointment.appointment_for == "Practitioner":
            appointment.primary_provider = appointment.practitioner_name or appointment.practitioner
            appointment.provider_type = "Practitioner"
            appointment.provider_icon = "fa-user-md"
            stats['practitioner_appointments'] += 1
        elif appointment.appointment_for == "Department":
            appointment.primary_provider = appointment.department_name or appointment.department
            appointment.provider_type = "Department"
            appointment.provider_icon = "fa-building"
            stats['department_appointments'] += 1
        elif appointment.appointment_for == "Service Unit":
            appointment.primary_provider = appointment.service_unit_name or appointment.service_unit
            appointment.provider_type = "Service Unit"
            appointment.provider_icon = "fa-hospital-o"
            stats['service_unit_appointments'] += 1
        else:
            appointment.primary_provider = "Not Specified"
            appointment.provider_type = "Unknown"
            appointment.provider_icon = "fa-question"
        
        # Format dates and times
        if appointment.appointment_date:
            appointment.formatted_date = format_date(appointment.appointment_date)
            
        if appointment.appointment_time:
            appointment.formatted_time = format_time(appointment.appointment_time)
        else:
            appointment.formatted_time = "All Day"
            
        if appointment.appointment_datetime:
            appointment.formatted_datetime = format_datetime(appointment.appointment_datetime)
        
        # Status styling
        status_colors = {
            'Scheduled': 'blue',
            'Open': 'orange',
            'Confirmed': 'green',
            'Checked In': 'purple',
            'Checked Out': 'darkgreen',
            'Closed': 'gray',
            'Cancelled': 'red',
            'No Show': 'darkred'
        }
        appointment.status_color = status_colors.get(appointment.status, 'gray')
        
        # Calculate statistics
        if appointment.status in ['Closed', 'Checked Out']:
            stats['completed_appointments'] += 1
        elif appointment.status == 'Cancelled':
            stats['cancelled_appointments'] += 1
        elif appointment.appointment_date >= today and appointment.status not in ['Closed', 'Cancelled', 'No Show']:
            stats['upcoming_appointments'] += 1
            
        if appointment.paid_amount:
            stats['total_paid'] += float(appointment.paid_amount)
        
        # Add duration display
        if appointment.duration:
            if appointment.duration >= 60:
                hours = appointment.duration // 60
                minutes = appointment.duration % 60
                if minutes > 0:
                    appointment.duration_display = f"{hours}h {minutes}m"
                else:
                    appointment.duration_display = f"{hours}h"
            else:
                appointment.duration_display = f"{appointment.duration}m"
        else:
            appointment.duration_display = "Not Set"
        
        # Payment status
        appointment.payment_status = "Paid" if appointment.invoiced else "Pending"
        appointment.payment_color = "green" if appointment.invoiced else "orange"
        
        # Add actions available
        appointment.can_reschedule = appointment.status in ['Scheduled', 'Confirmed', 'Open']
        appointment.can_cancel = appointment.status not in ['Cancelled', 'Closed', 'No Show']
        appointment.can_create_encounter = appointment.status in ['Checked In', 'Confirmed', 'Open']
        
        processed_appointments.append(appointment)
    
    # Get patient basic info
    patient_info = frappe.get_doc("Patient", patient)
    
    return {
        'appointments': processed_appointments,
        'stats': stats,
        'patient_info': {
            'name': patient_info.name,
            'patient_name': patient_info.patient_name,
            'sex': patient_info.sex,
            'dob': patient_info.dob,
            'mobile': patient_info.mobile,
            'email': patient_info.email
        }
    }


@frappe.whitelist()
def get_appointment_quick_actions(appointment_name):
    """
    Get available quick actions for an appointment
    
    Args:
        appointment_name (str): Appointment ID
        
    Returns:
        dict: Available actions for the appointment
    """
    appointment = frappe.get_doc("Patient Appointment", appointment_name)
    
    actions = {
        'can_reschedule': appointment.status in ['Scheduled', 'Confirmed', 'Open'],
        'can_cancel': appointment.status not in ['Cancelled', 'Closed', 'No Show'],
        'can_create_encounter': appointment.status in ['Checked In', 'Confirmed', 'Open'],
        'can_check_in': appointment.status in ['Open', 'Confirmed'] and not appointment.appointment_based_on_check_in,
        'can_confirm': appointment.status == 'Scheduled',
        'can_view_invoice': appointment.invoiced and appointment.ref_sales_invoice,
        'can_make_payment': not appointment.invoiced and appointment.status not in ['Cancelled', 'Closed']
    }
    
    return actions


@frappe.whitelist()
def get_patient_appointment_summary(patient):
    """
    Get a quick summary of patient appointments for dashboard
    
    Args:
        patient (str): Patient ID
        
    Returns:
        dict: Summary statistics
    """
    if not patient:
        return {}
    
    summary = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_appointments,
            SUM(CASE WHEN status IN ('Closed', 'Checked Out') THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled,
            SUM(CASE WHEN appointment_date >= CURDATE() AND status NOT IN ('Closed', 'Cancelled', 'No Show') THEN 1 ELSE 0 END) as upcoming,
            SUM(CASE WHEN invoiced = 1 THEN IFNULL(paid_amount, 0) ELSE 0 END) as total_paid,
            MAX(appointment_date) as last_appointment_date,
            MIN(appointment_date) as first_appointment_date
        FROM 
            `tabPatient Appointment`
        WHERE 
            patient = %s 
            AND docstatus < 2
    """, (patient,), as_dict=True)
    
    if summary:
        return summary[0]
    
    return {
        'total_appointments': 0,
        'completed': 0,
        'cancelled': 0,
        'upcoming': 0,
        'total_paid': 0,
        'last_appointment_date': None,
        'first_appointment_date': None
    }