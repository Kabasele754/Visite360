INTENTS={
 'booking':['book','appointment','reserve','reservation','visit','rendez-vous','réserver'],
 'product':['product','price','buy','cart','produit','prix','acheter','panier'],
 'quote':['quote','quotation','devis','estimate'],
 'contact':['human','agent','contact','call','whatsapp','person'],
}
def detect_intent(text):
    t=(text or '').lower()
    for intent,words in INTENTS.items():
        if any(w in t for w in words):return intent
    return 'question'
