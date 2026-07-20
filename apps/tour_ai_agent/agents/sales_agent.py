from .intent_router import detect_intent
def fallback_reply(text,context):
    intent=detect_intent(text); scene=context.get('scene') or {}; products=context.get('products') or []
    if intent=='booking': return {'text':'I can help you request an appointment. Please share your preferred date and time, then choose “Book appointment”.','intent':intent,'quick_actions':['book_appointment','contact_business']}
    if intent=='product':
        if products:return {'text':f"I found {len(products)} related product(s) for this scene. Open the product suggestions to compare prices or add one to your cart.",'intent':intent,'quick_actions':['view_products','open_cart']}
        return {'text':'I cannot confirm an exact product in this view yet. I can show products available from this business.','intent':intent,'quick_actions':['view_products']}
    if intent=='quote': return {'text':'I can prepare a quote request. Tell me what you need and your preferred contact details.','intent':intent,'quick_actions':['request_quote']}
    if intent=='contact': return {'text':'I can connect you with the business by email, phone, or WhatsApp when available.','intent':intent,'quick_actions':['contact_business']}
    summary=scene.get('summary') or 'You are exploring this virtual space.'
    return {'text':summary+' Would you like details, related products, or an appointment?','intent':intent,'quick_actions':['book_appointment','view_products','ask_question']}
