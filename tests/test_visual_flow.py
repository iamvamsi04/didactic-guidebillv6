import asyncio
import json
from uuid import uuid4
from fastapi.testclient import TestClient
from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient
from agent import billing_agent as module
from api.main import app
from config import settings
from context import context_manager as context


def call(name,**arguments):
    return CreateResult(finish_reason='function_calls',content=[FunctionCall(id=str(uuid4()),name=name,arguments=json.dumps(arguments))],
                        usage=RequestUsage(prompt_tokens=0,completion_tokens=0),cached=False)


def test_composed_tool_turn_attaches_chart_then_clears_it(monkeypatch):
    replay = ReplayChatCompletionClient([
        call('execute_sql_query',query='PRAGMA table_info(catalogue_current)'),
        call('execute_sql_query',query='SELECT name,availablequantity FROM catalogue_current ORDER BY name',
             chart={'type':'bar','title':'Stock available','x':'name','y':['availablequantity']}),
        'Here is current stock.','Welcome back.'])
    monkeypatch.setattr(module,'create_model_client',lambda:replay)
    async def run():
        agent = module.BillingAgent()
        await agent.start()
        try:
            result = await agent.chat('Chart stock by product',[],None,mode='admin')
            assert len(result['charts']) == 1
            assert sorted(r['availablequantity'] for r in result['charts'][0]['data']) == [15,40,60]
            followup = await agent.chat('Hi',[],'CUST001')
            assert followup['charts'] == []
        finally:
            await agent.close()
    asyncio.run(run())


def test_saved_charts_require_admin_and_are_excluded_from_model_history(monkeypatch):
    cid = context.conversation(mode='admin')
    rid = str(uuid4())
    chart = {'type':'bar','title':'Stock','x':'item','y':['qty'],'currency':None,'data':[{'item':'Keyboard','qty':40}]}
    response = {'response':'Recorded stock','charts':[chart],'invoices':[]}
    context.begin(cid,rid,'Chart stock')
    context.finish(cid,rid,response)
    assert context.history(cid)[-1] == {'role':'assistant','content':'Recorded stock'}
    assert context.history(cid,include_artifacts=True)[-1]['charts'] == [chart]
    class Engine:
        pass
    app.state.engine = Engine()
    monkeypatch.setattr(settings,'ADMIN_API_KEY','test-admin-key-123456789')
    with TestClient(app) as client:
        assert client.get('/conversations/'+cid).status_code == 403
        saved = client.get('/conversations/'+cid,headers={'X-Admin-Key':settings.ADMIN_API_KEY}).json()
        assert saved['messages'][-1]['charts'] == [chart]


def test_chart_limit_does_not_claim_an_unattached_chart():
    async def run():
        async with module.RecordingWorkbench() as wb:
            wb.mode = 'admin'
            for i in range(7):
                result = module.decode_result(await wb.call_tool('execute_sql_query',{
                    'query':"SELECT 'A' name,1 qty",'chart':{'type':'bar','title':f'Chart {i}','x':'name','y':['qty']}}))
            assert len(wb.charts) == 6
            assert 'chart_error' in result and 'chart' not in result
    asyncio.run(run())
