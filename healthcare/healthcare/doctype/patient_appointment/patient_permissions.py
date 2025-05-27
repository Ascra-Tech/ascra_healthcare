import frappe
from frappe import _

def get_patient_appointment_permission_query(user):
    """Return query conditions for Patient Appointment based on user role"""
    if not user:
        user = frappe.session.user
    
    # Get user's roles and role profile
    roles = frappe.get_roles(user)
    role_profile = frappe.db.get_value("User", user, "role_profile_name")
    
    # If Administrator or system roles, show all appointments
    if user == "Administrator" or "System Manager" in roles or "Healthcare Administrator" in roles:
        return ""
        
    # Check for Patient role or Patient role profile
    if "Patient" in roles or role_profile == "Patient":
        patient = frappe.db.get_value("Patient", {"user_id": user}, "name")
        if patient:
            return f"`tabPatient Appointment`.patient = '{patient}'"
        else:
            # If Patient role/profile but no linked patient, show nothing for this condition
            pass
    
    # Check for Healthcare Practitioner related roles or Doctor role profile
    practitioner_roles = ["Physician", "Healthcare Practitioner", "Practitioner"]
    if any(role in roles for role in practitioner_roles) or role_profile == "Doctor":
        # Find the Healthcare Practitioner linked to this user
        practitioner = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
        if practitioner:
            return f"`tabPatient Appointment`.practitioner = '{practitioner}'"
        else:
            # Log for debugging
            frappe.logger().info(f"User {user} has practitioner role but no linked Healthcare Practitioner record")
            # If no linked practitioner found
            return "1=0"
    
    # If no specific role matches but user has other healthcare roles, show all
    healthcare_roles = ["Nursing User", "Laboratory User"]
    if any(role in roles for role in healthcare_roles):
        return ""
            
    # Default - show only records created by the user
    return f"`tabPatient Appointment`.owner = '{user}'"

def has_patient_permission(doc, user):
    """Check if user has permission to access this Patient Appointment"""
    if not user:
        user = frappe.session.user
        
    # Get user's roles and role profile
    roles = frappe.get_roles(user)
    role_profile = frappe.db.get_value("User", user, "role_profile_name")
    
    # If Administrator or system roles, allow access to all
    if user == "Administrator" or "System Manager" in roles or "Healthcare Administrator" in roles:
        return True
        
    # Check for Patient role or Patient role profile
    if "Patient" in roles or role_profile == "Patient":
        patient = frappe.db.get_value("Patient", {"user_id": user}, "name")
        if patient and doc.patient == patient:
            return True
    
    # Check for Healthcare Practitioner related roles or Doctor role profile
    practitioner_roles = ["Physician", "Healthcare Practitioner", "Practitioner"]
    if any(role in roles for role in practitioner_roles) or role_profile == "Doctor":
        practitioner = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
        if practitioner and doc.practitioner == practitioner:
            return True
    
    # If user has other healthcare roles, allow access
    healthcare_roles = ["Nursing User", "Laboratory User"]
    if any(role in roles for role in healthcare_roles):
        return True
            
    # Default - allow access to records created by the user
    return doc.owner == user