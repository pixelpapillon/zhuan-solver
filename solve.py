#!/usr/bin/env python3
"""File-based entry point; no mouse clicks, no Windows dependency."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
from app.zhuan.solver import solve, format_solution


def main():
    parser=argparse.ArgumentParser(description='砖了个砖：完整求解、独立复验、中文操作顺序')
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--board',type=Path,help='已核对的14×10整数矩阵JSON；0为空')
    source.add_argument('--image',type=Path,help='完整截图，自动定位并生成识别核对文件')
    parser.add_argument('--crop',type=float,nargs=4,metavar=('X','Y','W','H'))
    parser.add_argument('--output',type=Path,default=Path('result'))
    parser.add_argument('--seconds',type=float,default=120)
    parser.add_argument('--max-nodes',type=int,default=200000)
    parser.add_argument('--gbfs-nodes',type=int,default=2000)
    parser.add_argument('--cache-size',type=int,default=100000)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    # Remove stale solution before any recognition/search failure can occur.
    for name in ('solution.txt','solution.json','status.json'):
        (args.output/name).unlink(missing_ok=True)
    try:
        if args.image:
            from app.zhuan.screenshot import recognize
            report=recognize(args.image,args.output,args.crop)
            print(f'已生成 {args.output}/recognized.png、board.json、recognition.json。请核对后用 --board 求解。')
            print('不确定格子：',sum(c['uncertain'] for c in report['cells']),'；奇数图案：',report['odd_labels'])
            return 2
        initial=json.loads(args.board.read_text())
        result=solve(initial,args.seconds,args.max_nodes,args.gbfs_nodes,args.cache_size)
        (args.output/'status.json').write_text(json.dumps(asdict(result),ensure_ascii=False,indent=2))
        if result.status!='solved':
            print(result.status, result.reason)
            return 3
        text=format_solution(initial,result)
        (args.output/'solution.txt').write_text(text+'\n')
        (args.output/'solution.json').write_text(json.dumps({'initial':initial,**asdict(result)},ensure_ascii=False,indent=2))
        print(text)
        print(f'\n已复验：{len(result.actions)} 步，最后剩余 0 块；搜索 {result.elapsed:.3f} 秒。')
        return 0
    except (ValueError,OSError) as exc:
        print(f'输入/验证失败：{exc}')
        return 2

if __name__=='__main__': raise SystemExit(main())
