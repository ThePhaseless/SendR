import os
import sys
from typing import List, Type
import sqlalchemy

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, make_transient
from sqlmodel import SQLModel, Session, select

# Obliczamy ścieżkę do backend/src względem lokalizacji tego skryptu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_SRC = os.path.join(PROJECT_ROOT, "backend", "src")

sys.path.append(BACKEND_SRC)

# Wczytujemy .env ręcznie dla skryptu
def load_env():
    possible_paths = [os.path.join("backend", ".env"), ".env"]
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

from models import (
    User, VerificationCode, AuthToken, UserLogin, FileUpload,
    UploadGroupSettings, UploadPassword, UploadEmailRecipient,
    DownloadLog, Transfer, Subscription
)

# Konfiguracja połączeń
SQLITE_DB_PATH = os.path.join(PROJECT_ROOT, "backend", "sendr.db")
SQLITE_URL = os.getenv("SQLITE_URL", f"sqlite:///{SQLITE_DB_PATH}")
POSTGRES_URL = os.getenv("DATABASE_URL")

if not os.path.exists(SQLITE_DB_PATH) and not os.getenv("SQLITE_URL"):
    print(f"UWAGA: Nie znaleziono pliku bazy SQLite w: {SQLITE_DB_PATH}")
    print("Jeśli Twoja baza ma inną nazwę lub lokalizację, ustaw zmienną SQLITE_URL.")

if not POSTGRES_URL:
    print("BŁĄD: Musisz ustawić zmienną środowiskową DATABASE_URL (postgresql://...)")
    sys.exit(1)

# SQLAlchemy domyślnie szuka psycopg2 dla prefixu postgresql://.
if POSTGRES_URL.startswith("postgresql://"):
    POSTGRES_URL = POSTGRES_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Silniki baz danych
sqlite_engine = create_engine(SQLITE_URL)
postgres_engine = create_engine(POSTGRES_URL)

# Sesje
SqliteSession = sessionmaker(bind=sqlite_engine)
PostgresSession = sessionmaker(bind=postgres_engine)

def migrate_table(model_class: Type[SQLModel]):
    print(f"Migracja tabeli: {model_class.__tablename__}...")
    
    with SqliteSession() as sqlite_session:
        # Pobieramy wszystkie rekordy z SQLite
        records = sqlite_session.query(model_class).all()
        if not records:
            print(f"  - Brak danych do przeniesienia.")
            return

        with PostgresSession() as pg_session:
            # CZYŚCIMY tabelę w Postgres przed migracją, aby uniknąć błędów UniqueViolation (Duplicate Key)
            # Używamy TRUNCATE ... CASCADE, aby wyczyścić też tabele powiązane
            pg_session.execute(text(f"TRUNCATE TABLE \"{model_class.__tablename__}\" CASCADE"))
            
            for record in records:
                # Odłączamy obiekt od starej sesji i czyścimy jego stan wewnętrzny
                sqlite_session.expunge(record)
                make_transient(record)
                # Dodajemy go jako "nowy" obiekt do Postgresa (zachowując ID)
                pg_session.add(record)
            
            pg_session.commit()
            print(f"  - Przeniesiono {len(records)} rekordów.")

def reset_postgres_sequences():
    """Po ręcznym wstawieniu rekordów z ID, Postgres musi zaktualizować liczniki (Sequences)."""
    print("Aktualizacja sekwencji ID w PostgreSQL...")
    with PostgresSession() as pg_session:
        inspector = sqlalchemy.inspect(postgres_engine)
        for table_name in inspector.get_table_names():
            # Sprawdzamy czy tabela ma kolumnę 'id'
            columns = [c['name'] for c in inspector.get_columns(table_name)]
            if 'id' in columns:
                query = f"SELECT setval(pg_get_serial_sequence('\"{table_name}\"', 'id'), coalesce((SELECT max(id) FROM \"{table_name}\"), 1), true);"
                pg_session.execute(text(query))
        pg_session.commit()
    print("  - Sekwencje zaktualizowane.")

if __name__ == "__main__":
    # Kolejność migracji (ważna ze względu na klucze obce)
    tables_to_migrate = [
        User,
        Subscription,
        VerificationCode,
        AuthToken,
        UserLogin,
        UploadGroupSettings,
        Transfer,
        UploadPassword,
        UploadEmailRecipient,
        FileUpload,
        DownloadLog
    ]

    print("--- START MIGRACJI SQLITE -> POSTGRESQL ---")
    
    for table in tables_to_migrate:
        try:
            migrate_table(table)
        except Exception as e:
            print(f"BŁĄD przy migracji {table.__name__}: {e}")
    
    try:
        reset_postgres_sequences()
    except Exception as e:
        print(f"UWAGA: Nie udało się zresetować sekwencji (prawdopodobnie brak uprawnień lub brak tabel): {e}")

    print("--- MIGRACJA ZAKOŃCZONA ---")
