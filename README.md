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

Le script lit les données dans un dossier `TANITA` placé **à la racine du projet**. Il s'agit d'une copie du contenu de la carte SD de la balance : il suffit de copier le dossier `TANITA` de la carte dans le projet.

```
tanita-report-generator/
├── TANITA/                  ← copie de la carte SD (ignorée par Git)
│   └── GRAPHV1/
│       └── DATA/
│           └── DATA1.CSV    ← mesures du profil utilisateur n°1
├── rapport/                 ← pages générées (ignorées par Git)
│   └── assets/
│       └── style.css        ← feuille de style des pages (versionnée)
├── templates/               ← templates Jinja2 des pages
│   ├── _base.html           ← structure commune (en-tête, navigation, pied de page)
│   ├── _macros.html         ← éléments réutilisables (variations, valeurs, profil)
│   ├── resultats.html
│   ├── details.html
│   └── evolution.html
└── generate_report.py
```

### Lancer la génération

Le script doit être exécuté **depuis le dossier du projet**, car les chemins sont relatifs au dossier courant :

```bash
cd tanita-report-generator
python generate_report.py
```

### Ce que fait le script

1. Il lit `TANITA/GRAPHV1/DATA/DATA1.CSV`, une ligne par pesée.
2. Il extrait 26 indicateurs selon leur position dans la ligne : date, heure, sexe, âge, taille, niveau d'activité, poids, IMC, masse grasse (totale et par bras, jambe et buste), masse musculaire (totale et par segment), masse osseuse, graisse viscérale, apport calorique quotidien, âge métabolique et eau corporelle.
3. Il classe les pesées de la plus récente à la plus ancienne et calcule, pour chaque mesure, la variation par rapport à la pesée précédente. Pour la page d'évolution, il calcule aussi le minimum, le maximum et la variation totale de chaque mesure.
4. Il génère les pages HTML à partir des templates Jinja2 du dossier `templates/`. Les nombres sont affichés avec une virgule décimale, et le sexe en clair (« Homme » ou « Femme ») au lieu du code de la balance.

> Seul le profil n°1 (`DATA1.CSV`) est lu. La balance peut gérer jusqu'à 8 profils (`DATA1.CSV` à `DATA8.CSV`).

## Fichiers générés

Les trois pages sont créées dans le dossier `rapport/` du projet, à côté de la feuille de style `assets/style.css`. Elles sont reliées entre elles par une barre de navigation :

| Fichier | Contenu |
|---|---|
| `resultats.html` | Profil, cartes des 8 mesures principales de la dernière pesée avec leur variation, puis tableau de toutes les pesées. |
| `details.html` | Détail d'une pesée choisie dans une liste déroulante : profil, composition globale avec variations, et répartition de la graisse et du muscle par segment (bras, jambes, buste). |
| `evolution.html` | Pour une mesure choisie dans une liste déroulante : dernière valeur, minimum, maximum, variation totale, puis historique avec la variation entre chaque pesée. |

Il suffit d'ouvrir `rapport/resultats.html` dans un navigateur. Aucune connexion Internet n'est nécessaire.

### Mise en forme

Les pages n'utilisent aucune librairie externe : toute la mise en forme est dans `rapport/assets/style.css`, versionnée avec le projet, et le peu de JavaScript nécessaire (listes déroulantes) est écrit directement dans les templates.

- Les pages s'adaptent aux petits écrans et suivent le mode clair ou sombre du système.
- Les variations sont affichées avec une flèche et une couleur neutre : une hausse ou une baisse n'est ni bonne ni mauvaise en soi (une baisse de la graisse n'a pas le même sens qu'une baisse de la masse musculaire).

Si le dossier `rapport/assets/` est supprimé, il faut le récupérer depuis Git (`git checkout -- rapport/assets`).

## Données personnelles

Les pages générées contiennent des données de santé (poids, composition corporelle, âge…). Les fichiers HTML du dossier `rapport/` sont donc **exclus du dépôt** par le `.gitignore`, tout comme le dossier `TANITA`. Seuls le script, les templates et la feuille de style sont versionnés.
