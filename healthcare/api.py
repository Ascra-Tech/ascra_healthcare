import frappe
from frappe import _

@frappe.whitelist()
def get_service_requests_for_billing(inpatient_record):
    """
    Fetch unbilled service requests with all necessary details for billing
    
    Args:
        inpatient_record (str): The Inpatient Record name
        
    Returns:
        list: List of service requests with billing details
    """
    if not inpatient_record:
        frappe.throw(_("Inpatient Record is required"))
    
    # Get service requests linked to the inpatient record
    service_requests = frappe.get_all(
        "Service Request",
        filters={
            "inpatient_record": inpatient_record,
            "docstatus": 1,  # Submitted
            "billing_status": ["!=", "Invoiced"]  # Not fully invoiced
        },
        fields=[
            "name", "template_dn", "order_date", "status", 
            "patient", "patient_name", "qty_invoiced", "quantity",
            "billing_status", "template_dt", "item_code", "company"
        ]
    )
    
    for sr in service_requests:
        # Get template details if available
        if sr.get("template_dt") and sr.get("template_dn"):
            try:
                template = frappe.get_doc(sr.template_dt, sr.template_dn)
                
                # Add template details
                sr["item_code"] = template.item if hasattr(template, "item") else sr.get("item_code")
                sr["item_name"] = template.template if hasattr(template, "template") else sr.get("template_dn")
                sr["description"] = template.description if hasattr(template, "description") else ""
                sr["rate"] = template.rate if hasattr(template, "rate") else 0
                sr["is_billable"] = template.is_billable if hasattr(template, "is_billable") else 0
                sr["hsn_sac"] = template.gst_hsn_code if hasattr(template, "gst_hsn_code") else ""
            except Exception as e:
                frappe.log_error(f"Error fetching template details for {sr.get('name')}: {str(e)}")
    
    return service_requests

@frappe.whitelist()
def create_sales_invoice_from_service_requests(inpatient_record, service_requests):
    """
    Create a Sales Invoice from selected Service Requests and update the Inpatient Record's billables
    
    Args:
        inpatient_record (str): The Inpatient Record name
        service_requests (list or str): List of service request names or JSON string
        
    Returns:
        dict: Created Sales Invoice details
    """
    if isinstance(service_requests, str):
        import json
        service_requests = json.loads(service_requests)
    
    if not service_requests:
        frappe.throw(_("No Service Requests selected for billing"))
    
    # Get the Inpatient Record
    inpatient_record_doc = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Group service requests by patient
    patient_groups = {}
    
    for sr_name in service_requests:
        # Get full service request details
        sr = frappe.get_doc("Service Request", sr_name)
        
        if not sr.patient:
            frappe.throw(_("Patient not found for Service Request {0}").format(sr.name))
        
        if sr.patient not in patient_groups:
            patient_groups[sr.patient] = {
                "patient": sr.patient,
                "patient_name": sr.patient_name,
                "company": sr.company,
                "items": []
            }
        
        # Get template details for billing
        template = None
        if sr.template_dt and sr.template_dn:
            try:
                template = frappe.get_doc(sr.template_dt, sr.template_dn)
            except Exception:
                frappe.log_error(f"Error fetching template {sr.template_dt} {sr.template_dn}")
        
        # Use template details or fallback to service request
        item_code = template.item if template and hasattr(template, "item") else sr.item_code
        item_name = template.template if template and hasattr(template, "template") else sr.template_dn
        description = template.description if template and hasattr(template, "description") else sr.template_dn
        rate = template.rate if template and hasattr(template, "rate") else 0
        hsn_sac = template.gst_hsn_code if template and hasattr(template, "gst_hsn_code") else ""
        
        # Skip if not billable
        if template and hasattr(template, "is_billable") and not template.is_billable:
            continue
            
        # Add to items list
        patient_groups[sr.patient]["items"].append({
            "service_request": sr.name,
            "item_code": item_code,
            "item_name": item_name,
            "description": description,
            "qty": sr.quantity - sr.qty_invoiced,
            "rate": rate,
            "hsn_sac": hsn_sac,
            "template_dt": sr.template_dt,
            "template_dn": sr.template_dn
        })
    
    # Process for each patient (typically just one)
    created_invoices = []
    
    for patient_key, patient_data in patient_groups.items():
        if not patient_data["items"]:
            continue
            
        # Get linked customer
        customer = frappe.get_value("Patient", patient_data["patient"], "customer")
        
        if not customer:
            frappe.throw(_("No customer linked to patient {0}. Please link a customer to the patient first.").format(
                patient_data["patient_name"] or patient_data["patient"]
            ))
        
        # Create sales invoice
        si = frappe.new_doc("Sales Invoice")
        si.customer = customer
        si.patient = patient_data["patient"]
        si.company = patient_data["company"]
        si.inpatient_record = inpatient_record
        
        # Add items
        for item in patient_data["items"]:
            si.append("items", {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "description": item["description"],
                "qty": item["qty"],
                "rate": item["rate"],
                "service_request": item["service_request"],
                "gst_hsn_code": item["hsn_sac"],
                "reference_dt": "Service Request",
                "reference_dn": item["service_request"]
            })
            
            # Also update the Inpatient Record's billables table
            # Check if the item already exists in the billables table
            existing_item = None
            for billable in inpatient_record_doc.items:
                if billable.item_code == item["item_code"]:
                    existing_item = billable
                    break
            
            # Get UOM and stock UOM information
            uom = stock_uom = "Nos"  # Default UOM
            try:
                item_doc = frappe.get_doc("Item", item["item_code"])
                stock_uom = item_doc.stock_uom
                uom = stock_uom
            except Exception:
                pass
            
            if existing_item:
                # Update existing item
                existing_item.quantity += item["qty"]
                existing_item.amount = existing_item.rate * existing_item.quantity
            else:
                # Add new item to the billables table
                inpatient_record_doc.append("items", {
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "quantity": item["qty"],
                    "uom": uom,
                    "stock_uom": stock_uom,
                    "conversion_factor": 1.0,
                    "rate": item["rate"],
                    "amount": item["rate"] * item["qty"]
                })
        
        si.set_missing_values()
        si.insert(ignore_permissions=False)
        
        # Save the inpatient record to update the billables table
        inpatient_record_doc.save(ignore_permissions=False)
        
        created_invoices.append({
            "name": si.name,
            "patient": si.patient,
            "grand_total": si.grand_total
        })
    
    return {
        "invoices": created_invoices,
        "count": len(created_invoices)
    }