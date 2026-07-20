from __future__ import annotations
import hashlib
from pathlib import Path
from PIL import Image, ImageEnhance

def sha256_file(path:str|Path)->str:
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def prepare_image(source:str|Path,destination:str|Path,max_size:int=1280,quality:int=85)->Path:
    destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    with Image.open(source).convert('RGB') as im:
        im.thumbnail((max_size,max_size),Image.Resampling.LANCZOS)
        im=ImageEnhance.Contrast(im).enhance(1.04)
        im.save(destination,'JPEG',quality=quality,optimize=True)
    return destination
