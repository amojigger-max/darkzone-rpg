"""Apply to chosen/all EXISTING group databases after installation, with the runner stopped."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import config
import db
import release
import migrations
from runtime_lock import exclusive


def main():
    p=argparse.ArgumentParser(description=__doc__)
    scope=p.add_mutually_exclusive_group(required=True)
    scope.add_argument('--all-groups',action='store_true')
    scope.add_argument('--game',type=int,action='append')
    p.add_argument('--reset-game',type=int,help='optional: reset ONLY this explicitly named world')
    p.add_argument('--season',default='v41-new-season')
    p.add_argument('--runner-stopped',action='store_true')
    p.add_argument('--confirm',default='')
    args=p.parse_args()
    known=[g for g in db.list_games() if g<0]
    if not known:p.error('no existing group databases; restore production data before rollout')
    games=known if args.all_groups else list(dict.fromkeys(args.game))
    if any(g not in known for g in games):p.error('every target must be an existing group world')
    if args.reset_game is not None and args.reset_game not in games:p.error('reset target must be explicitly inside the rollout scope')
    if not args.runner_stopped or args.confirm!=f'APPLY:{config.VERSION}':
        print(json.dumps({'dry_run':True,'games':games,'reset_only':args.reset_game,'required_confirmation':f'APPLY:{config.VERSION}','nothing_changed':True},ensure_ascii=False,indent=2))
        return
    with exclusive():
        migrations.run_all()
        result=[]
        if args.reset_game is not None:
            result.append(migrations.reset_game(args.reset_game,args.season,confirmed=True,special_rewards=True))
        for gid in games:result.append(release.apply(gid,confirmed=True))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    db.close_all()

if __name__=='__main__':main()
