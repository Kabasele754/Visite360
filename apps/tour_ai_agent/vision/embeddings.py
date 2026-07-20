from __future__ import annotations
import numpy as np
from PIL import Image
def image_embedding(path,bins=16):
    with Image.open(path).convert('RGB') as im:
        im.thumbnail((256,256)); a=np.asarray(im)
    values=[]
    for c in range(3):
        hist,_=np.histogram(a[:,:,c],bins=bins,range=(0,256),density=True); values.extend(hist.tolist())
    v=np.asarray(values,dtype=float); n=np.linalg.norm(v); return (v/n if n else v).round(7).tolist()
def cosine_similarity(a,b):
    if not a or not b:return 0.0
    x=np.asarray(a); y=np.asarray(b); d=np.linalg.norm(x)*np.linalg.norm(y); return float(np.dot(x,y)/d) if d else 0.0
