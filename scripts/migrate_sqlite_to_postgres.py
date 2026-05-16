import os
import sys
from typing import List, Type

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session, select

# Obliczamy ścieżkę do backend/src względem lokalizacji tego skryptu
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_SRC = os.path.join(PROJECT_ROOT, "backend", "src")

# Dodajemy ścieżkę do backend/src aby móc zaimportować modele
sys.path.append(BACKEND_SRC)

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
# Jeśli go nie ma, wymuszamy użycie nowszego psycopg (v3), który zainstalowaliśmy.
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
            # Czyścimy tabelę w Postgres przed migracją (opcjonalnie, bezpieczniej)
            # pg_session.execute(text(f"TRUNCATE TABLE \"{model_class.__tablename__}\" CASCADE"))
            
            # Dodajemy rekordy do Postgres
            for record in records:
                # Expunge odłącza obiekt od sesji SQLite, aby móc go dodać do Postgresa
                sqlite_session.expunge(record)
                # Resetujemy stan SQLAlchemy (usunięcie _sa_instance_state)
                record._sa_instance_state.identity = None
                record._sa_instance_state.key = None
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
                query = f"SELECT setval(pg_get_serial_sequence('\"{table_name}\"', 'id'), coalesce(max(id), 1)) FROM \"{table_name}\";"
                pg_session.execute(text(query))
        pg_session.commit()
    print("  - Sekwencje zaktualizowane.")

import sqlalchemy # do inspect

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
    
    # Tworzymy tabele w Postgres (jeśli alembic jeszcze tego nie zrobił)
    # SQLModel.metadata.create_all(postgres_engine)

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
