import os
import json
import io
import stripe
import requests as http_requests
from datetime import date, datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import init_db, get_db_context
from auth import (
    hash_password,
    verify_password,
    create_jwt,
    get_current_user,
    require_admin,
    generate_password,
    create_reset_token,
    verify_reset_token,
)
from email_service import send_welcome_email, send_password_reset_email, send_sale_notification
from claude_service import chat
from doc_service import generate_docx

app = FastAPI(title="Affiliate Terms Wizard")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://termswizard.mattmcwilliams.com")


@app.on_event("startup")
def startup():
    init_db()
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    print(f"ADMIN_EMAIL={admin_email!r}")
    if admin_email and admin_password:
        try:
            with get_db_context() as conn:
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ?", (admin_email,)
                ).fetchone()
                print(f"User already exists: {existing is not None}")
                if existing:
                    conn.execute(
                        "UPDATE users SET is_admin = 1, password_hash = ? WHERE email = ?",
                        (hash_password(admin_password), admin_email),
                    )
                    print("Existing user promoted to admin")
                else:
                    conn.execute(
                        "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, 1)",
                        (admin_email, hash_password(admin_password)),
                    )
                    print("Admin user created")
        except Exception as e:
            print(f"Admin creation error: {e}")


# ──────────────────────────────────────
# Pages
# ──────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse("reset_password.html", {"request": request})


@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    try:
        get_current_user(request)
    except HTTPException:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("app.html", {"request": request})


@app.get("/agreements", response_class=HTMLResponse)
async def agreements_page(request: Request):
    try:
        get_current_user(request)
    except HTTPException:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("agreements.html", {"request": request})


@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    try:
        get_current_user(request)
    except HTTPException:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("account.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    try:
        require_admin(request)
    except HTTPException:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/test-email")
async def test_email():
    try:
        send_welcome_email("matt@mattmcwilliams.com", "test-password-123")
        return {"result": "success"}
    except Exception as e:
        return {"result": "error", "detail": str(e)}


@app.get("/order", response_class=HTMLResponse)
async def order_page(request: Request):
    return templates.TemplateResponse("order.html", {
        "request": request,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY,
    })


@app.get("/order-confirmation", response_class=HTMLResponse)
async def confirmation_page(request: Request, email: str = ""):
    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "email": email,
    })


# ──────────────────────────────────────
# Auth API
# ──────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetRequestBody(BaseModel):
    email: str


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str


class PaymentIntentRequest(BaseModel):
    email: str
    first_name: str
    last_name: str


class AdminCreateUserRequest(BaseModel):
    email: str
    first_name: str = ""
    last_name: str = ""
    lifetime_limit: int = 20


@app.post("/api/create-payment-intent")
async def create_payment_intent(data: PaymentIntentRequest):
    try:
        intent = stripe.PaymentIntent.create(
            amount=2900,  # $29.00 in cents
            currency="usd",
            metadata={
                "product": "terms-wizard",
                "email": data.email,
                "first_name": data.first_name,
                "last_name": data.last_name,
            },
            receipt_email=data.email,
        )
        return {"client_secret": intent.client_secret}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/login")
async def login(body: LoginRequest):
    with get_db_context() as conn:
        user = conn.execute(
            "SELECT id, email, password_hash, is_admin FROM users WHERE email = ?",
            (body.email,),
        ).fetchone()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_jwt(user["id"], user["email"], bool(user["is_admin"]))
    response = JSONResponse({"success": True, "is_admin": bool(user["is_admin"])})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
        max_age=86400,
    )
    return response


@app.post("/api/logout")
async def logout():
    response = JSONResponse({"success": True})
    response.delete_cookie("access_token")
    return response


@app.post("/api/change-password")
async def change_password(body: ChangePasswordRequest, request: Request):
    user = get_current_user(request)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["user_id"],)
        ).fetchone()
        if not row or not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(body.new_password), user["user_id"]),
        )
    return {"success": True}


@app.post("/api/request-reset")
async def request_reset(body: ResetRequestBody):
    with get_db_context() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (body.email,)
        ).fetchone()
    # Always return success to avoid email enumeration
    if user:
        token = create_reset_token(user["id"])
        reset_url = f"{BASE_URL}/reset-password?token={token}"
        try:
            send_password_reset_email(body.email, reset_url)
        except Exception:
            pass  # Don't leak errors
    return {"success": True, "message": "If that email exists, a reset link has been sent."}


@app.post("/api/reset-password")
async def reset_password(body: ResetPasswordBody):
    user_id = verify_reset_token(body.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    with get_db_context() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(body.new_password), user_id),
        )
    return {"success": True}


# ──────────────────────────────────────
# Usage / Account API
# ──────────────────────────────────────

@app.get("/api/usage")
async def get_usage(request: Request):
    user = get_current_user(request)
    today = date.today().isoformat()
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT agreement_count, lifetime_limit FROM users WHERE id = ?", (user["user_id"],)
        ).fetchone()
        daily = conn.execute(
            "SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user["user_id"], today),
        ).fetchone()
    return {
        "lifetime_used": row["agreement_count"] if row else 0,
        "lifetime_max": row["lifetime_limit"] if row else 20,
        "daily_used": daily["count"] if daily else 0,
        "daily_max": 3,
        "email": user["email"],
    }


def check_limits(user_id: int) -> str | None:
    today = date.today().isoformat()
    with get_db_context() as conn:
        user_row = conn.execute(
            "SELECT agreement_count, lifetime_limit FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        daily_row = conn.execute(
            "SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, today),
        ).fetchone()

    lifetime = user_row["agreement_count"] if user_row else 0
    lifetime_limit = user_row["lifetime_limit"] if user_row else 20
    daily = daily_row["count"] if daily_row else 0

    if lifetime >= lifetime_limit:
        return "You've used all of your lifetime agreements. Visit your Account page to purchase more."
    if daily >= 3:
        return "You've reached your limit for today. Come back tomorrow!"
    return None


def increment_usage(user_id: int):
    today = date.today().isoformat()
    with get_db_context() as conn:
        conn.execute(
            "UPDATE users SET agreement_count = agreement_count + 1 WHERE id = ?",
            (user_id,),
        )
        existing = conn.execute(
            "SELECT id FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, today),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE daily_usage SET count = count + 1 WHERE user_id = ? AND usage_date = ?",
                (user_id, today),
            )
        else:
            conn.execute(
                "INSERT INTO daily_usage (user_id, usage_date, count) VALUES (?, ?, 1)",
                (user_id, today),
            )


# ──────────────────────────────────────
# Chat / Conversation API
# ──────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    conversation_id: int | None = None
    existing_agreement_text: str | None = None


def _is_agreement_text(text: str) -> bool:
    """Detect if a response is the full generated agreement."""
    t = text.strip()
    return "Affiliate Terms & Conditions" in t[:200] and "FTC DISCLOSURE REQUIREMENTS" in t


@app.post("/api/chat")
async def chat_endpoint(body: ChatMessage, request: Request):
    user = get_current_user(request)
    user_id = user["user_id"]

    with get_db_context() as conn:
        if body.conversation_id:
            conv = conn.execute(
                "SELECT id, messages, status FROM conversations WHERE id = ? AND user_id = ?",
                (body.conversation_id, user_id),
            ).fetchone()
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")
            messages = json.loads(conv["messages"])
        else:
            # Check limits before starting a new conversation
            limit_msg = check_limits(user_id)
            if limit_msg:
                return {"error": limit_msg, "limit_reached": True}
            conn.execute(
                "INSERT INTO conversations (user_id, messages) VALUES (?, '[]')",
                (user_id,),
            )
            conv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            body.conversation_id = conv_id
            messages = []

    # Add user message
    messages.append({"role": "user", "content": body.message})

    # Call Claude
    existing_text = body.existing_agreement_text or ""
    assistant_reply = chat(messages, existing_text)

    # Add assistant response
    messages.append({"role": "assistant", "content": assistant_reply})

    # Detect agreement completion: check if reply contains "Affiliate Terms & Conditions"
    # in the first few lines, indicating the full agreement was generated
    agreement_complete = _is_agreement_text(assistant_reply)

    with get_db_context() as conn:
        status = "completed" if agreement_complete else "active"
        conn.execute(
            "UPDATE conversations SET messages = ?, status = ? WHERE id = ?",
            (json.dumps(messages), status, body.conversation_id),
        )

    # If agreement is complete, save it and increment usage
    if agreement_complete:
        agreement_text = assistant_reply.strip()
        # Try to extract a title from the first line
        first_line = agreement_text.split("\n")[0].strip()
        title = first_line if len(first_line) < 200 else "Affiliate Terms & Conditions"

        # Extract company name from Q1 answer (second user message, first is "Let's get started")
        company_name = ""
        user_messages = [m["content"] for m in messages if m["role"] == "user"]
        if len(user_messages) >= 2:
            company_name = user_messages[1].strip()
        if not company_name:
            company_name = title

        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO agreements (user_id, title, company_name, conversation_id, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, title, company_name, body.conversation_id, agreement_text),
            )
        increment_usage(user_id)

    return {
        "reply": assistant_reply.strip(),
        "conversation_id": body.conversation_id,
        "agreement_complete": agreement_complete,
    }


@app.post("/api/conversation/new")
async def new_conversation(request: Request):
    user = get_current_user(request)
    limit_msg = check_limits(user["user_id"])
    if limit_msg:
        return {"error": limit_msg, "limit_reached": True}
    return {"success": True}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, request: Request):
    user = get_current_user(request)
    with get_db_context() as conn:
        conv = conn.execute(
            "SELECT id, messages, status FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user["user_id"]),
        ).fetchone()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": conv["id"],
        "messages": json.loads(conv["messages"]),
        "status": conv["status"],
    }


# ──────────────────────────────────────
# Upload existing agreement
# ──────────────────────────────────────

@app.post("/api/upload-agreement")
async def upload_agreement(request: Request, file: UploadFile = File(...)):
    get_current_user(request)

    content = await file.read()
    text = ""

    if file.filename and file.filename.lower().endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs)
    elif file.filename and file.filename.lower().endswith(".pdf"):
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise HTTPException(status_code=400, detail="Only .docx and .pdf files are supported")

    return {"text": text}


# ──────────────────────────────────────
# Agreements API
# ──────────────────────────────────────

@app.get("/api/agreements")
async def list_agreements(request: Request):
    user = get_current_user(request)
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, title, company_name, conversation_id, created_at FROM agreements WHERE user_id = ? ORDER BY created_at DESC",
            (user["user_id"],),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "company_name": r["company_name"] or r["title"],
            "conversation_id": r["conversation_id"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.get("/api/agreements/{agreement_id}")
async def get_agreement(agreement_id: int, request: Request):
    user = get_current_user(request)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT id, title, content, created_at FROM agreements WHERE id = ? AND user_id = ?",
            (agreement_id, user["user_id"]),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agreement not found")
    return {"id": row["id"], "title": row["title"], "content": row["content"], "created_at": row["created_at"]}


# ──────────────────────────────────────
# Word Doc Generation
# ──────────────────────────────────────

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocRequest(BaseModel):
    text: str


@app.post("/api/doc")
async def create_doc(body: DocRequest, request: Request):
    get_current_user(request)
    doc_bytes = generate_docx(body.text)
    return StreamingResponse(
        io.BytesIO(doc_bytes),
        media_type=DOCX_CONTENT_TYPE,
        headers={"Content-Disposition": "attachment; filename=affiliate-terms.docx"},
    )


@app.get("/api/agreements/{agreement_id}/doc")
async def download_agreement_doc(agreement_id: int, request: Request):
    user = get_current_user(request)
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT content, title FROM agreements WHERE id = ? AND user_id = ?",
            (agreement_id, user["user_id"]),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agreement not found")

    doc_bytes = generate_docx(row["content"])
    safe_title = "".join(c for c in row["title"] if c.isalnum() or c in " -_")[:50]
    return StreamingResponse(
        io.BytesIO(doc_bytes),
        media_type=DOCX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.docx"'},
    )


# ──────────────────────────────────────
# Stripe Webhook
# ──────────────────────────────────────

def _create_user_account(email: str, first_name: str = "", last_name: str = ""):
    """Create a new user account and send welcome email, or add 20 to lifetime limit if user already exists."""
    with get_db_context() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

    if existing:
        with get_db_context() as conn:
            conn.execute(
                "UPDATE users SET lifetime_limit = lifetime_limit + 20 WHERE id = ?",
                (existing["id"],),
            )
        return

    password = generate_password()
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, first_name, last_name, is_admin, agreement_count) VALUES (?, ?, ?, ?, 0, 0)",
            (email, hash_password(password), first_name, last_name),
        )
    try:
        send_welcome_email(email, password)
    except Exception as e:
        print(f"Failed to send welcome email to {email}: {e}")

    try:
        send_sale_notification(email, first_name, last_name)
    except Exception as e:
        print(f"Failed to send sale notification for {email}: {e}")

    # Create and tag subscriber in Kit (ConvertKit)
    kit_api_secret = os.getenv("KIT_API_SECRET")
    kit_tag_id = os.getenv("KIT_TAG_ID")
    if kit_api_secret and kit_tag_id:
        print(f"Kit API: email={email}, first_name={first_name}, api_key={kit_api_secret[:5]}..., tag_id={kit_tag_id}")
        kit_headers = {"X-Kit-Api-Key": kit_api_secret, "Content-Type": "application/json"}
        try:
            print("Kit API: Creating subscriber...")
            r1 = http_requests.post(
                "https://api.kit.com/v4/subscribers",
                headers=kit_headers,
                json={"email_address": email, "first_name": first_name},
            )
            print(f"Kit API: Create subscriber response: {r1.status_code} {r1.text}")
            print("Kit API: Tagging subscriber...")
            r2 = http_requests.post(
                f"https://api.kit.com/v4/tags/{kit_tag_id}/subscribers",
                headers=kit_headers,
                json={"email_address": email},
            )
            print(f"Kit API: Tag subscriber response: {r2.status_code} {r2.text}")
        except Exception as e:
            print(f"Failed to create/tag {email} in Kit: {e}")


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        if email:
            _create_user_account(email)

    elif event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        if payment_intent.get("metadata", {}).get("product") != "terms-wizard":
            return {"status": "ignored"}
        metadata = payment_intent.get("metadata", {})
        email = metadata.get("email")
        first_name = metadata.get("first_name", "")
        last_name = metadata.get("last_name", "")
        if email:
            _create_user_account(email, first_name, last_name)

    return {"status": "ok"}


# ──────────────────────────────────────
# Admin API
# ──────────────────────────────────────

@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    require_admin(request)
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, email, is_admin, agreement_count, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "email": r["email"],
            "is_admin": bool(r["is_admin"]),
            "agreement_count": r["agreement_count"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.post("/api/admin/users")
async def admin_create_user(body: AdminCreateUserRequest, request: Request):
    require_admin(request)

    with get_db_context() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (body.email,)
        ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="A user with that email already exists")

    password = generate_password()
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, first_name, last_name, lifetime_limit) VALUES (?, ?, ?, ?, ?)",
            (body.email, hash_password(password), body.first_name, body.last_name, body.lifetime_limit),
        )

    try:
        send_welcome_email(body.email, password)
    except Exception as e:
        print(f"Failed to send welcome email to {body.email}: {e}")

    return {"success": True, "email": body.email, "password": password}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
