# Affiliate Terms Wizard

A web app that helps users create professional affiliate program terms and conditions using an AI-powered chat interface.

## Features

- AI-guided questionnaire to create custom affiliate terms
- Upload & review existing agreements (.docx, .pdf)
- Word document (.docx) generation
- Stripe integration for account provisioning
- Usage limits (3/day, 20/lifetime)
- Admin dashboard
- Password reset via email

## Local Setup

### Prerequisites

- Python 3.11+

### 1. Clone and set up

```bash
cd ~/Projects/termswizard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 4. Create an admin user

```bash
python seed_admin.py --email admin@example.com --password yourpassword
```

### 5. Run the app

```bash
python main.py
```

The app runs at http://localhost:8000

## Deployment on Ubuntu

### 1. Server setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx
```

### 2. Deploy the app

```bash
sudo mkdir -p /opt/termswizard
cd /opt/termswizard
# Copy project files here

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with production values (set BASE_URL, JWT_SECRET, etc.)

python seed_admin.py --email admin@example.com --password yourpassword
```

### 3. Create systemd service

```bash
sudo tee /etc/systemd/system/termswizard.service > /dev/null <<EOF
[Unit]
Description=Affiliate Terms Wizard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/termswizard
ExecStart=/opt/termswizard/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/opt/termswizard/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable termswizard
sudo systemctl start termswizard
```

### 4. Configure Nginx

```bash
sudo tee /etc/nginx/sites-available/termswizard > /dev/null <<'EOF'
server {
    listen 80;
    server_name termswizard.mattmcwilliams.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 10M;
}
EOF

sudo ln -sf /etc/nginx/sites-available/termswizard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. SSL with Let's Encrypt

```bash
sudo certbot --nginx -d termswizard.mattmcwilliams.com
```

### 6. Stripe Webhook

Set up a webhook in Stripe Dashboard pointing to:
```
https://termswizard.mattmcwilliams.com/webhook/stripe
```

Listen for: `checkout.session.completed`

Copy the webhook signing secret to your `.env` file as `STRIPE_WEBHOOK_SECRET`.
