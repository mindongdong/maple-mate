"""실호출 검증 1건 (handoff §4·§6: 앱 키 `id` 무지정 1건).

기본 비활성(`-m 'not live'`). 실행:
    set -a; source spike/.env; set +a
    uv run pytest -m live tests/test_nexon_live.py -s
NEXON_APP_KEY + TEST_CHARACTER_NAME 이 환경에 없으면 skip.
"""

from __future__ import annotations

import os

import pytest

from maple_mate.nexon.client import NexonClient

pytestmark = pytest.mark.live


async def test_get_ocid_live():
    app_key = os.environ.get("NEXON_APP_KEY")
    character = os.environ.get("TEST_CHARACTER_NAME")
    if not app_key or not character:
        pytest.skip("NEXON_APP_KEY / TEST_CHARACTER_NAME 미설정")

    async with NexonClient(app_key) as client:
        ocid = await client.get_ocid(character)
    assert isinstance(ocid, str) and ocid
