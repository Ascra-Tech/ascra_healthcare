// Healthcare
frappe.ui.form.on('Sales Invoice', {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.doc.is_return) {
			frm.add_custom_button(__('Healthcare Services'), function() {
				frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					let link_customer = null;
					let msg = "Patient is not linked to a customer. Do you want to link the selected customer to the patient permanently?";
					if (r.message.customer){
						get_healthcare_services_to_invoice(frm, link_customer);
					} else {
						frappe.confirm(msg,
							() => {
								link_customer = true;
								get_healthcare_services_to_invoice(frm, link_customer);
							}, () => {
								get_healthcare_services_to_invoice(frm, link_customer);
						})
					}
				})
			},__('Get Items From'));
			frm.add_custom_button(__('Prescriptions'), function() {
				frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					let link_customer = null;
					let msg = "Patient is not linked to a customer. Do you want to link the selected customer to the patient permanently?";
					if (r.message.customer){
						get_drugs_to_invoice(frm, link_customer);
					} else {
						frappe.confirm(msg,
							() => {
								link_customer = true;
								get_drugs_to_invoice(frm, link_customer);
							}, () => {
								get_drugs_to_invoice(frm, link_customer);
						})
					}
				})
			},__('Get Items From'));
		}
	},

	patient(frm) {
		if (frm.doc.patient) {
			frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					if (!r.exc && r.message.customer) {
						frm.set_value("customer", r.message.customer);
					} else {
						frappe.show_alert({
							indicator: "warning",
							message: __("Patient <b>{0}</b> is not linked to a Customer",
								[`<a class='bold' href='/app/patient/${frm.doc.patient}'>${frm.doc.patient}</a>`]
							),
						});
						frm.set_value("customer", "");
					}
					frm.set_df_property("customer", "read_only", frm.doc.customer ? 1 : 0);
				})
		} else {
			frm.set_value("customer", "");
			frm.set_df_property("customer", "read_only", 0);
		}
	},

	service_unit: function (frm) {
		set_service_unit(frm);
	},

	items_add: function (frm) {
		set_service_unit(frm);
	}
});

var set_service_unit = function (frm) {
	if (frm.doc.service_unit && frm.doc.items.length > 0) {
		frm.doc.items.forEach((item) => {
			if (!item.service_unit) {
				frappe.model.set_value(item.doctype, item.name, "service_unit", frm.doc.service_unit);
			}
		});
	}
};

var get_healthcare_services_to_invoice = function(frm, link_customer) {
	var me = this;
	let selected_patient = '';
	var dialog = new frappe.ui.Dialog({
		title: __("Get Items from Healthcare Services"),
		fields:[
			{
				fieldtype: 'Link',
				options: 'Patient',
				label: 'Patient',
				fieldname: "patient",
				reqd: true
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'results_area' }
		]
	});
	var $wrapper;
	var $results;
	var $placeholder;
	dialog.set_values({
		'patient': frm.doc.patient
	});
	
	// Trigger the API call immediately after dialog is set up with initial patient value
	if (frm.doc.patient) {
		selected_patient = frm.doc.patient;
		var method = "healthcare.healthcare.utils.get_healthcare_services_to_invoice";
		var args = {patient: selected_patient, customer: frm.doc.customer, company: frm.doc.company, link_customer: link_customer};
		var columns = (["service", "reference_name", "reference_type"]);
		
		// Wait for the dialog to fully render before making the API call
		setTimeout(function() {
			get_healthcare_items(frm, true, $results, $placeholder, method, args, columns);
		}, 300);
	}
	
	dialog.fields_dict["patient"].df.onchange = () => {
		var patient = dialog.get_value("patient");
		if(patient && patient!=selected_patient){
			selected_patient = patient;
			
			// Get customer linked to this patient before making the API call
			frappe.db.get_value("Patient", patient, "customer")
				.then(r => {
					let customer = r.message.customer || frm.doc.customer;
					var method = "healthcare.healthcare.utils.get_healthcare_services_to_invoice";
					var args = {patient: patient, customer: customer, company: frm.doc.company, link_customer: link_customer};
					var columns = (["service", "reference_name", "reference_type"]);
					get_healthcare_items(frm, true, $results, $placeholder, method, args, columns);
				});
		}
		else if(!patient){
			selected_patient = '';
			$results.empty();
			$results.append($placeholder);
		}
	}
	$wrapper = dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
		style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
	$results = $wrapper.find('.results');
	$placeholder = $(`<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x fa-heartbeat text-extra-muted"></i>
					<p class="text-extra-muted">No billable Healthcare Services found</p>
				</span>
			</div>`);
	$results.on('click', '.list-item--head :checkbox', (e) => {
		$results.find('.list-item-container .list-row-check')
			.prop("checked", ($(e.target).is(':checked')));
	});
	set_primary_action(frm, dialog, $results, true);
	dialog.show();
};

var get_healthcare_items = function(frm, invoice_healthcare_services, $results, $placeholder, method, args, columns) {
	var me = this;
	$results.empty();
	frappe.call({
		method: method,
		args: args,
		callback: function(data) {
			if(data.message){
				$results.append(make_list_row(columns, invoice_healthcare_services));
				for(let i=0; i<data.message.length; i++){
					$results.append(make_list_row(columns, invoice_healthcare_services, data.message[i]));
				}
			}else {
				$results.append($placeholder);
			}
		}
	});
}

var make_list_row= function(columns, invoice_healthcare_services, result={}) {
	var me = this;
	// Make a head row by default (if result not passed)
	let head = Object.keys(result).length === 0;
	let contents = ``;
	columns.forEach(function(column) {
		contents += `<div class="list-item__content ellipsis">
			${
				head ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`
				:(column !== "name" ? `<span class="ellipsis">${__(result[column])}</span>`
					: `<a class="list-id ellipsis">
						${__(result[column])}</a>`)
			}
		</div>`;
	})

	let $row = $(`<div class="list-item">
		<div class="list-item__content" style="flex: 0 0 10px;">
			<input type="checkbox" class="list-row-check" ${result.checked ? 'checked' : ''}>
		</div>
		${contents}
	</div>`);

	$row = list_row_data_items(head, $row, result, invoice_healthcare_services);
	return $row;
};

var set_primary_action = function(frm, dialog, $results, invoice_healthcare_services) {
    var me = this;
    dialog.set_primary_action(__('Add'), function() {
        frm.clear_table('items');
        let checked_values = get_checked_values($results);
        if(checked_values.length > 0){
            // Get the patient from the dialog
            let selected_patient = dialog.get_value("patient");
            
            // Set the patient in the form
            frm.set_value("patient", selected_patient);
            
            // At this point, the patient(frm) trigger will execute and set the customer automatically
            // We just need to wait for it to finish, then add the items
            setTimeout(function() {
                if (frm.doc.customer) {
                    add_to_item_line(frm, checked_values, invoice_healthcare_services);
                    dialog.hide();
                } else {
                    frappe.msgprint(__("Patient {0} is not linked to a customer. Please select a customer before adding items.", [selected_patient]));
                }
            }, 500);
        }
        else{
            if(invoice_healthcare_services){
                frappe.msgprint(__("Please select Healthcare Service"));
            }
            else{
                frappe.msgprint(__("Please select Drug"));
            }
        }
    });
};

var get_checked_values= function($results) {
	return $results.find('.list-item-container').map(function() {
		let checked_values = {};
		if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
			checked_values['dn'] = $(this).attr('data-dn');
			checked_values['dt'] = $(this).attr('data-dt');
			checked_values['item'] = $(this).attr('data-item');
			if($(this).attr('data-rate') != 'undefined'){
				checked_values['rate'] = $(this).attr('data-rate');
			}
			else{
				checked_values['rate'] = false;
			}
			if($(this).attr('data-income-account') != 'undefined'){
				checked_values['income_account'] = $(this).attr('data-income-account');
			}
			else{
				checked_values['income_account'] = false;
			}
			if($(this).attr('data-qty') != 'undefined'){
				checked_values['qty'] = $(this).attr('data-qty');
			}
			else{
				checked_values['qty'] = false;
			}
			if($(this).attr('data-description') != 'undefined'){
				checked_values['description'] = $(this).attr('data-description');
			}
			else{
				checked_values['description'] = false;
			}
			return checked_values;
		}
	}).get();
};

var get_drugs_to_invoice = function(frm, link_customer) {
	var me = this;
	let selected_encounter = '';
	let selected_patient = '';
	var dialog = new frappe.ui.Dialog({
		title: __("Get Items from Medication Requests"),
		fields:[
			{ fieldtype: 'Link', options: 'Patient', label: 'Patient', fieldname: "patient", reqd: true },
			{ fieldtype: 'Link', options: 'Patient Encounter', label: 'Patient Encounter', fieldname: "encounter", reqd: true,
				description:'Quantity will be calculated only for items which has "Nos" as UoM. You may change as required for each invoice item.',
				get_query: function(doc) {
					return {
						filters: {
							patient: dialog.get_value("patient"),
							company: frm.doc.company,
							docstatus: 1
						}
					};
				}
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'results_area' }
		]
	});
	var $wrapper;
	var $results;
	var $placeholder;
	dialog.set_values({
		'patient': frm.doc.patient,
		'encounter': ""
	});
	
	// Save the initial patient value
	if (frm.doc.patient) {
		selected_patient = frm.doc.patient;
	}
	
	dialog.fields_dict["patient"].df.onchange = () => {
		var patient = dialog.get_value("patient");
		if (patient != selected_patient) {
			selected_patient = patient;
			dialog.set_value("encounter", "");
			selected_encounter = '';
		}
	};
	
	dialog.fields_dict["encounter"].df.onchange = () => {
		var encounter = dialog.fields_dict.encounter.input.value;
		if(encounter && encounter!=selected_encounter){
			selected_encounter = encounter;
			
			// Get customer linked to this patient before making the API call
			frappe.db.get_value("Patient", dialog.get_value("patient"), "customer")
				.then(r => {
					let customer = r.message.customer || frm.doc.customer;
					var method = "healthcare.healthcare.utils.get_drugs_to_invoice";
					var args = {encounter: encounter, customer: customer, link_customer: link_customer};
					var columns = (["drug_code", "quantity", "description"]);
					get_healthcare_items(frm, false, $results, $placeholder, method, args, columns);
				});
		}
		else if(!encounter){
			selected_encounter = '';
			$results.empty();
			$results.append($placeholder);
		}
	}
	$wrapper = dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
		style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
	$results = $wrapper.find('.results');
	$placeholder = $(`<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x fa-heartbeat text-extra-muted"></i>
					<p class="text-extra-muted">No Drug Prescription found</p>
				</span>
			</div>`);
	$results.on('click', '.list-item--head :checkbox', (e) => {
		$results.find('.list-item-container .list-row-check')
			.prop("checked", ($(e.target).is(':checked')));
	});
	set_primary_action(frm, dialog, $results, false);
	dialog.show();
};

var list_row_data_items = function(head, $row, result, invoice_healthcare_services) {
	if(invoice_healthcare_services){
		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container"
				data-dn= "${result.reference_name}" data-dt= "${result.reference_type}" data-item= "${result.service}"
				data-rate = ${result.rate}
				data-income-account = "${result.income_account}"
				data-qty = ${result.qty}
				data-description = "${result.description}">
				</div>`).append($row);
	}
	else{
		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container"
				data-item= "${result.drug_code}"
				data-qty = ${result.quantity}
				data-dn= "${result.reference_name}"
				data-dt= "${result.reference_type}"
				data-rate = ${result.rate}
				data-description = "${result.description}">
				</div>`).append($row);
	}
	return $row
};

var add_to_item_line = function(frm, checked_values, invoice_healthcare_services){
	if(invoice_healthcare_services){
		frappe.call({
			doc: frm.doc,
			method: "set_healthcare_services",
			args:{
				checked_values: checked_values
			},
			callback: function() {
				frm.trigger("validate");
				frm.refresh_fields();
			}
		});
	}
	else{
		for(let i=0; i<checked_values.length; i++){
			var si_item = frappe.model.add_child(frm.doc, 'Sales Invoice Item', 'items');
			frappe.model.set_value(si_item.doctype, si_item.name, 'item_code', checked_values[i]['item']);
			frappe.model.set_value(si_item.doctype, si_item.name, 'qty', 1);
			frappe.model.set_value(si_item.doctype, si_item.name, 'reference_dn', checked_values[i]['dn']);
			frappe.model.set_value(si_item.doctype, si_item.name, 'reference_dt', checked_values[i]['dt']);
			if(checked_values[i]['qty'] > 1){
				frappe.model.set_value(si_item.doctype, si_item.name, 'qty', parseFloat(checked_values[i]['qty']));
			}
		}
		frm.refresh_fields();
	}
};

// Complete Client-Side Script for Consumer Requests in Sales Invoice
// Replace your existing Consumer Requests code with this

// Update the refresh function to include Consumer Requests button
frappe.ui.form.on('Sales Invoice', {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.doc.is_return) {
			// Existing Healthcare Services button
			frm.add_custom_button(__('Healthcare Services'), function() {
				frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					let link_customer = null;
					let msg = "Patient is not linked to a customer. Do you want to link the selected customer to the patient permanently?";
					if (r.message.customer){
						get_healthcare_services_to_invoice(frm, link_customer);
					} else {
						frappe.confirm(msg,
							() => {
								link_customer = true;
								get_healthcare_services_to_invoice(frm, link_customer);
							}, () => {
								get_healthcare_services_to_invoice(frm, link_customer);
						})
					}
				})
			},__('Get Items From'));

			// Existing Prescriptions button
			frm.add_custom_button(__('Prescriptions'), function() {
				frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					let link_customer = null;
					let msg = "Patient is not linked to a customer. Do you want to link the selected customer to the patient permanently?";
					if (r.message.customer){
						get_drugs_to_invoice(frm, link_customer);
					} else {
						frappe.confirm(msg,
							() => {
								link_customer = true;
								get_drugs_to_invoice(frm, link_customer);
							}, () => {
								get_drugs_to_invoice(frm, link_customer);
						})
					}
				})
			},__('Get Items From'));

			// Consumer Requests button
			frm.add_custom_button(__('Consumer Requests'), function() {
				frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					let link_customer = null;
					let msg = "Patient is not linked to a customer. Do you want to link the selected customer to the patient permanently?";
					if (r.message && r.message.customer){
						get_consumer_requests_to_invoice(frm, link_customer);
					} else {
						frappe.confirm(msg,
							() => {
								link_customer = true;
								get_consumer_requests_to_invoice(frm, link_customer);
							}, () => {
								get_consumer_requests_to_invoice(frm, link_customer);
						})
					}
				})
			},__('Get Items From'));
		}
	},

	patient(frm) {
		if (frm.doc.patient) {
			frappe.db.get_value("Patient", frm.doc.patient, "customer")
				.then(r => {
					if (!r.exc && r.message && r.message.customer) {
						frm.set_value("customer", r.message.customer);
					} else {
						frappe.show_alert({
							indicator: "warning",
							message: __("Patient <b>{0}</b> is not linked to a Customer",
								[`<a class='bold' href='/app/patient/${frm.doc.patient}'>${frm.doc.patient}</a>`]
							),
						});
						frm.set_value("customer", "");
					}
					frm.set_df_property("customer", "read_only", frm.doc.customer ? 1 : 0);
				})
		} else {
			frm.set_value("customer", "");
			frm.set_df_property("customer", "read_only", 0);
		}
	},

	service_unit: function (frm) {
		set_service_unit(frm);
	},

	items_add: function (frm) {
		set_service_unit(frm);
	}
});

var set_service_unit = function (frm) {
	if (frm.doc.service_unit && frm.doc.items.length > 0) {
		frm.doc.items.forEach((item) => {
			if (!item.service_unit) {
				frappe.model.set_value(item.doctype, item.name, "service_unit", frm.doc.service_unit);
			}
		});
	}
};

// Consumer Requests functionality
var get_consumer_requests_to_invoice = function(frm, link_customer) {
	var me = this;
	let selected_patient = '';
	var dialog = new frappe.ui.Dialog({
		title: __("Get Items from Consumer Requests"),
		fields:[
			{
				fieldtype: 'Link',
				options: 'Patient',
				label: 'Patient',
				fieldname: "patient",
				reqd: true
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'results_area' }
		]
	});
	var $wrapper;
	var $results;
	var $placeholder;
	dialog.set_values({
		'patient': frm.doc.patient
	});
	
	// Trigger the API call immediately after dialog is set up with initial patient value
	if (frm.doc.patient) {
		selected_patient = frm.doc.patient;
		var method = "healthcare.controllers.sales_invoice_consumer.get_consumer_requests_to_invoice";
		var args = {patient: selected_patient, customer: frm.doc.customer, company: frm.doc.company};
		
		// Wait for the dialog to fully render before making the API call
		setTimeout(function() {
			get_consumer_request_list(frm, $results, $placeholder, method, args);
		}, 300);
	}
	
	dialog.fields_dict["patient"].df.onchange = () => {
		var patient = dialog.get_value("patient");
		if(patient && patient!=selected_patient){
			selected_patient = patient;
			
			// Get customer linked to this patient before making the API call
			frappe.db.get_value("Patient", patient, "customer")
				.then(r => {
					let customer = (r.message && r.message.customer) ? r.message.customer : frm.doc.customer;
					var method = "healthcare.controllers.sales_invoice_consumer.get_consumer_requests_to_invoice";
					var args = {patient: patient, customer: customer, company: frm.doc.company};
					get_consumer_request_list(frm, $results, $placeholder, method, args);
				});
		}
		else if(!patient){
			selected_patient = '';
			$results.empty();
			$results.append($placeholder);
		}
	}

	$wrapper = dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
		style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
	$results = $wrapper.find('.results');
	$placeholder = $(`<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x fa-shopping-cart text-extra-muted"></i>
					<p class="text-extra-muted">No pending Consumer Requests found</p>
				</span>
			</div>`);
	
	$results.on('click', '.list-item--head :checkbox', (e) => {
		$results.find('.list-item-container .list-row-check')
			.prop("checked", ($(e.target).is(':checked')));
	});
	
	set_consumer_requests_primary_action(frm, dialog, $results);
	dialog.show();
};

var get_consumer_request_list = function(frm, $results, $placeholder, method, args) {
	var me = this;
	$results.empty();
	frappe.call({
		method: method,
		args: args,
		callback: function(data) {
			console.log("Consumer Requests data:", data);
			if(data.message && data.message.length > 0){
				$results.append(make_consumer_request_list_row(null, true));
				for(let i=0; i<data.message.length; i++){
					$results.append(make_consumer_request_list_row(null, false, data.message[i]));
				}
			} else {
				$results.append($placeholder);
			}
		},
		error: function(err) {
			console.error("Error fetching Consumer Requests:", err);
			$results.append($placeholder);
		}
	});
}

var make_consumer_request_list_row = function(columns, head, result={}) {
	var me = this;
	let contents = ``;
	
	if (head) {
		// Header row
		contents = `
			<div class="list-item__content ellipsis"><span class="ellipsis">${__("Consumer Request")}</span></div>
			<div class="list-item__content ellipsis"><span class="ellipsis">${__("Request Type")}</span></div>
			<div class="list-item__content ellipsis"><span class="ellipsis">${__("Transaction Date")}</span></div>
			<div class="list-item__content ellipsis"><span class="ellipsis">${__("Billing Status")}</span></div>
			<div class="list-item__content ellipsis"><span class="ellipsis">${__("Pending Items")}</span></div>
			<div class="list-item__content ellipsis"><span class="ellipsis">${__("Pending Qty")}</span></div>
		`;
	} else {
		// Data row
		let transaction_date = result.transaction_date ? frappe.datetime.str_to_user(result.transaction_date) : '';
		let billing_status_class = result.billing_status === 'Pending' ? 'warning' : 'info';
		
		contents = `
			<div class="list-item__content ellipsis">
				<a class="list-id ellipsis" href="/app/consumer-request/${result.name}" target="_blank">
					${result.name || ''}
				</a>
			</div>
			<div class="list-item__content ellipsis">
				<span class="ellipsis">${result.consumer_request_type || ''}</span>
			</div>
			<div class="list-item__content ellipsis">
				<span class="ellipsis">${transaction_date}</span>
			</div>
			<div class="list-item__content ellipsis">
				<span class="ellipsis badge badge-${billing_status_class}">${result.billing_status || ''}</span>
			</div>
			<div class="list-item__content ellipsis">
				<span class="ellipsis"><strong>${result.pending_items || 0}</strong></span>
			</div>
			<div class="list-item__content ellipsis">
				<span class="ellipsis"><strong>${result.pending_qty || 0}</strong></span>
			</div>
		`;
	}

	let $row = $(`<div class="list-item">
		<div class="list-item__content" style="flex: 0 0 10px;">
			<input type="checkbox" class="list-row-check" ${result.checked ? 'checked' : ''}>
		</div>
		${contents}
	</div>`);

	if (head) {
		$row.addClass('list-item--head');
	} else {
		$row = $(`<div class="list-item-container"
			data-consumer-request="${result.name}">
			</div>`).append($row);
	}
	
	return $row;
};

var set_consumer_requests_primary_action = function(frm, dialog, $results) {
    var me = this;
    dialog.set_primary_action(__('Add'), function() {
        let checked_values = get_checked_consumer_requests($results);
        console.log("Checked Consumer Requests:", checked_values);
        
        if(checked_values.length > 0){
            // Get the patient from the dialog
            let selected_patient = dialog.get_value("patient");
            
            // Set the patient in the form
            frm.set_value("patient", selected_patient);
            
            // Wait for the patient trigger to set customer, then add items
            setTimeout(function() {
                if (frm.doc.customer) {
                    add_consumer_request_items(frm, checked_values);
                    dialog.hide();
                } else {
                    frappe.msgprint(__("Patient {0} is not linked to a customer. Please select a customer before adding items.", [selected_patient]));
                }
            }, 500);
        } else {
            frappe.msgprint(__("Please select at least one Consumer Request"));
        }
    });
};

var get_checked_consumer_requests = function($results) {
	return $results.find('.list-item-container').map(function() {
		if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
			return $(this).attr('data-consumer-request');
		}
	}).get();
};

var add_consumer_request_items = function(frm, checked_consumer_requests) {
	console.log("Adding Consumer Request items:", checked_consumer_requests);
	
	frappe.call({
		method: "healthcare.controllers.sales_invoice_consumer.set_consumer_requests",
		args: {
			doc: frm.doc,
			checked_consumer_requests: checked_consumer_requests
		},
		callback: function(r) {
			console.log("Response from set_consumer_requests:", r);
			if (!r.exc) {
				frm.refresh_fields();
				frappe.show_alert({
					message: __("Consumer Request items added successfully"),
					indicator: "green"
				});
			} else {
				console.error("Error:", r.exc);
				frappe.msgprint(__("Error adding Consumer Request items: {0}", [r.exc]));
			}
		},
		error: function(err) {
			console.error("API Error:", err);
			frappe.msgprint(__("Error adding Consumer Request items: {0}", [err.message || "Unknown error"]));
		}
	});
};

// Keep your existing Healthcare Services and Prescriptions functions below this line...

var get_healthcare_services_to_invoice = function(frm, link_customer) {
	var me = this;
	let selected_patient = '';
	var dialog = new frappe.ui.Dialog({
		title: __("Get Items from Healthcare Services"),
		fields:[
			{
				fieldtype: 'Link',
				options: 'Patient',
				label: 'Patient',
				fieldname: "patient",
				reqd: true
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'results_area' }
		]
	});
	var $wrapper;
	var $results;
	var $placeholder;
	dialog.set_values({
		'patient': frm.doc.patient
	});
	
	// Trigger the API call immediately after dialog is set up with initial patient value
	if (frm.doc.patient) {
		selected_patient = frm.doc.patient;
		var method = "healthcare.healthcare.utils.get_healthcare_services_to_invoice";
		var args = {patient: selected_patient, customer: frm.doc.customer, company: frm.doc.company, link_customer: link_customer};
		var columns = (["service", "reference_name", "reference_type"]);
		
		// Wait for the dialog to fully render before making the API call
		setTimeout(function() {
			get_healthcare_items(frm, true, $results, $placeholder, method, args, columns);
		}, 300);
	}
	
	dialog.fields_dict["patient"].df.onchange = () => {
		var patient = dialog.get_value("patient");
		if(patient && patient!=selected_patient){
			selected_patient = patient;
			
			// Get customer linked to this patient before making the API call
			frappe.db.get_value("Patient", patient, "customer")
				.then(r => {
					let customer = r.message.customer || frm.doc.customer;
					var method = "healthcare.healthcare.utils.get_healthcare_services_to_invoice";
					var args = {patient: patient, customer: customer, company: frm.doc.company, link_customer: link_customer};
					var columns = (["service", "reference_name", "reference_type"]);
					get_healthcare_items(frm, true, $results, $placeholder, method, args, columns);
				});
		}
		else if(!patient){
			selected_patient = '';
			$results.empty();
			$results.append($placeholder);
		}
	}
	$wrapper = dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
		style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
	$results = $wrapper.find('.results');
	$placeholder = $(`<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x fa-heartbeat text-extra-muted"></i>
					<p class="text-extra-muted">No billable Healthcare Services found</p>
				</span>
			</div>`);
	$results.on('click', '.list-item--head :checkbox', (e) => {
		$results.find('.list-item-container .list-row-check')
			.prop("checked", ($(e.target).is(':checked')));
	});
	set_primary_action(frm, dialog, $results, true);
	dialog.show();
};

var get_healthcare_items = function(frm, invoice_healthcare_services, $results, $placeholder, method, args, columns) {
	var me = this;
	$results.empty();
	frappe.call({
		method: method,
		args: args,
		callback: function(data) {
			if(data.message){
				$results.append(make_list_row(columns, invoice_healthcare_services));
				for(let i=0; i<data.message.length; i++){
					$results.append(make_list_row(columns, invoice_healthcare_services, data.message[i]));
				}
			}else {
				$results.append($placeholder);
			}
		}
	});
}

var make_list_row= function(columns, invoice_healthcare_services, result={}) {
	var me = this;
	// Make a head row by default (if result not passed)
	let head = Object.keys(result).length === 0;
	let contents = ``;
	columns.forEach(function(column) {
		contents += `<div class="list-item__content ellipsis">
			${
				head ? `<span class="ellipsis">${__(frappe.model.unscrub(column))}</span>`
				:(column !== "name" ? `<span class="ellipsis">${__(result[column])}</span>`
					: `<a class="list-id ellipsis">
						${__(result[column])}</a>`)
			}
		</div>`;
	})

	let $row = $(`<div class="list-item">
		<div class="list-item__content" style="flex: 0 0 10px;">
			<input type="checkbox" class="list-row-check" ${result.checked ? 'checked' : ''}>
		</div>
		${contents}
	</div>`);

	$row = list_row_data_items(head, $row, result, invoice_healthcare_services);
	return $row;
};

var set_primary_action = function(frm, dialog, $results, invoice_healthcare_services) {
    var me = this;
    dialog.set_primary_action(__('Add'), function() {
        frm.clear_table('items');
        let checked_values = get_checked_values($results);
        if(checked_values.length > 0){
            // Get the patient from the dialog
            let selected_patient = dialog.get_value("patient");
            
            // Set the patient in the form
            frm.set_value("patient", selected_patient);
            
            // At this point, the patient(frm) trigger will execute and set the customer automatically
            // We just need to wait for it to finish, then add the items
            setTimeout(function() {
                if (frm.doc.customer) {
                    add_to_item_line(frm, checked_values, invoice_healthcare_services);
                    dialog.hide();
                } else {
                    frappe.msgprint(__("Patient {0} is not linked to a customer. Please select a customer before adding items.", [selected_patient]));
                }
            }, 500);
        }
        else{
            if(invoice_healthcare_services){
                frappe.msgprint(__("Please select Healthcare Service"));
            }
            else{
                frappe.msgprint(__("Please select Drug"));
            }
        }
    });
};

var get_checked_values= function($results) {
	return $results.find('.list-item-container').map(function() {
		let checked_values = {};
		if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
			checked_values['dn'] = $(this).attr('data-dn');
			checked_values['dt'] = $(this).attr('data-dt');
			checked_values['item'] = $(this).attr('data-item');
			if($(this).attr('data-rate') != 'undefined'){
				checked_values['rate'] = $(this).attr('data-rate');
			}
			else{
				checked_values['rate'] = false;
			}
			if($(this).attr('data-income-account') != 'undefined'){
				checked_values['income_account'] = $(this).attr('data-income-account');
			}
			else{
				checked_values['income_account'] = false;
			}
			if($(this).attr('data-qty') != 'undefined'){
				checked_values['qty'] = $(this).attr('data-qty');
			}
			else{
				checked_values['qty'] = false;
			}
			if($(this).attr('data-description') != 'undefined'){
				checked_values['description'] = $(this).attr('data-description');
			}
			else{
				checked_values['description'] = false;
			}
			return checked_values;
		}
	}).get();
};

var get_drugs_to_invoice = function(frm, link_customer) {
	var me = this;
	let selected_encounter = '';
	let selected_patient = '';
	var dialog = new frappe.ui.Dialog({
		title: __("Get Items from Medication Requests"),
		fields:[
			{ fieldtype: 'Link', options: 'Patient', label: 'Patient', fieldname: "patient", reqd: true },
			{ fieldtype: 'Link', options: 'Patient Encounter', label: 'Patient Encounter', fieldname: "encounter", reqd: true,
				description:'Quantity will be calculated only for items which has "Nos" as UoM. You may change as required for each invoice item.',
				get_query: function(doc) {
					return {
						filters: {
							patient: dialog.get_value("patient"),
							company: frm.doc.company,
							docstatus: 1
						}
					};
				}
			},
			{ fieldtype: 'Section Break' },
			{ fieldtype: 'HTML', fieldname: 'results_area' }
		]
	});
	var $wrapper;
	var $results;
	var $placeholder;
	dialog.set_values({
		'patient': frm.doc.patient,
		'encounter': ""
	});
	
	// Save the initial patient value
	if (frm.doc.patient) {
		selected_patient = frm.doc.patient;
	}
	
	dialog.fields_dict["patient"].df.onchange = () => {
		var patient = dialog.get_value("patient");
		if (patient != selected_patient) {
			selected_patient = patient;
			dialog.set_value("encounter", "");
			selected_encounter = '';
		}
	};
	
	dialog.fields_dict["encounter"].df.onchange = () => {
		var encounter = dialog.fields_dict.encounter.input.value;
		if(encounter && encounter!=selected_encounter){
			selected_encounter = encounter;
			
			// Get customer linked to this patient before making the API call
			frappe.db.get_value("Patient", dialog.get_value("patient"), "customer")
				.then(r => {
					let customer = r.message.customer || frm.doc.customer;
					var method = "healthcare.healthcare.utils.get_drugs_to_invoice";
					var args = {encounter: encounter, customer: customer, link_customer: link_customer};
					var columns = (["drug_code", "quantity", "description"]);
					get_healthcare_items(frm, false, $results, $placeholder, method, args, columns);
				});
		}
		else if(!encounter){
			selected_encounter = '';
			$results.empty();
			$results.append($placeholder);
		}
	}
	$wrapper = dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
		style="border: 1px solid #d1d8dd; border-radius: 3px; height: 300px; overflow: auto;"></div>`);
	$results = $wrapper.find('.results');
	$placeholder = $(`<div class="multiselect-empty-state">
				<span class="text-center" style="margin-top: -40px;">
					<i class="fa fa-2x fa-heartbeat text-extra-muted"></i>
					<p class="text-extra-muted">No Drug Prescription found</p>
				</span>
			</div>`);
	$results.on('click', '.list-item--head :checkbox', (e) => {
		$results.find('.list-item-container .list-row-check')
			.prop("checked", ($(e.target).is(':checked')));
	});
	set_primary_action(frm, dialog, $results, false);
	dialog.show();
};

var list_row_data_items = function(head, $row, result, invoice_healthcare_services) {
	if(invoice_healthcare_services){
		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container"
				data-dn= "${result.reference_name}" data-dt= "${result.reference_type}" data-item= "${result.service}"
				data-rate = ${result.rate}
				data-income-account = "${result.income_account}"
				data-qty = ${result.qty}
				data-description = "${result.description}">
				</div>`).append($row);
	}
	else{
		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container"
				data-item= "${result.drug_code}"
				data-qty = ${result.quantity}
				data-dn= "${result.reference_name}"
				data-dt= "${result.reference_type}"
				data-rate = ${result.rate}
				data-description = "${result.description}">
				</div>`).append($row);
	}
	return $row
};

var add_to_item_line = function(frm, checked_values, invoice_healthcare_services){
	if(invoice_healthcare_services){
		frappe.call({
			doc: frm.doc,
			method: "set_healthcare_services",
			args:{
				checked_values: checked_values
			},
			callback: function() {
				frm.trigger("validate");
				frm.refresh_fields();
			}
		});
	}
	else{
		for(let i=0; i<checked_values.length; i++){
			var si_item = frappe.model.add_child(frm.doc, 'Sales Invoice Item', 'items');
			frappe.model.set_value(si_item.doctype, si_item.name, 'item_code', checked_values[i]['item']);
			frappe.model.set_value(si_item.doctype, si_item.name, 'qty', 1);
			frappe.model.set_value(si_item.doctype, si_item.name, 'reference_dn', checked_values[i]['dn']);
			frappe.model.set_value(si_item.doctype, si_item.name, 'reference_dt', checked_values[i]['dt']);
			if(checked_values[i]['qty'] > 1){
				frappe.model.set_value(si_item.doctype, si_item.name, 'qty', parseFloat(checked_values[i]['qty']));
			}
		}
		frm.refresh_fields();
	}
};