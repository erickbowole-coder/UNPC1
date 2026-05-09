from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import random  # Pour le matricule aléatoire
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
from io import BytesIO
from flask import send_file
from flask import send_file, url_for
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from docx import Document
from datetime import datetime
from flask_mail import Mail, Message
from datetime import datetime

app = Flask(__name__)
app.secret_key = "unpc_rdc_secure_key_2024"

# --- CONFIGURATION BASE DE DONNÉES ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///unpc.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

db = SQLAlchemy(app)

# --- CONFIGURATION EMAIL ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'erickbowole@gmail.com'
app.config['MAIL_PASSWORD'] = 'Eric Bowole'
app.config['MAIL_DEFAULT_SENDER'] = ('UNPC RDC', 'erickbowole@gmail.com')

mail = Mail(app)
# Liste des 26 provinces de la RDC
PROVINCES = [
    "Etranger","Bas-Uele", "Equateur", "Haut-Katanga", "Haut-Lomami", "Haut-Uele", "Ituri",
    "Kasai", "Kasai-Central", "Kasai-Oriental", "CD-Kinshasa","Kinshasa", "Kongo-Central",
    "Kwango", "Kwilu", "Lomami", "Lualaba", "Mai-Ndombe", "Maniema", "Mongala",
    "Nord-Kivu", "Nord-Ubangi", "Sankuru", "Sud-Kivu", "Sud-Ubangi", "Tanganyika",
    "Tshopo", "Tshuapa"
]

# --- MODÈLES DE DONNÉES ---

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='Administrateur')
    photo = db.Column(db.String(100), default='default_admin.jpg')

class CardSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bg_recto = db.Column(db.String(100), default='background_guilloche.png')
    bg_verso = db.Column(db.String(100), default='background_guilloche1.png')
    signature_1 = db.Column(db.String(100), default='sig1.png')
    signature_2 = db.Column(db.String(100), default='sig2.png')
    signataire_1_nom = db.Column(db.String(150), default='KAMAMDA WA KAMANDA M.')
    signataire_2_nom = db.Column(db.String(150), default='Charles DIMANJA WEMBI')

class Membre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    num_chronologie = db.Column(db.String(50), unique=True, nullable=True)

    # I. Identité
    nom = db.Column(db.String(100))
    postnom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    sexe = db.Column(db.String(20))
    etat_civil = db.Column(db.String(50))
    telephone = db.Column(db.String(25))
    date_naissance = db.Column(db.String(50))
    lieu_naissance = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)

    # II. Études
    ecole_journalisme = db.Column(db.String(150))
    titre_journalisme = db.Column(db.String(100))
    autre_ecole = db.Column(db.String(150))
    autre_titre = db.Column(db.String(100))

    # III. Professionnel
    organe = db.Column(db.String(150))
    fonction = db.Column(db.String(150))
    province = db.Column(db.String(100))
    ville = db.Column(db.String(100))
    profil_pro = db.Column(db.Text)  # Stocke le choix unique du profil

    # IV. Fichiers (Noms de fichiers)
    photo = db.Column(db.String(100), default='default.jpg')
    contrat_travail = db.Column(db.String(100))
    carte_sejour = db.Column(db.String(100))
    carte_presse_origine = db.Column(db.String(100))

    # V. Parrainage (Champs détaillés)
    parrain1_nom = db.Column(db.String(150))
    parrain1_contact = db.Column(db.String(50))
    parrain2_nom = db.Column(db.String(150))
    parrain2_contact = db.Column(db.String(50))

    # VI. Autres & Sécurité
    password = db.Column(db.String(200))
    matricule = db.Column(db.String(20), unique=True)
    statut = db.Column(db.String(20), default='En attente')
    statut_carte = db.Column(db.String(50), default='En attente')
    date_demande = db.Column(db.DateTime, default=datetime.utcnow)
    motif_rejet = db.Column(db.Text, nullable=True)

# --- INITIALISATION ---
with app.app_context():
    db.create_all()
    # Recherche de l'ancien administrateur par son nom d'utilisateur (username)
    admin_principal = Admin.query.filter_by(username='BulEx').first()

    if not admin_principal:
        # Si l'admin n'existe pas, on le crée avec les nouveaux identifiants
        db.session.add(Admin(
            nom="Administrateur Principal",
            username="BulEx",
            password=generate_password_hash("Babasous7@"),
            role="Administrateur"
        ))
        db.session.commit()
    else:
        # S'il existe déjà, on met à jour son mot de passe au cas où il aurait changé dans le code
        admin_principal.password = generate_password_hash("Babasous7@")
        db.session.commit()

with app.app_context():
    if not CardSettings.query.first():
        db.session.add(CardSettings())
        db.session.commit()

# --- FONCTIONS SUPPORTS ---
def generer_matricule_aleatoire():
    """Génère un matricule avec un nombre aléatoire entre 100 et 999"""
    nombre = random.randint(100, 9999999)
    return f"UNPC-{nombre}-RDC"

# --- FONCTION UTILITAIRE POUR ENVOYER L'EMAIL ---
def envoyer_notification(sujet, destinataire, corps):
    if not destinataire:
        print("Erreur : Aucun destinataire fourni.")
        return

    try:
        msg = Message(sujet, recipients=[destinataire])
        msg.body = corps
        mail.send(msg)
        print(f"Email envoyé avec succès à {destinataire}")
    except Exception as e:
        # Cela affichera l'erreur dans votre console PyCharm sans faire planter l'inscription
        print(f"ALERTE : L'email n'a pas pu être envoyé. Erreur : {e}")
# --- ROUTES D'ACCÈS ---

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        # 1. Recherche de l'Administrateur ou Imprimeur
        adm = Admin.query.filter_by(username=identifier).first()

        # 2. Vérification sécurisée
        if adm and check_password_hash(adm.password, password):
            session.clear()
            session['user_id'] = adm.id
            session['username'] = adm.username
            session['user_type'] = 'admin'
            session['user_role'] = adm.role
            session['user_photo'] = adm.photo if adm.photo else 'default_admin.jpg'

            # REDIRECTION BASÉE SUR LE RÔLE
            if adm.role == 'Imprimeur':
                return redirect(url_for('gestion_impressions'))
            else:
                # Pour le rôle 'Administrateur' ou autre
                return redirect(url_for('admin'))

        # 3. Si ce n'est pas un admin/imprimeur, on cherche un Journaliste (Membre)
        membre = Membre.query.filter((Membre.email == identifier) | (Membre.matricule == identifier)).first()

        if membre and check_password_hash(membre.password, password):
            session.clear()
            session['user_id'] = membre.id
            session['user_type'] = 'journaliste'
            session['user_photo'] = membre.photo
            return redirect(url_for('profil_detail', id=membre.id))

        # Si aucun des deux ne correspond
        flash("Identifiants incorrects", "danger")
        return render_template('login.html')

    return render_template('login.html')

# --- Modifiez uniquement la route register dans votre fichier app.py ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 1. RÉCUPÉRATION DES DONNÉES DU FORMULAIRE
        email_saisi = request.form.get('email')
        p1_nom = request.form.get('parrain1_nom')
        p1_tel = request.form.get('parrain1_contact')
        p2_nom = request.form.get('parrain2_nom')
        p2_tel = request.form.get('parrain2_contact')

        # Récupération du profil (choix unique via radio bouton)
        profil_choisi = request.form.get('profil')

        # 2. VÉRIFICATION D'UNICITÉ DE L'EMAIL
        existing_user = Membre.query.filter_by(email=email_saisi).first()
        if existing_user:
            flash("Cette adresse e-mail est déjà utilisée. Veuillez vous connecter ou utiliser une autre adresse.",
                  "danger")
            return redirect(url_for('register'))

        try:
            # 3. CRÉATION DE L'INSTANCE MEMBRE
            new_membre = Membre(
                nom=request.form.get('nom'),
                postnom=request.form.get('postnom'),
                prenom=request.form.get('prenom'),
                sexe=request.form.get('sexe'),
                etat_civil=request.form.get('etat_civil'),
                telephone=request.form.get('telephone'),
                date_naissance=request.form.get('date_naissance'),
                lieu_naissance=request.form.get('lieu_naissance'),
                email=email_saisi,
                ecole_journalisme=request.form.get('ecole_journalisme'),
                titre_journalisme=request.form.get('titre_journalisme'),
                autre_ecole=request.form.get('autre_ecole'),
                autre_titre=request.form.get('autre_titre'),
                organe=request.form.get('organe'),
                fonction=request.form.get('fonction'),
                province=request.form.get('province'),
                ville=request.form.get('ville'),
                profil_pro=profil_choisi,  # Utilise le choix unique[cite: 2, 3]
                parrain1_nom=p1_nom,
                parrain1_contact=p1_tel,
                parrain2_nom=p2_nom,
                parrain2_contact=p2_tel,
                password=generate_password_hash(request.form.get('password')),
                statut="En attente"
            )

            # 4. PREMIER ENREGISTREMENT POUR OBTENIR L'ID
            db.session.add(new_membre)
            db.session.commit()

            # 5. GESTION DU NUMÉRO CHRONOLOGIQUE (Format CD001 pour Kinshasa)
            if not new_membre.num_chronologie:
                if new_membre.province == "CD-Kinshasa":
                    code_prov = "CD"
                else:
                    code_prov = new_membre.province[:3].upper() if new_membre.province else "RDC"

                count = Membre.query.filter(
                    Membre.province == new_membre.province,
                    Membre.num_chronologie.isnot(None)
                ).count()

                # Génère le format avec 3 chiffres (ex: CD001)
                new_membre.num_chronologie = f"{code_prov}{(count + 1):03d}"

            # 6. GESTION DES FICHIERS
            fichiers = {
                'photo': request.files.get('photo'),
                'contrat_travail': request.files.get('contrat_travail'),
                'carte_sejour': request.files.get('carte_sejour'),
                'carte_presse_origine': request.files.get('carte_presse_origine')
            }

            for champ, fichier in fichiers.items():
                if fichier and fichier.filename != '':
                    ext = os.path.splitext(fichier.filename)[1]
                    nom_fichier = f"{new_membre.id}_{champ}{ext}"
                    chemin = os.path.join(app.config['UPLOAD_FOLDER'], nom_fichier)
                    fichier.save(chemin)
                    setattr(new_membre, champ, nom_fichier)

            # 7. GÉNÉRATION DU MATRICULE FINAL
            new_membre.matricule = f"UNPC{str(new_membre.id).zfill(4)}RDC"
            db.session.commit()

            # 8. NOTIFICATION ET REDIRECTION
            sujet = "Confirmation de réception - UNPC"
            corps = f"Bonjour {new_membre.prenom},\n\nVotre demande a été reçue. Matricule : {new_membre.matricule}."
            envoyer_notification(sujet, new_membre.email, corps)

            flash(f"Succès ! Votre matricule est : {new_membre.matricule}", "success")
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()  # Annule en cas d'erreur
            print(f"Erreur : {e}")
            flash("Une erreur technique est survenue.", "danger")
            return redirect(url_for('register'))

    return render_template('register.html', provinces=PROVINCES)
# --- ROUTES ADMIN ---


@app.route('/admin/ajouter', methods=['GET', 'POST'])
def add_admin():
    if session.get('user_type') != 'admin' or session.get('user_role') != 'Administrateur':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nom = request.form.get('nom')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        file = request.files.get('photo')

        exist_check = Admin.query.filter_by(username=username).first()
        if exist_check:
            flash("Cet identifiant est déjà utilisé", "danger")
        else:
            # 1. Créer l'entrée en base d'abord
            new_adm = Admin(
                nom=nom,
                username=username,
                password=generate_password_hash(password),
                role=role
            )
            db.session.add(new_adm)
            db.session.commit() # On commit pour avoir l'ID

            # 2. Gérer la photo après le commit
            if file and file.filename != '':
                ext = os.path.splitext(file.filename)[1]
                filename = f"admin_{new_adm.id}{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_adm.photo = filename
                db.session.commit()

            flash("Nouvel utilisateur ajouté !", "success")
            return redirect(url_for('add_admin'))

    admins = Admin.query.all()
    return render_template('add_admin.html', admins=admins)

    # 3. Logique d'affichage (GET) ou en cas d'erreur de formulaire
    # C'EST CE RETURN QUI MANQUE PROBABLEMENT !
    admins = Admin.query.all()
    return render_template('add_admin.html', admins=admins)
# --- ROUTES ADMIN ---

@app.route('/admin')
def admin():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    # Récupère tous les membres pour le tableau de bord
    membres = Membre.query.all()
    nb_en_attente = Membre.query.filter_by(statut='En attente').count()
    return render_template('admin.html', demandes=membres, nb_en_attente=nb_en_attente)

# Assurez-vous qu'il n'y a pas d'autre "def admin():" plus bas dans votre fichier !

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_admin(id):
    if session.get('user_type') != 'admin' or session.get('user_role') != 'Administrateur':
        return redirect(url_for('login'))

    adm = Admin.query.get_or_404(id)

    if request.method == 'POST':
        adm.nom = request.form.get('nom')
        adm.username = request.form.get('username')
        adm.role = request.form.get('role')

        # Mise à jour du mot de passe uniquement s'il est rempli
        password = request.form.get('password')
        if password:
            adm.password = generate_password_hash(password)

        db.session.commit()
        flash("Compte mis à jour avec succès", "success")
        return redirect(url_for('add_admin'))

    file = request.files.get('photo')
    if file and file.filename != '':
        filename = f"admin_{new_adm.id}.jpg" # ou générer un nom unique
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_adm.photo = filename
        db.session.commit()

    return render_template('edit_admin_form.html', admin_to_edit=adm)

@app.route('/admin/delete/<int:id>')
def delete_admin(id):
    """Route pour supprimer un administrateur (Corrige le BuildError)"""
    if session.get('user_type') != 'admin': return redirect(url_for('login'))
    adm = Admin.query.get_or_404(id)
    if adm.username == 'admin':
        flash("Impossible de supprimer l'administrateur principal", "danger")
    else:
        db.session.delete(adm)
        db.session.commit()
        flash("Administrateur supprimé", "success")
    return redirect(url_for('add_admin'))


@app.route('/admin/statistiques')
def statistiques():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    # 1. Calcul des compteurs de base
    total = Membre.query.count()
    valides = Membre.query.filter_by(statut='Validé').count()
    en_attente = Membre.query.filter_by(statut='En attente').count()

    # 2. Statistiques par genre
    hommes = Membre.query.filter_by(sexe='Masculin').count()
    femmes = Membre.query.filter_by(sexe='Féminin').count()

    # 3. Statistiques par province (uniquement pour les membres validés)
    stats_prov = db.session.query(Membre.province, db.func.count(Membre.id)).filter(Membre.statut == 'Validé').group_by(
        Membre.province).all()

    labels_prov = [item[0] for item in stats_prov]
    values_prov = [item[1] for item in stats_prov]

    return render_template('statistiques.html',
                           total=total,
                           valides=valides,
                           en_attente=en_attente,
                           hommes=hommes,
                           femmes=femmes,
                           labels_prov=labels_prov,
                           values_prov=values_prov)

@app.route('/admin/voir_profil/<int:id>')
def voir_profil(id):
    if session.get('user_type') != 'admin': return redirect(url_for('login'))
    m = Membre.query.get_or_404(id)
    return render_template('voir_profil.html', membre=m)

# --- ROUTES JOURNALISTES ET AUTRES ---

@app.route('/profil/<int:id>') # Ajoutez l'ID dans l'URL
def profil_detail(id):
    # On récupère le membre spécifique grâce à l'ID de l'URL, pas celui de la session
    m = Membre.query.get_or_404(id)
    return render_template('profil_detail.html', membre=m)

@app.route('/annuaire')
def annuaire():
    # On filtre les membres pour ne prendre que ceux dont le statut est 'Validé'
    journalistes = Membre.query.filter_by(statut='Validé').all()
    return render_template('annuaire.html', journalistes=journalistes)

@app.route('/imprimer_certificat/<int:id>')
def imprimer_certificat(id):
    m = Membre.query.get_or_404(id)
    return render_template('imprimer_certificat.html', membre=m)


@app.route('/imprimer_carte/<int:id>')
def imprimer_carte(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    # --- LA LIGNE MANQUANTE ÉTAIT ICI ---
    membre = Membre.query.get_or_404(id)
    settings = CardSettings.query.first()

    # Calcul automatique de la validité
    annee_actuelle = datetime.now().year
    annee_suivante = annee_actuelle + 2
    validite = f"{annee_actuelle} - {annee_suivante}"

    return render_template('imprimer_carte.html',membre=membre,validite=validite,settings=settings)

def export_annuaire(format):
    if session.get('user_type') != 'admin': return redirect(url_for('login'))
    flash(f"L'exportation au format {format.upper()} sera bientôt disponible.", "info")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin/invalider/<int:id>')
def invalider_journaliste(id):
    """Route pour invalider (suspendre) un journaliste"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    membre = Membre.query.get_or_404(id)
    membre.statut = 'Invalidé'  # Change le statut en base de données
    db.session.commit()

    flash(f"Le profil de {membre.nom} a été invalidé.", "warning")
    return redirect(url_for('admin'))

@app.route('/admin/valider/<int:id>')
def valider_journaliste(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    membre = Membre.query.get_or_404(id)

    # Générer la chronologie uniquement si elle n'existe pas encore
    if not membre.num_chronologie:
        # Définir le code de la province
        if membre.province == "CD-Kinshasa":
            code_prov = "CD"
        else:
            # Logique par défaut pour les autres provinces (ex: KAS, LUA, etc.)
            code_prov = membre.province[:3].upper() if membre.province else "RDC"

        # Compter combien de membres ont déjà un numéro pour cette province
        count = Membre.query.filter(
            Membre.province == membre.province,
            Membre.num_chronologie.isnot(None)
        ).count()

        # Générer le nouveau numéro (ex: CD001, CD002...)
        # count + 1 donne le rang actuel, zfill(3) ajoute les zéros à gauche
        nouveau_numero = f"{code_prov}{(count + 1):03d}"

        membre.num_chronologie = nouveau_numero

    membre.statut = 'Validé'
    db.session.commit()
    sujet = "Félicitations - Dossier Approuvé (UNPC)"
    corps = f"Bonjour {membre.nom},\n\nVotre dossier a été validé par l'UNPC.\nVotre numéro de chronologie est : {membre.num_chronologie}."
    envoyer_notification(sujet, membre.email, corps)
    flash(f"Dossier validé. Chronologie : {membre.num_chronologie}", "success")
    return redirect(url_for('admin'))


from sqlalchemy import case
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

@app.route('/export_annuaire/<format>')
def export_annuaire(format):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    # 1. RÉCUPÉRATION DU FILTRE DE PROVINCE
    province_filter = request.args.get('province')
    query = Membre.query

    # 2. APPLICATION DU FILTRE
    if province_filter and province_filter != "Toutes":
        query = query.filter_by(province=province_filter)

    # 3. TRI : Priorité Kinshasa (CD) en haut
    journalistes = query.order_by(
        case(
            (Membre.num_chronologie.like('CD%'), 0),
            else_=1
        ),
        Membre.num_chronologie.asc()
    ).all()

    # 4. PRÉPARATION DES DONNÉES AVEC LA FONCTION CARTE
    data = []
    for j in journalistes:
        photo_url = url_for('static', filename='uploads/' + j.photo, _external=True) if j.photo else "Pas de photo"
        comptage_national = str(j.id).zfill(4)

        data.append({
            "N° COMPTAGE": comptage_national,
            "ID MATRICULE": j.matricule,
            "NOM COMPLET": f"{j.nom} {j.postnom} {j.prenom}".upper(),
            "FONCTION SUR CARTE": j.fonction.upper() if j.fonction else "JOURNALISTE", # Ajout ici
            "PROVINCE": j.province,
            "NUMÉRO CHRONOLOGIE": j.num_chronologie if j.num_chronologie else "N/A",
            "PHOTO PROFIL (LIEN)": photo_url
        })

    if not data:
        flash("Aucune donnée à exporter.", "warning")
        return redirect(url_for('admin'))

    df = pd.DataFrame(data)

    # --- EXPORT EXCEL ---
    if format == 'excel':
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Annuaire UNPC')
        output.seek(0)
        return send_file(output, as_attachment=True,
                         download_name=f"export_unpc_{province_filter or 'general'}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- EXPORT PDF ---
    elif format == 'pdf':
        output = BytesIO()
        p = canvas.Canvas(output, pagesize=letter)
        p.setFont("Helvetica-Bold", 11)
        titre = f"ANNUAIRE UNPC - {province_filter.upper() if province_filter else 'LISTE OFFICIELLE'}"
        p.drawString(40, 750, titre)

        p.setFont("Helvetica", 7) # Taille réduite pour faire tenir la fonction
        y = 720
        for item in data:
            # Ligne PDF incluant la fonction sur la carte
            ligne = f"{item['N° COMPTAGE']} | {item['ID MATRICULE']} | {item['NOM COMPLET']} | {item['FONCTION SUR CARTE']} | {item['PROVINCE']} | {item['NUMÉRO CHRONOLOGIE']}"
            p.drawString(30, y, ligne)
            y -= 18
            if y < 50:
                p.showPage()
                p.setFont("Helvetica", 7)
                y = 750

        p.save()
        output.seek(0)
        return send_file(output, as_attachment=True,
                         download_name=f"annuaire_unpc_{province_filter or 'general'}.pdf",
                         mimetype="application/pdf")

    flash("Format non disponible", "danger")
    return redirect(url_for('admin'))

@app.route('/admin/supprimer_journaliste/<int:id>')
def supprimer_journaliste(id):
    """Route pour supprimer définitivement un membre/journaliste"""
    # Vérification de sécurité pour s'assurer que seul l'admin peut supprimer
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    membre = Membre.query.get_or_404(id)

    try:
        db.session.delete(membre)
        db.session.commit()
        flash(f"Le compte de {membre.nom} a été supprimé définitivement.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Une erreur est survenue lors de la suppression.", "danger")

    return redirect(url_for('admin'))


@app.route('/admin/update_statut_carte/<int:id>', methods=['POST'])
def update_statut_carte(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    membre = db.session.get(Membre, id)  # Utilisation de la méthode moderne
    nouveau_statut = request.form.get('statut_carte')

    if membre and nouveau_statut:
        membre.statut_carte = nouveau_statut
        db.session.commit()  # CRITIQUE : Enregistre les changements en base
        flash(f"Statut mis à jour pour {membre.nom}.", "success")

    return redirect(url_for('admin'))


@app.route('/edit_profil/<int:id>', methods=['GET', 'POST'])
def edit_profil(id):
    # Vérification : Est-ce un admin ?
    is_admin = session.get('user_type') == 'admin'
    # Vérification : Est-ce le propriétaire du profil ?
    is_owner = (session.get('user_type') == 'journaliste' and session.get('user_id') == id)

    # Sécurité : Si ni admin, ni propriétaire -> Dehors !
    if not (is_admin or is_owner):
        flash("Accès non autorisé : vous ne pouvez pas modifier ce profil.", "danger")
        return redirect(url_for('login'))

    # On récupère le membre à modifier
    membre = Membre.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # Mise à jour des informations de base
            membre.nom = request.form.get('nom')
            membre.postnom = request.form.get('postnom')
            membre.prenom = request.form.get('prenom')
            membre.sexe = request.form.get('sexe')
            membre.telephone = request.form.get('telephone')
            membre.email = request.form.get('email')
            membre.province = request.form.get('province')
            membre.ville = request.form.get('ville')
            membre.organe = request.form.get('organe')
            membre.fonction = request.form.get('fonction')
            membre.parrains = request.form.get('parrains')

            # Correction du champ Profil (Qualité)
            qualites = request.form.getlist('qualite')
            membre.profil_pro = ", ".join(qualites)

            # Gestion des fichiers
            for champ in ['photo', 'contrat_travail', 'carte_sejour', 'carte_presse_origine']:
                file = request.files.get(champ)
                if file and file.filename != '':
                    ext = os.path.splitext(file.filename)[1]
                    filename = f"{membre.id}_{champ}{ext}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    setattr(membre, champ, filename)

            db.session.commit()
            flash(f"Mise à jour réussie pour {membre.prenom} {membre.nom}", "success")

            if is_admin:
                return redirect(url_for('admin'))
            return redirect(url_for('profil_detail', id=membre.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la sauvegarde : {str(e)}", "danger")

    return render_template('edit_profil_2.html', membre=membre, provinces=PROVINCES)


@app.route('/admin/rejeter/<int:id>', methods=['POST'])
def rejeter_journaliste(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    membre = Membre.query.get_or_404(id)
    # Récupérer le motif depuis un formulaire dans l'admin
    motif = request.form.get('motif')

    membre.statut = 'Rejeté'
    membre.motif_rejet = motif
    db.session.commit()
    sujet = "Mise à jour de votre dossier - UNPC"
    corps = f"Bonjour {membre.nom},\n\nVotre dossier a été rejeté pour le motif suivant : {membre.motif_rejet}.\nVeuillez contacter l'UNPC pour plus d'informations."
    envoyer_notification(sujet, membre.email, corps)
    flash(f"Le dossier de {membre.nom} a été rejeté.", "danger")
    return redirect(url_for('admin'))


@app.route('/demander_nouvelle_carte/<int:id>')
def demander_nouvelle_carte(id):
    if not session.get('user_id'): return redirect(url_for('login'))

    membre = db.session.get(Membre, id)
    if membre:
        # Met à jour la colonne "Carte de Presse" sur l'admin
        membre.statut_carte = 'Nouvelle demande'
        db.session.commit()  # Enregistre le changement
        flash("Votre demande de nouvelle carte a été transmise.", "success")

    return redirect(url_for('voir_profil', id=id))


@app.route('/signaler_perte/<int:id>')
def signaler_perte(id):
    if not session.get('user_id'): return redirect(url_for('login'))

    membre = db.session.get(Membre, id)
    if membre:
        # Met à jour la colonne "Carte de Presse" sur l'admin
        membre.statut_carte = 'En attente'
        db.session.commit()  # Enregistre le changement
        flash("La perte a été signalée. votre dossier est remis en attente.", "warning")

    return redirect(url_for('voir_profil', id=id))


@app.route('/admin/gestion_impressions')
def gestion_impressions():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    # Récupération des paramètres de tri
    tri = request.args.get('tri', 'date')  # Par défaut par date

    # Requête de base pour les cartes à imprimer
    query = Membre.query.filter_by(statut_carte="Impression carte")

    # Application du tri
    if tri == 'province':
        query = query.order_by(Membre.province.asc())
    else:
        query = query.order_by(Membre.date_demande.desc())

    candidats = query.all()

    # Historique : Récupérer les 10 dernières cartes imprimées
    historique = Membre.query.filter_by(statut_carte="Carte créée") \
                     .order_by(Membre.date_demande.desc()).limit(10).all()

    return render_template('gestion_impressions.html',candidats=candidats,historique=historique,tri_actuel=tri, datetime=datetime)

@app.route('/admin/confirmer_impression/<int:id>')
def confirmer_impression(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    membre = Membre.query.get_or_404(id)
    # Mise à jour du statut vers "Carte créée"
    membre.statut_carte = "Carte créée"
    db.session.commit()
    sujet = "Votre carte de presse est prête !"
    corps = f"Bonjour {membre.nom},\n\nNous vous informons que votre carte de presse est désormais disponible et peut être retirée auprès de nos services."
    envoyer_notification(sujet, membre.email, corps)
    flash(f"Impression confirmée pour {membre.matricule}. Le statut est passé à 'Carte créée' auprès de l'adminstrateur UNPC et le propritaire a  été notifier", "success")
    return redirect(url_for('gestion_impressions'))


@app.route('/admin/supprimer_historique_impressions')
def supprimer_historique_impressions():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    # Pour "effacer" l'historique sans supprimer les membres, on change leur statut de carte
    historique = Membre.query.filter_by(statut_carte="Carte créée").all()
    for m in historique:
        # On peut remettre à 'Initial' ou une autre valeur pour les masquer de la vue impression
        m.statut_carte = "Archivé"

    db.session.commit()
    flash("L'historique des impressions a été vidé.", "info")
    return redirect(url_for('gestion_impressions'))


@app.route('/admin/settings/card', methods=['GET', 'POST'])
def card_settings():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    settings = CardSettings.query.first()

    if request.method == 'POST':
        # Mise à jour des noms
        settings.signataire_1_nom = request.form.get('nom1')
        settings.signataire_2_nom = request.form.get('nom2')

        # Gestion des fichiers images
        files = {
            'bg_recto': request.files.get('bg_recto'),
            'bg_verso': request.files.get('bg_verso'),
            'signature_1': request.files.get('sig1'),
            'signature_2': request.files.get('sig2')
        }

        for key, file in files.items():
            if file and file.filename != '':
                filename = f"custom_{key}{os.path.splitext(file.filename)[1]}"
                file.save(os.path.join(app.config['STATIC_FOLDER'], 'img', filename))
                setattr(settings, key, filename)

        db.session.commit()
        flash("Paramètres de la carte mis à jour !", "success")
        return redirect(url_for('card_settings'))

    return render_template('card_settings.html', settings=settings)

#Modification mot de passe
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return render_template('forgot_password.html')

        # 1. Chercher dans les Membres (Journalistes)
        user = Membre.query.filter_by(email=email).first()
        user_type = "journaliste"

        # 2. Si non trouvé, chercher dans les Admins
        if not user:
            user = Admin.query.filter_by(username=email).first()  # ou email si vous l'ajoutez
            user_type = "admin"

        # Vérification et protection de l'admin principal
        if user:
            if user_type == "admin" and user.username == "admin":
                flash(
                    "Action interdite : Le mot de passe de l'administrateur principal ne peut pas être réinitialisé ici.",
                    "danger")
            else:
                # Mise à jour sécurisée avec hachage
                user.password = generate_password_hash(new_password)
                db.session.commit()

                # Notification par email
                sujet = "Sécurité : Réinitialisation de votre mot de passe"
                corps = f"Bonjour,\n\nVotre mot de passe a été réinitialisé avec succès.\nSi vous n'êtes pas à l'origine de cette action, veuillez contacter l'UNPC immédiatement."
                destinataire = user.email if user_type == "journaliste" else email
                envoyer_notification(sujet, destinataire, corps)

                flash("Mot de passe mis à jour avec succès !", "success")
                return redirect(url_for('login'))
        else:
            flash("Aucun utilisateur trouvé avec cet identifiant.", "warning")

    return render_template('forgot_password.html')

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)