import base64
import logging
import os
import socket
import mimetypes
socket.setdefaulttimeout(15)
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import settings

logger = logging.getLogger(__name__)

# Gmail API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# List of automated system/marketing/job alert senders to ignore
SYSTEM_IGNORE_KEYWORDS = [
    'noreply', 'no-reply', 'donotreply', 'notifications', 'mailer-daemon', 
    'subscriptions', 'newsletter', 'jobalert', 'naukri', 'ambitionbox', 
    'recruiting', 'facebookmail', 'linkedin', 'huzzle', 'tcsion', 'digest',
    'groq', 'zerodha', 'harman', 'updates', 'promotions', 'offers', 'scaler'
]

class GmailClient:
    """Client for interacting with Google Gmail API."""

    def __init__(self):
        self.creds_file = settings.GMAIL_CREDENTIALS_FILE
        self.token_file = settings.GMAIL_TOKEN_FILE
        self.service = None

    def authenticate(self):
        """Authenticate with Google OAuth2."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info("Refreshed Gmail OAuth access token and saved to token.json.")
                except Exception as e:
                    logger.error(f"Error refreshing Gmail token: {e}")
                    creds = None
            
            if not creds and os.path.exists(self.creds_file):
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())

        if creds:
            self.service = build('gmail', 'v1', credentials=creds)
            return True
        
        logger.warning("Gmail credentials file not found. Running in Simulator/Mock Mode.")
        return False

    def fetch_unread_messages(self) -> list:
        """Fetch unread messages from live Gmail inbox, ignoring automated system & job alert emails."""
        if not self.service and not self.authenticate():
            return []

        try:
            try:
                results = self.service.users().messages().list(
                    userId=settings.GMAIL_USER_EMAIL,
                    q="is:unread label:INBOX",
                    maxResults=10
                ).execute()
            except Exception as conn_err:
                logger.warning(f"Gmail fetch connection warning ({conn_err}). Re-authenticating...")
                self.authenticate()
                results = self.service.users().messages().list(
                    userId=settings.GMAIL_USER_EMAIL,
                    q="is:unread label:INBOX",
                    maxResults=10
                ).execute()

            messages = results.get('messages', [])
            email_list = []

            for msg in messages:
                msg_id = msg['id']
                thread_id = msg['threadId']
                
                full_msg = self.service.users().messages().get(
                    userId=settings.GMAIL_USER_EMAIL,
                    id=msg_id,
                    format='full'
                ).execute()

                headers = full_msg.get('payload', {}).get('headers', [])
                subject = "No Subject"
                sender = "Unknown"
                sender_name = ""

                for header in headers:
                    name = header.get('name', '').lower()
                    if name == 'subject':
                        subject = header.get('value', 'No Subject')
                    elif name == 'from':
                        from_val = header.get('value', '')
                        if '<' in from_val and '>' in from_val:
                            sender_name = from_val.split('<')[0].strip(' "\'')
                            sender = from_val.split('<')[1].split('>')[0].strip()
                        else:
                            sender = from_val
                            sender_name = from_val

                # Skip self-sent emails (from user's own email account)
                sender_lower = sender.lower()
                user_email_lower = (settings.GMAIL_USER_EMAIL or "").lower().strip()
                if user_email_lower and (sender_lower == user_email_lower or user_email_lower in sender_lower):
                    logger.info(f"Skipping self-sent email: From '{sender}' | Subject '{subject}'")
                    self.mark_as_read(msg_id)
                    continue

                # Skip automated system & job alert emails
                subject_lower = subject.lower()
                if any(keyword in sender_lower or keyword in subject_lower for keyword in SYSTEM_IGNORE_KEYWORDS):
                    logger.info(f"Skipping automated email: From '{sender}' | Subject '{subject}'")
                    self.mark_as_read(msg_id)
                    continue

                body_text = self._extract_body(full_msg.get('payload', {}))

                email_list.append({
                    "message_id": msg_id,
                    "thread_id": thread_id,
                    "sender": sender,
                    "sender_name": sender_name or sender,
                    "recipient": settings.GMAIL_USER_EMAIL,
                    "subject": subject,
                    "body": body_text or subject
                })

            return email_list
        except Exception as e:
            logger.error(f"Error fetching unread Gmail messages: {e}")
            return []

    def _extract_body(self, payload: dict) -> str:
        """Helper to extract plain text body from Gmail message payload."""
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    sub_body = self._extract_body(part)
                    if sub_body:
                        return sub_body
        else:
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        return ""

    def mark_as_read(self, message_id: str):
        """Mark an email message as read in Gmail."""
        if not self.service:
            return
        try:
            self.service.users().messages().batchModify(
                userId=settings.GMAIL_USER_EMAIL,
                body={'ids': [message_id], 'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception as e:
            logger.error(f"Failed to mark message {message_id} as read: {e}")

    def send_email(self, to_email: str, subject: str, body_text: str, thread_id: str = None, attachments: list = None) -> bool:
        """Send an email or thread reply using Gmail API with optional file attachments."""
        if not self.service and not self.authenticate():
            att_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            logger.info(f"[MOCK GMAIL SEND] To: {to_email} | Subject: {subject}{att_info} | Body: {body_text[:50]}...")
            return True

        try:
            if attachments:
                message = MIMEMultipart("mixed")
                message['to'] = to_email
                message['subject'] = subject
                message.attach(MIMEText(body_text, 'plain'))

                for file_path in attachments:
                    if not file_path or not os.path.exists(file_path):
                        logger.warning(f"Attachment file not found: {file_path}")
                        continue

                    filename = os.path.basename(file_path)
                    content_type, encoding = mimetypes.guess_type(file_path)
                    if content_type is None or encoding is not None:
                        content_type = 'application/octet-stream'
                    
                    main_type, sub_type = content_type.split('/', 1)

                    with open(file_path, 'rb') as f:
                        part = MIMEBase(main_type, sub_type)
                        part.set_payload(f.read())

                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', filename=filename)
                    message.attach(part)
                    logger.info(f"Attached file '{filename}' to email payload.")
            else:
                message = MIMEText(body_text)
                message['to'] = to_email
                message['subject'] = subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            body = {'raw': raw_message}
            if thread_id:
                body['threadId'] = thread_id

            try:
                self.service.users().messages().send(
                    userId=settings.GMAIL_USER_EMAIL,
                    body=body
                ).execute()
            except Exception as send_err:
                err_str = str(send_err)
                if "thread" in err_str.lower() and "threadId" in body:
                    logger.warning(f"Gmail API error for threadId ({send_err}). Retrying send without threadId...")
                    body.pop("threadId", None)
                    self.service.users().messages().send(
                        userId=settings.GMAIL_USER_EMAIL,
                        body=body
                    ).execute()
                else:
                    logger.warning(f"Gmail connection error ({send_err}). Re-authenticating and retrying send...")
                    if self.authenticate():
                        self.service.users().messages().send(
                            userId=settings.GMAIL_USER_EMAIL,
                            body=body
                        ).execute()
                    else:
                        raise send_err

            att_log = f" (Attached {len(attachments)} file(s))" if attachments else ""
            logger.info(f"Successfully sent email to {to_email}{att_log}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via Gmail API: {e}")
            return False

gmail_client = GmailClient()
