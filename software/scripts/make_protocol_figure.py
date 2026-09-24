#!/usr/bin/env python3
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

root=Path(__file__).resolve().parents[2]
out=root/'paper'/'figures'/'protocol.pdf'
fig,ax=plt.subplots(figsize=(7.0,2.05))
ax.set_xlim(0,10); ax.set_ylim(0,3); ax.axis('off')
boxes=[
 (0.15,1.55,1.55,0.75,'Declaration','universe, affine map, mask'),
 (0.15,0.45,1.55,0.75,'Plan','committed + planned fragments'),
 (2.45,0.98,1.65,0.85,'Producer','exact counts + row chain'),
 (4.85,0.98,1.55,0.85,'Certificate','bound JSONL transcript'),
 (7.15,0.98,1.55,0.85,'Checker','strict parse + recompute'),
 (9.05,1.55,0.8,0.75,'Safe','D = 0'),
 (9.05,0.45,0.8,0.75,'Fault','earliest witness'),
]
for x,y,w,h,title,subtitle in boxes:
    patch=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.04',linewidth=0.8,facecolor='white')
    ax.add_patch(patch)
    ax.text(x+w/2,y+h*0.64,title,ha='center',va='center',fontsize=8.2,fontweight='bold')
    ax.text(x+w/2,y+h*0.30,subtitle,ha='center',va='center',fontsize=6.3,wrap=True)

def arrow(x1,y1,x2,y2):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=8,linewidth=0.8))
arrow(1.72,1.9,2.43,1.55); arrow(1.72,0.82,2.43,1.35)
arrow(4.12,1.4,4.83,1.4); arrow(6.42,1.4,7.13,1.4)
arrow(8.72,1.55,9.03,1.9); arrow(8.72,1.25,9.03,0.82)
ax.text(5.62,0.63,'SHA-256 input binding is substitution detection, not source authentication',ha='center',fontsize=6.4)
fig.tight_layout(pad=0.1)
fig.savefig(out,bbox_inches='tight')
