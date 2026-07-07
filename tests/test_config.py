import pytest

from app.config import _parse_admin_ids


def test_parse_admin_ids_accepts_commas_and_semicolons():
    assert _parse_admin_ids('123, 456;789') == {123, 456, 789}


def test_parse_admin_ids_rejects_invalid_values():
    with pytest.raises(ValueError):
        _parse_admin_ids('123, abc')
