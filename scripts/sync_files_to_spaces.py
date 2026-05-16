import os
import sys
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

# Obliczamy ścieżkę do root projektu względem lokalizacji tego skryptu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

# Wczytujemy .env ręcznie dla skryptu
def load_env():
    possible_paths = [os.path.join(BACKEND_DIR, ".env"), os.path.join(os.getcwd(), ".env")]
    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        parts = line.strip().split("=", 1)
                        if len(parts) == 2:
                            k, v = parts
                            os.environ.setdefault(k, v)
                            # Mapujemy też wersję bez prefixu SENDR_
                            if k.startswith("SENDR_"):
                                os.environ.setdefault(k.replace("SENDR_", ""), v)

load_env()

# Konfiguracja DigitalOcean Spaces (S3 compatible)
SPACES_ACCESS_KEY = os.getenv("SPACES_ACCESS_KEY")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY")
SPACES_BUCKET_NAME = os.getenv("SPACES_BUCKET_NAME")
SPACES_REGION = os.getenv("SPACES_REGION", "fra1")

# Ścieżka do folderu uploads
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BACKEND_DIR, "uploads"))

# Endpoint dla DO Spaces
SPACES_ENDPOINT = f"https://{SPACES_REGION}.digitaloceanspaces.com"

def sync_files():
    if not all([SPACES_ACCESS_KEY, SPACES_SECRET_KEY, SPACES_BUCKET_NAME]):
        print("BŁĄD: Musisz ustawić zmienne środowiskowe: SPACES_ACCESS_KEY, SPACES_SECRET_KEY, SPACES_BUCKET_NAME")
        print("Upewnij się, że plik .env w folderu backend/ zawiera te klucze.")
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
    # Filtrujemy tylko pliki (ignorujemy .gitkeep itp.)
    files = [f for f in files if os.path.isfile(os.path.join(UPLOAD_DIR, f)) and not f.startswith(".")]
    
    if not files:
        print(f"Brak plików do zsynchronizowania w {UPLOAD_DIR}.")
        return

    print(f"--- START SYNCHRONIZACJI PLIKÓW: {UPLOAD_DIR} -> SPACES:{SPACES_BUCKET_NAME} ---")
    
    success_count = 0
    fail_count = 0

    for filename in files:
        file_path = os.path.join(UPLOAD_DIR, filename)
        
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
