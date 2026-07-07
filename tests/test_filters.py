import pytest

from app.handlers.user import NonAdminFilter


class DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


class DummyEvent:
    def __init__(self, user_id: int):
        self.from_user = DummyUser(user_id)


@pytest.mark.asyncio
async def test_non_admin_filter_allows_regular_users():
    filt = NonAdminFilter()
    assert await filt(DummyEvent(10), admin_ids={1, 2}) is True


@pytest.mark.asyncio
async def test_non_admin_filter_blocks_admins():
    filt = NonAdminFilter()
    assert await filt(DummyEvent(1), admin_ids={1, 2}) is False
