import frappe
from frappe import _

@frappe.whitelist()
def get_item_stock_levels(item_code=None, company=None):
    """
    Get stock levels for an item across all warehouses, excluding:
    - Rejected warehouses
    - Transit warehouses
    - Group warehouses
    
    Args:
        item_code (str): Item code to check stock for
        company (str): Company to filter warehouses
        
    Returns:
        list: List of dictionaries with warehouse and stock info
    """
    if not item_code:
        frappe.throw(_("Item Code is required"))
    
    if not company:
        frappe.throw(_("Company is required"))
    
    # Get a list of all warehouses for the company
    warehouses = frappe.get_all(
        "Warehouse",
        filters={
            "company": company, 
            "disabled": 0,
            "is_group": 0,  # Exclude group warehouses
            "is_rejected_warehouse": 0  # Exclude rejected warehouses
        },
        fields=["name", "warehouse_name", "warehouse_type"]
    )
    
    # Query actual stock quantities in valid warehouses
    stock_data = []
    for warehouse in warehouses:
        # Skip transit warehouses
        if warehouse.warehouse_type == "Transit":
            continue
            
        actual_qty = get_actual_qty(item_code, warehouse.name)
        
        stock_data.append({
            "warehouse": warehouse.warehouse_name,
            "warehouse_code": warehouse.name,
            "actual_qty": actual_qty
        })
    
    return stock_data

@frappe.whitelist()
def get_warehouse_stock(item_code=None, warehouse=None):
    """
    Get the stock level of an item in a specific warehouse
    
    Args:
        item_code (str): Item code to check
        warehouse (str): Warehouse to check
        
    Returns:
        float: Available quantity
    """
    if not item_code or not warehouse:
        return 0
    
    return get_actual_qty(item_code, warehouse)

def get_actual_qty(item_code, warehouse):
    """
    Get the actual quantity of an item in a specific warehouse
    
    Args:
        item_code (str): Item code
        warehouse (str): Warehouse name
        
    Returns:
        float: Actual quantity of the item in the warehouse
    """
    # Use frappe.db.get_value to get stock balance
    actual_qty = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        "actual_qty"
    ) or 0
    
    return actual_qty

@frappe.whitelist()
def check_stock_availability_for_request(consumer_request=None):
    """
    Check stock availability for all items in a Consumer Request
    
    Args:
        consumer_request (str): Name of the Consumer Request document
        
    Returns:
        list: List of dictionaries with item status and stock info
    """
    if not consumer_request:
        frappe.throw(_("Consumer Request ID is required"))
    
    # Get the Consumer Request document
    doc = frappe.get_doc("Consumer Request", consumer_request)
    
    result = []
    
    # Check each item in the request
    for item in doc.get("table_hluy"):
        # Get stock level in the selected warehouse (if specified)
        warehouse_stock = 0
        if item.warehouse:
            warehouse_stock = get_actual_qty(item.item_code, item.warehouse)
        
        # Get total stock across all valid warehouses
        item_stock = get_item_stock_levels(item.item_code, doc.company)
        total_stock = sum(stock["actual_qty"] for stock in item_stock)
        
        result.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty_required": item.qty,
            "warehouse": item.warehouse,
            "warehouse_stock": warehouse_stock,
            "total_stock": total_stock,
            "sufficient_in_warehouse": warehouse_stock >= item.qty if item.warehouse else False,
            "sufficient_overall": total_stock >= item.qty,
            "stock_details": item_stock
        })
    
    return result

@frappe.whitelist()
def get_item_details_with_stock(item_code=None, company=None):
    """
    Get item details along with stock information
    
    Args:
        item_code (str): Item code to get details for
        company (str): Company to filter warehouses
        
    Returns:
        dict: Dictionary with item details and stock information
    """
    if not item_code:
        return {}
    
    # Get basic item details
    item_details = frappe.db.get_value(
        "Item",
        item_code,
        ["item_name", "description", "stock_uom", "item_group", "brand", "image"],
        as_dict=1
    )
    
    # Get stock information
    if company:
        item_details["stock_levels"] = get_item_stock_levels(item_code, company)
        
        # Calculate total stock across all warehouses
        item_details["total_stock"] = sum(stock["actual_qty"] for stock in item_details["stock_levels"])
    
    return item_details

@frappe.whitelist()
def get_valid_warehouses(doctype, txt, searchfield, start, page_len, filters):
    """
    Get valid warehouses for selection (excluding rejected, transit, and group warehouses)
    
    Args:
        doctype (str): DocType being queried
        txt (str): Search text entered by user
        searchfield (str): Field being searched
        start (int): Starting index for paged query
        page_len (int): Number of results per page
        filters (dict): Filters from the client
        
    Returns:
        list: List of warehouse tuples that meet the criteria
    """
    company = filters.get('company', '')
    
    condition = ""
    if txt:
        condition = f"AND (name LIKE %(txt)s OR warehouse_name LIKE %(txt)s)"
    
    return frappe.db.sql("""
        SELECT name, warehouse_name
        FROM `tabWarehouse`
        WHERE
            company = %(company)s AND
            disabled = 0 AND
            is_group = 0 AND
            is_rejected_warehouse = 0 AND
            (warehouse_type != 'Transit' OR warehouse_type IS NULL)
            {0}
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
    """.format(condition), {
        'company': company,
        'txt': f"%{txt}%",
        'start': start,
        'page_len': page_len
    })

@frappe.whitelist()
def auto_assign_warehouses(consumer_request=None, strategy="optimal"):
    """
    Automatically assign warehouses to items in a Consumer Request
    
    Args:
        consumer_request (str): Name of the Consumer Request document
        strategy (str): Strategy for warehouse assignment ('optimal' or 'single')
        
    Returns:
        dict: Status of the operation
    """
    if not consumer_request:
        return {"success": False, "error": "Consumer Request ID is required"}
    
    try:
        # Get the Consumer Request document
        doc = frappe.get_doc("Consumer Request", consumer_request)
        
        if strategy == "single":
            # Try to assign all items to a single warehouse if possible
            result = assign_single_warehouse(doc)
        else:
            # Default: Optimal strategy (best warehouse for each item)
            result = assign_optimal_warehouses(doc)
        
        if result["success"]:
            doc.save()
            return {"success": True}
        else:
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def assign_single_warehouse(doc):
    """
    Try to assign all items to a single warehouse
    
    Args:
        doc: Consumer Request document
        
    Returns:
        dict: Status of the operation
    """
    if not doc.company:
        return {"success": False, "error": "Company is required"}
    
    # Get all valid warehouses
    warehouses = frappe.get_all(
        "Warehouse",
        filters={
            "company": doc.company,
            "disabled": 0,
            "is_group": 0,
            "is_rejected_warehouse": 0
        },
        fields=["name", "warehouse_name", "warehouse_type"]
    )
    
    # Filter out Transit warehouses
    valid_warehouses = [wh.name for wh in warehouses if wh.warehouse_type != "Transit"]
    
    if not valid_warehouses:
        return {"success": False, "error": "No valid warehouses found"}
    
    # Get all items in the request
    items = [item.item_code for item in doc.get("table_hluy") if item.item_code]
    
    if not items:
        return {"success": False, "error": "No items in the request"}
    
    # Find a warehouse that can satisfy all items
    best_warehouse = None
    max_satisfied = 0
    
    for warehouse in valid_warehouses:
        satisfied_items = 0
        for item_row in doc.get("table_hluy"):
            if not item_row.item_code or not item_row.qty:
                continue
                
            actual_qty = get_actual_qty(item_row.item_code, warehouse)
            if actual_qty >= item_row.qty:
                satisfied_items += 1
        
        if satisfied_items > max_satisfied:
            max_satisfied = satisfied_items
            best_warehouse = warehouse
    
    # Assign the best warehouse to all items
    if best_warehouse:
        for item_row in doc.get("table_hluy"):
            if item_row.item_code:
                item_row.warehouse = best_warehouse
        
        return {
            "success": True, 
            "message": f"Assigned warehouse {best_warehouse} to {max_satisfied} of {len(items)} items"
        }
    else:
        return {"success": False, "error": "Could not find a suitable warehouse"}

def assign_optimal_warehouses(doc):
    """
    Assign the best warehouse for each item
    
    Args:
        doc: Consumer Request document
        
    Returns:
        dict: Status of the operation
    """
    if not doc.company:
        return {"success": False, "error": "Company is required"}
    
    assigned_count = 0
    
    for item_row in doc.get("table_hluy"):
        if not item_row.item_code or not item_row.qty:
            continue
            
        # Get stock levels for this item
        stock_data = get_item_stock_levels(item_row.item_code, doc.company)
        
        # Sort by available quantity (highest first)
        stock_data.sort(key=lambda x: x["actual_qty"], reverse=True)
        
        # Find the first warehouse with sufficient stock
        for stock in stock_data:
            if stock["actual_qty"] >= item_row.qty:
                item_row.warehouse = stock["warehouse_code"]
                assigned_count += 1
                break
    
    if assigned_count > 0:
        return {"success": True, "message": f"Assigned warehouses to {assigned_count} items"}
    else:
        return {"success": False, "error": "Could not find suitable warehouses for any items"}