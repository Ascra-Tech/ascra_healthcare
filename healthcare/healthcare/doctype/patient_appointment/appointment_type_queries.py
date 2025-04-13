# -*- coding: utf-8 -*-
# Copyright (c) 2023, Ascra Technologies LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_service_units_by_appointment_type(doctype, txt, searchfield, start, page_len, filters):
    """
    This function fetches service units associated with a specific appointment type
    from the Appointment Type Service Item child table.
    
    Args:
        doctype (str): The doctype being searched (Healthcare Service Unit)
        txt (str): The search text entered by the user
        searchfield (str): The field being searched
        start (int): The starting index for pagination
        page_len (int): The number of results per page
        filters (dict): The filters applied to the search
            - appointment_type: The selected appointment type
            - company: The selected company
    
    Returns:
        list: List of service units that match the criteria
    """
    appointment_type = filters.get('appointment_type')
    company = filters.get('company')
    
    if not appointment_type:
        return []
    
    # Get all service units linked to this appointment type through the child table
    service_units = frappe.db.sql("""
        SELECT hsu.name, hsu.healthcare_service_unit_name
        FROM `tabHealthcare Service Unit` hsu
        INNER JOIN `tabAppointment Type Service Item` atsi
        ON atsi.dt = 'Healthcare Service Unit' AND atsi.dn = hsu.name
        WHERE atsi.parent = %s
        AND (hsu.company = %s OR hsu.company IS NULL)
        AND hsu.is_group = 0
        AND hsu.allow_appointments = 1
        AND (hsu.name LIKE %s OR hsu.healthcare_service_unit_name LIKE %s)
        ORDER BY hsu.healthcare_service_unit_name
        LIMIT %s, %s
    """, (
        appointment_type,
        company,
        "%%%s%%" % txt,
        "%%%s%%" % txt,
        cint(start),
        cint(page_len)
    ), as_list=1)
    
    return service_units

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_practitioners_by_appointment_type(doctype, txt, searchfield, start, page_len, filters):
    """
    This function fetches practitioners associated with a specific appointment type
    from the Appointment Type Service Item child table.
    
    Args:
        doctype (str): The doctype being searched (Healthcare Practitioner)
        txt (str): The search text entered by the user
        searchfield (str): The field being searched
        start (int): The starting index for pagination
        page_len (int): The number of results per page
        filters (dict): The filters applied to the search
            - appointment_type: The selected appointment type
    
    Returns:
        list: List of practitioners that match the criteria
    """
    appointment_type = filters.get('appointment_type')
    
    if not appointment_type:
        return []
    
    # Get all practitioners linked to this appointment type through the child table
    practitioners = frappe.db.sql("""
        SELECT hp.name, CONCAT_WS(' ', COALESCE(hp.first_name, ''), COALESCE(hp.middle_name, ''), COALESCE(hp.last_name, '')) as practitioner_name
        FROM `tabHealthcare Practitioner` hp
        INNER JOIN `tabAppointment Type Service Item` atsi
        ON atsi.dt = 'Healthcare Practitioner' AND atsi.dn = hp.name
        WHERE atsi.parent = %s
        AND (hp.name LIKE %s OR hp.first_name LIKE %s)
        ORDER BY hp.first_name
        LIMIT %s, %s
    """, (
        appointment_type,
        "%%%s%%" % txt,
        "%%%s%%" % txt,
        cint(start),
        cint(page_len)
    ), as_list=1)
    
    return practitioners

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_departments_by_appointment_type(doctype, txt, searchfield, start, page_len, filters):
    """
    This function fetches departments associated with a specific appointment type
    from the Appointment Type Service Item child table.
    
    Args:
        doctype (str): The doctype being searched (Medical Department)
        txt (str): The search text entered by the user
        searchfield (str): The field being searched
        start (int): The starting index for pagination
        page_len (int): The number of results per page
        filters (dict): The filters applied to the search
            - appointment_type: The selected appointment type
    
    Returns:
        list: List of departments that match the criteria
    """
    appointment_type = filters.get('appointment_type')
    
    if not appointment_type:
        return []
    
    # Get all departments linked to this appointment type through the child table
    # Using the correct field 'department' which exists in Medical Department
    departments = frappe.db.sql("""
        SELECT md.name, md.department
        FROM `tabMedical Department` md
        INNER JOIN `tabAppointment Type Service Item` atsi
        ON atsi.dt = 'Medical Department' AND atsi.dn = md.name
        WHERE atsi.parent = %s
        AND (md.name LIKE %s OR md.department LIKE %s)
        ORDER BY md.department
        LIMIT %s, %s
    """, (
        appointment_type,
        "%%%s%%" % txt,
        "%%%s%%" % txt,
        cint(start),
        cint(page_len)
    ), as_list=1)
    
    return departments