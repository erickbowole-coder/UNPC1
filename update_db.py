import sqlite3

# Connexion à la base de données
conn = sqlite3.connect('unpc_portal.db')
cursor = conn.cursor()

try:
    # Ajout de la colonne password à la table journaliste
    cursor.execute("ALTER TABLE journaliste ADD COLUMN password TEXT DEFAULT '123456';")
    conn.commit()
    print("La colonne 'password' a été ajoutée avec succès.")
except sqlite3.OperationalError:
    print("La colonne existe peut-être déjà ou une erreur est survenue.")

conn.close()

from app import app, db

with app.app_context():
    # Commande SQL pour ajouter la colonne manquante
    try:
        db.session.execute(db.text("ALTER TABLE membre ADD COLUMN num_chronologie VARCHAR(50)"))
        db.session.commit()
        print("La colonne 'num_chronologie' a été ajoutée avec succès !")
    except Exception as e:
        print(f"Erreur ou colonne déjà existante : {e}")