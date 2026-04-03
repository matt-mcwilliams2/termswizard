import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")


def send_email(to_email: str, subject: str, html_body: str, text_body: str = ""):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())


def send_welcome_email(email: str, password: str):
    subject = "Welcome! Let's make your affiliate program bulletproof"
    text_body = f"""Hey there,

First off...huge congrats on grabbing Affiliate Terms Wizard!

Click here to access Affiliate Terms Wizard now: https://termswizard.mattmcwilliams.com

Email: {email}
Password: {password}

You just made a smart move toward building a stronger, safer, and way more professional affiliate program.

Now let's talk about why this actually matters.

Because let's face it...terms and conditions aren't exactly what gets people out of bed in the morning.

But when you get them right? They're the difference between "smooth sailing" and "I just spent four hours cleaning up an affiliate disaster."

Think of your affiliate terms as the constitution of your program. They lay the foundation for every partnership. They protect your brand. They tell your affiliates exactly what's allowed and what's not WITHOUT legal jargon or guesswork.

Most programs either:
- Skip this completely (risky)
- Copy and paste from someone else (yikes)
- Or hire a lawyer and pay $300+ for a basic contract (not ideal)

You? You've got the shortcut.

This tool walks you through the entire process, step-by-step. No legal training needed. No confusion. No overpriced attorneys. Just smart, clear, effective terms written for affiliate managers...by someone who's been there.

Start with the basics. Take your time. You can always redo them if needed.

Click here to access Affiliate Terms Wizard now: https://termswizard.mattmcwilliams.com

Best regards,
Matt"""

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

    send_email(email, subject, html_body, text_body)


def send_password_reset_email(email: str, reset_url: str):
    subject = "Reset your Affiliate Terms Wizard password"
    text_body = f"""Hi,

You requested a password reset for your Affiliate Terms Wizard account.

Click here to reset your password: {reset_url}

This link expires in 1 hour.

If you didn't request this, you can safely ignore this email.

Best regards,
Affiliate Terms Wizard"""

    html_body = f"""<div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
<p>Hi,</p>
<p>You requested a password reset for your Affiliate Terms Wizard account.</p>
<p><a href="{reset_url}" style="display: inline-block; background: #e8c14f; color: #000; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Reset Password</a></p>
<p>This link expires in 1 hour.</p>
<p>If you didn't request this, you can safely ignore this email.</p>
<p>Best regards,<br>Affiliate Terms Wizard</p>
</div>"""

    send_email(email, subject, html_body, text_body)
