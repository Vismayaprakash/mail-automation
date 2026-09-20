import logging
import os
import requests
from config import settings

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """Client for WhatsApp messaging supporting Meta Cloud API and Twilio WhatsApp Sandbox."""

    @property
    def recipient_phone(self) -> str:
        return settings.USER_PHONE_NUMBER.strip().lstrip('+')

    @property
    def phone_number_id(self) -> str:
        return settings.WHATSAPP_PHONE_NUMBER_ID.strip()

    @property
    def access_token(self) -> str:
        from dotenv import load_dotenv
        from config import BASE_DIR
        load_dotenv(BASE_DIR / ".env", override=True)
        return os.getenv("WHATSAPP_ACCESS_TOKEN", settings.WHATSAPP_ACCESS_TOKEN).strip()

    @property
    def api_url(self) -> str:
        return f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"

    @property
    def twilio_account_sid(self) -> str:
        return os.getenv("TWILIO_ACCOUNT_SID", "").strip()

    @property
    def twilio_auth_token(self) -> str:
        return os.getenv("TWILIO_AUTH_TOKEN", "").strip()

    @property
    def twilio_whatsapp_number(self) -> str:
        return os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886").strip()

    def send_approval_request(self, thread_id: str, sender_name: str, sender_email: str, subject: str, summary: str, draft_reply: str, past_context: str = None) -> str:
        """Send formatted WhatsApp approval request message."""
        summary_clean = summary[:1000] if len(summary) > 1000 else summary
        draft_clean = draft_reply[:2000] if len(draft_reply) > 2000 else draft_reply

        context_section = f"📜 *Previous Context:* {past_context.strip()}\n\n" if past_context and past_context.strip() else ""

        message_body = (
            f"📧 *New Email Notification*\n\n"
            f"👤 *From:* {sender_name} ({sender_email})\n"
            f"📌 *Subject:* {subject}\n\n"
            f"{context_section}"
            f"📝 *Summary:*\n{summary_clean}\n\n"
            f"💬 *Proposed Reply Draft:*\n\"{draft_clean}\"\n\n"
            f"----------------------------------------\n"
            f"❓ *Do you approve this reply?*\n"
            f"• Reply *YES* to approve and send.\n"
            f"• Reply *NO* or send a *Voice Note* to revise."
        )
        
        return self.send_text_message(message_body)

    def send_text_message(self, text: str) -> str:
        """Send text message to user's WhatsApp using Twilio or Meta Cloud API."""
        
        if len(text) > 4000:
            text = text[:3990] + "..."

        recipient = self.recipient_phone

        # 1. Try Twilio if Twilio credentials exist
        if self.twilio_account_sid and self.twilio_auth_token:
            try:
                url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
                tw_recipient = recipient if recipient.startswith("whatsapp:") else f"whatsapp:+{recipient}"
                data = {
                    "From": self.twilio_whatsapp_number,
                    "To": tw_recipient,
                    "Body": text
                }
                res = requests.post(url, data=data, auth=(self.twilio_account_sid, self.twilio_auth_token), timeout=15)
                res.raise_for_status()
                sid = res.json().get("sid", "")
                logger.info(f"Successfully sent WhatsApp message via Twilio. SID: {sid}")
                return sid
            except Exception as e:
                logger.error(f"Error sending via Twilio: {e}")

        # 2. Try Meta WhatsApp API
        if self.phone_number_id and self.access_token and recipient:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": text}
            }

            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=15)
                if response.status_code != 200:
                    logger.error(f"Meta WhatsApp API Error [{response.status_code}]: {response.text}")
                response.raise_for_status()
                data = response.json()
                msg_id = data.get("messages", [{}])[0].get("id", "")
                logger.info(f"Successfully sent WhatsApp message via Meta API. ID: {msg_id}")
                return msg_id
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message via Meta API: {e}")
                return ""

        # 3. Mock fallback
        logger.info(f"[MOCK WHATSAPP SEND] Recipient: {recipient} | Message:\n{text}")
        return "mock_msg_id_12345"

    def download_media(self, media_url_or_id: str, output_path: str) -> bool:
        """Download WhatsApp voice note media file."""
        if media_url_or_id.startswith("http"):
            try:
                auth = (self.twilio_account_sid, self.twilio_auth_token) if self.twilio_account_sid else None
                res = requests.get(media_url_or_id, auth=auth, timeout=30)
                res.raise_for_status()
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(res.content)
                logger.info(f"Downloaded media file to {output_path}")
                return True
            except Exception as e:
                logger.error(f"Error downloading media from URL: {e}")
                return False
                
        if not self.access_token:
            logger.info(f"[MOCK WHATSAPP MEDIA DOWNLOAD] Media ID: {media_url_or_id} -> {output_path}")
            return True

        media_url_endpoint = f"https://graph.facebook.com/v18.0/{media_url_or_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            res = requests.get(media_url_endpoint, headers=headers, timeout=15)
            res.raise_for_status()
            media_download_url = res.json().get("url")

            if not media_download_url:
                return False

            media_res = requests.get(media_download_url, headers=headers, timeout=30)
            media_res.raise_for_status()

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(media_res.content)

            logger.info(f"Successfully downloaded WhatsApp media to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error downloading WhatsApp media {media_url_or_id}: {e}")
            return False

whatsapp_client = WhatsAppClient()
