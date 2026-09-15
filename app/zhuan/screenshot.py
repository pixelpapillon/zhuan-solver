"""Offline template recognition with automatic lattice detection and review artifacts.
Scores are image distances, NOT calibrated probabilities. Never repair parity by guessing.
"""
from pathlib import Path
from collections import Counter
import json
import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[2]


def detect_grid(image):
    import cv2
    arr=np.asarray(image.convert('RGB'))
    mask=((arr[:,:,0]>185)&(arr[:,:,1]>185)&(arr[:,:,2]>130)).astype('uint8')*255
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    area=image.width*image.height
    boxes=[cv2.boundingRect(c) for c in contours]
    boxes=[b for b in boxes if .75<b[2]/b[3]<1.25 and area/1600<b[2]*b[3]<area/70]
    if len(boxes)<25: raise ValueError('无法可靠定位棋盘；需要检查图像或提供 --crop x y w h')
    w=float(np.median([b[2] for b in boxes])); h=float(np.median([b[3] for b in boxes]))
    boxes=[b for b in boxes if .8*w<b[2]<1.2*w and .8*h<b[3]<1.2*h]
    def groups(values, tolerance):
        result=[]
        for v in sorted(values):
            if not result or v-np.mean(result[-1])>tolerance: result.append([v])
            else: result[-1].append(v)
        return np.array([np.mean(g) for g in result])
    xs=groups([x+bw/2 for x,y,bw,bh in boxes],w*.3)
    ys=groups([y+bh/2 for x,y,bw,bh in boxes],h*.3)
    if len(xs)!=10 or len(ys)!=14:
        raise ValueError(f'未定位完整14×10网格（检测到{len(ys)}×{len(xs)}）；需人工核对裁剪')
    dx=float(np.median(np.diff(xs))); dy=float(np.median(np.diff(ys)))
    if max(abs(np.diff(xs)-dx))>dx*.08 or max(abs(np.diff(ys)-dy))>dy*.08:
        raise ValueError('网格间距不一致')
    return (float(xs[0]-dx/2),float(ys[0]-dy/2),10*dx,14*dy)


def feature(image):
    image=image.convert('RGB')
    w,h=image.size
    return np.asarray(image.crop((w*.09,h*.09,w*.91,h*.91)).resize((32,32)),dtype=np.float32)/255


def recognize(path, output, crop=None):
    image=ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    crop=tuple(crop) if crop is not None else detect_grid(image)
    x,y,w,h=crop
    if min(x,y)<0 or min(w,h)<=0 or x+w>image.width or y+h>image.height:
        raise ValueError('裁剪区域超出截图范围')
    templates=[]; labels=[]
    for p in sorted((ROOT/'datasets/zhuan_v1/train').glob('*/*.png')):
        label=int(p.parent.name.split('_')[-1])
        templates.append(feature(Image.open(p))); labels.append(label)
    templates=np.stack(templates); labels=np.array(labels)
    board=[]; records=[]
    annotated=image.copy(); draw=ImageDraw.Draw(annotated)
    for r in range(14):
        row=[]
        for c in range(10):
            box=(x+c*w/10,y+r*h/14,x+(c+1)*w/10,y+(r+1)*h/14)
            f=feature(image.crop(box))
            distances=np.mean((templates-f)**2,axis=(1,2,3))
            ranked=sorted((float(distances[labels==label].min()),int(label)) for label in set(labels))
            best,label=ranked[0]; margin=ranked[1][0]-best
            row.append(label)
            records.append({'row':r+1,'col':c+1,'label':label,'distance':best,'margin':margin,
                            'uncertain':best>.025 or margin<.008})
            draw.rectangle(box,outline='red' if records[-1]['uncertain'] else 'blue',width=2)
            draw.text((box[0]+3,box[1]+3),f'{r+1},{c+1}:{label}',fill='black',stroke_width=1,stroke_fill='white')
        board.append(row)
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    counts=Counter(v for row in board for v in row if v)
    report={'crop':crop,'board':board,'cells':records,'odd_labels':[k for k,v in counts.items() if v%2],
            'needs_review':True,'note':'模板距离不等于正确率；首次截图必须核对标注图与棋盘。'}
    (output/'recognition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    # Keep the raw candidate separate so a later manual correction is auditable.
    (output/'board.auto.json').write_text(json.dumps(board,ensure_ascii=False,indent=2))
    (output/'board.json').write_text(json.dumps(board,indent=2))
    annotated.save(output/'recognized.png')
    return report
