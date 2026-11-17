import csv
import os
from jinja2 import Environment, FileSystemLoader

class TanitaReportGenerator:
    # Les indices des colonnes que nous voulons extraire
    INDICES = {
        "Model": 11,
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

    # Lire le fichier CSV
    def _parseCsvFile(self):
        with open(self.csv_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter=',')
            self.rows = [row for row in reader]

    # Créer la page de résultats (resultats.html)
    def _generateResultatsHtml(self):
        # Extraire les indicateurs
        indicators = list(TanitaReportGenerator.INDICES.keys())
        # Charger et rendre le template pour la page d'évolution
        template = self.env.get_template("resultats.html")
        html_content = template.render(active_page="resultats", indicators=indicators, indices=TanitaReportGenerator.INDICES.items(), resultats=reversed(self.rows))
        with open(self.html_resultats_path, mode='w', encoding='utf-8') as file:
            file.write(html_content)

    # Générer la page de détails (details.html)
    def _generateDetailsHtml(self):
        # Extraire les dates/horaires
        dates_heures = [f"{row[TanitaReportGenerator.INDICES['Date']]} {row[TanitaReportGenerator.INDICES['Heure']]}" for row in reversed(self.rows)]
        # Organiser les détails sous forme de dictionnaire
        details = {
            f"{row[TanitaReportGenerator.INDICES['Date']]} {row[TanitaReportGenerator.INDICES['Heure']]}": {key: row[idx] for key, idx in TanitaReportGenerator.INDICES.items()}
            for row in reversed(self.rows)
        }
        # Charger et rendre le template pour la page de détails
        template = self.env.get_template("details.html")
        html_content = template.render(active_page="details", dates_heures=dates_heures, details=details)
        with open(self.html_details_path, mode='w', encoding='utf-8') as file:
            file.write(html_content)

    # Générer la page d'évolution (evolution.html)
    def _generateEvolutionHtml(self):
        # Extraire les indicateurs
        indicators = list(TanitaReportGenerator.INDICES.keys())[7:]
        # Organiser les données pour la page d'évolution
        evolution = {
            indicator: {
                f"{row[TanitaReportGenerator.INDICES['Date']]} {row[TanitaReportGenerator.INDICES['Heure']]}": row[TanitaReportGenerator.INDICES[indicator]]
                for row in reversed(self.rows)
            }
            for indicator in list(TanitaReportGenerator.INDICES.keys())[7:]
        }
        # Charger et rendre le template pour la page d'évolution
        template = self.env.get_template("evolution.html")
        html_content = template.render(active_page="evolution", indicators=indicators, evolution=evolution)
        with open(self.html_evolution_path, mode='w', encoding='utf-8') as file:
            file.write(html_content)

    # Générer toutes les pages HTML
    def generateHtmlFiles(self):
        self._generateResultatsHtml()
        self._generateDetailsHtml()
        self._generateEvolutionHtml()
        print(f"Les fichiers HTML ont été générés : {self.html_resultats_path}, {self.html_details_path}, {self.html_evolution_path}")

generator = TanitaReportGenerator()
generator.generateHtmlFiles()
