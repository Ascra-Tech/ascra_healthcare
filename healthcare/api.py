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

@frappe.whitelist()
def get_consumer_requests_for_billing(inpatient_record):
    """
    Fetch unbilled consumer requests with all necessary details for billing
    
    Args:
        inpatient_record (str): The Inpatient Record name
        
    Returns:
        list: List of consumer requests with billing details
    """
    if not inpatient_record:
        frappe.throw(_("Inpatient Record is required"))
    
    # Get consumer requests linked to the inpatient record
    consumer_requests = frappe.get_all(
        "Consumer Request",
        filters={
            "inpatient_record": inpatient_record,
            "docstatus": 1,  # Submitted
            "billing_status": ["in", ["Pending", "Partly Invoiced"]]  # Include both status types
        },
        fields=[
            "name", "transaction_date", "consumer_request_type", 
            "customer", "schedule_date", "company", "billing_status"
        ]
    )
    
    # For each consumer request, get its items
    for cr in consumer_requests:
        cr["items"] = []
        
        # Get items directly using the correct field names from the Consumer Request Item doctype
        items = frappe.get_all(
            "Consumer Request Item",
            filters={"parent": cr.name},
            fields=[
                "name", "idx", "item_code", "item_name", "qty", 
                "uom", "stock_uom", "conversion_factor", "invoiced"
            ]
        )
        
        # Get rates from Item Price table if not directly in the items
        for item in items:
            # Get rate from Item Price
            rate = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": item.item_code,
                    "price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
                },
                "price_list_rate"
            ) or 0
            
            item["rate"] = rate
            item["quantity"] = item.qty  # Add quantity field for consistency
            item["amount"] = item.qty * rate
            
            # Only add items that are not yet invoiced
            if not item.get("invoiced"):
                cr["items"].append(item)
        
    # Only include consumer requests that have unbilled items
    result = [cr for cr in consumer_requests if cr.get("items")]
    
    return result

@frappe.whitelist()
def create_sales_invoice_from_consumer_requests(inpatient_record, consumer_requests):
    """
    Create a Sales Invoice from selected Consumer Requests and update the Inpatient Record's billables
    
    Args:
        inpatient_record (str): The Inpatient Record name
        consumer_requests (list or str): List of consumer request objects or JSON string
        
    Returns:
        dict: Created Sales Invoice details
    """
    if isinstance(consumer_requests, str):
        import json
        consumer_requests = json.loads(consumer_requests)
    
    if not consumer_requests:
        frappe.throw(_("No Consumer Requests selected for billing"))
    
    # Get the Inpatient Record
    inpatient_record_doc = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Process selected consumer requests
    created_invoices = []
    
    # Group by customer if multiple
    customer_groups = {}
    
    for cr_data in consumer_requests:
        # If consumer request has no selected items, skip it
        if not cr_data.get("selected_items"):
            continue
            
        cr_name = cr_data.get("name")
        selected_items = cr_data.get("selected_items")
        
        # Get full consumer request details
        cr = frappe.get_doc("Consumer Request", cr_name)
        
        # Get customer
        customer = cr.customer
        
        if not customer:
            customer = frappe.get_value("Patient", inpatient_record_doc.patient, "customer")
            if not customer:
                frappe.throw(_("No customer linked to patient {0}. Please link a customer to the patient first.").format(
                    inpatient_record_doc.patient_name or inpatient_record_doc.patient
                ))
        
        # Initialize customer group if not exists
        if customer not in customer_groups:
            customer_groups[customer] = {
                "customer": customer,
                "company": cr.company,
                "items": []
            }
        
        # Add selected items to the customer group
        for item_idx in selected_items:
            # Get item from consumer request
            item = None
            for i in cr.get("items"):
                if i.idx == int(item_idx):
                    item = i
                    break
            
            if not item:
                continue
                
            # Add to customer group items
            customer_groups[customer]["items"].append({
                "consumer_request": cr_name,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,  # Use qty field instead of quantity
                "rate": item.rate if hasattr(item, "rate") else 0,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "amount": (item.qty or 0) * (item.rate or 0),
                "idx": item.idx
            })
    
    # Create invoices for each customer group
    for customer, data in customer_groups.items():
        if not data["items"]:
            continue
            
        # Create sales invoice
        si = frappe.new_doc("Sales Invoice")
        si.customer = customer
        si.patient = inpatient_record_doc.patient
        si.company = data["company"]
        si.inpatient_record = inpatient_record
        
        # Add items
        for item in data["items"]:
            si.append("items", {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "qty": item["qty"],
                "rate": item["rate"],
                "uom": item["uom"],
                "stock_uom": item["stock_uom"],
                "conversion_factor": item["conversion_factor"],
                "consumer_request": item["consumer_request"],
                "reference_dt": "Consumer Request",
                "reference_dn": item["consumer_request"]
            })
            
            # Also update the Inpatient Record's billables table
            # Check if the item already exists in the billables table
            existing_item = None
            for billable in inpatient_record_doc.get("items", []):
                if billable.item_code == item["item_code"]:
                    existing_item = billable
                    break
            
            # Get UOM and stock UOM information from item data
            uom = item["uom"] or "Nos"
            stock_uom = item["stock_uom"] or "Nos"
            
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
                    "conversion_factor": item["conversion_factor"],
                    "rate": item["rate"],
                    "amount": item["rate"] * item["qty"]
                })
        
        si.set_missing_values()
        si.insert(ignore_permissions=False)
        
        # Save the inpatient record to update the billables table
        inpatient_record_doc.save(ignore_permissions=False)
        
        # Update each consumer request item as invoiced
        for item in data["items"]:
            frappe.db.set_value(
                "Consumer Request Item",
                {"parent": item["consumer_request"], "idx": item["idx"]},
                "invoiced",
                1
            )
            
            # Update the consumer request's billing status
            # Count total items and invoiced items for this consumer request
            cr_name = item["consumer_request"]
            total_items = frappe.db.count("Consumer Request Item", {"parent": cr_name})
            invoiced_items = frappe.db.count("Consumer Request Item", {"parent": cr_name, "invoiced": 1})
            
            if total_items == invoiced_items:
                # All items invoiced
                frappe.db.set_value("Consumer Request", cr_name, "billing_status", "Invoiced")
            elif invoiced_items > 0:
                # Some items invoiced
                frappe.db.set_value("Consumer Request", cr_name, "billing_status", "Partly Invoiced")
        
        created_invoices.append({
            "name": si.name,
            "customer": si.customer,
            "grand_total": si.grand_total
        })
    
    return {
        "invoices": created_invoices,
        "count": len(created_invoices)
    }

@frappe.whitelist()
def create_sales_invoice_from_consumer_requests(inpatient_record, consumer_requests):
    """
    Create a Sales Invoice from selected Consumer Requests and update the Inpatient Record's billables
    
    Args:
        inpatient_record (str): The Inpatient Record name
        consumer_requests (list or str): List of consumer request objects or JSON string
        
    Returns:
        dict: Created Sales Invoice details
    """
    if isinstance(consumer_requests, str):
        import json
        consumer_requests = json.loads(consumer_requests)
    
    if not consumer_requests:
        frappe.throw(_("No Consumer Requests selected for billing"))
    
    # Get the Inpatient Record
    inpatient_record_doc = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Process selected consumer requests
    created_invoices = []
    
    # Group by customer if multiple
    customer_groups = {}
    
    # Track all billable items to be added/updated in Inpatient Record
    billable_items = []
    
    for cr_data in consumer_requests:
        # If consumer request has no selected items, skip it
        if not cr_data.get("selected_items"):
            continue
            
        cr_name = cr_data.get("name")
        selected_items = cr_data.get("selected_items")
        
        # Get full consumer request details
        cr = frappe.get_doc("Consumer Request", cr_name)
        
        # Get customer
        customer = cr.customer
        
        if not customer:
            customer = frappe.get_value("Patient", inpatient_record_doc.patient, "customer")
            if not customer:
                frappe.throw(_("No customer linked to patient {0}. Please link a customer to the patient first.").format(
                    inpatient_record_doc.patient_name or inpatient_record_doc.patient
                ))
        
        # Initialize customer group if not exists
        if customer not in customer_groups:
            customer_groups[customer] = {
                "customer": customer,
                "company": cr.company,
                "items": []
            }
        
        # Instead of cr.get("items"), fetch items directly from the database
        cr_items = frappe.get_all(
            "Consumer Request Item",
            filters={"parent": cr_name},
            fields=["idx", "item_code", "item_name", "qty", "uom", "stock_uom", "conversion_factor"]
        )
        
        # Add selected items to the customer group
        for item_idx_str in selected_items:
            item_idx = int(item_idx_str)
            
            # Find item with matching idx
            item = None
            for i in cr_items:
                if i.idx == item_idx:
                    item = i
                    break
            
            if not item:
                continue
            
            # Get rate from Item Price
            rate = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": item.item_code,
                    "price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
                },
                "price_list_rate"
            ) or 0
                
            # Add to customer group items
            customer_groups[customer]["items"].append({
                "consumer_request": cr_name,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "rate": rate,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "amount": (item.qty or 0) * rate,
                "idx": item.idx
            })
            
            # Track this item for the billables table
            billable_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "quantity": item.qty,
                "uom": item.uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": item.conversion_factor or 1.0,
                "rate": rate,
                "amount": (item.qty or 0) * rate
            })
    
    # Create invoices for each customer group
    for customer, data in customer_groups.items():
        if not data["items"]:
            continue
            
        # Create sales invoice
        si = frappe.new_doc("Sales Invoice")
        si.customer = customer
        si.patient = inpatient_record_doc.patient
        si.company = data["company"]
        si.inpatient_record = inpatient_record
        
        # Add items
        for item in data["items"]:
            si.append("items", {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "qty": item["qty"],
                "rate": item["rate"],
                "uom": item["uom"],
                "stock_uom": item["stock_uom"],
                "conversion_factor": item["conversion_factor"],
                "consumer_request": item["consumer_request"],
                "reference_dt": "Consumer Request",
                "reference_dn": item["consumer_request"]
            })
        
        si.set_missing_values()
        si.insert(ignore_permissions=False)
        
        # Update each consumer request item as invoiced
        for item in data["items"]:
            frappe.db.set_value(
                "Consumer Request Item",
                {"parent": item["consumer_request"], "idx": item["idx"]},
                "invoiced",
                1
            )
            
            # Update the consumer request's billing status
            # Count total items and invoiced items for this consumer request
            cr_name = item["consumer_request"]
            total_items = frappe.db.count("Consumer Request Item", {"parent": cr_name})
            invoiced_items = frappe.db.count("Consumer Request Item", {"parent": cr_name, "invoiced": 1})
            
            if total_items == invoiced_items:
                # All items invoiced
                frappe.db.set_value("Consumer Request", cr_name, "billing_status", "Invoiced")
            elif invoiced_items > 0:
                # Some items invoiced
                frappe.db.set_value("Consumer Request", cr_name, "billing_status", "Partly Invoiced")
        
        created_invoices.append({
            "name": si.name,
            "customer": si.customer,
            "grand_total": si.grand_total
        })
    
    # Now update the Inpatient Record billables table with all the items
    update_inpatient_billables(inpatient_record_doc, billable_items)
    
    return {
        "invoices": created_invoices,
        "count": len(created_invoices)
    }

def update_inpatient_billables(inpatient_record_doc, billable_items):
    """
    Update the billables table in the Inpatient Record with new items
    
    Args:
        inpatient_record_doc: The Inpatient Record document
        billable_items: List of items to add/update in the billables table
    """
    # Get existing billables as a dictionary for easy lookup
    existing_billables = {}
    for item in inpatient_record_doc.get("items", []):
        existing_billables[item.item_code] = item
    
    # Process each billable item
    for billable in billable_items:
        item_code = billable["item_code"]
        
        if item_code in existing_billables:
            # Update existing item
            existing_item = existing_billables[item_code]
            existing_item.quantity += billable["quantity"]
            existing_item.amount = existing_item.rate * existing_item.quantity
        else:
            # Add new item to the billables table
            inpatient_record_doc.append("items", {
                "item_code": billable["item_code"],
                "item_name": billable["item_name"],
                "quantity": billable["quantity"],
                "uom": billable["uom"],
                "stock_uom": billable["stock_uom"],
                "conversion_factor": billable["conversion_factor"],
                "rate": billable["rate"],
                "amount": billable["amount"]
            })
    
    # Save the inpatient record to update the billables table
    inpatient_record_doc.save(ignore_permissions=False)
    
    # Recalculate the totals
    update_inpatient_record_totals(inpatient_record_doc)

def update_inpatient_record_totals(inpatient_record_doc):
    """
    Update the total amount in the Inpatient Record
    
    Args:
        inpatient_record_doc: The Inpatient Record document
    """
    total_amount = 0
    
    # Calculate total from billables
    for item in inpatient_record_doc.get("items", []):
        total_amount += item.amount or 0
    
    # Update the total field
    inpatient_record_doc.total = total_amount
    inpatient_record_doc.save(ignore_permissions=False)