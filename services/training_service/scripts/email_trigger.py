import os
from typing import List
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

load_dotenv()

def send_email(recepient_emails: List[str], token_id: str):
    SMTP_SERVER = os.getenv("SMTP_SERVER","smtp.gmail.com")
    sender_email = os.getenv("SMTP_USERNAME")
    sender_password = os.getenv("SMTP_PASSWORD")
    SMTP_PORT = int(os.getenv("SMTP_PORT",587))
    BASE_URL = os.getenv("PUBLIC_BASE_URL")
    approve_url = BASE_URL+f"/churn_predictor/{token_id}/approve"
    try:
        with smtplib.SMTP(SMTP_SERVER,SMTP_PORT) as server:
            server.starttls()
            server.login(user = sender_email, password = sender_password)

            for recepient_email in recepient_emails:
                msg = MIMEMultipart()
                msg["FROM"] = sender_email
                msg['TO'] = recepient_email
                msg['SUBJECT'] = "[MODEL ALERT] New model is trained, check performance stats."

                html_body = f"""
                <html>
                  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <p>Hello,</p>
                    <p>A new machine learning model is trained due to the observed current model performance degradation.</p>
                    <p>The new model performance statistics are available to review in the <code>/artifacts/model_metadata.json</code> file.</p>
                    <p>Compare the model statistics and take necessary actions.</p>
                    
                    <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 25px 0; border-radius: 4px;">
                        <strong style="color: #007bff; display: block; margin-bottom: 10px;">[IMMEDIATE ACTION REQUIRED]</strong>
                        <p style="margin: 0 0 15px 0;">Please review the stats and select an action below to update the artifact:</p>
                        
                        <!-- Action Buttons -->
                        <div style="margin-top: 15px;">
                            <a href="{approve_url}" 
                               style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-right: 12px; display: inline-block;">
                               Approve Update
                            </a>
                        </div>
                    </div>
                    
                    <p style="margin-top: 30px;">Thanks,<br><strong>ML Automation</strong></p>
                  </body>
                </html>
                """

                try:
                    msg.attach(MIMEText(html_body,"html"))
                    server.sendmail(from_addr=sender_email, to_addrs=recepient_email, msg=msg.as_string())
                    print(f"Notification sent to {recepient_email} successfully!")
                except Exception as ex:
                    print(f"Unable to send email notification to {recepient_email}")
    except Exception as ex:
        print(f"Login to email server failed")



