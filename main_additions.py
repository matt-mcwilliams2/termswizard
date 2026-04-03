# ============================================================
# ADD THESE TO YOUR EXISTING main.py
# ============================================================

# 1. Add this to your imports at the top (if not already there):
#    import stripe
#    from pydantic import BaseModel

# 2. Add STRIPE_PUBLISHABLE_KEY to your env config section near
#    the other Stripe vars:
#
#    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# 3. Add this Pydantic model near your other models:

class PaymentIntentRequest(BaseModel):
    email: str
    first_name: str
    last_name: str

# 4. Add these three routes to your routes section:

@app.get("/order")
async def order_page(request: Request):
    return templates.TemplateResponse("order.html", {
        "request": request,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY
    })

@app.get("/order-confirmation")
async def confirmation_page(request: Request, email: str = ""):
    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "email": email
    })

@app.post("/api/create-payment-intent")
async def create_payment_intent(data: PaymentIntentRequest):
    try:
        intent = stripe.PaymentIntent.create(
            amount=4900,  # $49.00 in cents
            currency="usd",
            metadata={
                "email": data.email,
                "first_name": data.first_name,
                "last_name": data.last_name
            },
            receipt_email=data.email,
        )
        return {"client_secret": intent.client_secret}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 5. In your existing Stripe webhook handler, add handling for
#    payment_intent.succeeded alongside checkout.session.completed.
#    Find your webhook route and add this inside the handler:
#
#    elif event["type"] == "payment_intent.succeeded":
#        payment_intent = event["data"]["object"]
#        email = payment_intent.get("metadata", {}).get("email")
#        first_name = payment_intent.get("metadata", {}).get("first_name", "")
#        last_name = payment_intent.get("metadata", {}).get("last_name", "")
#        if email:
#            await create_user_account(email, first_name, last_name)
#
#    Make sure your create_user_account function (or however you
#    create accounts in the webhook) accepts first_name and last_name
#    and stores them in the database.
