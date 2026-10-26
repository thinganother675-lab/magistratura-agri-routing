import argparse
import json
from .benchmark import run, freeze

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run");r.add_argument("--split",choices=["dev","test"],default="dev");r.add_argument("--limit",type=int)
    f=sub.add_parser("freeze");f.add_argument("pilot")
    a=sub.add_parser("analyze");a.add_argument("run_dir")
    w=sub.add_parser("serve");w.add_argument("--port",type=int,default=8090)
    args=parser.parse_args()
    if args.command=="run": print(run(args.split,args.limit))
    elif args.command=="freeze": print(json.dumps(freeze(args.pilot),indent=2))
    elif args.command=="analyze":
        from .analysis import analyze
        print(json.dumps(analyze(args.run_dir),indent=2))
    else:
        from .web import serve
        serve(args.port)

if __name__ == "__main__":
    main()
