import pytest

from app.config import _normalize_publication_channel, _parse_admin_ids


def test_parse_admin_ids_accepts_commas_and_semicolons():
    assert _parse_admin_ids('123, 456;789 101\n202') == {123, 456, 789, 101, 202}


def test_parse_admin_ids_rejects_invalid_values():
    with pytest.raises(ValueError):
        _parse_admin_ids('123, abc')


def test_normalize_publication_channel_accepts_links_usernames_and_ids():
    assert _normalize_publication_channel('https://t.me/example_channel') == '@example_channel'
    assert _normalize_publication_channel('@example_channel') == '@example_channel'
    assert _normalize_publication_channel('-100123456789') == -100123456789
    assert _normalize_publication_channel('') is None
