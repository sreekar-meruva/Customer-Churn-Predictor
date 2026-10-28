import os
from typing import List
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

load_dotenv()

def send_email(recepient_emails: List[str]):
    SMTP_SERVER = os.getenv("SMTP_SERVER","smtp.gmail.com")
    sender_email = os.getenv("SMTP_USERNAME")
    sender_password = os.getenv("SMTP_PASSWORD")
    SMTP_PORT = int(os.getenv("SMTP_PORT",587))
    try:
        with smtplib.SMTP(SMTP_SERVER,SMTP_PORT) as server:
            server.starttls()
            server.login(user = sender_email, password = sender_password)

            for recepient_email in recepient_emails:
                msg = MIMEMultipart()
                msg["FROM"] = sender_email
                msg['TO'] = recepient_email
                msg['SUBJECT'] = "[MODEL ALERT] New model is trained, check performance stats."

                body = r""" Hello,
                A new machine learning model is trained due to the observed current model performance degradation.
                The new model performance statistics are available to review in /artifacts/model_metadata.json file.
                Compare the models statistics and take necessary actions.
                
                [IMMEDATE ACTION REQUIRED]
                
                Thanks
                ML Automation"""

                try:
                    msg.attach(MIMEText(body,"plain"))
                    server.sendmail(from_addr=sender_email, to_addrs=recepient_email, msg=msg.as_string())
                    print(f"Notification sent to {recepient_email} successfully!")
                except Exception as ex:
                    print(f"Unable to send email notification to {recepient_email}")
    except Exception as ex:
        print(f"Login to email server failed")



