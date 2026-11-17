import csv
import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from jinja2 import Environment, FileSystemLoader

class TanitaReportGenerator:
    # Les indices des colonnes que nous voulons extraire
    INDICES = {
        "Modèle": 11,
        "Date": 13,
        "Heure": 15,
        "Sexe": 19,
        "Âge": 21,
        "Taille (cm)": 23,
        "Niveau d'activité": 25,
        "Poids (kg)": 27,
        "IMC": 29,
        "Graisse corporelle totale (%)": 31,
        "Graisse corporelle bras droit (%)": 33,
        "Graisse corporelle bras gauche (%)": 35,
        "Graisse corporelle jambe droite (%)": 37,
        "Graisse corporelle jambe gauche (%)": 39,
        "Graisse corporelle buste (%)": 41,
        "Masse musculaire totale (kg)": 43,
        "Masse musculaire bras droit (kg)": 45,
        "Masse musculaire bras gauche (kg)": 47,
        "Masse musculaire jambe droite (kg)": 49,
        "Masse musculaire jambe gauche (kg)": 51,
        "Masse musculaire buste (kg)": 53,
        "Masse osseuse (kg)": 55,
        "Graisse viscérale": 57,
        "Apport calorique quotidien (kcal)": 59,
        "Âge métabolique": 61,
        "Eau corporelle (%)": 63
    }

    # Informations de profil (le reste des indicateurs sont des mesures)
    PROFIL = ["Modèle", "Sexe", "Âge", "Taille (cm)", "Niveau d'activité"]

    # Mesures suivies dans le temps (du poids à l'eau corporelle)
    MESURES = list(INDICES.keys())[7:]

    # Mesures mises en avant sur la page de résultats
    CLES = [
        "Poids (kg)",
        "IMC",
        "Graisse corporelle totale (%)",
        "Masse musculaire totale (kg)",
        "Graisse viscérale",
        "Eau corporelle (%)",
        "Masse osseuse (kg)",
        "Âge métabolique",
    ]

    # Mesures globales affichées sur la page de détails
    GLOBALES = [
        "Poids (kg)",
        "IMC",
        "Graisse corporelle totale (%)",
        "Masse musculaire totale (kg)",
        "Masse osseuse (kg)",
        "Eau corporelle (%)",
        "Graisse viscérale",
        "Apport calorique quotidien (kcal)",
        "Âge métabolique",
    ]

    # Segments corporels mesurés par la balance
    SEGMENTS = ["bras droit", "bras gauche", "buste", "jambe droite", "jambe gauche"]

    # Codes de sexe utilisés par la balance
    SEXES = {"1": "Homme", "2": "Femme"}

    # Nombre de profils gérés par la balance (PROF1.CSV à PROF8.CSV, DATA1.CSV à DATA8.CSV)
    NB_PROFILS = 8

    # Codes du fichier de profil (SYSTEM/PROFn.CSV)
    CODES_PROFIL = {"MO": "modele", "DB": "naissance", "GE": "sexe", "Hm": "taille", "AL": "activite"}

    def __init__(self):
        self._definePathes()
        self._initJina2Env()
        self._chargerNoms()
        self._chargerProfils()

    # Définir les chemins utilisés
    def _definePathes(self):
        racine = os.getcwd()
        self.template_dir = os.path.join(racine, "templates")
        self.tanita_dir = os.path.join(racine, "TANITA", "GRAPHV1")
        self.noms_path = os.path.join(racine, "profils.json")
        self.output_dir = os.path.join(racine, "rapport")

    # Initialiser l'environnement Jinja2
    def _initJina2Env(self):
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.env.filters["fr"] = TanitaReportGenerator._formatFr
        self.env.globals["nom"] = TanitaReportGenerator._nom
        self.env.globals["unite"] = TanitaReportGenerator._unite

    # Lire les noms donnés aux profils dans profils.json (facultatif), ex. {"1": "Éric"}
    def _chargerNoms(self):
        self.noms = {}
        if not os.path.exists(self.noms_path):
            return
        try:
            with open(self.noms_path, mode='r', encoding='utf-8') as file:
                self.noms = {str(k): str(v) for k, v in json.load(file).items()}
        except (ValueError, AttributeError) as erreur:
            print(f"Attention : profils.json est ignoré car il n'est pas valide ({erreur}).")

    # Lire les lignes non vides d'un fichier CSV de la carte SD (aucune si absent)
    @staticmethod
    def _lireCsv(path):
        if not os.path.exists(path):
            return []
        with open(path, mode='r', newline='', encoding='utf-8') as file:
            return [row for row in csv.reader(file, delimiter=',') if any(cell.strip() for cell in row)]

    # Détecter les profils : un profil est retenu s'il est configuré (PROFn.CSV non vide)
    # ou s'il a des pesées (DATAn.CSV non vide). Seuls ceux qui ont des pesées ont un rapport.
    def _chargerProfils(self):
        self.profils = []
        for numero in range(1, TanitaReportGenerator.NB_PROFILS + 1):
            config = self._lireConfig(numero)
            pesees = self._lirePesees(numero)
            if not config and not pesees:
                continue
            nom = self.noms.get(str(numero))
            self.profils.append({
                "numero": numero,
                "nom": nom or f"Profil {numero}",
                "nom_personnalise": bool(nom),
                "dossier": f"profil-{numero}",
                "configure": bool(config),
                "pesees": pesees,
                "derniere": pesees[0] if pesees else None,
                "description": TanitaReportGenerator._description(config, pesees),
            })

    # Lire la configuration d'un profil (SYSTEM/PROFn.CSV) : {"sexe": "1", "taille": "176.0", ...}
    def _lireConfig(self, numero):
        rows = TanitaReportGenerator._lireCsv(os.path.join(self.tanita_dir, "SYSTEM", f"PROF{numero}.CSV"))
        config = {}
        for row in rows[:1]:
            for i, cellule in enumerate(row[:-1]):
                if cellule in TanitaReportGenerator.CODES_PROFIL:
                    config[TanitaReportGenerator.CODES_PROFIL[cellule]] = row[i + 1]
        return config

    # Lire les pesées d'un profil (DATA/DATAn.CSV), de la plus récente à la plus ancienne
    def _lirePesees(self, numero):
        rows = TanitaReportGenerator._lireCsv(os.path.join(self.tanita_dir, "DATA", f"DATA{numero}.CSV"))
        dernier_indice = max(TanitaReportGenerator.INDICES.values())

        pesees = []
        for row in reversed(rows):
            if len(row) <= dernier_indice:
                print(f"Attention : une ligne incomplète de DATA{numero}.CSV est ignorée.")
                continue
            valeurs = {key: row[idx] for key, idx in TanitaReportGenerator.INDICES.items()}
            valeurs["Sexe"] = TanitaReportGenerator.SEXES.get(valeurs["Sexe"], valeurs["Sexe"])
            pesees.append({
                "id": f"{valeurs['Date']} {valeurs['Heure']}",
                "valeurs": valeurs,
            })

        # Variation de chaque mesure par rapport à la pesée précédente
        for i, pesee in enumerate(pesees):
            precedente = pesees[i + 1] if i + 1 < len(pesees) else None
            pesee["variations"] = {
                key: TanitaReportGenerator._variation(pesee["valeurs"][key], precedente["valeurs"][key]) if precedente else None
                for key in TanitaReportGenerator.MESURES
            }
        return pesees

    # Description courte d'un profil, ex. "Homme · 35 ans · 176 cm"
    # (d'après la dernière pesée, sinon d'après la configuration du profil)
    @staticmethod
    def _description(config, pesees):
        if pesees:
            valeurs = pesees[0]["valeurs"]
            sexe, age, taille = valeurs["Sexe"], valeurs["Âge"], valeurs["Taille (cm)"]
        else:
            sexe = TanitaReportGenerator.SEXES.get(config.get("sexe", ""), "")
            age = TanitaReportGenerator._age(config.get("naissance", ""))
            taille = config.get("taille", "")
        elements = [sexe]
        if age:
            elements.append(f"{age} ans")
        if taille:
            elements.append(f"{TanitaReportGenerator._formatFr(taille)} cm")
        return " · ".join(e for e in elements if e)

    # Âge à partir d'une date de naissance "jj/mm/aaaa" (chaîne vide si illisible)
    @staticmethod
    def _age(naissance):
        try:
            date_naissance = datetime.strptime(naissance, "%d/%m/%Y").date()
        except ValueError:
            return ""
        aujourdhui = date.today()
        return str(aujourdhui.year - date_naissance.year
                   - ((aujourdhui.month, aujourdhui.day) < (date_naissance.month, date_naissance.day)))

    # Profils qui ont au moins une pesée (ceux qui ont un rapport)
    def _profilsActifs(self):
        return [p for p in self.profils if p["pesees"]]

    # Écrire une page à partir de son template
    def _render(self, template_name, output_path, **contexte):
        template = self.env.get_template(template_name)
        with open(output_path, mode='w', encoding='utf-8') as file:
            file.write(template.render(**contexte))

    # Contexte commun à toutes les pages
    def _contexte(self, active_page, profil=None):
        actifs = self._profilsActifs()
        return {
            "active_page": active_page,
            "profil": profil,
            "profils": self.profils,
            "plusieurs_profils": len(actifs) > 1,
            "racine": "../" if profil else "",
            "pesees": profil["pesees"] if profil else [],
            "derniere": profil["derniere"] if profil else None,
            "nb_pesees": len(profil["pesees"]) if profil else sum(len(p["pesees"]) for p in actifs),
            "genere_le": datetime.now().strftime("%d/%m/%Y à %H:%M"),
        }

    # Générer les trois pages d'un profil dans rapport/profil-n/
    def _genererProfil(self, profil):
        dossier = os.path.join(self.output_dir, profil["dossier"])
        os.makedirs(dossier, exist_ok=True)

        self._render("resultats.html", os.path.join(dossier, "resultats.html"),
                     cles=TanitaReportGenerator.CLES,
                     mesures=TanitaReportGenerator.MESURES,
                     **self._contexte("resultats", profil))

        self._render("details.html", os.path.join(dossier, "details.html"),
                     champs_profil=TanitaReportGenerator.PROFIL,
                     globales=TanitaReportGenerator.GLOBALES,
                     segments=TanitaReportGenerator.SEGMENTS,
                     **self._contexte("details", profil))

        # Statistiques de chaque mesure sur l'ensemble des pesées
        statistiques = {}
        for key in TanitaReportGenerator.MESURES:
            valeurs = [p["valeurs"][key] for p in profil["pesees"]]
            nombres = [n for n in (TanitaReportGenerator._toFloat(v) for v in valeurs) if n is not None]
            statistiques[key] = {
                "derniere": valeurs[0] if valeurs else "",
                "min": TanitaReportGenerator._formatComme(min(nombres), valeurs) if nombres else "",
                "max": TanitaReportGenerator._formatComme(max(nombres), valeurs) if nombres else "",
                "total": TanitaReportGenerator._variation(valeurs[0], valeurs[-1]) if len(valeurs) > 1 else None,
            }
        self._render("evolution.html", os.path.join(dossier, "evolution.html"),
                     mesures=TanitaReportGenerator.MESURES,
                     statistiques=statistiques,
                     graphiques=TanitaReportGenerator._graphiques(profil["pesees"]),
                     **self._contexte("evolution", profil))

    # Points des graphiques de la page d'évolution, une série par mesure (dans l'ordre de MESURES),
    # du plus ancien au plus récent. "t" est l'instant de la pesée en millisecondes, ou None si la
    # date est illisible : le graphique espace alors les pesées régulièrement.
    @staticmethod
    def _graphiques(pesees):
        chronologie = list(reversed(pesees))
        instants = []
        for pesee in chronologie:
            try:
                moment = datetime.strptime(f"{pesee['valeurs']['Date']} {pesee['valeurs']['Heure']}", "%d/%m/%Y %H:%M:%S")
                instants.append((moment - datetime(1970, 1, 1)).total_seconds() * 1000)
            except ValueError:
                instants.append(None)
        if None in instants:
            instants = [None] * len(instants)

        graphiques = []
        for key in TanitaReportGenerator.MESURES:
            points = []
            for pesee, instant in zip(chronologie, instants):
                nombre = TanitaReportGenerator._toFloat(pesee["valeurs"][key])
                if nombre is None:
                    continue
                points.append({
                    "t": instant,
                    "v": nombre,
                    "texte": TanitaReportGenerator._formatFr(pesee["valeurs"][key]),
                    "date": pesee["valeurs"]["Date"],
                    "heure": pesee["valeurs"]["Heure"],
                })
            # Précision des mesures (nombre de décimales), pour l'échelle du graphique
            decimales = max((TanitaReportGenerator._decimales(p["valeurs"][key]) for p in chronologie), default=0)
            graphiques.append({
                "nom": TanitaReportGenerator._nom(key),
                "unite": TanitaReportGenerator._unite(key),
                "decimales": decimales,
                "points": points,
            })
        return graphiques

    # Générer toutes les pages HTML
    def generateHtmlFiles(self):
        os.makedirs(self.output_dir, exist_ok=True)

        # Supprimer les dossiers de profil d'une génération précédente
        for entree in os.listdir(self.output_dir):
            chemin = os.path.join(self.output_dir, entree)
            if re.fullmatch(r"profil-\d+", entree) and os.path.isdir(chemin):
                shutil.rmtree(chemin)

        actifs = self._profilsActifs()
        for profil in actifs:
            self._genererProfil(profil)

        # Un seul profil, sans autre profil à signaler : l'accueil redirige directement vers son rapport
        redirection = None
        if len(actifs) == 1 and len(self.profils) == 1:
            redirection = f"{actifs[0]['dossier']}/resultats.html"

        index_path = os.path.join(self.output_dir, "index.html")
        self._render("index.html", index_path, redirection=redirection, **self._contexte("index"))

        print(f"Rapport généré : {index_path}")
        for profil in self.profils:
            if profil["pesees"]:
                print(f"  - {profil['nom']} : {len(profil['pesees'])} pesée(s) -> rapport/{profil['dossier']}/")
            else:
                print(f"  - {profil['nom']} : configuré sur la balance, mais aucune pesée")
        if not self.profils:
            print("  Aucun profil trouvé dans TANITA/GRAPHV1.")

    # Convertir une valeur texte en nombre (None si ce n'en est pas un)
    @staticmethod
    def _toFloat(valeur):
        try:
            return float(valeur)
        except (TypeError, ValueError):
            return None

    # Nombre de décimales d'une valeur texte (ex. "100.1" -> 1)
    @staticmethod
    def _decimales(valeur):
        return len(valeur.split(".")[1]) if "." in valeur else 0

    # Formater un nombre avec autant de décimales que les valeurs d'origine
    @staticmethod
    def _formatComme(nombre, valeurs):
        decimales = max(TanitaReportGenerator._decimales(v) for v in valeurs)
        return f"{nombre:.{decimales}f}"

    # Variation entre deux valeurs texte : {"texte": "+0.1", "sens": "hausse|baisse|stable"}
    @staticmethod
    def _variation(actuelle, precedente):
        a = TanitaReportGenerator._toFloat(actuelle)
        b = TanitaReportGenerator._toFloat(precedente)
        if a is None or b is None:
            return None
        decimales = max(TanitaReportGenerator._decimales(actuelle), TanitaReportGenerator._decimales(precedente))
        ecart = round(a - b, decimales)
        if ecart == 0:
            return {"texte": "=", "sens": "stable"}
        return {"texte": f"{ecart:+.{decimales}f}", "sens": "hausse" if ecart > 0 else "baisse"}

    # Afficher les nombres avec une virgule décimale (ex. "100.1" -> "100,1")
    @staticmethod
    def _formatFr(valeur):
        texte = str(valeur)
        return texte.replace(".", ",") if re.fullmatch(r"[+-]?\d+\.\d+", texte) else texte

    # Libellé sans l'unité (ex. "Poids (kg)" -> "Poids")
    @staticmethod
    def _nom(libelle):
        return re.sub(r"\s*\([^)]*\)$", "", libelle)

    # Unité d'un libellé (ex. "Poids (kg)" -> "kg")
    @staticmethod
    def _unite(libelle):
        trouve = re.search(r"\(([^)]*)\)$", libelle)
        return trouve.group(1) if trouve else ""

# Écrire les messages en UTF-8 : sous Windows, quand la sortie n'est pas la console Windows
# (terminal Git Bash, par exemple), Python utilise sinon l'encodage cp1252 et les accents
# s'affichent mal. PYTHONIOENCODING, s'il est défini, reste prioritaire.
if not os.environ.get("PYTHONIOENCODING") and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

generator = TanitaReportGenerator()
generator.generateHtmlFiles()
