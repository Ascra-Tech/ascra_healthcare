# import frappe
# import urllib.parse

# @frappe.whitelist()
# def get_jitsi_url(appointment):
#     """
#     Return a unique Jitsi Meet room URL for the given appointment.
#     """
#     doc = frappe.get_doc("Patient Appointment", appointment)

#     if not doc.practitioner or not doc.patient:
#         frappe.throw("Practitioner or Patient information is missing.")

#     room_name = f"{doc.practitioner}-{doc.patient}-{doc.name}".replace(" ", "")
#     encoded_room = urllib.parse.quote(room_name)
#     jitsi_url = f"https://meet.jit.si/{encoded_room}"

#     return jitsi_url
