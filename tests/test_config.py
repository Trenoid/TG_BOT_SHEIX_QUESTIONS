import pytest

from app.config import _normalize_publication_channel, _parse_admin_ids, load_config


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


def test_load_config_parses_question_cooldown_exempt_ids(monkeypatch, tmp_path):
    monkeypatch.setattr('app.config.load_dotenv', lambda **kwargs: None)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    monkeypatch.setenv('ADMIN_IDS', '100')
    monkeypatch.setenv('SHEIKH_IDS', '200')
    monkeypatch.setenv('QUESTION_COOLDOWN_EXEMPT_IDS', '731354094, 300')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'support_bot.db'))
    monkeypatch.delenv('PUBLICATION_CHANNEL', raising=False)
    monkeypatch.delenv('RUSSIAN_AUDIO_URL', raising=False)

    config = load_config()

    assert config.question_cooldown_exempt_ids == {731354094, 300}
