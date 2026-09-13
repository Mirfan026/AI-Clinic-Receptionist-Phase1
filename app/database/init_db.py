from app.database.connection import get_engine, initialize_database
if __name__ == "__main__":
    engine = initialize_database(get_engine())
    print(f"Initialized database: {engine.url}")
