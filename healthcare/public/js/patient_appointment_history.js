// apps/healthcare/healthcare/public/js/patient_appointment_history.js
// Standalone Patient Appointment History feature for ERPNext Healthcare

frappe.provide('healthcare.patient_appointment_history');

// Main namespace for the appointment history functionality
healthcare.patient_appointment_history = {
    
    // Initialize the feature - call this from your main form
    init: function(frm) {
        this.setup_buttons(frm);
    },
    
    // Setup buttons in the form
    setup_buttons: function(frm) {
        if (frm.doc.patient && !frm.doc.__islocal) {
            // Add the Appointment History button under the View menu, after Patient History
            frm.add_custom_button(__('Appointment History'), function() {
                healthcare.patient_appointment_history.show_history_dialog(frm);
            }, __('View'));
            
            // Optional: Reorder buttons to ensure Appointment History comes after Patient History
            // This ensures consistent positioning
            setTimeout(function() {
                let view_menu = frm.page.btn_secondary.find('.btn-group .dropdown-menu');
                let appointment_history_btn = view_menu.find('a:contains("Appointment History")').parent();
                let patient_history_btn = view_menu.find('a:contains("Patient History")').parent();
                
                if (appointment_history_btn.length && patient_history_btn.length) {
                    appointment_history_btn.insertAfter(patient_history_btn);
                }
            }, 100);
        }
    },
    
    // Main function to show patient appointment history
    show_history_dialog: function(frm) {
        if (!frm.doc.patient) {
            frappe.msgprint({
                title: __('Patient Required'),
                message: __('Please select a patient first'),
                indicator: 'red'
            });
            return;
        }

        frappe.call({
            method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment_history.get_patient_appointment_history',
            args: {
                patient: frm.doc.patient
            },
            callback: function(r) {
                if (r.message) {
                    healthcare.patient_appointment_history.render_dialog(r.message, frm);
                } else {
                    frappe.msgprint({
                        title: __('No Data'),
                        message: __('No appointment history found for this patient'),
                        indicator: 'yellow'
                    });
                }
            },
            freeze: true,
            freeze_message: __('Loading appointment history...')
        });
    },

    // Function to render the appointment history dialog
    render_dialog: function(data, frm) {
        let dialog = new frappe.ui.Dialog({
            title: __('Appointment History - {0}', [data.patient_info.patient_name]),
            size: 'extra-large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'summary_section'
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    fieldtype: 'HTML', 
                    fieldname: 'appointments_table'
                }
            ],
            primary_action_label: __('Close'),
            primary_action: function() {
                dialog.hide();
            }
        });

        // Store data in dialog for later use
        dialog.appointment_data = data;
        dialog.source_frm = frm;

        // Render summary section
        healthcare.patient_appointment_history.render_summary(dialog, data);
        
        // Render appointments table
        healthcare.patient_appointment_history.render_table(dialog, data, frm);

        dialog.show();
        
        // Store dialog reference for action functions
        healthcare.patient_appointment_history.current_dialog = dialog;
    },

    // Function to render summary statistics
    render_summary: function(dialog, data) {
        let summary_html = '<div class="appointment-history-summary" style="margin-bottom: 20px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">';
        summary_html += '<div class="row">';
        summary_html += '<div class="col-md-8">';
        summary_html += '<h4 style="margin-bottom: 20px; color: white; font-weight: 600;">';
        summary_html += '<i class="fa fa-user-circle" style="margin-right: 10px; font-size: 1.2em;"></i>' + data.patient_info.patient_name;
        summary_html += '<small style="opacity: 0.8; font-weight: normal; margin-left: 10px;">(' + data.patient_info.name + ')</small>';
        summary_html += '</h4>';
        summary_html += '<div class="row text-center">';
        
        // Total appointments
        summary_html += '<div class="col-md-3">';
        summary_html += '<div class="stat-card" style="padding: 15px; background: rgba(255,255,255,0.15); border-radius: 10px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);">';
        summary_html += '<div class="h3" style="margin-bottom: 5px; font-weight: 700; color: white;">' + data.stats.total_appointments + '</div>';
        summary_html += '<small style="color: rgba(255,255,255,0.9); font-size: 12px;">Total Appointments</small>';
        summary_html += '</div></div>';
        
        // Completed appointments
        summary_html += '<div class="col-md-3">';
        summary_html += '<div class="stat-card" style="padding: 15px; background: rgba(255,255,255,0.15); border-radius: 10px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);">';
        summary_html += '<div class="h3" style="margin-bottom: 5px; font-weight: 700; color: white;">' + data.stats.completed_appointments + '</div>';
        summary_html += '<small style="color: rgba(255,255,255,0.9); font-size: 12px;">Completed</small>';
        summary_html += '</div></div>';
        
        // Upcoming appointments
        summary_html += '<div class="col-md-3">';
        summary_html += '<div class="stat-card" style="padding: 15px; background: rgba(255,255,255,0.15); border-radius: 10px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);">';
        summary_html += '<div class="h3" style="margin-bottom: 5px; font-weight: 700; color: white;">' + data.stats.upcoming_appointments + '</div>';
        summary_html += '<small style="color: rgba(255,255,255,0.9); font-size: 12px;">Upcoming</small>';
        summary_html += '</div></div>';
        
        // Cancelled appointments
        summary_html += '<div class="col-md-3">';
        summary_html += '<div class="stat-card" style="padding: 15px; background: rgba(255,255,255,0.15); border-radius: 10px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);">';
        summary_html += '<div class="h3" style="margin-bottom: 5px; font-weight: 700; color: white;">' + data.stats.cancelled_appointments + '</div>';
        summary_html += '<small style="color: rgba(255,255,255,0.9); font-size: 12px;">Cancelled</small>';
        summary_html += '</div></div>';
        
        summary_html += '</div></div>';
        
        // Right column with payment info
        summary_html += '<div class="col-md-4">';
        summary_html += '<div class="text-right" style="padding: 20px;">';
        summary_html += '<div class="h4" style="margin-bottom: 10px; font-weight: 600; color: white;">';
        summary_html += '<i class="fa fa-money" style="margin-right: 8px;"></i>';
        summary_html += healthcare.patient_appointment_history.format_currency(data.stats.total_paid);
        summary_html += '</div>';
        summary_html += '<small style="color: rgba(255,255,255,0.9);">Total Amount Paid</small>';
        
        summary_html += '<div style="margin-top: 20px;">';
        summary_html += '<div style="margin-bottom: 8px;">';
        summary_html += '<span class="badge" style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 20px; font-size: 11px;">';
        summary_html += '<i class="fa fa-user-md"></i> ' + data.stats.practitioner_appointments + ' Practitioner';
        summary_html += '</span></div>';
        
        summary_html += '<div style="margin-bottom: 8px;">';
        summary_html += '<span class="badge" style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 20px; font-size: 11px;">';
        summary_html += '<i class="fa fa-building"></i> ' + data.stats.department_appointments + ' Department';
        summary_html += '</span></div>';
        
        summary_html += '<div>';
        summary_html += '<span class="badge" style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 20px; font-size: 11px;">';
        summary_html += '<i class="fa fa-hospital-o"></i> ' + data.stats.service_unit_appointments + ' Service Unit';
        summary_html += '</span></div>';
        summary_html += '</div></div></div>';
        
        summary_html += '</div></div>';
        
        dialog.fields_dict.summary_section.$wrapper.html(summary_html);
    },

    // Function to render appointments table
    render_table: function(dialog, data, frm) {
        if (data.appointments.length === 0) {
            let empty_html = '<div class="text-center" style="padding: 60px; background: #f8f9fa; border-radius: 12px; border: 2px dashed #dee2e6;">';
            empty_html += '<i class="fa fa-calendar-times-o fa-4x text-muted" style="margin-bottom: 20px;"></i>';
            empty_html += '<h4 class="text-muted">No Appointments Found</h4>';
            empty_html += '<p class="text-muted">This patient has no appointment history.</p>';
            empty_html += '<button class="btn btn-primary btn-sm" onclick="frappe.new_doc(\'Patient Appointment\', {patient: \'' + data.patient_info.name + '\'})">';
            empty_html += '<i class="fa fa-plus"></i> Create First Appointment';
            empty_html += '</button></div>';
            
            dialog.fields_dict.appointments_table.$wrapper.html(empty_html);
            return;
        }

        let table_html = '<div class="appointment-history-table">';
        table_html += '<div class="form-group" style="margin-bottom: 20px;">';
        table_html += '<div class="clearfix">';
        table_html += '<label class="control-label" style="margin-right: 15px; font-weight: 600; color: #333; font-size: 16px;">';
        table_html += '<i class="fa fa-list-alt"></i> ' + __('Appointment History') + ' ';
        table_html += '<span class="badge badge-primary" style="background: #5e72e4; margin-left: 8px;">' + data.appointments.length + '</span>';
        table_html += '</label>';
        table_html += '<div class="pull-right">';
        table_html += '<button class="btn btn-sm btn-default" onclick="healthcare.patient_appointment_history.export_data()" style="margin-right: 10px;">';
        table_html += '<i class="fa fa-download"></i> ' + __('Export CSV') + '</button>';
        table_html += '<button class="btn btn-sm btn-success" onclick="frappe.new_doc(\'Patient Appointment\', {patient: \'' + data.patient_info.name + '\'})">';
        table_html += '<i class="fa fa-plus"></i> ' + __('New Appointment') + '</button>';
        table_html += '</div></div></div>';

        table_html += '<div class="table-responsive" style="max-height: 550px; overflow-y: auto; border: 1px solid #e9ecef; border-radius: 8px;">';
        table_html += '<table class="table table-striped table-hover" style="margin-bottom: 0; font-size: 13px;">';
        table_html += '<thead style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); position: sticky; top: 0; z-index: 10;">';
        table_html += '<tr>';
        table_html += '<th width="14%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Date & Time') + '</th>';
        table_html += '<th width="16%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Appointment Type') + '</th>';
        table_html += '<th width="22%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Provider') + '</th>';
        table_html += '<th width="10%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Duration') + '</th>';
        table_html += '<th width="12%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Status') + '</th>';
        table_html += '<th width="12%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Payment') + '</th>';
        table_html += '<th width="8%" style="font-weight: 600; padding: 12px 8px; border-bottom: 2px solid #dee2e6;">' + __('Actions') + '</th>';
        table_html += '</tr></thead><tbody>';

        data.appointments.forEach(function(appointment, index) {
            let row_style = 'cursor: pointer; transition: all 0.2s ease; border-left: 4px solid ' + (appointment.appointment_type_color || '#e9ecef') + ';';
            
            table_html += '<tr data-appointment="' + appointment.name + '" style="' + row_style + '" ';
            table_html += 'onmouseover="this.style.backgroundColor=\'#f8f9fa\'; this.style.transform=\'translateX(2px)\'" ';
            table_html += 'onmouseout="this.style.backgroundColor=\'\'; this.style.transform=\'translateX(0)\'">';
            
            // Date & Time column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle;">';
            table_html += '<div style="line-height: 1.4;">';
            table_html += '<strong style="color: #495057; font-size: 13px;">' + appointment.formatted_date + '</strong><br>';
            table_html += '<small class="text-muted"><i class="fa fa-clock-o" style="margin-right: 4px;"></i>' + appointment.formatted_time + '</small>';
            table_html += '</div></td>';
            
            // Appointment Type column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle;">';
            table_html += '<div style="display: flex; align-items: center; line-height: 1.4;">';
            table_html += '<div style="width: 12px; height: 12px; background-color: ' + (appointment.appointment_type_color || '#ccc') + '; border-radius: 50%; margin-right: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"></div>';
            table_html += '<div><span style="font-weight: 500; color: #495057;">' + (appointment.appointment_type || 'Not Set') + '</span></div>';
            table_html += '</div></td>';
            
            // Provider column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle;">';
            table_html += '<div style="display: flex; align-items: center; line-height: 1.4;">';
            table_html += '<div style="width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 12px;">';
            table_html += '<i class="fa ' + appointment.provider_icon + '" style="color: white; font-size: 14px;"></i>';
            table_html += '</div>';
            table_html += '<div>';
            table_html += '<div style="font-weight: 500; color: #495057; margin-bottom: 2px;">' + appointment.primary_provider + '</div>';
            table_html += '<small class="text-muted" style="font-size: 11px;">' + appointment.provider_type + '</small>';
            table_html += '</div></div></td>';
            
            // Duration column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle;">';
            table_html += '<span class="badge" style="background: #e3f2fd; color: #1976d2; padding: 6px 10px; border-radius: 12px; font-weight: 500; font-size: 11px;">';
            table_html += '<i class="fa fa-hourglass-half" style="margin-right: 4px;"></i>' + appointment.duration_display;
            table_html += '</span></td>';
            
            // Status column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle;">';
            table_html += '<span class="label" style="background-color: ' + appointment.status_color + '; color: white; padding: 6px 12px; border-radius: 15px; font-size: 11px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">';
            table_html += appointment.status + '</span></td>';
            
            // Payment column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle;">';
            table_html += '<div style="line-height: 1.4;">';
            let payment_class = appointment.payment_color === 'green' ? 'badge-success' : 'badge-warning';
            let payment_icon = appointment.payment_color === 'green' ? 'fa-check' : 'fa-clock-o';
            table_html += '<span class="badge ' + payment_class + '" style="font-size: 10px; padding: 4px 8px; margin-bottom: 4px;">';
            table_html += '<i class="fa ' + payment_icon + '" style="margin-right: 3px;"></i>' + appointment.payment_status + '</span>';
            if (appointment.paid_amount) {
                table_html += '<div style="margin-top: 3px;"><small style="font-weight: 600; color: #28a745;">';
                table_html += healthcare.patient_appointment_history.format_currency(appointment.paid_amount) + '</small></div>';
            }
            table_html += '</div></td>';
            
            // Actions column
            table_html += '<td style="padding: 12px 8px; vertical-align: middle; position: relative;">';
            table_html += '<div class="dropdown">';
            table_html += '<button class="btn btn-xs btn-default dropdown-toggle" data-toggle="dropdown" style="padding: 4px 8px; border-radius: 15px; border: 1px solid #dee2e6;">';
            table_html += '<i class="fa fa-ellipsis-v"></i></button>';
            table_html += '<ul class="dropdown-menu dropdown-menu-right" style="min-width: 180px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); z-index: 9999;">';
            
            // View Details
            table_html += '<li><a href="#" onclick="healthcare.patient_appointment_history.view_appointment(\'' + appointment.name + '\')" style="padding: 10px 16px; display: block; text-decoration: none; color: #495057;">';
            table_html += '<i class="fa fa-eye" style="width: 20px; color: #007bff; margin-right: 8px;"></i> ' + __('View Details') + '</a></li>';
            
            // Reschedule (conditional)
            if (appointment.can_reschedule) {
                table_html += '<li><a href="#" onclick="healthcare.patient_appointment_history.reschedule_appointment(\'' + appointment.name + '\')" style="padding: 10px 16px; display: block; text-decoration: none; color: #495057;">';
                table_html += '<i class="fa fa-calendar" style="width: 20px; color: #17a2b8; margin-right: 8px;"></i> ' + __('Reschedule') + '</a></li>';
            }
            
            // Create Encounter (conditional)
            if (appointment.can_create_encounter) {
                table_html += '<li><a href="#" onclick="healthcare.patient_appointment_history.create_encounter(\'' + appointment.name + '\')" style="padding: 10px 16px; display: block; text-decoration: none; color: #495057;">';
                table_html += '<i class="fa fa-stethoscope" style="width: 20px; color: #28a745; margin-right: 8px;"></i> ' + __('Create Encounter') + '</a></li>';
            }
            
            // View Invoice (conditional)
            if (appointment.ref_sales_invoice) {
                table_html += '<li><a href="#" onclick="healthcare.patient_appointment_history.view_invoice(\'' + appointment.ref_sales_invoice + '\')" style="padding: 10px 16px; display: block; text-decoration: none; color: #495057;">';
                table_html += '<i class="fa fa-file-text-o" style="width: 20px; color: #6c757d; margin-right: 8px;"></i> ' + __('View Invoice') + '</a></li>';
            }
            
            // View Notes (conditional)
            if (appointment.notes) {
                let safe_notes = healthcare.patient_appointment_history.escape_quotes(appointment.notes);
                table_html += '<li><a href="#" onclick="healthcare.patient_appointment_history.show_notes(\'' + safe_notes + '\')" style="padding: 10px 16px; display: block; text-decoration: none; color: #495057;">';
                table_html += '<i class="fa fa-sticky-note-o" style="width: 20px; color: #ffc107; margin-right: 8px;"></i> ' + __('View Notes') + '</a></li>';
            }
            
            table_html += '</ul></div></td></tr>';
        });

        table_html += '</tbody></table></div>';
        table_html += '<div style="margin-top: 15px; padding: 12px 16px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #5e72e4;">';
        table_html += '<small style="color: #6c757d;"><i class="fa fa-info-circle" style="margin-right: 8px; color: #5e72e4;"></i> ';
        table_html += __('Click on any appointment row for quick view, or use the actions menu for specific operations.') + '</small>';
        table_html += '</div></div>';

        dialog.fields_dict.appointments_table.$wrapper.html(table_html);
        
        // Add click event for rows
        dialog.fields_dict.appointments_table.$wrapper.find('tr[data-appointment]').on('click', function(e) {
            if (!$(e.target).closest('.dropdown, .btn-group').length) {
                let appointment_name = $(this).data('appointment');
                healthcare.patient_appointment_history.view_appointment(appointment_name);
            }
        });
    },

    // Action functions
    view_appointment: function(appointment_name) {
        frappe.set_route('Form', 'Patient Appointment', appointment_name);
        if (healthcare.patient_appointment_history.current_dialog) {
            healthcare.patient_appointment_history.current_dialog.hide();
        }
    },

    reschedule_appointment: function(appointment_name) {
        if (healthcare.patient_appointment_history.current_dialog) {
            healthcare.patient_appointment_history.current_dialog.hide();
        }
        
        frappe.set_route('Form', 'Patient Appointment', appointment_name);
        
        // Show helpful message after a delay
        setTimeout(function() {
            frappe.show_alert({
                message: __('Use the "Check Availability" or "Reschedule" button to reschedule this appointment'),
                indicator: 'blue'
            });
        }, 1000);
    },

    create_encounter: function(appointment_name) {
        frappe.model.open_mapped_doc({
            method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.make_encounter',
            source_name: appointment_name
        });
        if (healthcare.patient_appointment_history.current_dialog) {
            healthcare.patient_appointment_history.current_dialog.hide();
        }
    },

    view_invoice: function(invoice_name) {
        frappe.set_route('Form', 'Sales Invoice', invoice_name);
        if (healthcare.patient_appointment_history.current_dialog) {
            healthcare.patient_appointment_history.current_dialog.hide();
        }
    },

    show_notes: function(notes) {
        frappe.msgprint({
            title: __('Appointment Notes'),
            message: '<div style="max-height: 300px; overflow-y: auto; padding: 10px; background: #f8f9fa; border-radius: 6px; white-space: pre-wrap;">' + notes + '</div>',
            indicator: 'blue'
        });
    },

    export_data: function() {
        if (!healthcare.patient_appointment_history.current_dialog || 
            !healthcare.patient_appointment_history.current_dialog.appointment_data) {
            frappe.msgprint(__('No data available to export'));
            return;
        }

        let data = healthcare.patient_appointment_history.current_dialog.appointment_data;
        let csv_content = "Date,Time,Appointment Type,Provider Type,Provider Name,Duration,Status,Payment Status,Amount,Notes\n";
        
        data.appointments.forEach(function(appointment) {
            let notes = (appointment.notes || '').replace(/"/g, '""').replace(/\n/g, ' ').replace(/\r/g, ' ');
            let row = [
                appointment.formatted_date,
                appointment.formatted_time,
                appointment.appointment_type || '',
                appointment.provider_type,
                appointment.primary_provider,
                appointment.duration_display,
                appointment.status,
                appointment.payment_status,
                appointment.paid_amount || '0',
                notes
            ];
            csv_content += row.map(field => '"' + field + '"').join(',') + '\n';
        });

        // Create and download file
        let blob = new Blob([csv_content], { type: 'text/csv;charset=utf-8;' });
        let url = window.URL.createObjectURL(blob);
        let a = document.createElement('a');
        a.href = url;
        a.download = data.patient_info.name + '_appointment_history_' + frappe.datetime.now_date() + '.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        frappe.show_alert({
            message: __('Appointment history exported successfully'),
            indicator: 'green'
        });
    },

    // Helper function for currency formatting
    format_currency: function(amount) {
        if (!amount) return '₹0';
        return '₹' + parseFloat(amount).toLocaleString('en-IN', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2
        });
    },

    // Helper function to escape quotes and special characters
    escape_quotes: function(str) {
        if (!str) return '';
        return str.replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, ' ').replace(/\r/g, ' ');
    }
};

// Integration with Patient Appointment forms
frappe.ui.form.on('Patient Appointment', {
    refresh: function(frm) {
        // Add small delay to ensure other refresh events complete first
        setTimeout(function() {
            healthcare.patient_appointment_history.init(frm);
        }, 300);
    },
    
    patient: function(frm) {
        // Re-initialize when patient changes
        setTimeout(function() {
            healthcare.patient_appointment_history.init(frm);
        }, 100);
    }
});