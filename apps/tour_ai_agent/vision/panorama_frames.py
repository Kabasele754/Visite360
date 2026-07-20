from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from PIL import Image

def _bilinear(img,x,y):
    h,w,_=img.shape; x=np.mod(x,w); y=np.clip(y,0,h-1)
    x0=np.floor(x).astype(int); x1=(x0+1)%w; y0=np.floor(y).astype(int); y1=np.minimum(y0+1,h-1)
    wx=x-x0; wy=y-y0
    return ((1-wx)[...,None]*(1-wy)[...,None]*img[y0,x0]+wx[...,None]*(1-wy)[...,None]*img[y0,x1]+(1-wx)[...,None]*wy[...,None]*img[y1,x0]+wx[...,None]*wy[...,None]*img[y1,x1]).astype(np.uint8)

def equirectangular_to_perspective(image_path:str|Path,out_path:str|Path,yaw:float,pitch:float=0,fov:float=95,size:int=640)->Path:
    pano=np.asarray(Image.open(image_path).convert('RGB')); h,w,_=pano.shape
    xx,yy=np.meshgrid(np.linspace(-1,1,size),np.linspace(-1,1,size))
    z=1/np.tan(np.deg2rad(fov)/2); dirs=np.stack([xx,-yy,np.full_like(xx,z)],axis=-1)
    dirs/=np.linalg.norm(dirs,axis=-1,keepdims=True)
    ya=np.deg2rad(yaw); pi=np.deg2rad(pitch)
    ry=np.array([[math.cos(ya),0,math.sin(ya)],[0,1,0],[-math.sin(ya),0,math.cos(ya)]])
    rx=np.array([[1,0,0],[0,math.cos(pi),-math.sin(pi)],[0,math.sin(pi),math.cos(pi)]])
    d=dirs@((ry@rx).T); lon=np.arctan2(d[...,0],d[...,2]); lat=np.arcsin(np.clip(d[...,1],-1,1))
    x=(lon/(2*np.pi)+.5)*w; y=(.5-lat/np.pi)*h
    out=Image.fromarray(_bilinear(pano,x,y)); out_path=Path(out_path); out_path.parent.mkdir(parents=True,exist_ok=True); out.save(out_path,'JPEG',quality=88,optimize=True); return out_path

def generate_panorama_frames(image_path:str|Path,output_dir:str|Path,size:int=640)->list[dict]:
    result=[]
    for yaw,name in [(0,'front'),(90,'right'),(180,'back'),(270,'left')]:
        p=Path(output_dir)/f'{name}.jpg'; equirectangular_to_perspective(image_path,p,yaw=yaw,size=size); result.append({'name':name,'yaw':yaw,'pitch':0,'path':str(p)})
    return result
