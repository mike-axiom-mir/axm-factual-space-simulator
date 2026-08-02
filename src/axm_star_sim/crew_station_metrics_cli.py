from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .crew_station_metrics import *
def rd(p):return json.loads(p.read_text(encoding="utf-8"))
def wr(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding="utf-8")
def parser():
 p=argparse.ArgumentParser(prog='axm-crew-stations');s=p.add_subparsers(dest='command',required=True)
 x=s.add_parser('snapshot');x.add_argument('--ship-state',type=Path,required=True);x.add_argument('--previous-state',type=Path);x.add_argument('--output',type=Path)
 x=s.add_parser('station');x.add_argument('--ship-state',type=Path,required=True);x.add_argument('--station-id',required=True);x.add_argument('--previous-state',type=Path);x.add_argument('--output',type=Path)
 x=s.add_parser('all-stations');x.add_argument('--ship-state',type=Path,required=True);x.add_argument('--previous-state',type=Path);x.add_argument('--output',type=Path,required=True)
 x=s.add_parser('create-competency');x.add_argument('--output',type=Path,required=True)
 x=s.add_parser('learning-pressure');x.add_argument('--ship-state',type=Path,required=True);x.add_argument('--role-id',required=True);x.add_argument('--competency-state',type=Path);x.add_argument('--previous-state',type=Path)
 x=s.add_parser('verify-competency');x.add_argument('--competency-state',type=Path,required=True)
 return p
def main(argv=None):
 a=parser().parse_args(argv)
 try:
  if a.command=='create-competency':wr(a.output,create_competency_state());return 0
  if a.command=='verify-competency':r=verify_competency_state(rd(a.competency_state));print(json.dumps(r,indent=2));return 0 if r['valid'] else 1
  ship=rd(a.ship_state);prev=rd(a.previous_state) if getattr(a,'previous_state',None) else None
  if a.command=='snapshot':r=create_telemetry_snapshot(ship,prev)
  elif a.command=='station':r=create_station_view(ship,a.station_id,prev)
  elif a.command=='all-stations':r=create_all_station_views(ship,prev);wr(a.output,r);return 0
  elif a.command=='learning-pressure':r=compute_learning_pressure(ship,a.role_id,rd(a.competency_state) if a.competency_state else None,prev)
  if getattr(a,'output',None):wr(a.output,r)
  print(json.dumps(r,indent=2,ensure_ascii=False));return 0
 except Exception as e:print('ERROR:',e,file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
