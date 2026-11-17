import csv
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta
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

    # Mesures calculées par le script à partir des mesures de la balance (formules du guide Tanita)
    DERIVEES = [
        "Masse grasse (kg)",                    # poids × graisse corporelle %
        "Masse maigre (kg)",                    # poids − masse grasse
        "Métabolisme de base (kcal)",           # apport calorique quotidien / facteur d'activité
        "Indice de masse musculaire (kg/m²)",   # masse musculaire / taille²
    ]

    # Mesures suivies dans le temps : celles de la balance (du poids à l'eau corporelle), puis les mesures calculées
    MESURES = list(CODES.values())[list(CODES).index("Wk"):] + DERIVEES

    # Mesures que le guide ne donne que pour les adultes (18 à 99 ans)
    CODES_ADULTES = ["mW", "mr", "ml", "mR", "mL", "mT", "bW", "rD", "rA", "ww"]

    # Nombre de pesées du tableau « Dernières pesées » de la page de résultats
    NB_DERNIERES_PESEES = 10

    # Mesures globales des pages de résultats (cartes) et de détails (cases), regroupées :
    # la première mesure de chaque case est la principale, les suivantes la complètent.
    # Masse maigre = masse musculaire (eau des muscles comprise) + masse osseuse, à l'arrondi près,
    # puisque pour Tanita poids = masse grasse + masse musculaire + masse osseuse.
    GLOBALES = [
        ["Poids (kg)"],
        ["IMC", "Indice de masse musculaire (kg/m²)"],
        ["Graisse corporelle totale (%)", "Masse grasse (kg)"],
        ["Masse maigre (kg)", "Masse musculaire totale (kg)", "Masse osseuse (kg)"],
        ["Eau corporelle (%)"],
        ["Graisse viscérale"],
        ["Apport calorique quotidien (kcal)"],
        ["Métabolisme de base (kcal)"],
        ["Âge métabolique"],
    ]

    # Courte explication affichée sous certaines mesures de la page de détails
    DESCRIPTIONS = {
        "Apport calorique quotidien (kcal)": "Calories à consommer par jour pour garder ce poids",
        "Métabolisme de base (kcal)": "Énergie dépensée au repos complet",
    }

    # Définitions du manuel BC-601 affichées sous le profil de la page de détails,
    # par champ puis par valeur affichée
    DEFINITIONS_PROFIL = {
        "Niveau d'activité": {
            "1 · Peu ou pas d'exercice": "Vie peu active : peu ou pas d'exercice.",
            "2 · Activité modérée": "Vie modérément active : exercice occasionnel, de faible intensité.",
            "3 · Activité intense": "Activité physique intense.",
            "_note": "Sert uniquement au calcul de l'apport calorique quotidien.",
        },
        "Type de corps": {
            "Standard": "Réglage de la plupart des adultes. Le mode athlète est réservé à environ 10 h d'activité "
                        "intense par semaine, avec un pouls au repos d'environ 60 battements par minute ou moins.",
            "Athlète": "Environ 10 h d'activité intense par semaine, avec un pouls au repos d'environ 60 battements "
                       "par minute ou moins. La balance utilise alors des formules adaptées et fixe le niveau d'activité à 3.",
        },
    }

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

    # --- Données du guide Tanita (BC_Guide.pdf) -----------------------------------------------

    # Apport calorique quotidien = métabolisme de base × facteur d'activité (source : OMS),
    # par sexe ("1" homme, "2" femme) et niveau d'activité
    FACTEURS_ACTIVITE = {
        "1": {"1": 1.55, "2": 1.78, "3": 2.10},
        "2": {"1": 1.56, "2": 1.64, "3": 1.82},
    }

    # Plages de graisse corporelle des adultes standard (Gallagher D. et al., Am J Clin Nutr 2000,
    # source citée par le guide) : (âge min, âge max, début standard, début excès, début obésité)
    PLAGES_GRAISSE = {
        "1": [(20, 39, 8, 20, 25), (40, 59, 11, 22, 28), (60, 99, 13, 25, 30)],
        "2": [(20, 39, 21, 33, 39), (40, 59, 23, 34, 40), (60, 99, 24, 36, 42)],
    }

    # Eau corporelle moyenne d'un adulte en bonne santé (%)
    PLAGES_EAU = {"1": (50, 65), "2": (45, 60)}

    # Classes d'IMC (kg/m²) de la jauge colorée : (borne inférieure, libellé court, libellé complet).
    # La jauge va de 15 à 45 kg/m² ; les couleurs sont les variables CSS --imc-1 à --imc-6.
    JAUGE_IMC = (15, 45)
    CLASSES_IMC = [
        (None, "Insuffisance pondérale", "Insuffisance pondérale (maigreur ou dénutrition)"),
        (18.5, "Corpulence normale", "Corpulence normale (poids idéal)"),
        (25.0, "Surpoids", "Surpoids"),
        (30.0, "Obésité modérée (classe I)", "Obésité modérée (classe I)"),
        (35.0, "Obésité sévère (classe II)", "Obésité sévère (classe II)"),
        (40.0, "Obésité massive (classe III)", "Obésité massive ou morbide (classe III)"),
    ]

    # Graisse viscérale : 1 à 12 = niveau sain, 13 à 59 = excès
    VISCERALE_SAINE = (1, 12)

    # Masse osseuse moyenne estimée des 20-40 ans selon le poids : (poids maximum exclu, masse osseuse)
    OS_MOYEN = {
        "1": [(65, 2.66), (95, 3.29), (None, 3.69)],
        "2": [(50, 1.95), (75, 2.40), (None, 2.95)],
    }

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
        self.env.globals["jauge_imc"] = TanitaReportGenerator._jaugeImc

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

            # Mesures réservées aux adultes par le guide : ignorées avant 18 ans
            age = TanitaReportGenerator._toFloat(ligne.get("AG"))
            if age is not None and age < 18:
                for code in TanitaReportGenerator.CODES_ADULTES:
                    ligne.pop(code, None)

            # Valeurs par libellé ; une valeur absente (ex. mesures non fournies pour un enfant) reste vide
            valeurs = {libelle: ligne.get(code, "") for code, libelle in TanitaReportGenerator.CODES.items()}
            valeurs.update(TanitaReportGenerator._derivees(ligne))
            reperes = TanitaReportGenerator._reperes(ligne)
            valeurs["Sexe"] = TanitaReportGenerator.SEXES.get(valeurs["Sexe"], valeurs["Sexe"])
            valeurs["Niveau d'activité"] = TanitaReportGenerator.NIVEAUX_ACTIVITE.get(valeurs["Niveau d'activité"], valeurs["Niveau d'activité"])
            valeurs["Type de corps"] = TanitaReportGenerator._typeCorps(valeurs["Type de corps"])
            pesees.append({
                "id": f"{valeurs['Date']} {valeurs['Heure']}",
                "moment": moment,
                "valeurs": valeurs,
                "reperes": reperes,
            })

        if unites_incoherentes:
            print(f"Attention : {unites_incoherentes} pesée(s) de {nom_fichier} ont un IMC qui ne correspond ni à des kg ni à des livres ; "
                  "les valeurs sont affichées telles quelles.")

        # De la plus récente à la plus ancienne (ordre du fichier si une date est illisible)
        if all(p["moment"] for p in pesees):
            pesees.sort(key=lambda p: p["moment"], reverse=True)
        else:
            pesees.reverse()

        # Variation de chaque mesure par rapport à la moyenne des pesées des 7 jours qui précèdent
        TanitaReportGenerator._comparer7Jours(pesees)
        return pesees

    # ------------------------------------------------------------------------------------------
    # Mesures calculées et repères (guide Tanita)
    # ------------------------------------------------------------------------------------------

    # Mesures calculées à partir des valeurs d'une ligne (vides si une donnée manque)
    @staticmethod
    def _derivees(ligne):
        f = TanitaReportGenerator._toFloat
        poids, graisse, muscle = f(ligne.get("Wk")), f(ligne.get("FW")), f(ligne.get("mW"))
        taille, apport = f(ligne.get("Hm")), f(ligne.get("rD"))
        facteur = TanitaReportGenerator.FACTEURS_ACTIVITE.get(ligne.get("GE"), {}).get(ligne.get("AL"))

        derivees = dict.fromkeys(TanitaReportGenerator.DERIVEES, "")
        if poids is not None and graisse is not None:
            masse_grasse = round(poids * graisse / 100, 1)
            derivees["Masse grasse (kg)"] = f"{masse_grasse:.1f}"
            derivees["Masse maigre (kg)"] = f"{poids - masse_grasse:.1f}"
        if apport is not None and facteur:
            derivees["Métabolisme de base (kcal)"] = f"{apport / facteur:.0f}"
        if muscle is not None and taille:
            derivees["Indice de masse musculaire (kg/m²)"] = f"{muscle / (taille / 100) ** 2:.1f}"
        return derivees

    # Repères du guide pour une pesée d'adulte, par libellé de mesure :
    # {"libelle": "Niveau sain", "plage": "Sain : 1 à 12", "statut": "bon|attention|exces|alerte|None",
    #  "min": 1, "max": 12}  (min et max : plage affichée en bande sur le graphique)
    @staticmethod
    def _reperes(ligne):
        f, fr = TanitaReportGenerator._toFloat, TanitaReportGenerator._formatFr
        sexe, age, poids = ligne.get("GE"), f(ligne.get("AG")), f(ligne.get("Wk"))
        if sexe not in TanitaReportGenerator.SEXES or age is None or age < 18:
            return {}
        reperes = {}

        # Graisse corporelle (plages définies à partir de 20 ans)
        graisse = f(ligne.get("FW"))
        tranche = next((t for t in TanitaReportGenerator.PLAGES_GRAISSE[sexe] if t[0] <= age <= t[1]), None)
        if graisse is not None and tranche:
            _, _, standard, exces, obesite = tranche
            if graisse < standard:
                libelle, statut = "Masse grasse insuffisante", "attention"
            elif graisse < exces:
                libelle, statut = "Standard", "bon"
            elif graisse < obesite:
                libelle, statut = "Masse grasse excessive", "exces"
            else:
                libelle, statut = "Obésité", "alerte"
            reperes["Graisse corporelle totale (%)"] = {
                "libelle": libelle, "statut": statut, "min": standard, "max": exces,
                "plage": f"Standard de {standard} à {exces} % ({tranche[0]}-{tranche[1]} ans)",
            }

        # Eau corporelle
        eau = f(ligne.get("ww"))
        if eau is not None:
            bas, haut = TanitaReportGenerator.PLAGES_EAU[sexe]
            libelle, statut = ("Dans la moyenne", "bon") if bas <= eau <= haut else \
                              (("Sous la moyenne", "attention") if eau < bas else ("Au-dessus de la moyenne", "attention"))
            reperes["Eau corporelle (%)"] = {"libelle": libelle, "statut": statut, "min": bas, "max": haut,
                                             "plage": f"Moyenne de {bas} à {haut} %"}

        # Graisse viscérale
        viscerale = f(ligne.get("IF"))
        if viscerale is not None:
            bas, haut = TanitaReportGenerator.VISCERALE_SAINE
            sain = viscerale <= haut
            reperes["Graisse viscérale"] = {"libelle": "Niveau sain" if sain else "Excès", "statut": "bon" if sain else "exces",
                                            "min": bas, "max": haut, "plage": f"Sain de {bas} à {haut}"}

        # Masse osseuse : moyenne estimée pour ce poids (simple comparaison, sans statut)
        os_ = f(ligne.get("bW"))
        if os_ is not None and poids is not None:
            moyenne = next(m for limite, m in TanitaReportGenerator.OS_MOYEN[sexe] if limite is None or poids < limite)
            reperes["Masse osseuse (kg)"] = {"libelle": f"Moyenne pour ce poids : {fr(f'{moyenne:.2f}')} kg",
                                             "statut": None, "plage": "Moyenne des 20-40 ans"}

        # Âge métabolique comparé à l'âge réel (sans statut)
        age_metabolique = f(ligne.get("rA"))
        if age_metabolique is not None:
            ecart = int(age_metabolique - age)
            libelle = "Égal à l'âge réel" if ecart == 0 else \
                      f"{abs(ecart)} an{'s' if abs(ecart) > 1 else ''} de {'plus' if ecart > 0 else 'moins'} que l'âge réel"
            reperes["Âge métabolique"] = {"libelle": libelle, "statut": None, "plage": f"Âge réel : {int(age)} ans"}

        return reperes

    # Mini-courbes de tendance de la page de résultats : moyenne par jour des derniers jours de pesée,
    # sous forme de tracé SVG dans un cadre de 100 × 30 (None s'il y a moins de 2 jours)
    NB_JOURS_TENDANCE = 60

    @staticmethod
    def _tendances(pesees, cles):
        if not all(p["moment"] for p in pesees):
            return {}
        jours = {}
        for pesee in pesees:
            jours.setdefault(pesee["moment"].date(), []).append(pesee)
        dates = sorted(jours)[-TanitaReportGenerator.NB_JOURS_TENDANCE:]

        tendances = {}
        for cle in cles:
            points = []
            for jour in dates:
                nombres = [n for n in (TanitaReportGenerator._toFloat(p["valeurs"][cle]) for p in jours[jour]) if n is not None]
                if nombres:
                    points.append((jour.toordinal(), sum(nombres) / len(nombres)))
            if len(points) < 2:
                tendances[cle] = None
                continue
            x_min, x_max = points[0][0], points[-1][0]
            v_min, v_max = min(v for _, v in points), max(v for _, v in points)
            # Comme pour le graphique d'évolution, l'étendue verticale couvre au moins 10 fois la
            # précision de la balance : une moyenne de 3,75 kg au lieu de 3,8 kg ne fait pas un pic
            decimales = max((TanitaReportGenerator._decimales(p["valeurs"][cle]) for p in pesees), default=0)
            etendue_min = 10 * 10 ** -decimales
            if v_max - v_min < etendue_min:
                centre = (v_min + v_max) / 2
                v_min, v_max = centre - etendue_min / 2, centre + etendue_min / 2
            def xy(point):
                x = (point[0] - x_min) / (x_max - x_min) * 100
                y = 27 - (point[1] - v_min) / (v_max - v_min) * 24
                return f"{x:.1f},{y:.1f}"
            tendances[cle] = {"trace": "M" + "L".join(xy(p) for p in points), "nb_jours": len(points)}
        return tendances

    # Variations de chaque pesée par rapport à la moyenne des pesées des 7 jours glissants qui la
    # précèdent (de l'instant de la pesée moins 7 jours jusqu'à elle, exclue ; une pesée faite
    # quelques minutes plus tôt le même jour en fait partie). Utilisées par les pages Résultats et Détails.
    # Ajoute à chaque pesée "variations" ({mesure: variation ou None}) et "comparaison"
    # ({"debut": "07/08/2024 à 16:36", "nb": nombre de pesées de la fenêtre}, ou None sans date lisible).
    @staticmethod
    def _comparer7Jours(pesees):
        f = TanitaReportGenerator._toFloat
        datees = all(p["moment"] for p in pesees)

        # Précision de chaque mesure ; une décimale de plus pour les mesures entières (moyenne de 9 et 10)
        decimales = {cle: max((TanitaReportGenerator._decimales(p["valeurs"][cle]) for p in pesees), default=0)
                     for cle in TanitaReportGenerator.MESURES}

        for i, pesee in enumerate(pesees):
            pesee["variations"] = dict.fromkeys(TanitaReportGenerator.MESURES)
            if not datees:
                pesee["comparaison"] = None
                continue
            debut = pesee["moment"] - timedelta(days=7)
            # Les pesées sont de la plus récente à la plus ancienne : la fenêtre suit la pesée i
            fenetre = []
            for precedente in pesees[i + 1:]:
                if precedente["moment"] < debut:
                    break
                if precedente["moment"] < pesee["moment"]:
                    fenetre.append(precedente)
            pesee["comparaison"] = {"debut": debut.strftime("%d/%m/%Y à %H:%M"), "nb": len(fenetre)}

            for cle in TanitaReportGenerator.MESURES:
                actuelle = f(pesee["valeurs"][cle])
                nombres = [n for n in (f(p["valeurs"][cle]) for p in fenetre) if n is not None]
                if actuelle is None or not nombres:
                    continue
                nb_decimales = decimales[cle] if decimales[cle] or abs(actuelle) >= 100 else 1
                ecart = round(actuelle - sum(nombres) / len(nombres), nb_decimales)
                pesee["variations"][cle] = {"texte": "=", "sens": "stable"} if ecart == 0 else \
                    {"texte": f"{ecart:+.{nb_decimales}f}", "sens": "hausse" if ecart > 0 else "baisse"}

    # Jauge d'IMC : segments (proportionnels à la largeur de chaque classe entre 15 et 45 kg/m²),
    # classe de la valeur et position du curseur en %. None si la valeur n'est pas un nombre.
    @staticmethod
    def _jaugeImc(valeur):
        imc = TanitaReportGenerator._toFloat(valeur)
        bas, haut = TanitaReportGenerator.JAUGE_IMC
        bornes = [bas] + [c[0] for c in TanitaReportGenerator.CLASSES_IMC[1:]] + [haut]
        segments = []
        for i, (_, court, complet) in enumerate(TanitaReportGenerator.CLASSES_IMC):
            segments.append({"numero": i + 1, "court": court, "complet": complet, "debut": bornes[i], "fin": bornes[i + 1],
                             "largeur": bornes[i + 1] - bornes[i], "position": (bornes[i] - bas) / (haut - bas) * 100,
                             "graduation": f"{bornes[i]:g}".replace(".", ",")})
        if imc is None:
            return None
        classe = next(s for s in reversed(segments) if s["numero"] == 1 or imc >= s["debut"])
        # Hors de la jauge, le curseur reste au bord mais passe en rouge
        return {"imc": imc, "texte": TanitaReportGenerator._formatFr(valeur), "segments": segments, "classe": classe,
                "curseur": (min(max(imc, bas), haut) - bas) / (haut - bas) * 100, "bas": bas, "haut": haut,
                "hors_limites": imc < bas or imc > haut}

    # Bilan depuis la première pesée : variation du poids, de la masse grasse et de la masse maigre
    @staticmethod
    def _bilan(pesees):
        if len(pesees) < 2:
            return None
        premiere, derniere = pesees[-1]["valeurs"], pesees[0]["valeurs"]
        bilan = {"depuis": premiere["Date"]}
        for cle, libelle in (("poids", "Poids (kg)"), ("grasse", "Masse grasse (kg)"), ("maigre", "Masse maigre (kg)")):
            variation = TanitaReportGenerator._variation(derniere[libelle], premiere[libelle])
            if variation and variation["sens"] == "stable":
                variation = {"texte": "0", "sens": "stable"}
            bilan[cle] = variation
        return bilan if bilan["poids"] else None

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

        # Résultats : mêmes cases que la composition globale de la page de détails
        cles_resultats = [cle for groupe in TanitaReportGenerator.GLOBALES for cle in groupe]
        self._render("resultats.html", os.path.join(dossier, "resultats.html"),
                     groupes=TanitaReportGenerator.GLOBALES,
                     cles=cles_resultats,
                     descriptions=TanitaReportGenerator.DESCRIPTIONS,
                     bilan=TanitaReportGenerator._bilan(profil["pesees"]),
                     tendances=TanitaReportGenerator._tendances(profil["pesees"], cles_resultats),
                     nb_dernieres=TanitaReportGenerator.NB_DERNIERES_PESEES,
                     **self._contexte("resultats", profil))

        self._render("details.html", os.path.join(dossier, "details.html"),
                     champs_profil=TanitaReportGenerator.PROFIL,
                     globales=TanitaReportGenerator.GLOBALES,
                     descriptions=TanitaReportGenerator.DESCRIPTIONS,
                     definitions_profil=TanitaReportGenerator.DEFINITIONS_PROFIL,
                     segments=TanitaReportGenerator.SEGMENTS,
                     **self._contexte("details", profil))

        # Page d'évolution : la synthèse, les moyennes et l'historique sont calculés dans le
        # navigateur (assets/evolution.js) à partir des pesées de chaque mesure
        # Définition de la jauge d'IMC pour le JavaScript (mêmes classes que les autres pages)
        jauge = TanitaReportGenerator._jaugeImc(str(TanitaReportGenerator.JAUGE_IMC[0]))
        self._render("evolution.html", os.path.join(dossier, "evolution.html"),
                     jauge_imc_definition={"bas": jauge["bas"], "haut": jauge["haut"], "segments": jauge["segments"]},
                     mesures=TanitaReportGenerator.MESURES,
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

            # Plage de repère du guide (d'après la pesée la plus récente qui en a une), affichée en bande
            repere = next((p["reperes"][key] for p in pesees if "min" in p["reperes"].get(key, {})), None)
            graphiques.append({
                "nom": TanitaReportGenerator._nom(key),
                "unite": TanitaReportGenerator._unite(key),
                "decimales": decimales,
                "points": points,
                "repere": {"min": repere["min"], "max": repere["max"], "plage": repere["plage"]} if repere else None,
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
