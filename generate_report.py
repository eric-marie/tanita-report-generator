import csv
import os
import re
from datetime import datetime
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

    def __init__(self):
        self._definePathes()
        self._initJina2Env()
        self._parseCsvFile()

    # Définir les chemins utilisés
    def _definePathes(self):
        self.template_dir = os.path.join(os.getcwd(), "templates")
        self.csv_path = os.path.join(os.getcwd(), "TANITA", "GRAPHV1", "DATA", "DATA1.CSV")
        self.output_dir = os.path.join(os.getcwd(), "rapport")
        os.makedirs(self.output_dir, exist_ok=True)
        self.html_resultats_path = os.path.join(self.output_dir, "resultats.html")
        self.html_details_path = os.path.join(self.output_dir, "details.html")
        self.html_evolution_path = os.path.join(self.output_dir, "evolution.html")

    # Initialiser l'environnement Jinja2
    def _initJina2Env(self):
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.env.filters["fr"] = TanitaReportGenerator._formatFr
        self.env.globals["nom"] = TanitaReportGenerator._nom
        self.env.globals["unite"] = TanitaReportGenerator._unite

    # Lire le fichier CSV et préparer les pesées, de la plus récente à la plus ancienne
    def _parseCsvFile(self):
        with open(self.csv_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=',')
            rows = [row for row in reader if row]

        self.pesees = []
        for row in reversed(rows):
            valeurs = {key: row[idx] for key, idx in TanitaReportGenerator.INDICES.items()}
            valeurs["Sexe"] = TanitaReportGenerator.SEXES.get(valeurs["Sexe"], valeurs["Sexe"])
            self.pesees.append({
                "id": f"{valeurs['Date']} {valeurs['Heure']}",
                "valeurs": valeurs,
            })

        # Variation de chaque mesure par rapport à la pesée précédente
        for i, pesee in enumerate(self.pesees):
            precedente = self.pesees[i + 1] if i + 1 < len(self.pesees) else None
            pesee["variations"] = {
                key: TanitaReportGenerator._variation(pesee["valeurs"][key], precedente["valeurs"][key]) if precedente else None
                for key in TanitaReportGenerator.MESURES
            }

    # Contexte commun à toutes les pages
    def _contexte(self, active_page):
        return {
            "active_page": active_page,
            "pesees": self.pesees,
            "derniere": self.pesees[0] if self.pesees else None,
            "genere_le": datetime.now().strftime("%d/%m/%Y à %H:%M"),
        }

    # Écrire une page à partir de son template
    def _render(self, template_name, output_path, **contexte):
        template = self.env.get_template(template_name)
        with open(output_path, mode='w', encoding='utf-8') as file:
            file.write(template.render(**contexte))

    # Créer la page de résultats (resultats.html)
    def _generateResultatsHtml(self):
        self._render("resultats.html", self.html_resultats_path,
                     cles=TanitaReportGenerator.CLES,
                     mesures=TanitaReportGenerator.MESURES,
                     **self._contexte("resultats"))

    # Générer la page de détails (details.html)
    def _generateDetailsHtml(self):
        self._render("details.html", self.html_details_path,
                     profil=TanitaReportGenerator.PROFIL,
                     globales=TanitaReportGenerator.GLOBALES,
                     segments=TanitaReportGenerator.SEGMENTS,
                     **self._contexte("details"))

    # Générer la page d'évolution (evolution.html)
    def _generateEvolutionHtml(self):
        # Statistiques de chaque mesure sur l'ensemble des pesées
        statistiques = {}
        for key in TanitaReportGenerator.MESURES:
            valeurs = [p["valeurs"][key] for p in self.pesees]
            nombres = [n for n in (TanitaReportGenerator._toFloat(v) for v in valeurs) if n is not None]
            statistiques[key] = {
                "derniere": valeurs[0] if valeurs else "",
                "min": TanitaReportGenerator._formatComme(min(nombres), valeurs) if nombres else "",
                "max": TanitaReportGenerator._formatComme(max(nombres), valeurs) if nombres else "",
                "total": TanitaReportGenerator._variation(valeurs[0], valeurs[-1]) if len(valeurs) > 1 else None,
            }
        self._render("evolution.html", self.html_evolution_path,
                     mesures=TanitaReportGenerator.MESURES,
                     statistiques=statistiques,
                     **self._contexte("evolution"))

    # Générer toutes les pages HTML
    def generateHtmlFiles(self):
        self._generateResultatsHtml()
        self._generateDetailsHtml()
        self._generateEvolutionHtml()
        print(f"Les fichiers HTML ont été générés : {self.html_resultats_path}, {self.html_details_path}, {self.html_evolution_path}")

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

generator = TanitaReportGenerator()
generator.generateHtmlFiles()
