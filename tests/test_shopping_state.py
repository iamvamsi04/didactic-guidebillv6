import asyncio
import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient

from agent import billing_agent as module
from api.main import app
from config import settings
from context import context_manager as context
from context.shopping_state import ShoppingTracker, empty_state
from database.connection import transaction
from mcp_server.tools.billing_tools import request_order, place_order


def answer(reply, **update):
    return json.dumps({'reply':reply, 'shopping_update':update})


def call(tool_name, **arguments):
    return CreateResult(finish_reason='function_calls', content=[FunctionCall(
        id=str(uuid4()), name=tool_name, arguments=json.dumps(arguments))],
        usage=RequestUsage(prompt_tokens=0,completion_tokens=0),cached=False)


def draft(tracker, order_id='MEMORY-1'):
    args = {'customer_id':'CUST001','order_id':order_id,'items':[{'item_code':'ITEM001','quantity':1}]}
    result = request_order(**args)
    assert result['ok']
    tracker.observe('request_order',args,result,'CUST001')
    return result['order_id']


def test_preferences_corrections_removals_and_reset_do_not_cancel_draft():
    tracker = ShoppingTracker(None, 'CUST001')
    tracker.finish(answer('For office use.',needs=['office work'],budget={'amount':'150','currency':'USD','scope':'all_in'},
                          quantity=2,preferred_features={'connection':'wireless','weight':'under 2 kg'}))
    tracker.finish(answer('Budget changed.',budget={'amount':'200','currency':None},preferred_features={'weight':None}))
    assert tracker.state['needs'] == ['office work']
    assert tracker.state['quantity'] == 2
    assert tracker.state['budget'] == {'amount':'200','currency':None,'scope':'unknown'}
    assert tracker.state['preferred_features'] == {'connection':'wireless'}
    oid = draft(tracker)
    tracker.finish(answer('Starting a new search.',reset_preferences=True,needs=['gaming']))
    assert tracker.state['needs'] == ['gaming'] and tracker.state['budget'] is None
    assert tracker.state['quantity'] is None and tracker.state['preferred_features'] == {}
    assert tracker.state['current_draft']['order_id'] == oid


def test_product_order_grounding_and_pending_proposals():
    tracker = ShoppingTracker(None,'CUST001')
    tracker.observe('compare_products',{}, {'ok':True,'products':[{'item_code':'ITEM001'},{'item_code':'ITEM002'}]},'CUST001')
    tracker.finish(answer('1. Mouse 2. Keyboard',displayed_product_ids=['ITEM002','ITEM001']))
    assert tracker.state['displayed_product_ids'] == ['ITEM002','ITEM001']
    assert tracker.state['compared_product_ids'] == ['ITEM001','ITEM002']
    tracker.finish(answer('Keyboard selected.',selected_product_ids=['ITEM001']))
    assert tracker.state['selected_product_ids'] == ['ITEM001']
    oid = draft(tracker)
    proposal = {'action':'place_order','order_id':oid,'summary':'Place one keyboard for USD 79.90?'}
    tracker.finish(answer(proposal['summary'],pending_confirmation=proposal))
    assert tracker.state['pending_confirmation']['status'] == 'awaiting_customer'
    resumed = ShoppingTracker(tracker.state,'CUST001')
    assert resumed.state['pending_confirmation']
    resumed.finish(answer('You are welcome.'))
    assert resumed.state['pending_confirmation'] is None
    with transaction() as conn:
        conn.execute('UPDATE orders SET charged_price=100 WHERE order_id=?',(oid,))
    changed = ShoppingTracker(tracker.state,'CUST001')
    assert changed.state['pending_confirmation'] is None
    assert changed.state['current_draft']['totals']['charged_price'] == '100.00'


@pytest.mark.parametrize('update', [
    {'budget':{'amount':'NaN'}}, {'quantity':True}, {'stage':'placed'},
    {'selected_product_ids':['INVENTED']}, {'active_draft_id':'OTHER'},
    {'preferred_features':{str(i):'x' for i in range(21)}},
])
def test_invalid_updates_cannot_poison_saved_state_or_adopt_another_customers_draft(update):
    request_order('CUST002',[{'item_code':'ITEM001','quantity':1}],'OTHER')
    tracker = ShoppingTracker(None,'CUST001')
    tracker.finish(answer('Saved.',needs=['office']))
    reply = tracker.finish(answer('Visible reply.',**update))
    assert reply.startswith('Visible reply.')
    assert tracker.state['needs'] == ['office']
    assert tracker.state['current_draft'] is None
    assert tracker.state['selected_product_ids'] == []


def test_pending_must_be_in_visible_reply_and_completed_actions_are_cleared():
    tracker = ShoppingTracker(None,'CUST001')
    oid = draft(tracker)
    proposal = {'action':'place_order','order_id':oid,'summary':'Place the order?'}
    tracker.finish(answer('No proposal here.',pending_confirmation=proposal))
    assert tracker.state['pending_confirmation'] is None
    tracker.finish(answer('Place the order?',pending_confirmation=proposal))
    result = place_order(oid,'CUST001')
    tracker.observe('place_order',{'order_id':oid},result,'CUST001')
    tracker.finish(answer('Place the order?',pending_confirmation=proposal))
    assert tracker.state['pending_confirmation'] is None
    assert tracker.state['current_draft'] is None
    assert tracker.state['last_order']['status'] == 'placed'


def test_migration_preserves_old_messages_and_repeated_initialization():
    cid = context.conversation(customer_id='CUST001')
    rid = str(uuid4())
    context.begin(cid,rid,'Earlier message')
    context.finish(cid,rid,{'response':'Earlier response'})
    with sqlite3.connect(settings.CONTEXT_DB) as conn:
        conn.execute('DROP TABLE shopping_states')
    context.initialize()
    context.initialize()
    assert context.shopping_state(cid) == empty_state()
    assert context.history(cid)[-1]['content'] == 'Earlier response'


def test_api_memory_survives_restart_history_limit_and_cached_request(monkeypatch):
    monkeypatch.setattr(settings,'azure_configuration_error',lambda:None)
    captured = []
    class Replay(ReplayChatCompletionClient):
        async def create(self,messages,**kwargs):
            captured.append(str(messages))
            return await super().create(messages,**kwargs)
    first_model = Replay([
        answer('I will use that budget. What connection do you prefer?', needs=['quiet office work'],
               budget={'amount':'100','currency':'USD','scope':'merchandise_total'},quantity=1,
               next_question='What connection do you prefer?'),
        call('compare_products',products=['ITEM001','ITEM002']),
        answer('1. Keyboard 2. Mouse',preferred_features={'connection':'wired'},
               displayed_product_ids=['ITEM001','ITEM002']),
    ])
    monkeypatch.setattr(module,'create_model_client',lambda:first_model)
    app.state.engine = module.BillingAgent()
    with TestClient(app) as client:
        cid = client.post('/conversations',json={'customer_id':'CUST001'}).json()['conversation_id']
        body = {'conversation_id':cid,'request_id':str(uuid4()),'message':'Office work. My merchandise budget is USD 100 for one.'}
        response = client.post('/chat',json=body)
        assert response.status_code == 200, response.text
        assert client.post('/chat',json=body).json() == response.json()
        assert len(captured) == 1
        response = client.post('/chat',json={**body,'request_id':str(uuid4()),'message':'Wired. Compare the keyboard and mouse.'})
        assert response.status_code == 200, response.text
        assert response.json()['response'] == '1. Keyboard 2. Mouse'
        assert response.json()['shopping_state']['compared_product_ids'] == ['ITEM001','ITEM002']
    # Preferences must survive even after their messages leave the 40-message history window.
    for i in range(22):
        rid = str(uuid4())
        context.begin(cid,rid,f'Unrelated turn {i}')
        context.finish(cid,rid,{'response':'Okay'})
    assert 'quiet office work' not in str(context.history(cid))
    second_model = Replay([
        call('request_order',customer_id='CUST001',order_id='RESUMED',items=[{'item_code':'ITEM002','quantity':1}]),
        answer('Place one mouse for USD 29.50?',selected_product_ids=['ITEM002'],
               pending_confirmation={'action':'place_order','order_id':'RESUMED','summary':'Place one mouse for USD 29.50?'}),
        call('place_order',customer_id='CUST001',order_id='RESUMED'), answer('Your order is placed.'),
        answer('What are you shopping for?'),
    ])
    monkeypatch.setattr(module,'create_model_client',lambda:second_model)
    app.state.engine = module.BillingAgent()
    with TestClient(app) as client:
        saved = client.get('/conversations/'+cid).json()['shopping_state']
        assert saved['budget']['amount'] == '100' and saved['displayed_product_ids'][1] == 'ITEM002'
        response = client.post('/chat',json={**body,'request_id':str(uuid4()),'message':'I want the second one.'})
        assert response.status_code == 200, response.text
        state = response.json()['shopping_state']
        assert state['current_draft']['order_id'] == 'RESUMED'
        assert state['pending_confirmation']['status'] == 'awaiting_customer'
        assert 'quiet office work' in captured[-2]
        response = client.post('/chat',json={**body,'request_id':str(uuid4()),'message':'Yes, place that mouse order.'})
        assert response.status_code == 200, response.text
        assert response.json()['shopping_state']['last_order']['status'] == 'placed'
        assert response.json()['shopping_state']['pending_confirmation'] is None
        other = client.post('/conversations',json={'customer_id':'CUST002'}).json()['conversation_id']
        assert client.get('/conversations/'+other).json()['shopping_state'] == empty_state()
        response = client.post('/chat',json={**body,'conversation_id':other,'request_id':str(uuid4()),'message':'Hello'})
        assert response.status_code == 200, response.text
        assert response.json()['shopping_state']['needs'] == []
        assert 'quiet office work' not in captured[-1]


@pytest.mark.parametrize('new_customer',[False,True])
def test_committed_action_is_checkpointed_when_final_model_reply_fails(monkeypatch,new_customer):
    monkeypatch.setattr(settings,'azure_configuration_error',lambda:None)
    class FailingReplay(ReplayChatCompletionClient):
        async def create(self,messages,**kwargs):
            if self._current_index:
                raise RuntimeError('Model disconnected after the tool committed')
            return await super().create(messages,**kwargs)
    action = (call('manage_customer',customer_id='NEW-SHOPPER',name='New Shopper',confirmed=True) if new_customer else
              call('request_order',customer_id='CUST001',order_id='INTERRUPTED',items=[{'item_code':'ITEM001','quantity':1}]))
    replay = FailingReplay([action])
    monkeypatch.setattr(module,'create_model_client',lambda:replay)
    app.state.engine = module.BillingAgent()
    with TestClient(app) as client:
        cid = client.post('/conversations',json={'customer_id':None if new_customer else 'CUST001'}).json()['conversation_id']
        body = {'conversation_id':cid,'request_id':str(uuid4()),'message':'Create a draft for one keyboard.'}
        assert client.post('/chat',json=body).status_code == 503
        if new_customer:
            assert context.get_conversation(cid)['customer_id'] == 'NEW-SHOPPER'
        else:
            assert context.shopping_state(cid)['current_draft']['order_id'] == 'INTERRUPTED'
        assert context.shopping_state(cid)['pending_confirmation'] is None
        assert client.post('/chat',json=body).status_code == 409


def test_state_and_reply_commit_together_and_checkpoint_rejects_wrong_owner():
    cid = context.conversation(customer_id='CUST001')
    rid = str(uuid4())
    context.begin(cid,rid,'Hello')
    state = empty_state()
    state['needs'] = ['office']
    with pytest.raises(ValueError):
        context.checkpoint_shopping(cid,rid,state,'CUST002')
    assert context.shopping_state(cid)['needs'] == []
    context.finish(cid,rid,{'response':'Hello','shopping_state':state})
    state['needs'] = ['should roll back']
    with pytest.raises(sqlite3.IntegrityError):
        context.finish(cid,rid,{'response':'Duplicate','shopping_state':state})
    assert context.shopping_state(cid)['needs'] == ['office']
    assert context.history(cid)[-1]['content'] == 'Hello'


def test_malformed_state_response_does_not_expose_internal_json():
    tracker = ShoppingTracker(None,None)
    with pytest.raises(ValueError):
        tracker.finish('{"reply":"Hello", "shopping_update":{')
    reply = tracker.finish('```json\n'+answer('Hello',needs=['office'])+'\n```')
    assert reply == 'Hello' and tracker.state['needs'] == ['office']
