"""Unit tests for management tasks and their attachments."""

import pytest

from app.domain.management import InvalidManagementAttachment
from app.services.management_service import ManagementService
from tests.support.memory_management_repository import InMemoryManagementRepository


def _service() -> ManagementService:
    return ManagementService(InMemoryManagementRepository())


def _create(service: ManagementService, **extra):
    return service.create_task(
        subject="Filtración",
        body="Hay humedad en el hall.",
        created_by_user_id="user-1",
        created_by_name="Ana",
        client_id="client-1",
        client_name="Edificio",
        from_staff=False,
        **extra,
    )


def test_create_task_stores_attachments() -> None:
    service = _service()

    task = _create(
        service,
        attachments=[
            {"kind": "file", "name": "cotizacion.pdf", "url": "data:application/pdf;base64,aaa"},
            {"kind": "file", "name": "gastos.xlsx", "url": "data:application/vnd.ms-excel;base64,bbb"},
            {"kind": "file", "name": "acta.doc", "url": "data:application/msword;base64,ccc"},
            {"kind": "image", "name": "foto.jpg", "url": "data:image/jpeg;base64,ddd"},
        ],
    )

    stored = service.get_task(task.id)
    assert [item.name for item in stored.attachments] == [
        "cotizacion.pdf",
        "gastos.xlsx",
        "acta.doc",
        "foto.jpg",
    ]
    assert {item.kind for item in stored.attachments} == {"file", "image"}
    assert all(item.message_id is None and item.task_id == task.id for item in stored.attachments)


def test_create_task_without_attachments_has_none() -> None:
    service = _service()

    task = _create(service)

    assert service.get_task(task.id).attachments == ()


def test_file_with_unsupported_extension_is_rejected() -> None:
    service = _service()

    with pytest.raises(InvalidManagementAttachment):
        _create(
            service,
            attachments=[{"kind": "file", "name": "virus.exe", "url": "data:application/x;base64,aaa"}],
        )


def test_unknown_attachment_kind_is_rejected() -> None:
    service = _service()

    with pytest.raises(InvalidManagementAttachment):
        _create(service, attachments=[{"kind": "audio", "name": "a.mp3", "url": "data:audio/mp3;base64,aa"}])


def test_message_attachments_belong_to_the_message() -> None:
    service = _service()
    task = _create(service)

    updated = service.add_message(
        task.id,
        body="Adjunto la cotización.",
        author_user_id="user-2",
        author_name="Luis",
        from_staff=True,
        attachments=[{"kind": "file", "name": "cotizacion.pdf", "url": "data:application/pdf;base64,aaa"}],
    )

    reply = updated.messages[-1]
    assert [item.name for item in reply.attachments] == ["cotizacion.pdf"]
    assert reply.attachments[0].message_id == reply.id
    assert updated.attachments == ()
