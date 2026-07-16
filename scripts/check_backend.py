import urllib.request, ssl
url = 'https://agentic-ai-project-scak5chlx6swzadpaq9fgy.streamlit.app/api/events'
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    resp = urllib.request.urlopen(url, context=ctx, timeout=10)
    print('OK', resp.getcode())
    data = resp.read(200)
    print(data.decode(errors='ignore'))
except Exception as e:
    print('ERROR', e)
