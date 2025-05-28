// frappe.ui.form.on('Patient', {
//     refresh(frm) {
//         // Add a custom button to the Patient form
//         frm.add_custom_button("Start Video Call", function () {
            
//             // Dynamically load the Jitsi Meet script if not already loaded
//             if (typeof JitsiMeetExternalAPI === 'undefined') {
//                 const script = document.createElement('script');
//                 script.src = 'https://meet.jit.si/external_api.js';
//                 script.onload = () => {
//                     console.log('Jitsi API loaded');
//                     startJitsiMeeting(frm);
//                 };
//                 script.onerror = () => {
//                     frappe.msgprint("Error loading Jitsi Meet API. Please check your internet connection.");
//                 };
//                 document.head.appendChild(script);
//             } else {
//                 // If already loaded, start the meeting directly
//                 startJitsiMeeting(frm);
//             }
//         });
//     }
// });

// // Function to start the Jitsi meeting
// function startJitsiMeeting(frm) {
//     // Create a dialog for the Jitsi Meet room
//     const dialog = new frappe.ui.Dialog({
//         title: 'Jitsi Video Call',
//         size: 'extra-large',
//         fields: [
//             {
//                 fieldtype: 'HTML',
//                 fieldname: 'jitsi_html',
//                 options: '<div id="jitsi_meet_container" style="height: 600px;"></div>'
//             }
//         ]
//     });

//     // Show the dialog
//     dialog.show();

//     // Delay to ensure the dialog is fully loaded before initializing Jitsi
//     setTimeout(() => {
//         // Check if JitsiMeetExternalAPI is available (script loaded)
//         if (typeof JitsiMeetExternalAPI !== 'undefined') {
//             const domain = "meet.jit.si";
//             const roomName = `PatientRoom-${frm.doc.name}`; // Room name based on patient ID
//             const options = {
//                 roomName: roomName,
//                 width: '100%',
//                 height: 600,
//                 parentNode: document.getElementById("jitsi_meet_container"),
//                 userInfo: {
//                     displayName: frm.doc.patient_name || "Doctor"
//                 }
//             };

//             // Initialize the Jitsi meeting
//             const api = new JitsiMeetExternalAPI(domain, options);

//             // Optional: Automatically request video and audio permissions
//             api.executeCommand('toggleVideo');
//             api.executeCommand('toggleAudio');
//         } else {
//             // Show an error message if Jitsi API is not loaded
//             frappe.msgprint("Jitsi Meet script not loaded. Please check your internet connection.");
//         }
//     }, 300); // Wait for 300ms before initializing Jitsi
// }
