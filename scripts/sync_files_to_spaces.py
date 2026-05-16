import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

# Konfiguracja DigitalOcean Spaces (S3 compatible)
SPACES_ACCESS_KEY = os.getenv("SPACES_ACCESS_KEY")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY")
SPACES_BUCKET_NAME = os.getenv("SPACES_BUCKET_NAME")
SPACES_REGION = os.getenv("SPACES_REGION", "fra1")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "backend/uploads")

# Endpoint dla DO Spaces
SPACES_ENDPOINT = f"https://{SPACES_REGION}.digitaloceanspaces.com"

def sync_files():
    if not all([SPACES_ACCESS_KEY, SPACES_SECRET_KEY, SPACES_BUCKET_NAME]):
        print("BŁĄD: Musisz ustawić zmienne środowiskowe: SPACES_ACCESS_KEY, SPACES_SECRET_KEY, SPACES_BUCKET_NAME")
        return

    # Inicjalizacja klienta S3 dla Spaces
    session = boto3.session.Session()
    client = session.client(
        's3',
        region_name=SPACES_REGION,
        endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=SPACES_ACCESS_KEY,
        aws_secret_access_key=SPACES_SECRET_KEY
    )

    if not os.path.exists(UPLOAD_DIR):
        print(f"BŁĄD: Katalog {UPLOAD_DIR} nie istnieje.")
        return

    files = os.listdir(UPLOAD_DIR)
    if not files:
        print("Brak plików do zsynchronizowania.")
        return

    print(f"--- START SYNCHRONIZACJI PLIKÓW: {UPLOAD_DIR} -> SPACES:{SPACES_BUCKET_NAME} ---")
    
    success_count = 0
    fail_count = 0

    for filename in files:
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Pomijamy podkatalogi
        if not os.path.isfile(file_path):
            continue

        print(f"Wysyłanie: {filename}...")
        try:
            # Wysyłamy plik (Multipart upload jest automatyczny w boto3 dla dużych plików)
            client.upload_file(file_path, SPACES_BUCKET_NAME, filename)
            print(f"  - Sukces.")
            success_count += 1
        except ClientError as e:
            print(f"  - BŁĄD (ClientError): {e}")
            fail_count += 1
        except Exception as e:
            print(f"  - BŁĄD: {e}")
            fail_count += 1

    print("\n--- SYNCHRONIZACJA ZAKOŃCZONA ---")
    print(f"Pomyślnie wysłano: {success_count}")
    print(f"Błędy: {fail_count}")

if __name__ == "__main__":
    sync_files()
