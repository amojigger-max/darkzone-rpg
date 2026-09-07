"""Offline, single-world maintenance command. Stop the production runner first."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import db
import migrations


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game',type=int,required=True)
    p.add_argument('--season',required=True)
    p.add_argument('--confirm',default='')
    p.add_argument('--special-rewards',action='store_true')
    args=p.parse_args()
    if args.confirm!=f'RESET:{args.game}':
        print(json.dumps({'dry_run':True,'game':args.game,'database':db.game_path(args.game),'confirmation_needed':f'RESET:{args.game}','nothing_changed':True}))
        return
    from runtime_lock import exclusive
    with exclusive():
        result=migrations.reset_game(args.game,args.season,confirmed=True,special_rewards=args.special_rewards)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
