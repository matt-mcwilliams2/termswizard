import os
import requests


RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")


def send_email(to_email: str, subject: str, html_body: str):
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        },
    )
    resp.raise_for_status()


def send_welcome_email(email: str, password: str):
    subject = "Welcome! Let's make your affiliate program bulletproof"

    html_body = f"""<div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
<p>Hey there,</p>

<p>First off...huge congrats on grabbing Affiliate Terms Wizard!</p>

<p>\U0001f449 <a href="https://termswizard.mattmcwilliams.com" style="color: #39125a; font-weight: bold;">Click here to access Affiliate Terms Wizard now</a></p>

<p><strong>Email:</strong> {email}<br>
<strong>Password:</strong> {password}</p>

<p>You just made a smart move toward building a stronger, safer, and way more professional affiliate program.</p>

<p>Now let's talk about why this actually matters.</p>

<p>Because let's face it...terms and conditions aren't exactly what gets people out of bed in the morning.</p>

<p>But when you get them right? They're the difference between "smooth sailing" and "I just spent four hours cleaning up an affiliate disaster."</p>

<p>Think of your affiliate terms as the constitution of your program. They lay the foundation for every partnership. They protect your brand. They tell your affiliates exactly what's allowed and what's not WITHOUT legal jargon or guesswork.</p>

<p>Most programs either:</p>
<ul>
<li>Skip this completely (risky)</li>
<li>Copy and paste from someone else (yikes)</li>
<li>Or hire a lawyer and pay $300+ for a basic contract (not ideal)</li>
</ul>

<p>You? You've got the shortcut.</p>

<p>This tool walks you through the entire process, step-by-step. No legal training needed. No confusion. No overpriced attorneys. Just smart, clear, effective terms written for affiliate managers...by someone who's been there.</p>

<p>Start with the basics. Take your time. You can always redo them if needed.</p>

<p>\U0001f449 <a href="https://termswizard.mattmcwilliams.com" style="color: #39125a; font-weight: bold;">Click here to access Affiliate Terms Wizard now</a></p>

<p>Best regards,<br>Matt</p>
</div>"""

    send_email(email, subject, html_body)


def send_password_reset_email(email: str, reset_url: str):
    subject = "Reset your Affiliate Terms Wizard password"

    html_body = f"""<div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
<p>Hi,</p>
<p>You requested a password reset for your Affiliate Terms Wizard account.</p>
<p><a href="{reset_url}" style="display: inline-block; background: #e8c14f; color: #000; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Reset Password</a></p>
<p>This link expires in 1 hour.</p>
<p>If you didn't request this, you can safely ignore this email.</p>
<p>Best regards,<br>Affiliate Terms Wizard</p>
</div>"""

    send_email(email, subject, html_body)
