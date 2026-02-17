import sqlite3
import os

class Database:
    def __init__(self, db_name="database/inventaire.db"):
        # S'assure que le dossier database existe
        os.makedirs(os.path.dirname(db_name), exist_ok=True)
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Table des Catégories (Photo, Vidéo, Son...)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE
            )
        ''')

        # Table du Matériel
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                marque TEXT,
                modele TEXT,
                sn TEXT UNIQUE,
                prix_achat REAL,
                date_achat TEXT,
                id_categorie INTEGER,
                emplacement TEXT,
                statut TEXT DEFAULT 'En stock',
                facture_path TEXT,
                qr_path TEXT,
                FOREIGN KEY (id_categorie) REFERENCES categories (id)
            )
        ''')

        # Table des Réparations
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reparations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_equipement INTEGER,
                date_reparation TEXT,
                description TEXT,
                cout REAL,
                prestataire TEXT,
                FOREIGN KEY (id_equipement) REFERENCES equipement (id)
            )
        ''')

        # Table des Kits
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS kits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_kit TEXT NOT NULL UNIQUE
            )
        ''')

        # Liaison Matériel <-> Kits (Un matériel peut être dans un kit)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS kit_items (
                id_kit INTEGER,
                id_equipement INTEGER,
                PRIMARY KEY (id_kit, id_equipement),
                FOREIGN KEY (id_kit) REFERENCES kits (id),
                FOREIGN KEY (id_equipement) REFERENCES equipement (id)
            )
        ''')

        self.conn.commit()

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    # Test de création
    db = Database()
    print("Base de données initialisée avec succès.")
    db.close()