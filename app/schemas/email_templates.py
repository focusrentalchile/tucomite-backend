"""HTTP schemas for email templates."""

from pydantic import BaseModel, Field


class EmailTemplateResponse(BaseModel):
    """One email template for the admin table and editor."""

    id: str
    key: str
    name: str
    subject: str
    html_body: str
    updated_at: str


class EmailTemplateListResponse(BaseModel):
    """List of email templates."""

    items: list[EmailTemplateResponse]


class UpdateEmailTemplateRequest(BaseModel):
    """Body to update subject and HTML of one template."""

    subject: str = Field(min_length=1, max_length=255)
    html_body: str = Field(min_length=1)
