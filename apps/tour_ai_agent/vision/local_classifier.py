from __future__ import annotations
from collections import Counter
RULES={
 'hotel_room':{'bed':5,'tv':1,'chair':1,'sink':1},'restaurant':{'dining table':4,'chair':2,'wine glass':2,'bottle':1},
 'office':{'laptop':3,'keyboard':2,'mouse':2,'chair':1,'tv':1},'store':{'handbag':2,'bottle':1,'backpack':1,'tie':1},
 'living_room':{'couch':5,'tv':2,'chair':1,'potted plant':1},'kitchen':{'refrigerator':5,'oven':4,'microwave':3,'sink':2},
 'conference_room':{'chair':2,'tv':2,'laptop':2,'dining table':2}
}
def classify_scene(detections):
    counts=Counter(d.label for d in detections); scores={k:sum(counts[l]*w for l,w in rule.items()) for k,rule in RULES.items()}
    if not scores or max(scores.values())<=0:return {'scene_type':'interior_space','confidence':.35,'scores':scores}
    typ=max(scores,key=scores.get); total=max(1,sum(scores.values())); conf=min(.97,.5+scores[typ]/(2*total)); return {'scene_type':typ,'confidence':round(conf,4),'scores':scores}
