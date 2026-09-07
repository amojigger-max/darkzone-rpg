import pytest
import db
import countries
import run
from game import state,campaign,events


async def test_idle_world_missiles_resolve_after_connection_restart(player,equip,clock,monkeypatch):
    for gid in (-201,-202):
        with db.world(gid):
            countries.init_items();player(1,'ir');player(2,'iq')
            campaign.declare(1,'iq');clock.advance(3601)
            equip(1,'موشکی');campaign.launch_missile(1,1,'1.power')
            db.ex('UPDATE users SET last_active=0')
    db.close_all();clock.advance(100)
    class Done(Exception):pass
    async def one_cycle(seconds):
        if seconds:raise Done()
    monkeypatch.setattr(run.asyncio,'sleep',one_cycle)
    with pytest.raises(Done):await run.campaign_loop()
    for gid in (-201,-202):
        with db.world(gid):
            assert db.one('SELECT status FROM missions')[0]=='resolved'
            assert db.one('SELECT COUNT(*) FROM outbox')[0]>=3


def test_sidebar_extensions_are_in_same_original_router():
    import handlers
    names={f.callback.__name__ for f in handlers.router.callback_query.handlers}
    assert {'cb_buy','cb_strike','cb_city','cb_un','cb_operation_start','cb_strait_fee','cb_end_alliance'}<=names
