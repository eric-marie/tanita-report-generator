# Tanita Report Generator

Génère un petit rapport HTML consultable dans un navigateur à partir des mesures enregistrées par une balance impédancemètre **Tanita BC-601** sur sa carte SD.

## But du projet

La balance BC-601 enregistre chaque pesée sur une carte SD, dans des fichiers CSV peu lisibles où chaque valeur est précédée d'un code (`Wk,100.1`, `FW,22.1`…). Ce projet transforme ces données brutes en pages HTML claires pour :

- consulter toutes les pesées dans un tableau ;
- voir le détail complet d'une pesée ;
- suivre l'évolution d'un indicateur dans le temps.

## Fonctionnement

### Prérequis

- Python 3
- [Jinja2](https://pypi.org/project/Jinja2/) :

```bash
pip install jinja2
```

### Organisation attendue des dossiers

Le script lit les données dans un dossier `TANITA` placé **à côté** de ce projet, c'est-à-dire une copie du contenu de la carte SD de la balance :

```
Tanita Project/
├── TANITA/                      ← copie de la carte SD (non versionnée)
│   └── GRAPHV1/
│       └── DATA/
│           └── DATA1.CSV        ← mesures du profil utilisateur n°1
└── tanita-report-generator/     ← ce dépôt
    ├── generate_report.py
    └── templates/
```

### Lancer la génération

Le script doit être exécuté **depuis le dossier du projet**, car les chemins sont relatifs au dossier courant :

```bash
cd tanita-report-generator
python generate_report.py
```

### Ce que fait le script

1. Il lit `../TANITA/GRAPHV1/DATA/DATA1.CSV`, une ligne par pesée.
2. Il extrait 26 indicateurs selon leur position dans la ligne : date, heure, sexe, âge, taille, niveau d'activité, poids, IMC, masse grasse (totale et par bras, jambe et buste), masse musculaire (totale et par segment), masse osseuse, graisse viscérale, apport calorique quotidien, âge métabolique et eau corporelle.
3. Il génère les pages HTML à partir des templates Jinja2 du dossier `templates/`, mis en forme avec Bootstrap 4. Les pesées sont classées de la plus récente à la plus ancienne.

> Seul le profil n°1 (`DATA1.CSV`) est lu. La balance peut gérer jusqu'à 8 profils (`DATA1.CSV` à `DATA8.CSV`).

## Fichiers générés

Les trois pages sont créées à la racine du projet et reliées entre elles par une barre de navigation :

| Fichier | Contenu |
|---|---|
| `resultats.html` | Tableau de toutes les pesées, avec l'ensemble des indicateurs en colonnes. |
| `details.html` | Détail d'une pesée choisie dans une liste déroulante (date et heure). |
| `evolution.html` | Historique des valeurs d'un indicateur choisi dans une liste déroulante (du poids à l'eau corporelle). |

Il suffit d'ouvrir `resultats.html` dans un navigateur. Une connexion Internet est nécessaire pour charger Bootstrap et Font Awesome depuis leurs CDN.

## Données personnelles

Les pages générées contiennent des données de santé (poids, composition corporelle, âge…). Elles sont donc **exclues du dépôt** par le `.gitignore`, tout comme le dossier `TANITA`, qui se trouve en dehors du projet. Seuls le script et les templates sont versionnés.
