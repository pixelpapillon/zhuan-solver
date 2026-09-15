"""Reverify a saved solution without running search or trusting its verified flag."""
import argparse
import json
from app.zhuan.solver import Result,format_solution
from app.zhuan.verifier import verify_route


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('solution')
    args=parser.parse_args()
    with open(args.solution) as f: data=json.load(f)
    actions=[(tuple(a),tuple(b),d) for a,b,d in data['actions']]
    verify_route(data['initial'],actions)
    format_solution(data['initial'],Result('solved',actions,verified=True))
    print(f'复验通过：{len(actions)}步，全部合法，无配对歧义，最终0块。')

if __name__=='__main__': main()
