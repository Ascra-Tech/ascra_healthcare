// frappe.ui.form.on('Patient Appointment', {
//     refresh: function(frm) {
//         // Check if the user has required role
//         if (!frm.is_new() && frappe.user_roles.includes('Practitioner') || frappe.user_roles.includes('Healthcare Administrator')) {
            
//             frm.add_custom_button(__('Start Video Call'), function() {
//                 frappe.show_alert({ message: __('Generating Meeting Link...'), indicator: 'blue' });

//                 frappe.call({
//                     method: 'healthcare.healthcare.patient_appo.patient_appo.get_jitsi_url',
//                     args: { appointment: frm.doc.name },
//                     callback: function(r) {
//                         if (r.message) {
//                             frappe.show_alert({ message: __('Opening Jitsi Meet...'), indicator: 'green' });
//                             window.open(r.message, '_blank');
//                         } else {
//                             frappe.msgprint(__('Failed to generate Jitsi URL'));
//                         }
//                     },
//                     error: function(err) {
//                         frappe.msgprint(__('Something went wrong while generating the link.'));
//                     }
//                 });
//             });
//         }
//     }
// });
