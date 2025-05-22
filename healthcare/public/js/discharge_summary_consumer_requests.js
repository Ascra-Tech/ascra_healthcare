// Copyright (c) 2023, healthcare and contributors
// For license information, please see license.txt

// Consumer Requests integration for Discharge Summary
frappe.ui.form.on("Discharge Summary", {
    refresh: function(frm) {
        // Show consumer requests when form loads
        if (frm.doc.inpatient_record) {
            show_consumer_requests(frm);
        }
    },
    
    onload: function(frm) {
        // Show consumer requests on form load
        if (frm.doc.inpatient_record) {
            show_consumer_requests(frm);
        }
    },
    
    inpatient_record: function(frm) {
        // Refresh consumer requests when inpatient record changes
        if (frm.doc.inpatient_record) {
            show_consumer_requests(frm);
        } else {
            // Clear the HTML field if no inpatient record
            frm.set_df_property('consumable_orders_html', 'options', '');
        }
    }
});

var show_consumer_requests = function(frm) {
    if (!frm.doc.inpatient_record || !frm.doc.patient) {
        return;
    }

    // Show loading indicator
    frm.set_df_property('consumable_orders_html', 'options', 
        '<div class="text-center" style="padding: 20px;">' +
        '<i class="fa fa-spinner fa-spin"></i> Loading Consumer Requests...' +
        '</div>'
    );

    // Call server method to get consumer requests
    frappe.call({
        method: "healthcare.controllers.discharge_summary_consumer_requests.get_consumer_requests",
        args: {
            inpatient_record: frm.doc.inpatient_record,
            patient: frm.doc.patient
        },
        callback: function(response) {
            if (response.message && response.message.length > 0) {
                render_consumer_requests(frm, response.message);
            } else {
                // Show message when no consumer requests found
                frm.set_df_property('consumable_orders_html', 'options',
                    '<div class="text-center text-muted" style="padding: 20px;">' +
                    '<i class="fa fa-info-circle" style="font-size: 24px; margin-bottom: 10px;"></i>' +
                    '<p>No Consumer Requests found for this patient.</p>' +
                    '</div>'
                );
            }
        },
        error: function(err) {
            console.error("Error fetching consumer requests:", err);
            frm.set_df_property('consumable_orders_html', 'options',
                '<div class="text-center text-danger" style="padding: 20px;">' +
                '<i class="fa fa-exclamation-triangle" style="font-size: 24px; margin-bottom: 10px;"></i>' +
                '<p>Error loading Consumer Requests. Please try again.</p>' +
                '</div>'
            );
        }
    });
};

var render_consumer_requests = function(frm, consumer_requests) {
    if (!consumer_requests || consumer_requests.length === 0) {
        frm.set_df_property('consumable_orders_html', 'options',
            '<div class="text-center text-muted" style="padding: 20px;">' +
            '<i class="fa fa-info-circle" style="font-size: 24px; margin-bottom: 10px;"></i>' +
            '<p>No Consumer Requests found for this patient.</p>' +
            '</div>'
        );
        return;
    }

    let html = `
        <div class="consumer-requests-container" style="margin: 10px 0;">
            <div class="row">
                <div class="col-md-12">
                    <h5 class="text-primary" style="margin-bottom: 15px; border-bottom: 2px solid #007bff; padding-bottom: 8px;">
                        <i class="fa fa-shopping-cart"></i> Consumer Requests Summary
                        <span class="badge badge-primary" style="margin-left: 10px;">${consumer_requests.length}</span>
                    </h5>
                </div>
            </div>
    `;

    // Group requests by type
    let grouped_requests = {};
    consumer_requests.forEach(request => {
        if (!grouped_requests[request.consumer_request_type]) {
            grouped_requests[request.consumer_request_type] = [];
        }
        grouped_requests[request.consumer_request_type].push(request);
    });

    // Render each group
    Object.keys(grouped_requests).forEach(request_type => {
        let type_requests = grouped_requests[request_type];
        let type_color = get_request_type_color(request_type);
        
        html += `
            <div class="row" style="margin-bottom: 20px;">
                <div class="col-md-12">
                    <div class="panel panel-default" style="border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden;">
                        <div class="panel-heading" style="background: linear-gradient(135deg, ${type_color.bg} 0%, ${type_color.bgLight} 100%); border: none; padding: 12px 15px;">
                            <h6 class="panel-title" style="margin: 0; font-weight: 600; color: ${type_color.text};">
                                <i class="${type_color.icon}"></i> ${request_type}
                                <span class="badge" style="background-color: ${type_color.badgeBg}; color: ${type_color.badgeText}; margin-left: 10px;">
                                    ${type_requests.length} ${type_requests.length === 1 ? 'request' : 'requests'}
                                </span>
                            </h6>
                        </div>
                        <div class="panel-body" style="padding: 15px; background-color: #fafbfc;">
        `;

        type_requests.forEach((request, index) => {
            let status_color = get_status_color(request.status);
            let billing_color = get_billing_color(request.billing_status);
            let border_color = index === 0 ? type_color.border : '#e9ecef';
            
            html += `
                <div class="consumer-request-item" style="border: 1px solid ${border_color}; border-radius: 6px; padding: 15px; margin-bottom: 12px; background-color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: all 0.3s ease;">
                    <div class="row">
                        <div class="col-md-8">
                            <div style="margin-bottom: 10px;">
                                <strong style="font-size: 14px;">
                                    <a href="/app/consumer-request/${request.name}" target="_blank" 
                                       style="text-decoration: none; color: #007bff;" 
                                       onmouseover="this.style.textDecoration='underline'" 
                                       onmouseout="this.style.textDecoration='none'">
                                        <i class="fa fa-external-link" style="font-size: 12px; margin-right: 5px;"></i>
                                        ${request.name}
                                    </a>
                                </strong>
                                <div style="margin-top: 5px;">
                                    <span class="label label-${status_color}" style="font-size: 10px; margin-right: 8px; padding: 3px 8px;">
                                        ${request.status || 'Draft'}
                                    </span>
                                    <span class="label label-${billing_color}" style="font-size: 10px; padding: 3px 8px;">
                                        ${request.billing_status || 'Pending'}
                                    </span>
                                </div>
                            </div>
                            <div class="text-muted" style="font-size: 12px; line-height: 1.4;">
                                <div style="margin-bottom: 3px;">
                                    <i class="fa fa-calendar" style="width: 14px;"></i> 
                                    <strong>Transaction:</strong> ${frappe.datetime.str_to_user(request.transaction_date)}
                                    ${request.schedule_date ? ` | <i class="fa fa-clock-o" style="width: 14px; margin-left: 10px;"></i> <strong>Required By:</strong> ${frappe.datetime.str_to_user(request.schedule_date)}` : ''}
                                </div>
                                ${request.company ? `<div><i class="fa fa-building" style="width: 14px;"></i> <strong>Company:</strong> ${request.company}</div>` : ''}
                                ${request.item_count ? `<div><i class="fa fa-list" style="width: 14px;"></i> <strong>Items:</strong> ${request.item_count} items, Total Qty: ${request.total_quantity || 0}</div>` : ''}
                            </div>
                        </div>
                        <div class="col-md-4 text-right">
                            <div style="margin-bottom: 8px;">
                                <button class="btn btn-xs btn-primary" onclick="view_consumer_request_items('${request.name}')" 
                                        style="margin-bottom: 5px; padding: 4px 8px;">
                                    <i class="fa fa-list"></i> View Items
                                </button>
                                <button class="btn btn-xs btn-default" onclick="open_consumer_request('${request.name}')" 
                                        style="margin-bottom: 5px; padding: 4px 8px; margin-left: 5px;">
                                    <i class="fa fa-external-link"></i> Open
                                </button>
                            </div>
                            <div style="font-size: 11px; color: #666;">
                                ${request.per_ordered ? `<div><strong>Ordered:</strong> ${request.per_ordered}%</div>` : '<div><strong>Ordered:</strong> 0%</div>'}
                                ${request.per_received ? `<div><strong>Received:</strong> ${request.per_received}%</div>` : '<div><strong>Received:</strong> 0%</div>'}
                                ${request.qty_invoiced ? `<div><strong>Invoiced:</strong> ${request.qty_invoiced}</div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    // Add summary statistics
    let total_requests = consumer_requests.length;
    let pending_statuses = ['Draft', 'Submitted', 'Pending', 'Partially Ordered'];
    let completed_statuses = ['Received', 'Issued', 'Transferred'];
    let pending_requests = consumer_requests.filter(r => pending_statuses.includes(r.status)).length;
    let completed_requests = consumer_requests.filter(r => completed_statuses.includes(r.status)).length;
    let in_progress_requests = total_requests - pending_requests - completed_requests;

    html += `
        <div class="row" style="margin-top: 20px;">
            <div class="col-md-12">
                <div class="panel panel-info" style="border-radius: 8px; overflow: hidden;">
                    <div class="panel-heading" style="background: linear-gradient(135deg, #17a2b8 0%, #20c997 100%); border: none; color: white;">
                        <h6 style="margin: 0; font-weight: 600;">
                            <i class="fa fa-chart-bar"></i> Summary Statistics
                        </h6>
                    </div>
                    <div class="panel-body" style="padding: 20px; background-color: #f8f9fa;">
                        <div class="row text-center">
                            <div class="col-md-3">
                                <div class="stat-box" style="padding: 15px; background: white; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 24px; font-weight: bold; color: #007bff; margin-bottom: 5px;">${total_requests}</div>
                                    <div style="font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Total Requests</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="stat-box" style="padding: 15px; background: white; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 24px; font-weight: bold; color: #ffc107; margin-bottom: 5px;">${pending_requests}</div>
                                    <div style="font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Pending</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="stat-box" style="padding: 15px; background: white; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 24px; font-weight: bold; color: #fd7e14; margin-bottom: 5px;">${in_progress_requests}</div>
                                    <div style="font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">In Progress</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="stat-box" style="padding: 15px; background: white; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <div style="font-size: 24px; font-weight: bold; color: #28a745; margin-bottom: 5px;">${completed_requests}</div>
                                    <div style="font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Completed</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    html += `</div>`;

    // Add the HTML to the form
    frm.set_df_property('consumable_orders_html', 'options', html);
    frm.refresh_field('consumable_orders_html');
};

// Helper function to get request type color scheme
var get_request_type_color = function(request_type) {
    const type_colors = {
        'Consumable Request': {
            bg: '#007bff', bgLight: '#4dabf7', text: 'white', 
            icon: 'fa fa-cube', border: '#007bff',
            badgeBg: 'rgba(255,255,255,0.2)', badgeText: 'white'
        },
        'Blood Request': {
            bg: '#dc3545', bgLight: '#f56565', text: 'white',
            icon: 'fa fa-tint', border: '#dc3545',
            badgeBg: 'rgba(255,255,255,0.2)', badgeText: 'white'
        },
        'Medicine Request': {
            bg: '#28a745', bgLight: '#68d391', text: 'white',
            icon: 'fa fa-pills', border: '#28a745',
            badgeBg: 'rgba(255,255,255,0.2)', badgeText: 'white'
        }
    };
    return type_colors[request_type] || {
        bg: '#6c757d', bgLight: '#adb5bd', text: 'white',
        icon: 'fa fa-box', border: '#6c757d',
        badgeBg: 'rgba(255,255,255,0.2)', badgeText: 'white'
    };
};

// Helper function to get status color
var get_status_color = function(status) {
    const status_colors = {
        'Draft': 'default',
        'Submitted': 'info',
        'Pending': 'warning',
        'Partially Ordered': 'info',
        'Partially Received': 'info',
        'Ordered': 'primary',
        'Issued': 'success',
        'Transferred': 'success',
        'Received': 'success',
        'Stopped': 'danger',
        'Cancelled': 'danger'
    };
    return status_colors[status] || 'default';
};

// Helper function to get billing status color
var get_billing_color = function(billing_status) {
    const billing_colors = {
        'Pending': 'warning',
        'Partly Invoiced': 'info',
        'Invoiced': 'success'
    };
    return billing_colors[billing_status] || 'default';
};

// Global function to view consumer request items
window.view_consumer_request_items = function(consumer_request_name) {
    frappe.call({
        method: "healthcare.controllers.discharge_summary_consumer_requests.get_consumer_request_items",
        args: {
            consumer_request: consumer_request_name
        },
        callback: function(response) {
            if (response.message && response.message.length > 0) {
                show_consumer_request_items_dialog(consumer_request_name, response.message);
            } else {
                frappe.msgprint({
                    title: __('No Items Found'),
                    message: __('No items found for this Consumer Request.'),
                    indicator: 'blue'
                });
            }
        },
        error: function(err) {
            console.error("Error fetching items:", err);
            frappe.msgprint({
                title: __('Error'),
                message: __('Failed to fetch items. Please try again.'),
                indicator: 'red'
            });
        }
    });
};

// Global function to open consumer request
window.open_consumer_request = function(consumer_request_name) {
    frappe.set_route('Form', 'Consumer Request', consumer_request_name);
};

// Function to show consumer request items in a dialog
var show_consumer_request_items_dialog = function(consumer_request_name, items) {
    let dialog = new frappe.ui.Dialog({
        title: `Items in ${consumer_request_name}`,
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'items_html'
            }
        ]
    });

    let total_qty = items.reduce((sum, item) => sum + (item.qty || 0), 0);
    let invoiced_items = items.filter(item => item.invoiced).length;

    let items_html = `
        <div style="margin-bottom: 15px;">
            <div class="row">
                <div class="col-md-4">
                    <div class="alert alert-info" style="margin: 0; padding: 10px;">
                        <strong>Total Items:</strong> ${items.length}
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="alert alert-primary" style="margin: 0; padding: 10px;">
                        <strong>Total Quantity:</strong> ${total_qty}
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="alert alert-success" style="margin: 0; padding: 10px;">
                        <strong>Invoiced Items:</strong> ${invoiced_items}/${items.length}
                    </div>
                </div>
            </div>
        </div>
        <div class="table-responsive">
            <table class="table table-bordered table-striped" style="margin: 0;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="padding: 12px 8px; font-weight: 600;">Item Code</th>
                        <th style="padding: 12px 8px; font-weight: 600;">Item Name</th>
                        <th style="padding: 12px 8px; font-weight: 600; text-align: center;">Quantity</th>
                        <th style="padding: 12px 8px; font-weight: 600; text-align: center;">UOM</th>
                        <th style="padding: 12px 8px; font-weight: 600; text-align: center;">Required By</th>
                        <th style="padding: 12px 8px; font-weight: 600;">Source Warehouse</th>
                        <th style="padding: 12px 8px; font-weight: 600;">Target Warehouse</th>
                        <th style="padding: 12px 8px; font-weight: 600; text-align: center;">Status</th>
                    </tr>
                </thead>
                <tbody>
    `;

    items.forEach((item, index) => {
        let row_style = index % 2 === 0 ? 'background-color: #fafbfc;' : 'background-color: white;';
        items_html += `
            <tr style="${row_style}">
                <td style="padding: 12px 8px;">
                    <strong style="color: #007bff;">${item.item_code}</strong>
                    ${item.item_group ? `<br><small class="text-muted">${item.item_group}</small>` : ''}
                </td>
                <td style="padding: 12px 8px;">
                    ${item.item_name || '-'}
                    ${item.brand ? `<br><small class="text-muted">Brand: ${item.brand}</small>` : ''}
                </td>
                <td style="padding: 12px 8px; text-align: center;">
                    <span style="font-weight: 600; color: #333;">${item.qty || 0}</span>
                    ${item.qty_invoiced ? `<br><small class="text-success">Invoiced: ${item.qty_invoiced}</small>` : ''}
                </td>
                <td style="padding: 12px 8px; text-align: center;">${item.stock_uom || '-'}</td>
                <td style="padding: 12px 8px; text-align: center;">
                    ${item.schedule_date ? frappe.datetime.str_to_user(item.schedule_date) : '-'}
                </td>
                <td style="padding: 12px 8px;">
                    ${item.from_warehouse || '-'}
                    ${item.available_qty !== undefined ? `<br><small class="text-info">Available: ${item.available_qty}</small>` : ''}
                </td>
                <td style="padding: 12px 8px;">${item.warehouse || '-'}</td>
                <td style="padding: 12px 8px; text-align: center;">
                    <span class="label label-${item.invoiced ? 'success' : 'warning'}" style="font-size: 11px; padding: 4px 8px;">
                        ${item.invoiced ? 'Invoiced' : 'Pending'}
                    </span>
                </td>
            </tr>
        `;
    });

    items_html += `
                </tbody>
            </table>
        </div>
    `;

    dialog.fields_dict.items_html.$wrapper.html(items_html);
    dialog.show();
};

// Add some custom CSS for better styling
$(document).ready(function() {
    if (!$('#consumer-requests-styles').length) {
        $('<style id="consumer-requests-styles">')
            .html(`
                .consumer-request-item:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
                }
                .stat-box:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
                }
                .btn-xs {
                    font-size: 11px;
                    line-height: 1.2;
                }
                .consumer-requests-container {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif;
                }
            `)
            .appendTo('head');
    }
});