"""Use cases for public contact form messages."""

import uuid
from datetime import datetime, timezone

from app.domain.contact import ContactMessageRecord, PrivacyConsentRequired
from app.repositories.contact_repository import ContactRepository


class ContactService:
    """Stores and lists public contact submissions."""

    def __init__(self, repository: ContactRepository) -> None:
        self._repository = repository

    def list_messages(self) -> list[ContactMessageRecord]:
        """Return every contact message for the super admin."""
        return self._repository.list_messages()

    def create_message(
        self,
        *,
        name: str,
        email: str,
        message: str,
        privacy_accepted: bool,
    ) -> ContactMessageRecord:
        """Persist a contact message when privacy consent is given."""
        if not privacy_accepted:
            raise PrivacyConsentRequired()
        cleaned_name = name.strip()
        cleaned_email = email.strip().lower()
        cleaned_message = message.strip()
        if not cleaned_name or not cleaned_email or not cleaned_message:
            raise ValueError("Name, email, and message are required.")
        if "@" not in cleaned_email or "." not in cleaned_email.split("@", 1)[-1]:
            raise ValueError("A valid email is required.")
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        record = ContactMessageRecord(
            id=str(uuid.uuid4()),
            name=cleaned_name,
            email=cleaned_email,
            message=cleaned_message,
            privacy_accepted=True,
            privacy_accepted_at=now,
            created_at=now,
        )
        self._repository.add_message(record)
        return record
