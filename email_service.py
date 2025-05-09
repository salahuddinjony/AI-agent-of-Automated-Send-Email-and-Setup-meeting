import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailService:
    def __init__(self, sender_email, password):
        self.sender_email = sender_email
        self.password = password

    def send_email(self, recipients, subject, content, generate_joke=False, joke_topic='computer'):
        """Send an email to the specified recipients."""
        try:
            # Generate joke if requested
            if generate_joke:
                from llm_service import LLMService
                llm_service = LLMService()
                joke = llm_service.generate_joke(joke_topic)
                content = f"Here's a joke about {joke_topic}s:\n\n{joke}\n\n{content}"
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(content, 'plain'))
            
            # Send email
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
                smtp_server.login(self.sender_email, self.password)
                smtp_server.send_message(msg)
            
            return True, "Email sent successfully"
        except Exception as e:
            return False, f"Failed to send email: {str(e)}" 