// frappe.ui.form.on('Event', {
//     add_video_conferencing: function(frm) {
//         if (frm.doc.add_video_conferencing) {
//             const roomName = `meeting-${frappe.datetime.now_datetime().replace(/[^a-zA-Z0-9]/g, "")}`;
//             const meetLink = `https://meet.jit.si/${roomName}`;

//             frm.set_value('custom_google_meet', meetLink);

//             // Create or show a div where Jitsi will load
//             if (!document.getElementById('jitsi-meet-container')) {
//                 const jitsiDiv = document.createElement('div');
//                 jitsiDiv.id = 'jitsi-meet-container';
//                 jitsiDiv.style.height = '500px'; // Set height for the video window
//                 jitsiDiv.style.width = '100%';
//                 frm.fields_dict['custom_google_meet'].$wrapper.append(jitsiDiv);
//             }

//             // Load Jitsi Meet External API
//             const domain = "meet.jit.si";
//             const options = {
//                 roomName: roomName,
//                 width: "100%",
//                 height: 500,
//                 parentNode: document.getElementById('jitsi-meet-container'),
//                 interfaceConfigOverwrite: {
//                     SHOW_JITSI_WATERMARK: false,
//                     DEFAULT_REMOTE_DISPLAY_NAME: 'Guest',
//                 },
//                 configOverwrite: {
//                     startWithAudioMuted: false,
//                     startWithVideoMuted: false,
//                 }
//             };
//             const api = new JitsiMeetExternalAPI(domain, options);

//             // Optional: Listen to events (like when someone joins)
//             api.addListener('participantJoined', function(event) {
//                 console.log("New participant joined: ", event.displayName);
//                 frappe.msgprint(`New participant joined: ${event.displayName}`);
//             });

//             api.addListener('videoConferenceJoined', function(event) {
//                 console.log("You joined the meeting!");
//             });

//         } else {
//             frm.set_value('custom_google_meet', '');
//             const container = document.getElementById('jitsi-meet-container');
//             if (container) container.remove(); // Remove Jitsi if unchecked
//         }
//     }
// });

