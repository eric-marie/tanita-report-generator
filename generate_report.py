import csv
import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from jinja2 import Environment, FileSystemLoader

class TanitaReportGenerator:
    # Codes des valeurs d'une ligne de pesée (DATA/DATAn.CSV) et leur libellé.
    # Chaque valeur est précédée de son code dans le fichier : "Wk,100.1" = poids de 100,1 kg.
    # L'ordre ci-dessous est celui de l'affichage.
    CODES = {
        "MO": "Modèle",
        "DT": "Date",
        "Ti": "Heure",
        "GE": "Sexe",
        "AG": "Âge",
        "Hm": "Taille (cm)",
        "AL": "Niveau d'activité",
        "Bt": "Type de corps",
        "Wk": "Poids (kg)",
        "MI": "IMC",
        "FW": "Graisse corporelle totale (%)",
        "Fr": "Graisse corporelle bras droit (%)",
        "Fl": "Graisse corporelle bras gauche (%)",
        "FR": "Graisse corporelle jambe droite (%)",
        "FL": "Graisse corporelle jambe gauche (%)",
        "FT": "Graisse corporelle buste (%)",
        "mW": "Masse musculaire totale (kg)",
        "mr": "Masse musculaire bras droit (kg)",
        "ml": "Masse musculaire bras gauche (kg)",
        "mR": "Masse musculaire jambe droite (kg)",
        "mL": "Masse musculaire jambe gauche (kg)",
        "mT": "Masse musculaire buste (kg)",
        "bW": "Masse osseuse (kg)",
        "IF": "Graisse viscérale",
        "rD": "Apport calorique quotidien (kcal)",
        "rA": "Âge métabolique",
        "ww": "Eau corporelle (%)",
    }

    # Codes des valeurs exprimées en masse (à convertir si la balance est réglée en livres)
    CODES_MASSE = ["Wk", "mW", "mr", "ml", "mR", "mL", "mT", "bW"]

    # Informations de profil (le reste des indicateurs sont des mesures)
    PROFIL = ["Modèle", "Sexe", "Âge", "Taille (cm)", "Niveau d'activité", "Type de corps"]

    # Mesures suivies dans le temps (du poids à l'eau corporelle)
    MESURES = list(CODES.values())[list(CODES).index("Wk"):]

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

    # Libellés des codes de la balance (manuel BC-601)
    SEXES = {"1": "Homme", "2": "Femme"}
    NIVEAUX_ACTIVITE = {
        "1": "1 · Peu ou pas d'exercice",
        "2": "2 · Activité modérée",
        "3": "3 · Activité intense",
    }
    # La balance n'a que deux types de corps : standard (0) et athlète
    TYPE_STANDARD = "0"

    # Nombre de profils de la balance BC-601 (4 touches personnelles).
    # La carte SD prévoit 8 fichiers (PROF1 à PROF8, DATA1 à DATA8) : les 4 derniers restent vides.
    NB_PROFILS = 4
    NB_FICHIERS = 8

    # Codes du fichier de profil (SYSTEM/PROFn.CSV)
    CODES_PROFIL = {"MO": "modele", "DB": "naissance", "GE": "sexe", "Hm": "taille", "AL": "activite", "Bt": "type"}

    # Conversion des livres et des pouces
    KG_PAR_LIVRE = 0.45359237
    CM_PAR_POUCE = 2.54

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

    # ------------------------------------------------------------------------------------------
    # Lecture des fichiers de la carte SD
    # ------------------------------------------------------------------------------------------

    # Lire les lignes d'un fichier de la carte SD et vérifier leur somme de contrôle.
    # Retourne la liste des lignes valides, chacune sous forme de dictionnaire {code: valeur}.
    @staticmethod
    def _lireLignes(path):
        if not os.path.exists(path):
            return []
        with open(path, mode='rb') as file:
            brut = file.read()

        lignes = []
        nom = os.path.basename(path)
        for numero, ligne in enumerate(brut.splitlines(), start=1):
            if not ligne.strip():
                continue
            if not TanitaReportGenerator._sommeControleValide(ligne):
                print(f"Attention : la ligne {numero} de {nom} est ignorée (somme de contrôle incorrecte, ligne abîmée).")
                continue
            cellules = next(csv.reader([ligne.decode("ascii", errors="replace")]))
            lignes.append(TanitaReportGenerator._valeursParCode(cellules))
        return lignes

    # Somme de contrôle "CS" en fin de ligne : somme des octets de la ligne jusqu'à la virgule
    # qui précède "CS", modulo 256, en hexadécimal (ex. ",CS,34"). Une ligne sans "CS" est acceptée.
    @staticmethod
    def _sommeControleValide(ligne):
        position = ligne.rfind(b",CS,")
        if position < 0:
            return True
        try:
            attendue = int(ligne[position + 4:].strip(), 16)
        except ValueError:
            return False
        return sum(ligne[:position + 1]) % 256 == attendue

    # Convertir les cellules d'une ligne en dictionnaire {code: valeur}.
    # Une ligne commence par un en-tête ("{0,16,~0,2,~1,2,...") puis alterne code et valeur.
    @staticmethod
    def _valeursParCode(cellules):
        valeurs = {}
        i = 0
        while i + 1 < len(cellules):
            code, valeur = cellules[i].strip(), cellules[i + 1].strip()
            if not (code.startswith("{") or code.startswith("~")) and code not in valeurs:
                valeurs[code] = valeur
            i += 2
        return valeurs

    # Détecter le format des dates d'un fichier : "%d/%m/%Y", "%m/%d/%Y" ou "%Y/%m/%d".
    # Un jour supérieur à 12 lève l'ambiguïté ; à défaut, le format français jj/mm/aaaa est retenu.
    @staticmethod
    def _formatDates(dates, nom_fichier):
        parties = [re.split(r"[/.-]", d) for d in dates if d]
        parties = [p for p in parties if len(p) == 3 and all(x.isdigit() for x in p)]
        if not parties:
            return None
        separateur = re.search(r"[/.-]", next(d for d in dates if d)).group(0)
        if all(len(p[0]) == 4 for p in parties):
            return f"%Y{separateur}%m{separateur}%d"
        if any(int(p[0]) > 12 for p in parties):
            return f"%d{separateur}%m{separateur}%Y"
        if any(int(p[1]) > 12 for p in parties):
            return f"%m{separateur}%d{separateur}%Y"
        print(f"Remarque : le format des dates de {nom_fichier} est ambigu (aucun jour supérieur à 12), jj/mm/aaaa est retenu.")
        return f"%d{separateur}%m{separateur}%Y"

    # Vérifier l'unité des masses grâce à l'IMC : IMC = poids (kg) / taille (m)².
    # Si l'IMC ne correspond qu'avec un poids en livres (et éventuellement une taille en pouces),
    # les masses sont converties en kg et la taille en cm. Retourne l'unité détectée.
    @staticmethod
    def _verifierUnites(valeurs):
        poids = TanitaReportGenerator._toFloat(valeurs.get("Wk"))
        taille = TanitaReportGenerator._toFloat(valeurs.get("Hm"))
        imc = TanitaReportGenerator._toFloat(valeurs.get("MI"))
        if not (poids and taille and imc):
            return "inconnue"

        def concorde(poids_kg, taille_cm):
            return abs(poids_kg / (taille_cm / 100) ** 2 - imc) <= 0.3

        hypotheses = [
            ("kg", 1, 1),
            ("lb", TanitaReportGenerator.KG_PAR_LIVRE, TanitaReportGenerator.CM_PAR_POUCE),
            ("lb", TanitaReportGenerator.KG_PAR_LIVRE, 1),
        ]
        for unite, facteur_masse, facteur_taille in hypotheses:
            if concorde(poids * facteur_masse, taille * facteur_taille):
                if facteur_masse != 1:
                    for code in TanitaReportGenerator.CODES_MASSE:
                        masse = TanitaReportGenerator._toFloat(valeurs.get(code))
                        if masse is not None:
                            valeurs[code] = f"{masse * facteur_masse:.1f}"
                if facteur_taille != 1:
                    valeurs["Hm"] = f"{taille * facteur_taille:.1f}"
                return unite
        return "incohérente"

    # Détecter les profils 1 à 4 : un profil est retenu s'il est configuré (PROFn.CSV non vide)
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

        # Fichiers au-delà des 4 profils de la balance : signalés s'ils contiennent quelque chose
        for numero in range(TanitaReportGenerator.NB_PROFILS + 1, TanitaReportGenerator.NB_FICHIERS + 1):
            for dossier, prefixe in (("SYSTEM", "PROF"), ("DATA", "DATA")):
                if TanitaReportGenerator._lireLignes(os.path.join(self.tanita_dir, dossier, f"{prefixe}{numero}.CSV")):
                    print(f"Remarque : {prefixe}{numero}.CSV n'est pas vide mais la BC-601 n'a que {TanitaReportGenerator.NB_PROFILS} profils ; il est ignoré.")

    # Lire la configuration d'un profil (SYSTEM/PROFn.CSV) : {"sexe": "1", "taille": "176.0", ...}
    def _lireConfig(self, numero):
        lignes = TanitaReportGenerator._lireLignes(os.path.join(self.tanita_dir, "SYSTEM", f"PROF{numero}.CSV"))
        if not lignes:
            return {}
        return {nom: lignes[0][code] for code, nom in TanitaReportGenerator.CODES_PROFIL.items() if code in lignes[0]}

    # Lire les pesées d'un profil (DATA/DATAn.CSV), de la plus récente à la plus ancienne
    def _lirePesees(self, numero):
        nom_fichier = f"DATA{numero}.CSV"
        lignes = TanitaReportGenerator._lireLignes(os.path.join(self.tanita_dir, "DATA", nom_fichier))
        format_date = TanitaReportGenerator._formatDates([l.get("DT", "") for l in lignes], nom_fichier)

        pesees = []
        unites_incoherentes = 0
        for ligne in lignes:
            if "Wk" not in ligne:
                print(f"Attention : une ligne de {nom_fichier} sans poids est ignorée.")
                continue
            unite = TanitaReportGenerator._verifierUnites(ligne)
            if unite == "lb":
                print(f"Remarque : une pesée de {nom_fichier} était en livres ; elle a été convertie en kg.")
            elif unite == "incohérente":
                unites_incoherentes += 1

            # Date et heure de la pesée, la date étant réécrite au format jj/mm/aaaa
            moment = None
            if format_date and ligne.get("DT") and ligne.get("Ti"):
                try:
                    moment = datetime.strptime(f"{ligne['DT']} {ligne['Ti']}", f"{format_date} %H:%M:%S")
                    ligne["DT"] = moment.strftime("%d/%m/%Y")
                except ValueError:
                    pass

            # Valeurs par libellé ; une valeur absente (ex. mesures non fournies pour un enfant) reste vide
            valeurs = {libelle: ligne.get(code, "") for code, libelle in TanitaReportGenerator.CODES.items()}
            valeurs["Sexe"] = TanitaReportGenerator.SEXES.get(valeurs["Sexe"], valeurs["Sexe"])
            valeurs["Niveau d'activité"] = TanitaReportGenerator.NIVEAUX_ACTIVITE.get(valeurs["Niveau d'activité"], valeurs["Niveau d'activité"])
            valeurs["Type de corps"] = TanitaReportGenerator._typeCorps(valeurs["Type de corps"])
            pesees.append({
                "id": f"{valeurs['Date']} {valeurs['Heure']}",
                "moment": moment,
                "valeurs": valeurs,
            })

        if unites_incoherentes:
            print(f"Attention : {unites_incoherentes} pesée(s) de {nom_fichier} ont un IMC qui ne correspond ni à des kg ni à des livres ; "
                  "les valeurs sont affichées telles quelles.")

        # De la plus récente à la plus ancienne (ordre du fichier si une date est illisible)
        if all(p["moment"] for p in pesees):
            pesees.sort(key=lambda p: p["moment"], reverse=True)
        else:
            pesees.reverse()

        # Variation de chaque mesure par rapport à la pesée précédente
        for i, pesee in enumerate(pesees):
            precedente = pesees[i + 1] if i + 1 < len(pesees) else None
            pesee["variations"] = {
                key: TanitaReportGenerator._variation(pesee["valeurs"][key], precedente["valeurs"][key]) if precedente else None
                for key in TanitaReportGenerator.MESURES
            }
        return pesees

    # Libellé du type de corps : standard (0) ou athlète
    @staticmethod
    def _typeCorps(code):
        if code == "":
            return ""
        return "Standard" if code == TanitaReportGenerator.TYPE_STANDARD else "Athlète"

    # Description courte d'un profil, ex. "Homme · 35 ans · 176 cm"
    # (d'après la dernière pesée, sinon d'après la configuration du profil)
    @staticmethod
    def _description(config, pesees):
        if pesees:
            valeurs = pesees[0]["valeurs"]
            sexe, age, taille, type_corps = valeurs["Sexe"], valeurs["Âge"], valeurs["Taille (cm)"], valeurs["Type de corps"]
        else:
            sexe = TanitaReportGenerator.SEXES.get(config.get("sexe", ""), "")
            age = TanitaReportGenerator._age(config.get("naissance", ""))
            taille = config.get("taille", "")
            type_corps = TanitaReportGenerator._typeCorps(config.get("type", ""))
        elements = [sexe]
        if age:
            elements.append(f"{age} ans")
        if taille:
            elements.append(f"{TanitaReportGenerator._formatFr(taille)} cm")
        if type_corps == "Athlète":
            elements.append("athlète")
        return " · ".join(e for e in elements if e)

    # Âge à partir d'une date de naissance (chaîne vide si illisible)
    @staticmethod
    def _age(naissance):
        format_date = TanitaReportGenerator._formatDates([naissance], "PROF") if naissance else None
        try:
            date_naissance = datetime.strptime(naissance, format_date).date()
        except (TypeError, ValueError):
            return ""
        aujourdhui = date.today()
        return str(aujourdhui.year - date_naissance.year
                   - ((aujourdhui.month, aujourdhui.day) < (date_naissance.month, date_naissance.day)))

    # Profils qui ont au moins une pesée (ceux qui ont un rapport)
    def _profilsActifs(self):
        return [p for p in self.profils if p["pesees"]]

    # ------------------------------------------------------------------------------------------
    # Génération des pages
    # ------------------------------------------------------------------------------------------

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
            valeurs = [p["valeurs"][key] for p in profil["pesees"] if p["valeurs"][key] != ""]
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
        temporel = all(p["moment"] for p in chronologie)

        graphiques = []
        for key in TanitaReportGenerator.MESURES:
            points = []
            for pesee in chronologie:
                nombre = TanitaReportGenerator._toFloat(pesee["valeurs"][key])
                if nombre is None:
                    continue
                points.append({
                    "t": (pesee["moment"] - datetime(1970, 1, 1)).total_seconds() * 1000 if temporel else None,
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

    # ------------------------------------------------------------------------------------------
    # Outils de mise en forme
    # ------------------------------------------------------------------------------------------

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
