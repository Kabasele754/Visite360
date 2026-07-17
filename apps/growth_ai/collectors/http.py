import json, urllib.parse, urllib.request
class HttpError(RuntimeError): pass
def request_json(url,headers=None,params=None,method='GET',body=None,timeout=45):
    if params: url += ('&' if '?' in url else '?')+urllib.parse.urlencode(params,doseq=True)
    data=None
    h={'Accept':'application/json',**(headers or {})}
    if body is not None: data=json.dumps(body).encode(); h['Content-Type']='application/json'
    req=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode() or '{}')
    except Exception as e: raise HttpError(str(e)) from e
