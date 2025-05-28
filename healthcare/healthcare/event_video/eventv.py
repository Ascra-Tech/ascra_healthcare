# import frappe
# from frappe.utils import get_datetime
# from frappe.core.doctype.communication.email import make

# def send_mail_on_save(doc, method):
#     # Ensure mandatory fields are set
#     if not doc.starts_on or not doc.ends_on or not doc.custom_google_meet:
#         frappe.throw("Start Time, End Time, and Google Meet Link are mandatory fields.")
    
#     # Format the start and end time
#     start_time = get_datetime(doc.starts_on)
#     end_time = get_datetime(doc.ends_on)
    
#     # Prepare email content
#     subject = f"Meeting Scheduled: {doc.subject}"
#     message = f"""
#     <p><strong>Start Time:</strong> {start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
#     <p><strong>End Time:</strong> {end_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
#     <p><strong>Google Meet Link:</strong> <a href="{doc.custom_google_meet}" target="_blank">Click here to join the meeting</a></p>
#     <p>Thank you,</p>
#     <p>Your Medical Team</p>
#     """
#     participants = doc.event_participants or []
    
#     for participant in participants:
#         print("Participant: ", participant)
       
#         if hasattr(participant, "patient"):  # Check if there's a patient field
#             patient_field = participant.patient
#             print("Patient Field: ", patient_field)
            
#             if patient_field:
#                 # Fetch the email of the patient from the Patient doctype
#                 patient_email = frappe.get_value("Patient", patient_field, "email")
#                 if patient_email:
#                     frappe.sendmail(
#                         recipients=patient_email,
#                         subject=subject,
#                         message=message,
#                         reference_doctype=doc.doctype,
#                         reference_docname=doc.name
#                     )
