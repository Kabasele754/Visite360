from apps.tour_ai_agent.providers.openai_client import OpenAIClient
from .prompt_builder import build_sales_instructions,build_input
from .sales_agent import fallback_reply
from .intent_router import detect_intent
def run_agent(*,text,context):
    client=OpenAIClient()
    if client.enabled:
        try:
            result=client.respond(instructions=build_sales_instructions(context),input_text=build_input(text,context))
            if result and result.get('text'):return {'text':result['text'],'intent':detect_intent(text),'quick_actions':['book_appointment','view_products','contact_business'],'provider':'openai','response_id':result.get('response_id')}
        except Exception: pass
    result=fallback_reply(text,context); result['provider']='local'; return result
