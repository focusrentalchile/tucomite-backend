"""Unit tests for the default voting window hours of a building."""

import pytest

from app.domain.client_settings import InvalidVoteWindowSettings
from app.services.client_settings_service import ClientSettingsService
from tests.support.memory_client_settings_repository import InMemoryClientSettingsRepository


def test_defaults_are_24_72_and_168_hours() -> None:
    service = ClientSettingsService(InMemoryClientSettingsRepository())

    assert service.hours_for_priority("client-1", 1) == 24
    assert service.hours_for_priority("client-1", 2) == 72
    assert service.hours_for_priority("client-1", 3) == 168


def test_update_is_saved_per_building() -> None:
    service = ClientSettingsService(InMemoryClientSettingsRepository())

    service.update_vote_window(
        "client-1",
        high_hours=12,
        medium_hours=48,
        low_hours=96,
        consensus_grace_days=7,
    )

    assert service.hours_for_priority("client-1", 1) == 12
    assert service.hours_for_priority("client-1", 2) == 48
    assert service.hours_for_priority("client-1", 3) == 96
    assert service.consensus_grace_days("client-1") == 7
    assert service.hours_for_priority("client-2", 1) == 24
    assert service.consensus_grace_days("client-2") == 5


def test_hours_outside_the_range_are_rejected() -> None:
    service = ClientSettingsService(InMemoryClientSettingsRepository())

    with pytest.raises(InvalidVoteWindowSettings):
        service.update_vote_window(
            "client-1",
            high_hours=0,
            medium_hours=48,
            low_hours=96,
            consensus_grace_days=5,
        )
    with pytest.raises(InvalidVoteWindowSettings):
        service.update_vote_window(
            "client-1",
            high_hours=12,
            medium_hours=48,
            low_hours=24 * 366,
            consensus_grace_days=5,
        )
    with pytest.raises(InvalidVoteWindowSettings):
        service.update_vote_window(
            "client-1",
            high_hours=12,
            medium_hours=48,
            low_hours=96,
            consensus_grace_days=0,
        )
