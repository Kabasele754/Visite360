from __future__ import annotations
import json, os
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum, Count
from .models import AppointmentRequest, CustomerBehaviorEvent, MarketInsightReport, Order, Product

def build_organization_snapshot(organization):
    products=list(Product.objects.filter(organization=organization).values("id","name","price","stock_quantity","view_count","order_count","status","is_featured")[:200])
    orders=organization.orders.exclude(status=Order.Status.CANCELLED)
    paid=orders.filter(payment_status="paid")
    events=CustomerBehaviorEvent.objects.filter(organization=organization).values("event_type").annotate(total=Count("id"))
    event_map={x["event_type"]:x["total"] for x in events}
    sources=list(organization.market_sources.filter(is_active=True).values("source_type","url","label","metrics","latest_summary"))
    appointments=organization.appointment_requests.values("status").annotate(total=Count("id"))
    appointment_map={x["status"]:x["total"] for x in appointments}
    product_views=sum(int(x.get("view_count") or 0) for x in products); product_orders=sum(int(x.get("order_count") or 0) for x in products)
    return {"organization":organization.name,"sources":sources,"products":products,"commerce":{"orders_total":orders.count(),"orders_paid":paid.count(),"paid_revenue":str(paid.aggregate(v=Sum("total"))["v"] or Decimal("0")),"average_order_value":str((paid.aggregate(v=Sum("total"))["v"] or Decimal("0"))/max(paid.count(),1)),"product_views":product_views,"product_units_ordered":product_orders,"view_to_order_rate":round(product_orders/max(product_views,1)*100,2)},"behavior_events":event_map,"appointments":appointment_map,"tours":{"count":organization.tours.count()}}

def _fallback(snapshot):
    products=[p for p in snapshot["products"] if p["status"]=="active"]
    low=[p["name"] for p in products if p["stock_quantity"]<5]
    return {"executive_summary":"Connect virtual-tour attention, product discovery, appointments and paid orders into one measurable funnel.","strengths":[f"{len(products)} active products",f"{snapshot['tours']['count']} virtual tours"],"weaknesses":["External social metrics require regular imports or official API connections."],"opportunities":["Place products inside the highest-intent tour scenes","Retarget visitors who viewed products but did not purchase"],"recommendations":["Track view_product, add_to_cart, begin_checkout, purchase and book_appointment events.","Use one primary offer per campaign and measure paid conversion."]+([f"Restock or pause promotion for: {', '.join(low[:5])}."] if low else []),"suggested_campaigns":[{"name":"Tour to Order","goal":"Convert tour engagement into purchases","channels":["Website","Instagram","WhatsApp"]}],"priority_actions":[{"priority":1,"action":"Connect featured products to relevant tour scenes","impact":"high","effort":"medium"}],"funnel_diagnosis":snapshot["commerce"],"product_recommendations":products[:5],"appointment_strategy":["Show booking CTA after meaningful scene engagement"],"content_calendar":[{"day":"Monday","content":"Featured product + tour scene"},{"day":"Thursday","content":"Customer proof + booking CTA"}]}

def generate_market_insight(organization):
    snapshot=build_organization_snapshot(organization); model=getattr(settings,"GEMINI_MARKET_MODEL",os.getenv("GEMINI_MARKET_MODEL","gemini-2.5-flash"))
    result=None
    try:
        from google import genai
        from google.genai import types
        client=genai.Client(vertexai=getattr(settings,"GOOGLE_GENAI_USE_VERTEXAI",True),project=getattr(settings,"GOOGLE_CLOUD_PROJECT",None),location=getattr(settings,"GOOGLE_CLOUD_LOCATION","us-central1"))
        schema={"type":"object","properties":{k:v for k,v in {"executive_summary":{"type":"string"},"strengths":{"type":"array","items":{"type":"string"}},"weaknesses":{"type":"array","items":{"type":"string"}},"opportunities":{"type":"array","items":{"type":"string"}},"recommendations":{"type":"array","items":{"type":"string"}},"suggested_campaigns":{"type":"array","items":{"type":"object"}},"priority_actions":{"type":"array","items":{"type":"object"}},"funnel_diagnosis":{"type":"object"},"product_recommendations":{"type":"array","items":{"type":"object"}},"appointment_strategy":{"type":"array","items":{"type":"string"}},"content_calendar":{"type":"array","items":{"type":"object"}}}.items()},"required":["executive_summary","recommendations","priority_actions","funnel_diagnosis"]}
        prompt="""You are Twinscopes Growth Intelligence, a senior ecommerce, local-market and virtual-tour strategist. Analyze only supplied metrics. Diagnose the funnel from tour/product views to cart, checkout, paid order and appointment. Prioritize actions by impact and effort. Recommend products to feature, tour hotspots, delivery policies, appointment CTAs, social campaigns and a 7-day content plan. Do not invent metrics. Return concise JSON.\n\n"""+json.dumps(snapshot,default=str,ensure_ascii=False)
        response=client.models.generate_content(model=model,contents=prompt,config=types.GenerateContentConfig(response_mime_type="application/json",response_schema=schema,temperature=.2)); result=json.loads(response.text)
    except Exception:
        result=_fallback(snapshot); model="fallback-rules"
    return MarketInsightReport.objects.create(organization=organization,input_snapshot=snapshot,executive_summary=result.get("executive_summary",""),strengths=result.get("strengths",[]),weaknesses=result.get("weaknesses",[]),opportunities=result.get("opportunities",[]),recommendations=result.get("recommendations",[]),suggested_campaigns=result.get("suggested_campaigns",[]),priority_actions=result.get("priority_actions",[]),funnel_diagnosis=result.get("funnel_diagnosis",{}),product_recommendations=result.get("product_recommendations",[]),appointment_strategy=result.get("appointment_strategy",[]),content_calendar=result.get("content_calendar",[]),model_name=model)
