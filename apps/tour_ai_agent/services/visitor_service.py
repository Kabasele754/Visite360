import hashlib,secrets
def get_visitor_id(request):
    value=request.COOKIES.get('tw_visitor_id') or request.headers.get('X-Twinscopes-Visitor')
    return value or secrets.token_urlsafe(18)
def get_session_id(request):
    if not request.session.session_key: request.session.save()
    return request.session.session_key
def request_fingerprint(request):
    raw=f"{request.META.get('REMOTE_ADDR','')}|{request.META.get('HTTP_USER_AGENT','')}"
    return hashlib.sha256(raw.encode()).hexdigest()
