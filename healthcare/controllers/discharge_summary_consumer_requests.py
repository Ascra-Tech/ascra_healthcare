# Copyright (c) 2023, healthcare and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days, cint, flt, get_datetime
import json

@frappe.whitelist()
def get_consumer_requests(inpatient_record, patient):
    """
    Get all consumer requests related to the patient and inpatient record
    """
    try:
        if not patient:
            frappe.throw(_("Patient is required to fetch Consumer Requests"))
        
        # Get customer linked to patient
        customer = frappe.db.get_value("Patient", patient, "customer")
        if not customer:
            frappe.log_error(f"No customer linked to patient: {patient}")
            return []
        
        # Base filters for consumer requests
        filters = {
            "customer": customer,
            "docstatus": ["!=", 2]  # Exclude cancelled documents
        }
        
        # Get inpatient record dates for filtering
        inpatient_dates = None
        if inpatient_record:
            inpatient_dates = frappe.db.get_value(
                "Inpatient Record", 
                inpatient_record, 
                ["scheduled_date", "admitted_datetime", "discharge_datetime", "status"], 
                as_dict=True
            )
            
            if inpatient_dates:
                # Filter requests within admission period
                admission_start = inpatient_dates.get("scheduled_date") or inpatient_dates.get("admitted_datetime")
                if admission_start:
                    filters["transaction_date"] = [">=", getdate(admission_start)]
                
                # If patient is discharged, filter up to discharge date
                if inpatient_dates.get("discharge_datetime"):
                    discharge_date = getdate(inpatient_dates.get("discharge_datetime"))
                    if "transaction_date" in filters:
                        filters["transaction_date"] = ["between", [getdate(admission_start), discharge_date]]
                    else:
                        filters["transaction_date"] = ["<=", discharge_date]
        
        # Fetch consumer requests
        consumer_requests = frappe.get_all(
            "Consumer Request",
            filters=filters,
            fields=[
                "name", "consumer_request_type", "transaction_date", "schedule_date",
                "company", "billing_status", "status", "per_ordered", "per_received",
                "qty_invoiced", "creation", "modified", "customer"
            ],
            order_by="transaction_date desc, creation desc"
        )
        
        # Enrich with additional data
        for request in consumer_requests:
            # Get item count and total quantity
            item_stats = frappe.db.sql("""
                SELECT 
                    COUNT(*) as item_count,
                    SUM(COALESCE(qty, 0)) as total_quantity,
                    SUM(CASE WHEN invoiced = 1 THEN 1 ELSE 0 END) as invoiced_items,
                    SUM(COALESCE(qty_invoiced, 0)) as total_qty_invoiced
                FROM `tabConsumer Request Item`
                WHERE parent = %s
            """, (request.name,), as_dict=True)
            
            if item_stats and item_stats[0]:
                stats = item_stats[0]
                request["item_count"] = cint(stats.get("item_count", 0))
                request["total_quantity"] = flt(stats.get("total_quantity", 0))
                request["invoiced_items"] = cint(stats.get("invoiced_items", 0))
                request["total_qty_invoiced"] = flt(stats.get("total_qty_invoiced", 0))
            else:
                request["item_count"] = 0
                request["total_quantity"] = 0
                request["invoiced_items"] = 0
                request["total_qty_invoiced"] = 0
            
            # Calculate progress percentages if not already set
            if not request.get("per_ordered"):
                request["per_ordered"] = 0
            if not request.get("per_received"):
                request["per_received"] = 0
            
            # Add formatted dates for display
            request["formatted_transaction_date"] = frappe.utils.formatdate(request.transaction_date)
            if request.schedule_date:
                request["formatted_schedule_date"] = frappe.utils.formatdate(request.schedule_date)
            
            # Add urgency indicator based on schedule date
            if request.schedule_date:
                days_until_due = (getdate(request.schedule_date) - getdate()).days
                if days_until_due < 0:
                    request["urgency"] = "overdue"
                elif days_until_due <= 1:
                    request["urgency"] = "urgent"
                elif days_until_due <= 3:
                    request["urgency"] = "soon"
                else:
                    request["urgency"] = "normal"
            else:
                request["urgency"] = "normal"
        
        # Log successful fetch
        frappe.logger().info(f"Fetched {len(consumer_requests)} consumer requests for patient {patient}")
        
        return consumer_requests
        
    except Exception as e:
        frappe.log_error(f"Error in get_consumer_requests: {str(e)}", "Consumer Requests Fetch Error")
        frappe.throw(_("Failed to fetch Consumer Requests. Please try again later."))


@frappe.whitelist()
def get_consumer_request_items(consumer_request):
    """
    Get all items for a specific consumer request with enhanced details
    """
    try:
        if not consumer_request:
            frappe.throw(_("Consumer Request is required"))
        
        # Validate consumer request exists
        if not frappe.db.exists("Consumer Request", consumer_request):
            frappe.throw(_("Consumer Request {0} not found").format(consumer_request))
        
        # Fetch consumer request items
        items = frappe.get_all(
            "Consumer Request Item",
            filters={"parent": consumer_request},
            fields=[
                "name", "item_code", "item_name", "qty", "stock_uom",
                "schedule_date", "from_warehouse", "warehouse", "invoiced",
                "qty_invoiced", "description", "item_group", "brand",
                "conversion_factor", "stock_qty"
            ],
            order_by="idx"
        )
        
        # Enrich items with additional data
        for item in items:
            # Get current stock levels if warehouses are specified
            if item.get("from_warehouse"):
                try:
                    stock_qty = frappe.db.get_value(
                        "Bin", 
                        {"item_code": item.item_code, "warehouse": item.from_warehouse}, 
                        "actual_qty"
                    ) or 0
                    item["available_qty"] = flt(stock_qty)
                    
                    # Check if there's enough stock
                    required_qty = flt(item.get("qty", 0))
                    item["has_sufficient_stock"] = stock_qty >= required_qty
                    item["stock_shortage"] = max(0, required_qty - stock_qty)
                except Exception:
                    item["available_qty"] = 0
                    item["has_sufficient_stock"] = False
                    item["stock_shortage"] = flt(item.get("qty", 0))
            
            # Get comprehensive item details
            item_details = frappe.db.get_value(
                "Item",
                item.item_code,
                [
                    "item_name", "description", "image", "has_serial_no", 
                    "has_batch_no", "is_stock_item", "valuation_rate",
                    "last_purchase_rate", "item_group", "brand"
                ],
                as_dict=True
            )
            
            if item_details:
                item.update(item_details)
                
                # Calculate estimated value
                rate = flt(item_details.get("last_purchase_rate")) or flt(item_details.get("valuation_rate"))
                if rate and item.get("qty"):
                    item["estimated_value"] = flt(rate * flt(item.get("qty")))
                else:
                    item["estimated_value"] = 0
            
            # Add urgency indicator for item schedule
            if item.get("schedule_date"):
                days_until_due = (getdate(item.schedule_date) - getdate()).days
                if days_until_due < 0:
                    item["urgency"] = "overdue"
                elif days_until_due <= 1:
                    item["urgency"] = "urgent"
                elif days_until_due <= 3:
                    item["urgency"] = "soon"
                else:
                    item["urgency"] = "normal"
            else:
                item["urgency"] = "normal"
            
            # Format dates
            if item.get("schedule_date"):
                item["formatted_schedule_date"] = frappe.utils.formatdate(item.schedule_date)
        
        return items
        
    except Exception as e:
        frappe.log_error(f"Error in get_consumer_request_items: {str(e)}", "Consumer Request Items Fetch Error")
        frappe.throw(_("Failed to fetch Consumer Request items. Please try again later."))


@frappe.whitelist()
def get_consumer_request_summary(inpatient_record, patient):
    """
    Get comprehensive summary statistics for consumer requests
    """
    try:
        consumer_requests = get_consumer_requests(inpatient_record, patient)
        
        if not consumer_requests:
            return {
                "total_requests": 0,
                "total_items": 0,
                "total_quantity": 0,
                "total_value": 0,
                "pending_requests": 0,
                "completed_requests": 0,
                "overdue_requests": 0,
                "types_summary": {},
                "status_breakdown": {},
                "urgency_breakdown": {}
            }
        
        # Calculate summary statistics
        total_requests = len(consumer_requests)
        total_items = sum(req.get("item_count", 0) for req in consumer_requests)
        total_quantity = sum(req.get("total_quantity", 0) for req in consumer_requests)
        
        # Status-based counts
        pending_statuses = ["Draft", "Submitted", "Pending", "Partially Ordered"]
        completed_statuses = ["Received", "Issued", "Transferred"]
        
        pending_requests = len([req for req in consumer_requests if req.get("status") in pending_statuses])
        completed_requests = len([req for req in consumer_requests if req.get("status") in completed_statuses])
        overdue_requests = len([req for req in consumer_requests if req.get("urgency") == "overdue"])
        
        # Group by type
        types_summary = {}
        status_breakdown = {}
        urgency_breakdown = {"overdue": 0, "urgent": 0, "soon": 0, "normal": 0}
        
        for request in consumer_requests:
            # Type summary
            req_type = request.get("consumer_request_type", "Unknown")
            if req_type not in types_summary:
                types_summary[req_type] = {
                    "count": 0,
                    "total_items": 0,
                    "total_quantity": 0,
                    "pending": 0,
                    "completed": 0
                }
            
            types_summary[req_type]["count"] += 1
            types_summary[req_type]["total_items"] += request.get("item_count", 0)
            types_summary[req_type]["total_quantity"] += request.get("total_quantity", 0)
            
            if request.get("status") in pending_statuses:
                types_summary[req_type]["pending"] += 1
            elif request.get("status") in completed_statuses:
                types_summary[req_type]["completed"] += 1
            
            # Status breakdown
            status = request.get("status", "Draft")
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            # Urgency breakdown
            urgency = request.get("urgency", "normal")
            urgency_breakdown[urgency] += 1
        
        return {
            "total_requests": total_requests,
            "total_items": total_items,
            "total_quantity": total_quantity,
            "pending_requests": pending_requests,
            "completed_requests": completed_requests,
            "overdue_requests": overdue_requests,
            "types_summary": types_summary,
            "status_breakdown": status_breakdown,
            "urgency_breakdown": urgency_breakdown
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_consumer_request_summary: {str(e)}", "Consumer Request Summary Error")
        return {}


@frappe.whitelist()
def create_consumer_request_from_discharge(discharge_summary, items_data, request_type="Medicine Request"):
    """
    Create consumer request from discharge summary with enhanced validation
    """
    try:
        if isinstance(items_data, str):
            items_data = json.loads(items_data)
        
        if not items_data:
            frappe.throw(_("No items provided to create Consumer Request"))
        
        discharge_doc = frappe.get_doc("Discharge Summary", discharge_summary)
        
        # Get patient and customer
        customer = frappe.db.get_value("Patient", discharge_doc.patient, "customer")
        if not customer:
            frappe.throw(_("Patient must be linked to a Customer to create Consumer Request"))
        
        # Validate request type
        valid_types = ["Consumable Request", "Blood Request", "Medicine Request"]
        if request_type not in valid_types:
            request_type = "Medicine Request"
        
        # Create consumer request
        consumer_request = frappe.new_doc("Consumer Request")
        consumer_request.customer = customer
        consumer_request.consumer_request_type = request_type
        consumer_request.transaction_date = nowdate()
        consumer_request.schedule_date = add_days(nowdate(), 1)  # Next day delivery
        consumer_request.company = discharge_doc.company
        
        # Add reference to discharge summary in a custom field if it exists
        if frappe.db.has_column("Consumer Request", "discharge_summary"):
            consumer_request.discharge_summary = discharge_summary
        
        # Add items with validation
        for item_data in items_data:
            if not item_data.get("item_code"):
                continue
                
            # Validate item exists
            if not frappe.db.exists("Item", item_data.get("item_code")):
                frappe.throw(_("Item {0} does not exist").format(item_data.get("item_code")))
            
            consumer_request.append("table_hluy", {
                "item_code": item_data.get("item_code"),
                "qty": flt(item_data.get("quantity", 1)),
                "schedule_date": item_data.get("schedule_date") or add_days(nowdate(), 1),
                "warehouse": item_data.get("target_warehouse"),
                "from_warehouse": item_data.get("source_warehouse"),
                "description": item_data.get("description")
            })
        
        if not consumer_request.get("table_hluy"):
            frappe.throw(_("No valid items to add to Consumer Request"))
        
        consumer_request.insert()
        
        # Log successful creation
        frappe.logger().info(f"Created Consumer Request {consumer_request.name} from Discharge Summary {discharge_summary}")
        
        return consumer_request.name
        
    except Exception as e:
        frappe.log_error(f"Error creating consumer request from discharge: {str(e)}", "Consumer Request Creation Error")
        frappe.throw(_("Failed to create Consumer Request. Error: {0}").format(str(e)))


@frappe.whitelist()
def validate_consumer_requests_for_discharge(inpatient_record, patient):
    """
    Validate consumer requests before allowing patient discharge with detailed reporting
    """
    try:
        consumer_requests = get_consumer_requests(inpatient_record, patient)
        
        if not consumer_requests:
            return {"has_pending": False, "message": "No consumer requests found"}
        
        # Check for pending requests
        pending_statuses = ["Draft", "Submitted", "Pending", "Partially Ordered"]
        pending_requests = [
            req for req in consumer_requests 
            if req.get("status") in pending_statuses
        ]
        
        # Check for overdue requests
        overdue_requests = [
            req for req in consumer_requests
            if req.get("urgency") == "overdue"
        ]
        
        if pending_requests or overdue_requests:
            pending_names = [req["name"] for req in pending_requests]
            overdue_names = [req["name"] for req in overdue_requests]
            
            messages = []
            if pending_requests:
                messages.append(_("Pending Consumer Requests: {0}").format(", ".join(pending_names)))
            if overdue_requests:
                messages.append(_("Overdue Consumer Requests: {0}").format(", ".join(overdue_names)))
            
            return {
                "has_pending": True,
                "message": "; ".join(messages),
                "pending_requests": pending_names,
                "overdue_requests": overdue_names,
                "pending_count": len(pending_requests),
                "overdue_count": len(overdue_requests)
            }
        
        return {
            "has_pending": False, 
            "message": f"All {len(consumer_requests)} consumer requests are completed"
        }
        
    except Exception as e:
        frappe.log_error(f"Error validating consumer requests: {str(e)}", "Consumer Request Validation Error")
        return {"has_pending": False, "error": str(e)}


@frappe.whitelist()
def update_consumer_request_status(consumer_request, new_status):
    """
    Update consumer request status with validation
    """
    try:
        if not frappe.db.exists("Consumer Request", consumer_request):
            frappe.throw(_("Consumer Request {0} not found").format(consumer_request))
        
        valid_statuses = [
            "Draft", "Submitted", "Pending", "Partially Ordered", 
            "Partially Received", "Ordered", "Issued", "Transferred", 
            "Received", "Stopped", "Cancelled"
        ]
        
        if new_status not in valid_statuses:
            frappe.throw(_("Invalid status: {0}").format(new_status))
        
        frappe.db.set_value("Consumer Request", consumer_request, "status", new_status)
        frappe.db.commit()
        
        return {"success": True, "message": f"Status updated to {new_status}"}
        
    except Exception as e:
        frappe.log_error(f"Error updating consumer request status: {str(e)}", "Consumer Request Status Update Error")
        frappe.throw(_("Failed to update status. Error: {0}").format(str(e)))


# Hook this into the discharge summary validation if needed
def enhance_discharge_summary_validation(doc, method):
    """
    Add consumer request validation to discharge summary
    Call this from hooks.py if you want automatic validation
    """
    if doc.inpatient_record and doc.patient:
        try:
            validation_result = validate_consumer_requests_for_discharge(
                doc.inpatient_record, 
                doc.patient
            )
            
            if validation_result.get("has_pending"):
                # Create a warning message with details
                message = validation_result.get("message", "")
                if validation_result.get("pending_count"):
                    message += f" ({validation_result.get('pending_count')} pending"
                    if validation_result.get("overdue_count"):
                        message += f", {validation_result.get('overdue_count')} overdue"
                    message += ")"
                
                # Log warning but don't prevent discharge
                # Change this to frappe.throw() if you want to make it mandatory
                frappe.msgprint(
                    message,
                    title=_("Consumer Requests Status"),
                    indicator="orange"
                )
                
        except Exception as e:
            frappe.log_error(f"Error in discharge summary validation: {str(e)}", "Discharge Summary Validation Error")


def on_consumer_request_update(doc, method):
    """
    Hook for when consumer request is updated
    Can be used to trigger notifications or updates
    """
    try:
        # Log status changes
        if hasattr(doc, '_doc_before_save') and doc._doc_before_save:
            old_status = doc._doc_before_save.status
            new_status = doc.status
            
            if old_status != new_status:
                frappe.logger().info(f"Consumer Request {doc.name} status changed from {old_status} to {new_status}")
                
                # You can add notifications here if needed
                # send_status_change_notification(doc, old_status, new_status)
        
    except Exception as e:
        frappe.log_error(f"Error in consumer request update hook: {str(e)}", "Consumer Request Update Hook Error")


# Utility functions
def get_consumer_request_analytics(patient=None, date_range=None):
    """
    Get analytics data for consumer requests
    """
    try:
        filters = {"docstatus": ["!=", 2]}
        
        if patient:
            customer = frappe.db.get_value("Patient", patient, "customer")
            if customer:
                filters["customer"] = customer
        
        if date_range:
            filters["transaction_date"] = ["between", date_range]
        
        requests = frappe.get_all("Consumer Request", filters=filters, fields=["*"])
        
        # Process analytics
        analytics = {
            "total_requests": len(requests),
            "by_type": {},
            "by_status": {},
            "by_month": {},
            "avg_completion_time": 0
        }
        
        for req in requests:
            # By type
            req_type = req.get("consumer_request_type", "Unknown")
            analytics["by_type"][req_type] = analytics["by_type"].get(req_type, 0) + 1
            
            # By status
            status = req.get("status", "Draft")
            analytics["by_status"][status] = analytics["by_status"].get(status, 0) + 1
            
            # By month
            month = req.get("transaction_date").strftime("%Y-%m") if req.get("transaction_date") else "Unknown"
            analytics["by_month"][month] = analytics["by_month"].get(month, 0) + 1
        
        return analytics
        
    except Exception as e:
        frappe.log_error(f"Error in consumer request analytics: {str(e)}", "Consumer Request Analytics Error")
        return {}


@frappe.whitelist()
def get_pending_consumer_requests_count(patient):
    """
    Get count of pending consumer requests for a patient
    """
    try:
        customer = frappe.db.get_value("Patient", patient, "customer")
        if not customer:
            return 0
        
        pending_statuses = ["Draft", "Submitted", "Pending", "Partially Ordered"]
        count = frappe.db.count("Consumer Request", {
            "customer": customer,
            "status": ["in", pending_statuses],
            "docstatus": ["!=", 2]
        })
        
        return count
        
    except Exception as e:
        frappe.log_error(f"Error getting pending consumer requests count: {str(e)}")
        return 0