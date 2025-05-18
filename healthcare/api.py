import frappe
from frappe import _
import json
from typing import List, Dict, Union, Optional, Any

@frappe.whitelist()
def get_service_requests_for_billing(inpatient_record: str) -> List[Dict]:
    """
    Fetch unbilled service requests with all necessary details for billing
    
    Args:
        inpatient_record: The Inpatient Record name
        
    Returns:
        List of service requests with billing details
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
        _add_template_details_to_service_request(sr)
    
    return service_requests


def _add_template_details_to_service_request(service_request: Dict) -> None:
    """
    Add template details to a service request if available
    
    Args:
        service_request: The service request dictionary to enhance
    """
    if not service_request.get("template_dt") or not service_request.get("template_dn"):
        return
        
    try:
        template = frappe.get_doc(service_request.template_dt, service_request.template_dn)
        
        # Add template details
        template_fields = {
            "item": "item_code",
            "template": "item_name",
            "description": "description",
            "rate": "rate",
            "is_billable": "is_billable",
            "gst_hsn_code": "hsn_sac"
        }
        
        for template_field, sr_field in template_fields.items():
            if hasattr(template, template_field):
                service_request[sr_field] = getattr(template, template_field)
            elif sr_field not in service_request:
                service_request[sr_field] = "" if sr_field in ["description", "hsn_sac"] else 0
                
    except Exception as e:
        frappe.log_error(
            f"Error fetching template details for {service_request.get('name')}: {str(e)}",
            "Service Request Template Error"
        )


@frappe.whitelist()
def create_sales_invoice_from_service_requests(inpatient_record: str, service_requests: Union[List, str]) -> Dict:
    """
    Create a Sales Invoice from selected Service Requests and update the Inpatient Record's billables
    
    Args:
        inpatient_record: The Inpatient Record name
        service_requests: List of service request names or JSON string
        
    Returns:
        Created Sales Invoice details
    """
    if isinstance(service_requests, str):
        service_requests = json.loads(service_requests)
    
    if not service_requests:
        frappe.throw(_("No Service Requests selected for billing"))
    
    # Get the Inpatient Record
    inpatient_record_doc = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Group service requests by patient
    patient_groups = _group_service_requests_by_patient(service_requests)
    
    # Process for each patient (typically just one)
    created_invoices = []
    
    for patient_key, patient_data in patient_groups.items():
        if not patient_data["items"]:
            continue
            
        # Create sales invoice and update inpatient record
        invoice = _create_invoice_from_service_items(inpatient_record_doc, patient_data)
        
        if invoice:
            created_invoices.append({
                "name": invoice.name,
                "patient": invoice.patient,
                "grand_total": invoice.grand_total
            })
    
    return {
        "invoices": created_invoices,
        "count": len(created_invoices)
    }


def _group_service_requests_by_patient(service_request_names: List[str]) -> Dict[str, Dict]:
    """
    Group service requests by patient and prepare for billing
    
    Args:
        service_request_names: List of service request names
        
    Returns:
        Dictionary of patients with their service items for billing
    """
    patient_groups = {}
    
    for sr_name in service_request_names:
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
        
        # Get template details
        template = None
        if sr.template_dt and sr.template_dn:
            try:
                template = frappe.get_doc(sr.template_dt, sr.template_dn)
            except Exception:
                frappe.log_error(f"Error fetching template {sr.template_dt} {sr.template_dn}")
        
        # Use template details or fallback to service request
        item_code = getattr(template, "item", None) if template else None
        item_code = item_code or sr.item_code
        
        item_name = getattr(template, "template", None) if template else None
        item_name = item_name or sr.template_dn
        
        description = getattr(template, "description", None) if template else None
        description = description or sr.template_dn
        
        rate = getattr(template, "rate", 0) if template else 0
        hsn_sac = getattr(template, "gst_hsn_code", "") if template else ""
        
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
    
    return patient_groups


def _create_invoice_from_service_items(inpatient_record_doc, patient_data: Dict) -> Optional[Any]:
    """
    Create a sales invoice for a patient from service items and update inpatient record
    
    Args:
        inpatient_record_doc: The Inpatient Record document
        patient_data: Dictionary with patient info and service items
        
    Returns:
        Created Sales Invoice document or None if creation failed
    """
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
    si.inpatient_record = inpatient_record_doc.name
    
    # Billable items to add to the inpatient record
    billable_items = []
    
    # Add items
    for item in patient_data["items"]:
        si.append("items", {
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "description": item["description"],
            "qty": item["qty"],
            "rate": item["rate"],
            "gst_hsn_code": item["hsn_sac"],
            "reference_dt": "Service Request",
            "reference_dn": item["service_request"]
        })
        
        # Get UOM information
        uom = stock_uom = "Nos"  # Default UOM
        try:
            item_doc = frappe.get_doc("Item", item["item_code"])
            stock_uom = item_doc.stock_uom
            uom = stock_uom
        except Exception:
            pass
        
        # Add to billable items list for inpatient record
        billable_items.append({
            "item_code": item["item_code"],
            "item_name": item["item_name"],
            "quantity": item["qty"],
            "uom": uom,
            "stock_uom": stock_uom,
            "conversion_factor": 1.0,
            "rate": item["rate"],
            "amount": item["rate"] * item["qty"]
        })
    
    # Update inpatient record billables
    update_inpatient_billables(inpatient_record_doc, billable_items)
    
    si.set_missing_values()
    si.insert(ignore_permissions=False)
    
    return si


@frappe.whitelist()
def get_consumer_requests_for_billing(inpatient_record: str) -> List[Dict]:
    """
    Fetch unbilled consumer requests for an inpatient record
    
    Args:
        inpatient_record: The Inpatient Record name
        
    Returns:
        List of consumer requests with summary information
    """
    if not inpatient_record:
        frappe.throw(_("Inpatient Record is required"))
    
    # Get consumer requests linked to the inpatient record that aren't fully billed
    consumer_requests = frappe.get_all(
        "Consumer Request",
        filters={
            "inpatient_record": inpatient_record,
            "docstatus": 1,  # Submitted
            "billing_status": ["in", ["Pending", "Partly Invoiced"]]
        },
        fields=[
            "name", "transaction_date", "consumer_request_type", 
            "customer", "company", "billing_status", "title"
        ]
    )
    
    # For each request, calculate the total amount
    for cr in consumer_requests:
        # Simply get the items and sum up the amounts
        items = frappe.get_all(
            "Consumer Request Item",
            filters={"parent": cr.name},
            fields=["item_code", "qty"]
        )
        
        total = 0
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
            
            total += item.qty * rate
        
        cr["total_amount"] = total
    
    return consumer_requests


def _calculate_consumer_request_total(consumer_request_name: str) -> float:
    """
    Calculate the total amount for a consumer request
    
    Args:
        consumer_request_name: The Consumer Request name
        
    Returns:
        Total amount for unbilled items
    """
    # Get all unbilled items
    items = frappe.get_all(
        "Consumer Request Item",
        filters={"parent": consumer_request_name, "invoiced": 0},
        fields=["item_code", "qty"]
    )
    
    total = 0
    
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
        
        total += item.qty * rate
    
    return total


@frappe.whitelist()
def create_sales_invoice_from_consumer_requests(inpatient_record: str, consumer_requests: Union[List, str]) -> Dict:
    """
    Create a Sales Invoice from selected Consumer Requests and link them directly
    
    Args:
        inpatient_record: The Inpatient Record name
        consumer_requests: List of consumer request names or JSON string
        
    Returns:
        Created Sales Invoice details
    """
    if isinstance(consumer_requests, str):
        consumer_requests = json.loads(consumer_requests)
    
    if not consumer_requests:
        frappe.throw(_("No Consumer Requests selected for billing"))
    
    # Get the Inpatient Record
    inpatient_record_doc = frappe.get_doc("Inpatient Record", inpatient_record)
    
    # Group requests by customer
    customer_groups = {}
    
    # Keep track of consumer requests and amounts for updating billables
    consumer_request_amounts = {}
    
    for cr_name in consumer_requests:
        # Get consumer request details
        cr = frappe.get_doc("Consumer Request", cr_name)
        
        # Skip if already fully invoiced
        if cr.billing_status == "Invoiced":
            frappe.msgprint(_("Consumer Request {0} is already fully invoiced").format(cr.name))
            continue
            
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
                "company": cr.company,
                "items": [],
                "requests": []  # To track all consumer requests for this customer
            }
        
        # Add to requests list for this customer
        customer_groups[customer]["requests"].append(cr_name)
        
        # Calculate total for this consumer request
        total_amount = 0
        
        # Add items from this consumer request
        for item in cr.get("table_hluy", []):
            # Skip already invoiced items
            if hasattr(item, "invoiced") and item.invoiced == 1:
                continue
                
            # Calculate remaining quantity to be invoiced
            qty_remaining = item.qty - (item.qty_invoiced or 0)
            if qty_remaining <= 0:
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
            
            # Update total amount
            total_amount += qty_remaining * rate
            
            # Add to customer group items
            customer_groups[customer]["items"].append({
                "item_code": item.item_code,
                "item_name": item.item_name or item.item_code,
                "description": item.description or item.item_name or item.item_code,
                "qty": qty_remaining,
                "rate": rate,
                "consumer_request": cr.name,
                "idx": item.idx
            })
        
        # Track amount for billing table
        if total_amount > 0:
            consumer_request_amounts[cr.name] = {
                "amount": total_amount,
                "type": cr.consumer_request_type
            }
    
    # Create invoices for each customer
    created_invoices = []
    
    for customer, data in customer_groups.items():
        if not data["items"]:
            continue
            
        # Create Sales Invoice
        si = frappe.new_doc("Sales Invoice")
        si.customer = customer
        si.patient = inpatient_record_doc.patient
        si.company = data["company"]
        si.inpatient_record = inpatient_record
        
        # Add all consumer requests to the child table
        for request_name in data["requests"]:
            si.append("custom_consumer_requests", {
                "consumer_request": request_name
            })
        
        # Add items to invoice
        for item in data["items"]:
            si.append("items", {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "description": item["description"],
                "qty": item["qty"],
                "rate": item["rate"],
                "reference_dt": "Consumer Request",
                "reference_dn": item["consumer_request"]
            })
        
        # Insert the invoice
        si.set_missing_values()
        si.insert(ignore_permissions=True)
        
        # Add to inpatient record billables immediately
        for cr_name, cr_data in consumer_request_amounts.items():
            # First check if an entry already exists for this consumer request
            exists = False
            for bill in inpatient_record_doc.get("billables_consumable_requests", []):
                if bill.consumer_requests == cr_name and bill.sales_invoice == si.name:
                    exists = True
                    break
            
            if not exists:
                # Add to billables_consumable_requests table
                inpatient_record_doc.append("billables_consumable_requests", {
                    "sales_invoice": si.name,
                    "grand_total": cr_data["amount"],
                    "consumer_requests": cr_name,
                    "request_type": cr_data["type"]
                })
        
        # Save inpatient record to update billables
        try:
            inpatient_record_doc.save(ignore_permissions=True)
            
            # Update totals
            total_consumable = sum(row.grand_total or 0 for row in inpatient_record_doc.get("billables_consumable_requests", []))
            inpatient_record_doc.total_consumable_amount = total_consumable
            inpatient_record_doc.save(ignore_permissions=True)
            
            frappe.db.commit()  # Commit the transaction to make sure changes are saved
            
        except Exception as e:
            frappe.log_error(f"Error updating Inpatient Record billables: {str(e)}", "Consumer Billables Error")
            
            # If normal saving failed, try direct SQL
            for cr_name, cr_data in consumer_request_amounts.items():
                add_to_inpatient_record(inpatient_record, si.name, cr_name, cr_data["type"], cr_data["amount"])
        
        # Add to created invoices - note that we no longer include custom_consumer_request in the response
        created_invoices.append({
            "name": si.name,
            "customer": customer,
            "grand_total": si.grand_total,
            "consumer_requests": [cr for cr in data["requests"]]  # Include all linked consumer requests in the response
        })
    
    return {
        "invoices": created_invoices,
        "count": len(created_invoices)
    }

def add_to_inpatient_record(inpatient_record, invoice_name, consumer_request, request_type, amount):
    """
    Add entry to inpatient record's billables_consumable_requests table using SQL
    """
    try:
        # Check if already exists
        existing = frappe.db.exists(
            "Inpatient Consumable Requests",
            {
                "parent": inpatient_record,
                "sales_invoice": invoice_name,
                "consumer_requests": consumer_request
            }
        )
        
        if existing:
            frappe.log_error(f"Entry already exists for {consumer_request} in {inpatient_record}", "Inpatient Update")
            return
        
        # Create new entry
        child_name = frappe.generate_hash("Inpatient Consumable Requests", 10)
        
        # Insert directly with SQL
        frappe.db.sql("""
            INSERT INTO `tabInpatient Consumable Requests` 
            (name, creation, modified, modified_by, owner, docstatus, 
            parent, parentfield, parenttype, idx, 
            sales_invoice, grand_total, consumer_requests, request_type)
            VALUES (%s, NOW(), NOW(), %s, %s, 0, 
            %s, 'billables_consumable_requests', 'Inpatient Record', 
            (SELECT IFNULL(MAX(idx), 0) + 1 FROM `tabInpatient Consumable Requests` 
                WHERE parent=%s AND parentfield='billables_consumable_requests'),
            %s, %s, %s, %s)
        """, (
            child_name, frappe.session.user, frappe.session.user,
            inpatient_record, inpatient_record,
            invoice_name, amount, consumer_request, request_type
        ))
        
        # Update the total consumable amount in the parent
        update_inpatient_total(inpatient_record)
        
        frappe.db.commit()  # Commit transaction to ensure changes are saved
        
        frappe.log_error(f"Successfully added {consumer_request} to {inpatient_record}", "Inpatient Update Success")
        
    except Exception as e:
        frappe.log_error(f"Error adding to inpatient record: {str(e)}", "Inpatient Update Error")

def update_inpatient_total(inpatient_record):
    """Update the total_consumable_amount in Inpatient Record"""
    try:
        # Calculate new total
        total = frappe.db.sql("""
            SELECT IFNULL(SUM(grand_total), 0)
            FROM `tabInpatient Consumable Requests`
            WHERE parent = %s AND parentfield = 'billables_consumable_requests'
        """, (inpatient_record,))[0][0]
        
        # Update the parent record
        frappe.db.set_value("Inpatient Record", inpatient_record, "total_consumable_amount", total)
        
    except Exception as e:
        frappe.log_error(f"Error updating inpatient total: {str(e)}", "Inpatient Total Update Error")

def update_consumer_request_billing_status(consumer_request_name):
    """Update the billing status of a Consumer Request based on its items"""
    cr = frappe.get_doc("Consumer Request", consumer_request_name)
    
    # Count total items and invoiced items
    total_qty = total_invoiced_qty = 0
    
    for item in cr.get("table_hluy", []):
        total_qty += item.qty or 0
        total_invoiced_qty += item.qty_invoiced or 0
    
    # Update the qty_invoiced field on the parent document
    cr.qty_invoiced = total_invoiced_qty
    
    # Calculate percent invoiced (using per_received for now)
    if hasattr(cr, "per_received"):
        cr.per_received = (total_invoiced_qty / total_qty * 100) if total_qty > 0 else 0
    
    # Set billing status
    if total_invoiced_qty >= total_qty:
        cr.billing_status = "Invoiced"
    elif total_invoiced_qty > 0:
        cr.billing_status = "Partly Invoiced"
    else:
        cr.billing_status = "Pending"
    
    # Save the changes
    cr.db_update()

def update_inpatient_record_with_consumer_billables(inpatient_record_name, sales_invoice, cr_data):
    """
    Update the Inpatient Record's billables_consumable_requests table using direct SQL
    
    Args:
        inpatient_record_name: Name of the Inpatient Record
        sales_invoice: Sales Invoice document
        cr_data: Dictionary of Consumer Request data
    """
    try:
        # Log for debugging
        frappe.log_error(
            f"Updating Inpatient Record {inpatient_record_name} for Sales Invoice {sales_invoice.name}",
            "Consumer Billables Update"
        )
        
        # For each consumer request, create a child table entry directly
        for cr_name, data in cr_data.items():
            # Generate a new name for the child record
            child_name = frappe.generate_hash("Inpatient Consumable Requests", 10)
            
            # Get consumer request type
            cr_type = frappe.db.get_value("Consumer Request", cr_name, "consumer_request_type") or "Consumer Request"
            
            # Insert directly into the child table
            frappe.db.sql("""
                INSERT INTO `tabInpatient Consumable Requests` 
                (name, creation, modified, modified_by, owner, docstatus, 
                parent, parentfield, parenttype, idx, 
                sales_invoice, grand_total, consumer_requests, request_type)
                VALUES (%s, NOW(), NOW(), %s, %s, 0, 
                %s, 'billables_consumable_requests', 'Inpatient Record', 
                (SELECT IFNULL(MAX(idx), 0) + 1 FROM `tabInpatient Consumable Requests` 
                    WHERE parent=%s AND parentfield='billables_consumable_requests'),
                %s, %s, %s, %s)
            """, (
                child_name, frappe.session.user, frappe.session.user,
                inpatient_record_name, inpatient_record_name,
                sales_invoice.name, data.get("amount", 0), cr_name, cr_type
            ))
        
        # Update the total consumable amount in the Inpatient Record
        # First, calculate the new total
        total_consumable = frappe.db.sql("""
            SELECT IFNULL(SUM(grand_total), 0) 
            FROM `tabInpatient Consumable Requests` 
            WHERE parent=%s AND parentfield='billables_consumable_requests'
        """, (inpatient_record_name,))[0][0]
        
        # Update the parent record
        frappe.db.set_value("Inpatient Record", inpatient_record_name, 
                          "total_consumable_amount", total_consumable)
        
        # Force a cache clear
        frappe.clear_cache(doctype="Inpatient Record")
        
        # Log success
        frappe.log_error(f"Successfully updated Inpatient Record {inpatient_record_name} with {len(cr_data)} billables via SQL",
                        "Consumer Billables Success")
        
    except Exception as e:
        frappe.log_error(f"Failed to update Inpatient Record {inpatient_record_name} via SQL: {str(e)}", 
                         title="Inpatient Record SQL Update Error")

def sales_invoice_on_submit(doc, method):
    """
    Update Consumer Request Items when Sales Invoice is submitted
    """
    try:
        # Check for references to Consumer Requests
        consumer_requests = set()
        for item in doc.items:
            if item.reference_dt == "Consumer Request" and item.reference_dn:
                consumer_requests.add(item.reference_dn)
        
        if not consumer_requests:
            return
            
        # Process each consumer request
        for cr_name in consumer_requests:
            cr = frappe.get_doc("Consumer Request", cr_name)
            
            # Update Consumer Request status
            cr.billing_status = "Invoiced"
            cr.db_update()
            
            # Update all items
            for item in cr.get("table_hluy", []):
                frappe.db.set_value(
                    "Consumer Request Item",
                    {"parent": cr_name, "idx": item.idx},
                    {
                        "qty_invoiced": item.qty,
                        "invoiced": 1
                    }
                )
            
    except Exception as e:
        frappe.log_error(f"Error in sales_invoice_on_submit: {str(e)}", "Sales Invoice Submit Error")

def add_to_inpatient_record(inpatient_record, invoice_name, consumer_request, request_type, amount):
    """
    Add entry to inpatient record's billables_consumable_requests table using SQL
    """
    try:
        # Check if already exists
        existing = frappe.db.exists(
            "Inpatient Consumable Requests",
            {
                "parent": inpatient_record,
                "sales_invoice": invoice_name,
                "consumer_requests": consumer_request
            }
        )
        
        if existing:
            frappe.log_error(f"Entry already exists for {consumer_request} in {inpatient_record}", "Inpatient Update")
            return
        
        # Create new entry
        child_name = frappe.generate_hash("Inpatient Consumable Requests", 10)
        
        # Insert directly with SQL
        frappe.db.sql("""
            INSERT INTO `tabInpatient Consumable Requests` 
            (name, creation, modified, modified_by, owner, docstatus, 
            parent, parentfield, parenttype, idx, 
            sales_invoice, grand_total, consumer_requests, request_type)
            VALUES (%s, NOW(), NOW(), %s, %s, 0, 
            %s, 'billables_consumable_requests', 'Inpatient Record', 
            (SELECT IFNULL(MAX(idx), 0) + 1 FROM `tabInpatient Consumable Requests` 
                WHERE parent=%s AND parentfield='billables_consumable_requests'),
            %s, %s, %s, %s)
        """, (
            child_name, frappe.session.user, frappe.session.user,
            inpatient_record, inpatient_record,
            invoice_name, amount, consumer_request, request_type
        ))
        
        # Update the total consumable amount in the parent
        update_inpatient_total(inpatient_record)
        
        frappe.log_error(f"Successfully added {consumer_request} to {inpatient_record}", "Inpatient Update Success")
        
    except Exception as e:
        frappe.log_error(f"Error adding to inpatient record: {str(e)}", "Inpatient Update Error")

def update_inpatient_total(inpatient_record):
    """Update the total_consumable_amount in Inpatient Record"""
    try:
        # Calculate new total
        total = frappe.db.sql("""
            SELECT IFNULL(SUM(grand_total), 0)
            FROM `tabInpatient Consumable Requests`
            WHERE parent = %s AND parentfield = 'billables_consumable_requests'
        """, (inpatient_record,))[0][0]
        
        # Update the parent record
        frappe.db.set_value("Inpatient Record", inpatient_record, "total_consumable_amount", total)
        
    except Exception as e:
        frappe.log_error(f"Error updating inpatient total: {str(e)}", "Inpatient Total Update Error")

def _group_consumer_requests_by_customer_non_itemized(consumer_request_names: List[str], inpatient_record_doc) -> Dict[str, Dict]:
    """
    Group consumer requests by customer for non-itemized billing
    
    Args:
        consumer_request_names: List of consumer request names
        inpatient_record_doc: The Inpatient Record document
        
    Returns:
        Dictionary of customers with their consumer requests for billing
    """
    customer_groups = {}
    
    for cr_name in consumer_request_names:
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
                "requests": []
            }
        
        # Calculate total amount for unbilled items
        total_amount = _calculate_consumer_request_total(cr_name)
        
        # Create an appropriate item code and name based on the request type
        request_type_key = cr.consumer_request_type.lower().replace(' ', '_')
        item_code = frappe.db.get_single_value("Healthcare Settings", f"{request_type_key}_item") or "Healthcare-MISC-BILL"
        item_name = cr.title or f"{cr.consumer_request_type} for {cr.name}"
        description = f"{cr.consumer_request_type} for {cr.name}"
        
        # Add to customer group
        customer_groups[customer]["requests"].append({
            "name": cr.name,
            "consumer_request_type": cr.consumer_request_type,
            "item_code": item_code,
            "item_name": item_name, 
            "description": description,
            "total_amount": total_amount
        })
    
    return customer_groups


def _update_consumer_request_status_non_itemized(consumer_request_name: str) -> None:
    """
    Update consumer request billing status to 'Invoiced'
    
    Args:
        consumer_request_name: The Consumer Request name
    """
    # Update the billing status to 'Invoiced'
    frappe.db.set_value("Consumer Request", consumer_request_name, "billing_status", "Invoiced")


def _group_consumer_requests_by_customer(consumer_requests: List[Dict], inpatient_record_doc) -> Dict[str, Dict]:
    """
    Group consumer requests by customer and prepare items for billing
    
    Args:
        consumer_requests: List of consumer request objects with selected items
        inpatient_record_doc: The Inpatient Record document
        
    Returns:
        Dictionary of customers with their consumer items for billing
    """
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
            item = next((i for i in cr_items if i.idx == item_idx), None)
            
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
    
    return customer_groups


def _update_consumer_request_statuses(items: List[Dict]) -> None:
    """
    Update consumer request items as invoiced and update billing statuses
    
    Args:
        items: List of consumer request items that were invoiced
    """
    # Group items by consumer request
    consumer_requests = {}
    
    for item in items:
        cr_name = item["consumer_request"]
        
        if cr_name not in consumer_requests:
            consumer_requests[cr_name] = []
            
        consumer_requests[cr_name].append(item["idx"])
        
        # Mark item as invoiced
        frappe.db.set_value(
            "Consumer Request Item",
            {"parent": cr_name, "idx": item["idx"]},
            "invoiced", 
            1
        )
    
    # Update billing status for each consumer request
    for cr_name, item_indices in consumer_requests.items():
        total_items = frappe.db.count("Consumer Request Item", {"parent": cr_name})
        invoiced_items = frappe.db.count("Consumer Request Item", {"parent": cr_name, "invoiced": 1})
        
        if total_items == invoiced_items:
            # All items invoiced
            frappe.db.set_value("Consumer Request", cr_name, "billing_status", "Invoiced")
        elif invoiced_items > 0:
            # Some items invoiced
            frappe.db.set_value("Consumer Request", cr_name, "billing_status", "Partly Invoiced")


def update_inpatient_billables(inpatient_record_doc, billable_items: List[Dict]) -> None:
   """
   Update the billables table in the Inpatient Record with new items.
   This function is used exclusively for service requests billing workflow.
   
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


def update_inpatient_record_totals(inpatient_record_doc) -> None:
   """
   Update the total amount in the Inpatient Record
   
   Args:
       inpatient_record_doc: The Inpatient Record document
   """
   total_amount = sum(item.amount or 0 for item in inpatient_record_doc.get("items", []))
   
   # Update the total field
   inpatient_record_doc.total = total_amount
   inpatient_record_doc.save(ignore_permissions=False)


def update_inpatient_record_consumable_totals(inpatient_record_doc) -> None:
   """
   Update the total consumable amount in the Inpatient Record
   
   Args:
       inpatient_record_doc: The Inpatient Record document
   """
   total_amount = sum(item.grand_total or 0 for item in inpatient_record_doc.get("billables_consumable_requests", []))
   
   # Update the total field
   inpatient_record_doc.total_consumable_amount = total_amount
   inpatient_record_doc.save(ignore_permissions=False)


@frappe.whitelist()
def get_sales_invoice_items(sales_invoice: str) -> Dict:
   """
   Get items from a Sales Invoice for display in a dialog
   
   Args:
       sales_invoice: The Sales Invoice name
       
   Returns:
       Dict with invoice details and items
   """
   if not sales_invoice:
       frappe.throw(_("Sales Invoice is required"))
   
   # Get the Sales Invoice items - using standard fields instead of specific fields
   items = frappe.get_all(
       "Sales Invoice Item",
       filters={"parent": sales_invoice},
       fields=[
           "item_code", "item_name", "description", "qty", "uom", 
           "rate", "amount", "reference_dt", "reference_dn"
       ]
   )
   
   # Get the Sales Invoice for additional details
   invoice = frappe.get_doc("Sales Invoice", sales_invoice)
   
   # Add invoice details to the response
   result = {
       "items": items,
       "invoice": {
           "name": invoice.name,
           "status": invoice.status,
           "total": invoice.total,
           "grand_total": invoice.grand_total,
           "customer": invoice.customer,
           "patient": invoice.patient,
           "posting_date": invoice.posting_date
       }
   }
   
   return result


@frappe.whitelist()
def get_all_sales_invoice_items(inpatient_record: str) -> Dict:
   """
   Get items from all Sales Invoices linked to an Inpatient Record
   
   Args:
       inpatient_record: The Inpatient Record name
       
   Returns:
       Dict with invoices and their items
   """
   if not inpatient_record:
       frappe.throw(_("Inpatient Record is required"))
   
   # Get the Inpatient Record
   inpatient_doc = frappe.get_doc("Inpatient Record", inpatient_record)
   
   # Get all Sales Invoice names from billables_consumable_requests
   invoice_names = []
   for row in inpatient_doc.get("billables_consumable_requests", []):
       if row.sales_invoice:
           invoice_names.append(row.sales_invoice)
   
   if not invoice_names:
       return {
           "invoices": [],
           "items": []
       }
   
   # Get all invoices
   invoices = []
   all_items = []
   
   for invoice_name in invoice_names:
       try:
           # Get invoice details
           invoice = frappe.get_doc("Sales Invoice", invoice_name)
           
           # Add to invoices list
           invoices.append({
               "name": invoice.name,
               "status": invoice.status,
               "total": invoice.total,
               "grand_total": invoice.grand_total,
               "customer": invoice.customer,
               "patient": invoice.patient,
               "posting_date": invoice.posting_date
           })
           
           # Get all items for this invoice
           for item in invoice.items:
               all_items.append({
                   "invoice_name": invoice.name,
                   "item_code": item.item_code,
                   "item_name": item.item_name,
                   "description": item.description,
                   "qty": item.qty,
                   "uom": item.uom,
                   "rate": item.rate,
                   "amount": item.amount,
                   "reference_dt": item.reference_dt,
                   "reference_dn": item.reference_dn
               })
               
       except Exception as e:
           frappe.log_error(f"Error fetching invoice {invoice_name}: {str(e)}")
   
   return {
       "invoices": invoices,
       "items": all_items
   }