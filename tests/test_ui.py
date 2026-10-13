from uuid import uuid4
import httpx
from streamlit.testing.v1 import AppTest
from config import settings


def test_streamlit_chat_flow(monkeypatch):
    cid = str(uuid4())
    def respond(self, method, url, **kwargs):
        if url.endswith("/health"):
            data = {"model_configured": True, "model": "test-model"}
        elif url.endswith("/conversations"):
            data = {"conversation_id": cid}
        elif url.endswith("/chat"):
            assert kwargs["json"]["conversation_id"] == cid
            data = {"response": "There are 4 customers.", "invoices": []}
        else:
            raise AssertionError(url)
        return httpx.Response(200, json=data, request=httpx.Request(method, url))
    monkeypatch.setattr(httpx.Client, "request", respond)
    app = AppTest.from_file(str(settings.ROOT / "ui/streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "💳 Billing Agent"
    app.chat_input[0].set_value("How many customers?").run()
    assert not app.exception
    assert any(m.value == "There are 4 customers." for m in app.markdown)


def test_admin_login_and_logout_clear_session(monkeypatch):
    key = 'test-admin-key-123456789'
    def respond(self, method, url, **kwargs):
        if url.endswith('/admin/access'):
            assert kwargs['headers']['X-Admin-Key'] == key
            data = {'authorized':True}
        elif url.endswith('/health'):
            data = {'model_configured':True}
        elif url.endswith('/conversations'):
            assert kwargs['json']['mode'] == 'admin'
            assert kwargs['headers']['X-Admin-Key'] == key
            data = {'conversation_id':str(uuid4())}
        elif url.endswith('/chat'):
            assert kwargs['headers']['X-Admin-Key'] == key
            data = {'response':'Store revenue report','invoices':[], 'charts':[
                {'type':kind,'title':'Revenue '+kind,'x':'month','y':['revenue'],'currency':'USD',
                 'data':[{'month':1,'revenue':10},{'month':2,'revenue':20}]}
                for kind in ('bar','line','area','pie','scatter')]}
        else:
            raise AssertionError(url)
        return httpx.Response(200,json=data,request=httpx.Request(method,url))
    monkeypatch.setattr(httpx.Client,'request',respond)
    app = AppTest.from_file(str(settings.ROOT/'ui/streamlit_app.py'),default_timeout=30).run()
    app.radio[0].set_value('Admin').run()
    assert not app.chat_input
    next(x for x in app.text_input if x.label == 'Admin key').set_value(key)
    next(x for x in app.button if x.label == 'Unlock admin mode').click().run()
    assert not app.exception
    app.chat_input[0].set_value('Show revenue').run()
    assert any(m.value == 'Store revenue report' for m in app.markdown)
    assert not app.exception
    assert len(app.get('vega_lite_chart')) == 5
    next(x for x in app.button if x.label == 'Log out of admin mode').click().run()
    assert not app.exception
    assert app.radio[0].value == 'Customer'
    assert app.session_state['admin_key'] == ''
    assert app.session_state['messages'] == []
    assert app.session_state['conversation_id'] is None
