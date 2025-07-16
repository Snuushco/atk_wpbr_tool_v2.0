import os
import stripe
from dotenv import load_dotenv
import logging

# Laad environment variables
load_dotenv()

# Stripe configuratie
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Product en prijs configuratie
PRODUCT_NAME = "ATK-WPBR Tool Toegang"
PRODUCT_DESCRIPTION = "Toegang tot de ATK-WPBR Tool voor het aanvragen van beveiligingspassen"
PRICE_AMOUNT = 2500  # €25.00 in centen
PRICE_CURRENCY = "eur"

# Configureer Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    logging.warning("STRIPE_SECRET_KEY niet ingesteld - betaalfunctionaliteit uitgeschakeld")

def create_payment_intent(amount=None, currency=None, metadata=None):
    """Maak een nieuwe payment intent aan"""
    if not STRIPE_SECRET_KEY:
        return None, "Stripe niet geconfigureerd"
    
    try:
        amount = amount or PRICE_AMOUNT
        currency = currency or PRICE_CURRENCY
        
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata or {},
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return intent, None
    except Exception as e:
        logging.error(f"Error creating payment intent: {e}")
        return None, str(e)

def get_payment_intent(payment_intent_id):
    """Haal een payment intent op"""
    if not STRIPE_SECRET_KEY:
        return None
    
    try:
        return stripe.PaymentIntent.retrieve(payment_intent_id)
    except Exception as e:
        logging.error(f"Error retrieving payment intent: {e}")
        return None

def create_customer(email, name=None):
    """Maak een nieuwe Stripe customer aan"""
    if not STRIPE_SECRET_KEY:
        return None, "Stripe niet geconfigureerd"
    
    try:
        customer = stripe.Customer.create(
            email=email,
            name=name,
        )
        return customer, None
    except Exception as e:
        logging.error(f"Error creating customer: {e}")
        return None, str(e)

def get_customer(customer_id):
    """Haal een customer op"""
    if not STRIPE_SECRET_KEY:
        return None
    
    try:
        return stripe.Customer.retrieve(customer_id)
    except Exception as e:
        logging.error(f"Error retrieving customer: {e}")
        return None

def verify_webhook_signature(payload, sig_header):
    """Verificeer webhook signature"""
    if not STRIPE_WEBHOOK_SECRET:
        return None, "Webhook secret niet ingesteld"
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        return event, None
    except ValueError as e:
        return None, f"Invalid payload: {e}"
    except stripe.error.SignatureVerificationError as e:
        return None, f"Invalid signature: {e}"

def get_price_info():
    """Haal prijsinformatie op"""
    return {
        'amount': PRICE_AMOUNT,
        'currency': PRICE_CURRENCY,
        'formatted_price': f"€{PRICE_AMOUNT/100:.2f}",
        'product_name': PRODUCT_NAME,
        'product_description': PRODUCT_DESCRIPTION
    }

def is_stripe_configured():
    """Controleer of Stripe correct is geconfigureerd"""
    return bool(STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY) 