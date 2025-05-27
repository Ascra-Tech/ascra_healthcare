frappe.ui.form.on('Consumer Request', {
    refresh: function(frm) {
        // Add a custom button to refresh stock levels for all items
        frm.add_custom_button(__('Check Stock Levels'), function() {
            show_consolidated_stock_dialog(frm);
        });
    },
    
    // When the Purpose field changes, set the appropriate item filter
    consumer_request_type: function(frm) {
        set_item_filter(frm);
    },
    
    // Also set the filter when the form loads
    onload: function(frm) {
        set_item_filter(frm);
    }
});

frappe.ui.form.on('Consumer Request Item', {
    // When item is selected, show stock levels in all warehouses
    item_code: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code && frm.doc.company) {
            fetch_item_stock_levels(frm, row);
        }
    },
    
    // When target warehouse is selected, check stock in that specific warehouse
    warehouse: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code && row.warehouse && row.qty > 0) {
            check_target_warehouse_stock(frm, row);
        }
    },
    
    // When quantity is changed, validate against target warehouse if selected
    qty: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.item_code && row.warehouse && row.qty > 0) {
            check_target_warehouse_stock(frm, row);
        }
    }
});

// Function to set the item filter based on the purpose
function set_item_filter(frm) {
    // Define the item group to filter by based on the consumer_request_type
    let item_group = "";
    
    switch(frm.doc.consumer_request_type) {
        case "Consumable Request":
            item_group = "Consumable";
            break;
        case "Blood Request":
            item_group = "Blood";
            break;
        case "Medicine Request":
            item_group = "Medicines";
            break;
        default:
            item_group = ""; // No filter if type is not set
    }
    
    // Set the filter on the item_code field in the child table
    frm.set_query("item_code", "table_hluy", function() {
        let filters = {};
        
        // Only add the item_group filter if a purpose is selected
        if (item_group) {
            filters["item_group"] = item_group;
        }
        
        return {
            filters: filters
        };
    });
    
    // Also set a warehouse filter to prevent selection of rejected, transit, or group warehouses
    frm.set_query("warehouse", "table_hluy", function() {
        return {
            filters: {
                "is_group": 0,
                "is_rejected_warehouse": 0
            },
            query: "healthcare.controllers.stock_level.get_valid_warehouses"
        };
    });
    
    // Show message to user about what's filtered
    if (item_group) {
        frappe.show_alert({
            message: __(`Items filtered by ${item_group}`),
            indicator: 'blue'
        }, 5);
    }
}

// Modern consolidated stock level display for all items using buttons instead of tabs
function show_consolidated_stock_dialog(frm) {
    if (!frm.doc.company) {
        frappe.msgprint(__("Please select a company first"));
        return;
    }
    
    if (!frm.doc.table_hluy || frm.doc.table_hluy.length === 0) {
        frappe.msgprint(__("No items to check"));
        return;
    }
    
    // Create a dialog with more modern UI for stock display
    let dialog = new frappe.ui.Dialog({
        title: __('Stock Availability'),
        size: 'extra-large', // Large dialog for better visibility
        fields: [
            {
                fieldname: 'view_selector',
                fieldtype: 'HTML',
                options: `
                    <div class="btn-group mb-3" role="group">
                        <button type="button" class="btn btn-primary view-btn active" data-view="summary">Summary</button>
                        <button type="button" class="btn btn-default view-btn" data-view="detailed">Detailed View</button>
                        <button type="button" class="btn btn-default view-btn" data-view="actions">Quick Actions</button>
                    </div>
                `
            },
            {
                fieldname: 'content_area',
                fieldtype: 'HTML'
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    // Show the dialog with a loading message
    dialog.show();
    dialog.get_field('content_area').$wrapper.html(`
        <div class="text-center p-4">
            <div class="spinner-border text-primary" role="status">
                <span class="sr-only">Loading...</span>
            </div>
            <div class="mt-2">${__('Loading stock information...')}</div>
        </div>
    `);
    
    // Fetch stock information for all items
    fetch_all_items_stock(frm, function(stock_data) {
        // Initially show the summary view
        dialog.get_field('content_area').$wrapper.html(generate_summary_view(stock_data));
        
        // Set up view switching
        dialog.$wrapper.find('.view-btn').on('click', function() {
            dialog.$wrapper.find('.view-btn').removeClass('active btn-primary').addClass('btn-default');
            $(this).removeClass('btn-default').addClass('active btn-primary');
            
            const view = $(this).data('view');
            if (view === 'summary') {
                dialog.get_field('content_area').$wrapper.html(generate_summary_view(stock_data));
            } else if (view === 'detailed') {
                dialog.get_field('content_area').$wrapper.html(generate_detailed_view(frm, stock_data));
            } else if (view === 'actions') {
                dialog.get_field('content_area').$wrapper.html(generate_actions_view(frm, stock_data));
            }
            
            // Initialize warehouse selection functionality after view change
            init_warehouse_selection(frm, dialog, stock_data);
        });
        
        // Initialize warehouse selection functionality
        init_warehouse_selection(frm, dialog, stock_data);
    });
}

// Fetch stock information for all items in the request
function fetch_all_items_stock(frm, callback) {
    frappe.call({
        method: "healthcare.controllers.stock_level.check_stock_availability_for_request",
        args: {
            consumer_request: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                callback(r.message);
            } else {
                callback([]);
            }
        }
    });
}

// Generate summary view with status indicators
function generate_summary_view(stock_data) {
    let html = `
    <div class="stock-summary">
        <div class="alert alert-info mb-3">
            Summary showing overall stock status for all items.
        </div>
        
        <div class="mb-3">
            <input type="text" class="form-control" id="summary-search" placeholder="Search items...">
        </div>
        
        <div class="table-responsive">
            <table class="table table-bordered table-hover">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th class="text-right">Required</th>
                        <th>Target Warehouse</th>
                        <th class="text-right">Available in Target</th>
                        <th class="text-right">Total Available</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    stock_data.forEach(function(item) {
        let status_indicator = '';
        let row_class = '';
        
        if (!item.warehouse) {
            status_indicator = `<span class="indicator gray">No Warehouse Selected</span>`;
            row_class = 'table-secondary';
        } else if (item.warehouse_stock >= item.qty_required) {
            status_indicator = `<span class="indicator green">Sufficient Stock</span>`;
            row_class = 'table-success';
        } else if (item.total_stock >= item.qty_required) {
            status_indicator = `<span class="indicator blue">Available in Other Warehouses</span>`;
            row_class = 'table-info';
        } else {
            status_indicator = `<span class="indicator red">Insufficient Stock</span>`;
            row_class = 'table-danger';
        }
        
        let warehouse_stock = item.warehouse ? (item.warehouse_stock || 0) : '-';
        
        html += `
        <tr class="${row_class}" data-item-code="${item.item_code}">
            <td>${item.item_code} - ${item.item_name}</td>
            <td class="text-right">${item.qty_required}</td>
            <td>${item.warehouse || '-'}</td>
            <td class="text-right">${warehouse_stock}</td>
            <td class="text-right">${item.total_stock}</td>
            <td>${status_indicator}</td>
        </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    </div>
    `;
    
    return html;
}

// Generate detailed view with expandable sections
function generate_detailed_view(frm, stock_data) {
    let html = `
    <div class="stock-details">
        <div class="alert alert-info mb-3">
            Detailed view showing stock levels across all warehouses for each item.
        </div>
    `;
    
    stock_data.forEach(function(item, index) {
        let sufficient = item.warehouse && item.warehouse_stock >= item.qty_required;
        let status_class = sufficient ? 'bg-success text-white' : 
                          (item.total_stock >= item.qty_required ? 'bg-info text-white' : 'bg-danger text-white');
        
        html += `
        <div class="card mb-3">
            <div class="card-header ${status_class}">
                <div class="d-flex justify-content-between">
                    <h5 class="mb-0">${item.item_code} - ${item.item_name}</h5>
                    <span>Required: ${item.qty_required}</span>
                </div>
            </div>
            <div class="card-body p-0">
                <table class="table table-sm table-striped mb-0">
                    <thead>
                        <tr>
                            <th>Warehouse</th>
                            <th class="text-right">Available Qty</th>
                            <th class="text-center">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        // Sort warehouses by available quantity (highest first)
        let warehouses = item.stock_details || [];
        warehouses.sort((a, b) => b.actual_qty - a.actual_qty);
        
        warehouses.forEach(function(warehouse) {
            let qty_class = warehouse.actual_qty <= 0 ? 'text-danger' : '';
            let disabled = warehouse.actual_qty <= 0 ? 'disabled' : '';
            
            html += `
            <tr>
                <td>${warehouse.warehouse}</td>
                <td class="text-right ${qty_class}">${warehouse.actual_qty}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-primary select-warehouse" 
                            data-item-code="${item.item_code}" 
                            data-warehouse="${warehouse.warehouse_code}" 
                            ${disabled}>
                        Select
                    </button>
                </td>
            </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        </div>
        `;
    });
    
    html += `</div>`;
    
    return html;
}

// Generate quick actions view
function generate_actions_view(frm, stock_data) {
    let html = `
    <div class="stock-actions">
        <div class="alert alert-info mb-3">
            Quickly assign warehouses based on stock availability.
        </div>
        
        <div class="card mb-3">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">Automated Warehouse Assignment</h5>
            </div>
            <div class="card-body">
                <p>Select an assignment strategy to automatically assign warehouses:</p>
                
                <div class="d-flex mb-3">
                    <button class="btn btn-success mr-2 auto-assign" data-strategy="optimal">
                        <i class="fa fa-magic"></i> Optimal Assignment
                    </button>
                    <button class="btn btn-info mr-2 auto-assign" data-strategy="single">
                        <i class="fa fa-building"></i> Prefer Single Warehouse
                    </button>
                </div>
                
                <div class="alert alert-warning">
                    <strong>Note:</strong> Automated assignment will overwrite any existing warehouse selections.
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h5 class="mb-0">Items Requiring Attention</h5>
            </div>
            <div class="card-body p-0">
    `;
    
    // Filter items that need attention
    let attention_items = stock_data.filter(item => 
        !item.warehouse || item.warehouse_stock < item.qty_required
    );
    
    if (attention_items.length === 0) {
        html += `
        <div class="alert alert-success m-3">
            All items have sufficient stock in their selected warehouses.
        </div>
        `;
    } else {
        html += `<ul class="list-group list-group-flush">`;
        
        attention_items.forEach(function(item) {
            let issue = !item.warehouse ? 
                "No warehouse selected" : 
                `Insufficient stock (${item.warehouse_stock}/${item.qty_required})`;
            
            let action_button = "";
            
            if (!item.warehouse) {
                action_button = `<button class="btn btn-sm btn-primary suggest-warehouse" data-item-code="${item.item_code}">Suggest Warehouse</button>`;
            } else if (item.warehouse_stock < item.qty_required && item.total_stock >= item.qty_required) {
                action_button = `<button class="btn btn-sm btn-info suggest-warehouse" data-item-code="${item.item_code}">Find Better Warehouse</button>`;
            }
            
            html += `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>${item.item_code}</strong> - ${issue}
                </div>
                ${action_button}
            </li>
            `;
        });
        
        html += `</ul>`;
    }
    
    html += `
            </div>
        </div>
    </div>
    `;
    
    return html;
}

// Initialize warehouse selection and other interactive functionality
function init_warehouse_selection(frm, dialog, stock_data) {
    // Handle warehouse selection buttons
    dialog.$wrapper.find('.select-warehouse').off('click').on('click', function() {
        let item_code = $(this).data('item-code');
        let warehouse = $(this).data('warehouse');
        
        // Find the row in the grid and update the warehouse
        $.each(frm.doc.table_hluy || [], function(i, row) {
            if (row.item_code === item_code) {
                frappe.model.set_value(row.doctype, row.name, 'warehouse', warehouse);
                
                frappe.show_alert({
                    message: __(`Warehouse selected for ${item_code}`),
                    indicator: 'green'
                });
                
                return false; // break the loop
            }
        });
    });
    
    // Handle search in summary view
    dialog.$wrapper.find('#summary-search').off('keyup').on('keyup', function() {
        let search_text = $(this).val().toLowerCase();
        
        dialog.$wrapper.find('.stock-summary tbody tr').each(function() {
            let row_text = $(this).text().toLowerCase();
            if (row_text.indexOf(search_text) === -1) {
                $(this).hide();
            } else {
                $(this).show();
            }
        });
    });
    
    // Handle automated warehouse assignment
    dialog.$wrapper.find('.auto-assign').off('click').on('click', function() {
        let strategy = $(this).data('strategy');
        
        // Show confirmation dialog
        frappe.confirm(
            __('This will automatically assign warehouses to all items. Continue?'),
            function() {
                // User confirmed, proceed with assignment
                auto_assign_warehouses(frm, strategy);
                dialog.hide();
            }
        );
    });
    
    // Handle suggest warehouse buttons
    dialog.$wrapper.find('.suggest-warehouse').off('click').on('click', function() {
        let item_code = $(this).data('item-code');
        
        // Find the row in the grid
        $.each(frm.doc.table_hluy || [], function(i, row) {
            if (row.item_code === item_code) {
                fetch_item_stock_levels(frm, row); // Show stock levels dialog for this item
                return false; // break the loop
            }
        });
        
        dialog.hide();
    });
}

// Automatically assign warehouses based on chosen strategy
function auto_assign_warehouses(frm, strategy) {
    frappe.call({
        method: "healthcare.controllers.stock_level.auto_assign_warehouses",
        args: {
            consumer_request: frm.doc.name,
            strategy: strategy
        },
        callback: function(r) {
            if (r.message && r.message.success) {
                frm.reload_doc();
                frappe.show_alert({
                    message: __('Warehouses assigned successfully'),
                    indicator: 'green'
                });
            } else {
                frappe.show_alert({
                    message: __('Failed to assign warehouses: ') + (r.message && r.message.error || 'Unknown error'),
                    indicator: 'red'
                });
            }
        }
    });
}

// Function to fetch and display stock levels for a specific item
function fetch_item_stock_levels(frm, row) {
    frappe.call({
        method: "healthcare.controllers.stock_level.get_item_stock_levels",
        args: {
            item_code: row.item_code,
            company: frm.doc.company
        },
        callback: function(r) {
            if (r.message) {
                display_stock_info(frm, row, r.message);
            }
        }
    });
}

// Function to check stock in the target warehouse
function check_target_warehouse_stock(frm, row) {
    frappe.call({
        method: "healthcare.controllers.stock_level.get_warehouse_stock",
        args: {
            item_code: row.item_code,
            warehouse: row.warehouse
        },
        callback: function(r) {
            if (r.message !== undefined) {
                let available_qty = r.message;
                let required_qty = row.qty || 0;
                
                // Create an alert message based on stock availability
                if (required_qty > available_qty) {
                    frappe.show_alert({
                        message: __(`Warning: Only ${available_qty} units of ${row.item_code} available in ${row.warehouse}, but ${required_qty} required`),
                        indicator: 'orange'
                    }, 7);
                } else if (available_qty > 0) {
                    frappe.show_alert({
                        message: __(`${available_qty} units of ${row.item_code} available in ${row.warehouse}`),
                        indicator: 'green'
                    }, 5);
                } else {
                    frappe.show_alert({
                        message: __(`No stock available for ${row.item_code} in ${row.warehouse}`),
                        indicator: 'red'
                    }, 7);
                }
            }
        }
    });
}

// Function to display stock information for a single item
function display_stock_info(frm, row, stock_data) {
    // Define a global function for selecting warehouse
    window.select_warehouse_for_item = function(doctype, name, warehouse) {
        frappe.model.set_value(doctype, name, 'warehouse', warehouse);
        frappe.hide_msgprint();
    };
    
    // Sort warehouses by stock quantity (highest first)
    stock_data.sort((a, b) => b.actual_qty - a.actual_qty);
    
    // Calculate total stock
    let total_stock = 0;
    stock_data.forEach(function(stock) {
        total_stock += stock.actual_qty;
    });
    
    // Create HTML table with stock information
    let html = '<div style="max-height: 300px; overflow-y: auto;"><table class="table table-bordered table-hover" style="margin-bottom:0;">';
    html += '<thead><tr><th>Warehouse</th><th class="text-right">Available Qty</th><th></th></tr></thead><tbody>';
    
    stock_data.forEach(function(stock) {
        let qty_class = stock.actual_qty <= 0 ? 'text-danger' : '';
        
        // Add a button to select this warehouse - pass the correct parameters
        let select_button = '';
        if (stock.actual_qty > 0) {
            select_button = `<button class="btn btn-xs btn-primary" 
                                     onclick="select_warehouse_for_item('${row.doctype}', '${row.name}', '${stock.warehouse_code}'); return false;">
                                Select
                             </button>`;
        }
        
        html += `<tr>
                    <td>${stock.warehouse}</td>
                    <td class="text-right ${qty_class}">${stock.actual_qty}</td>
                    <td>${select_button}</td>
                 </tr>`;
    });
    
    let total_class = total_stock <= 0 ? 'text-danger' : '';
    html += `<tr>
                <td><strong>Total</strong></td>
                <td class="text-right ${total_class}"><strong>${total_stock}</strong></td>
                <td></td>
             </tr>`;
    html += '</tbody></table></div>';
    
    // Display stock information in a dialog
    frappe.msgprint({
        title: __(`Stock Levels for ${row.item_code}`),
        message: html,
        indicator: total_stock > 0 ? 'green' : 'red',
        wide: true
    });
}