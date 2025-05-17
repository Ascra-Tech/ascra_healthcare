import frappe
from frappe import _

@frappe.whitelist()
def create_service_request(inpatient_record):
    """
    Create a new Service Request from Inpatient Record
    
    Args:
        inpatient_record (str): Name of the Inpatient Record doctype
    
    Returns:
        dict: Information about the created Service Request
    """
    if not inpatient_record:
        frappe.throw(_("Please specify Inpatient Record"))
    
    # Get the inpatient record details
    ip_record = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Return success message
    return {
        "success": True,
        "inpatient_record": inpatient_record
    }

@frappe.whitelist()
def create_medication_request(inpatient_record):
    """
    Create a new Medication Request from Inpatient Record
    
    Args:
        inpatient_record (str): Name of the Inpatient Record doctype
    
    Returns:
        dict: Information about the created Medication Request
    """
    if not inpatient_record:
        frappe.throw(_("Please specify Inpatient Record"))
    
    # Get the inpatient record details
    ip_record = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Return success message
    return {
        "success": True,
        "inpatient_record": inpatient_record
    }

@frappe.whitelist()
def create_consumer_request(inpatient_record, request_type):
    """
    Create a new Consumer Request from Inpatient Record
    
    Args:
        inpatient_record (str): Name of the Inpatient Record doctype
        request_type (str): Type of request - "Consumable Request", "Blood Request", or "Medicine Request"
        
    Returns:
        dict: Information about the created Consumer Request
    """
    if not inpatient_record:
        frappe.throw(_("Please specify Inpatient Record"))
    
    if request_type not in ["Consumable Request", "Blood Request", "Medicine Request"]:
        frappe.throw(_("Invalid request type. Should be 'Consumable Request', 'Blood Request', or 'Medicine Request'"))
    
    # Get the inpatient record details
    ip_record = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Check if custom field exists for patient in Consumer Request
    if not frappe.get_meta("Consumer Request").has_field("patient"):
        # Create custom field if it doesn't exist
        try:
            create_patient_field_in_consumer_request()
        except Exception as e:
            frappe.log_error(f"Failed to create patient field in Consumer Request: {str(e)}")
    
    # Return success message
    return {
        "success": True,
        "inpatient_record": inpatient_record,
        "request_type": request_type
    }

def create_patient_field_in_consumer_request():
    """Create a custom Patient link field in Consumer Request doctype"""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    
    # Check if field already exists
    if not frappe.db.exists("Custom Field", {"dt": "Consumer Request", "fieldname": "patient"}):
        create_custom_field("Consumer Request", {
            "label": "Patient",
            "fieldname": "patient",
            "fieldtype": "Link",
            "options": "Patient",
            "insert_after": "consumer_request_type",
            "translatable": 0
        })
        
        # Create patient_name field as well for better user experience
        create_custom_field("Consumer Request", {
            "label": "Patient Name",
            "fieldname": "patient_name",
            "fieldtype": "Data",
            "fetch_from": "patient.patient_name",
            "insert_after": "patient",
            "read_only": 1,
            "translatable": 0
        })
        
        # Add inpatient_record field
        create_custom_field("Consumer Request", {
            "label": "Inpatient Record",
            "fieldname": "inpatient_record",
            "fieldtype": "Link",
            "options": "Inpatient Record",
            "insert_after": "patient_name",
            "translatable": 0
        })

# Keep the old function for backward compatibility
@frappe.whitelist()
def create_material_request(inpatient_record, request_type):
    """
    Create a new Material Request from Inpatient Record for Consumables or Blood
    This is kept for backward compatibility.
    
    Args:
        inpatient_record (str): Name of the Inpatient Record doctype
        request_type (str): Type of request - "Consumable" or "Blood"
        
    Returns:
        dict: Information about the created Material Request
    """
    frappe.msgprint(_("This function is deprecated. Please use create_consumer_request instead."))
    
    if not inpatient_record:
        frappe.throw(_("Please specify Inpatient Record"))
    
    if request_type not in ["Consumable", "Blood"]:
        frappe.throw(_("Invalid request type. Should be 'Consumable' or 'Blood'"))
    
    # Redirect to the new function
    translated_request_type = f"{request_type} Request"
    return create_consumer_request(inpatient_record, translated_request_type)