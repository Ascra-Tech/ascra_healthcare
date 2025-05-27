import frappe
from erpnext.stock.get_item_details import get_item_details

@frappe.whitelist()
def get_consumer_requests_to_invoice(patient, customer, company):
    """
    Get Consumer Requests (not items) for a patient that can be invoiced
    """
    if not patient:
        return []
    
    # If no customer provided, try to get from patient
    if not customer:
        customer = frappe.db.get_value("Patient", patient, "customer")
        if not customer:
            frappe.throw(f"No customer linked to patient {patient}")
    
    # Get Consumer Requests for this customer that are not fully invoiced
    consumer_requests = frappe.db.sql("""
        SELECT 
            cr.name,
            cr.consumer_request_type,
            cr.transaction_date,
            cr.billing_status,
            cr.schedule_date,
            COUNT(cri.name) as total_items,
            SUM(CASE WHEN cri.invoiced = 1 THEN 1 ELSE 0 END) as invoiced_items,
            SUM(cri.qty) as total_qty,
            SUM(IFNULL(cri.qty_invoiced, 0)) as invoiced_qty
        FROM `tabConsumer Request` cr
        LEFT JOIN `tabConsumer Request Item` cri ON cr.name = cri.parent
        WHERE cr.customer = %s 
        AND cr.company = %s
        AND cr.docstatus = 1
        AND cr.billing_status IN ('Pending', 'Partly Invoiced')
        GROUP BY cr.name
        ORDER BY cr.transaction_date DESC
    """, (customer, company), as_dict=True)
    
    # Format data for display
    formatted_requests = []
    for cr in consumer_requests:
        pending_items = cr.total_items - cr.invoiced_items
        pending_qty = cr.total_qty - cr.invoiced_qty
        
        # Only include if there are pending items
        if pending_items > 0:
            formatted_requests.append({
                'name': cr.name,
                'consumer_request_type': cr.consumer_request_type,
                'transaction_date': cr.transaction_date,
                'schedule_date': cr.schedule_date,
                'billing_status': cr.billing_status,
                'total_items': cr.total_items,
                'pending_items': pending_items,
                'total_qty': cr.total_qty,
                'pending_qty': pending_qty
            })
    
    return formatted_requests

@frappe.whitelist()
def set_consumer_requests(doc, checked_consumer_requests):
    """
    Add ALL items from selected Consumer Requests to Sales Invoice
    """
    if isinstance(doc, str):
        doc = frappe.get_doc(frappe.parse_json(doc))
    
    if isinstance(checked_consumer_requests, str):
        checked_consumer_requests = frappe.parse_json(checked_consumer_requests)
    
    # Get price list (with error handling)
    price_lists = frappe.db.get_values("Price List", {"selling": 1}, ["name", "currency"])
    if not price_lists:
        frappe.throw("No selling price list found")
    price_list, price_list_currency = price_lists[0]
    
    total_items_added = 0
    
    for cr_name in checked_consumer_requests:
        # Get Consumer Request
        consumer_request = frappe.get_doc("Consumer Request", cr_name)
        
        # Get all pending items from this Consumer Request
        for consumer_request_item in consumer_request.table_hluy:
            # Skip if already fully invoiced
            if consumer_request_item.invoiced and consumer_request_item.qty_invoiced >= consumer_request_item.qty:
                continue
            
            # Calculate pending quantity
            pending_qty = consumer_request_item.qty - (consumer_request_item.qty_invoiced or 0)
            if pending_qty <= 0:
                continue
            
            # Create new invoice line item
            item_line = doc.append("items", {})
            
            # Setup args for getting item details
            args = {
                "doctype": "Sales Invoice",
                "item_code": consumer_request_item.item_code,
                "company": doc.company,
                "customer": doc.customer,
                "selling_price_list": price_list,
                "price_list_currency": price_list_currency,
                "plc_conversion_rate": 1.0,
                "conversion_rate": 1.0,
            }
            
            # Get standard item details
            item_details = get_item_details(args)
            
            # Set item details
            item_line.item_code = consumer_request_item.item_code
            item_line.item_name = consumer_request_item.item_name or ""
            item_line.qty = pending_qty
            
            # Set rate and amount
            if item_details and item_details.get("price_list_rate"):
                item_line.rate = item_details.price_list_rate
            else:
                item_line.rate = 0.0
                
            item_line.amount = float(item_line.rate) * float(item_line.qty)
            
            # Set Consumer Request reference
            item_line.reference_dt = "Consumer Request"
            item_line.reference_dn = consumer_request.name
            
            # Set additional fields
            if consumer_request_item.description:
                item_line.description = consumer_request_item.description
            
            # Set warehouse information if available
            if consumer_request_item.warehouse:
                item_line.warehouse = consumer_request_item.warehouse
            
            # Update Consumer Request Item invoicing status
            consumer_request_item.qty_invoiced = (consumer_request_item.qty_invoiced or 0) + pending_qty
            if consumer_request_item.qty_invoiced >= consumer_request_item.qty:
                consumer_request_item.invoiced = 1
            
            total_items_added += 1
        
        # Save Consumer Request with updated item statuses
        consumer_request.save(ignore_permissions=True)
    
    # Update Consumer Request billing status
    update_consumer_request_billing_status(checked_consumer_requests)
    
    # Set missing values and recalculate
    doc.set_missing_values(for_validate=True)
    
    frappe.msgprint(f"Added {total_items_added} items from {len(checked_consumer_requests)} Consumer Request(s)")
    return doc

def update_consumer_request_billing_status(consumer_request_names):
    """
    Update the billing status of Consumer Requests
    """
    for consumer_request_name in consumer_request_names:
        consumer_request = frappe.get_doc("Consumer Request", consumer_request_name)
        
        # Count total items and invoiced items
        total_items = len(consumer_request.table_hluy)
        invoiced_items = sum(1 for item in consumer_request.table_hluy if item.invoiced)
        
        # Update billing status
        if invoiced_items == 0:
            consumer_request.billing_status = "Pending"
        elif invoiced_items < total_items:
            consumer_request.billing_status = "Partly Invoiced"
        else:
            consumer_request.billing_status = "Invoiced"
        
        # Calculate total invoiced quantity
        total_qty_invoiced = sum(item.qty_invoiced or 0 for item in consumer_request.table_hluy)
        consumer_request.qty_invoiced = total_qty_invoiced
        
        consumer_request.save(ignore_permissions=True)

# Event handlers for Sales Invoice submission/cancellation
def on_sales_invoice_submit(doc, method):
    """Update Consumer Request status when Sales Invoice is submitted"""
    update_consumer_request_status_from_invoice(doc)

def on_sales_invoice_cancel(doc, method):
    """Update Consumer Request status when Sales Invoice is cancelled"""
    update_consumer_request_status_from_invoice(doc, cancel=True)

def update_consumer_request_status_from_invoice(sales_invoice, cancel=False):
    """Update Consumer Request billing status based on Sales Invoice items"""
    
    consumer_requests = set()
    
    # Get all Consumer Request references from Sales Invoice items
    for item in sales_invoice.items:
        if item.reference_dt == "Consumer Request" and item.reference_dn:
            consumer_requests.add(item.reference_dn)
    
    # Update each Consumer Request
    for cr_name in consumer_requests:
        try:
            consumer_request = frappe.get_doc("Consumer Request", cr_name)
            
            if cancel:
                # Reset invoicing status when invoice is cancelled
                reset_consumer_request_invoicing(consumer_request, sales_invoice)
            else:
                # Update invoicing status when invoice is submitted
                update_consumer_request_invoicing(consumer_request, sales_invoice)
                
        except Exception as e:
            frappe.log_error(f"Error updating Consumer Request {cr_name}: {str(e)}")

def update_consumer_request_invoicing(consumer_request, sales_invoice):
    """Update Consumer Request invoicing details when invoice is submitted"""
    
    # Get invoiced quantities for this Consumer Request from this Sales Invoice
    invoiced_items = {}
    for item in sales_invoice.items:
        if (item.reference_dt == "Consumer Request" and 
            item.reference_dn == consumer_request.name):
            
            # Find the corresponding Consumer Request Item
            for cr_item in consumer_request.table_hluy:
                if cr_item.item_code == item.item_code:
                    invoiced_items[cr_item.name] = invoiced_items.get(cr_item.name, 0) + item.qty
                    break
    
    # Update Consumer Request Items
    for cr_item in consumer_request.table_hluy:
        if cr_item.name in invoiced_items:
            cr_item.qty_invoiced = (cr_item.qty_invoiced or 0) + invoiced_items[cr_item.name]
            if cr_item.qty_invoiced >= cr_item.qty:
                cr_item.invoiced = 1
    
    # Update overall Consumer Request status
    total_items = len(consumer_request.table_hluy)
    invoiced_items_count = sum(1 for item in consumer_request.table_hluy if item.invoiced)
    total_qty_invoiced = sum(item.qty_invoiced or 0 for item in consumer_request.table_hluy)
    
    consumer_request.qty_invoiced = total_qty_invoiced
    
    if invoiced_items_count == 0:
        consumer_request.billing_status = "Pending"
    elif invoiced_items_count < total_items:
        consumer_request.billing_status = "Partly Invoiced"
    else:
        consumer_request.billing_status = "Invoiced"
        consumer_request.status = "Invoiced"
    
    consumer_request.save(ignore_permissions=True)

def reset_consumer_request_invoicing(consumer_request, sales_invoice):
    """Reset Consumer Request invoicing details when invoice is cancelled"""
    
    # Get invoiced quantities for this Consumer Request from this Sales Invoice
    invoiced_items = {}
    for item in sales_invoice.items:
        if (item.reference_dt == "Consumer Request" and 
            item.reference_dn == consumer_request.name):
            
            # Find the corresponding Consumer Request Item
            for cr_item in consumer_request.table_hluy:
                if cr_item.item_code == item.item_code:
                    invoiced_items[cr_item.name] = invoiced_items.get(cr_item.name, 0) + item.qty
                    break
    
    # Reset Consumer Request Items
    for cr_item in consumer_request.table_hluy:
        if cr_item.name in invoiced_items:
            cr_item.qty_invoiced = max(0, (cr_item.qty_invoiced or 0) - invoiced_items[cr_item.name])
            if cr_item.qty_invoiced < cr_item.qty:
                cr_item.invoiced = 0
    
    # Update overall Consumer Request status
    total_items = len(consumer_request.table_hluy)
    invoiced_items_count = sum(1 for item in consumer_request.table_hluy if item.invoiced)
    total_qty_invoiced = sum(item.qty_invoiced or 0 for item in consumer_request.table_hluy)
    
    consumer_request.qty_invoiced = total_qty_invoiced
    
    if invoiced_items_count == 0:
        consumer_request.billing_status = "Pending"
        consumer_request.status = "Submitted"
    elif invoiced_items_count < total_items:
        consumer_request.billing_status = "Partly Invoiced"
    else:
        consumer_request.billing_status = "Invoiced"
    
    consumer_request.save(ignore_permissions=True)