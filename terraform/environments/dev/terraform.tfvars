environment    = "dev"
region         = "fra1"
domain_name    = "sendr.email"

# --- SECRETS ---
app_secret_key = "12345678901234567890"
resend_api_key = "re_92bt93Vp_KmKJqvaYtuTDPwmXw2Hgrh1U"

# --- DIGITALOCEAN SPACES (S3) ---
spaces_access_key = "DO00K79HNABNA2UHA42Y"
spaces_secret_key = "gI8UphnLZzRr1xMH/hBLK89a5WO2NeWLPRscCewuTlE"

# --- KONFIGURACJA KLASTRA K8S ---
k8s_node_count = 2
k8s_auto_scale = false

do_token="YOUR_DIGITALOCEAN_TOKEN"

smtp_host = "smtp.resend.com"
smtp_port = 587
smtp_user = "resend"
smtp_password = "re_92bt93Vp_KmKJqvaYtuTDPwmXw2Hgrh1U"
