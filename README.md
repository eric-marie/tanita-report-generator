# Tanita Report Generator

Génère un petit rapport HTML consultable dans un navigateur à partir des mesures enregistrées par une balance impédancemètre **Tanita BC-601** sur sa carte SD.

## But du projet

La balance BC-601 enregistre chaque pesée sur une carte SD, dans des fichiers CSV peu lisibles où chaque valeur est précédée d'un code (`Wk,100.1`, `FW,22.1`…). Ce projet transforme ces données brutes en pages HTML claires pour :

- retrouver les différents profils de la balance (jusqu'à 8) ;
- consulter toutes les pesées d'un profil dans un tableau ;
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
│       ├── SYSTEM/
│       │   └── PROF1.CSV … PROF8.CSV   ← configuration des profils 1 à 8
│       └── DATA/
│           └── DATA1.CSV … DATA8.CSV   ← pesées des profils 1 à 8
├── rapport/                 ← pages générées (ignorées par Git)
│   └── assets/              ← versionné
│       ├── style.css        ← feuille de style des pages
│       └── graphique.js     ← dessin des graphiques de la page Évolution
├── templates/               ← templates Jinja2 des pages
│   ├── _base.html           ← structure commune (en-tête, navigation, pied de page)
│   ├── _macros.html         ← éléments réutilisables (variations, valeurs, profil)
│   ├── index.html           ← page d'accueil : liste des profils
│   ├── resultats.html
│   ├── details.html
│   └── evolution.html
├── profils.example.json     ← modèle pour nommer les profils (versionné)
├── profils.json             ← noms des profils, facultatif (ignoré par Git)
└── generate_report.py
```

### Nommer les profils (facultatif)

La balance ne stocke aucun nom : les profils sont seulement numérotés de 1 à 8 et s'affichent par défaut comme « Profil 1 », « Profil 2 »… Pour leur donner un nom, copier le modèle `profils.example.json` en `profils.json` et l'adapter :

```json
{
    "1": "Prénom du profil 1",
    "2": "Prénom du profil 2"
}
```

Les clés sont les numéros de profil sur la balance. Un profil absent du fichier garde son nom par défaut. `profils.json` est ignoré par Git, car il contient des données personnelles.

### Lancer la génération

Le script doit être exécuté **depuis le dossier du projet**, car les chemins sont relatifs au dossier courant :

```bash
cd tanita-report-generator
python generate_report.py
```

### Ce que fait le script

1. **Il détecte les profils.** Pour chaque numéro de 1 à 8, il regarde deux fichiers de la carte SD :
   - `SYSTEM/PROFn.CSV` : non vide si le profil est configuré sur la balance (modèle, date de naissance, sexe, taille, niveau d'activité) ;
   - `DATA/DATAn.CSV` : non vide si le profil a des pesées enregistrées.

   Un profil qui a **au moins une pesée** est considéré comme utilisé et reçoit son propre rapport. Un profil configuré mais sans pesée est seulement signalé sur la page d'accueil. Les autres sont ignorés.
2. **Il lit les pesées** de chaque profil, une ligne par pesée, et en extrait 26 indicateurs selon leur position dans la ligne : date, heure, sexe, âge, taille, niveau d'activité, poids, IMC, masse grasse (totale et par bras, jambe et buste), masse musculaire (totale et par segment), masse osseuse, graisse viscérale, apport calorique quotidien, âge métabolique et eau corporelle.
3. **Il calcule les variations.** Les pesées sont classées de la plus récente à la plus ancienne et, pour chaque mesure, il calcule la variation par rapport à la pesée précédente. Pour la page d'évolution, il calcule aussi le minimum, le maximum et la variation totale de chaque mesure, et prépare les points des graphiques (date et heure de chaque pesée, valeur, précision de la mesure).
4. **Il génère les pages HTML** à partir des templates Jinja2 du dossier `templates/`. Les nombres sont affichés avec une virgule décimale, et le sexe en clair (« Homme » ou « Femme ») au lieu du code de la balance. Les dossiers de profil d'une génération précédente sont supprimés au préalable, pour ne pas garder un profil qui n'existe plus.

Le script affiche ensuite les profils trouvés et le nombre de pesées de chacun.

## Fichiers générés

Toutes les pages sont créées dans le dossier `rapport/` du projet, à côté de la feuille de style `assets/style.css` :

```
rapport/
├── index.html               ← page d'accueil
├── profil-1/
│   ├── resultats.html
│   ├── details.html
│   └── evolution.html
├── profil-3/                ← un dossier par profil ayant des pesées
│   └── …
└── assets/
    ├── style.css
    └── graphique.js
```

| Fichier | Contenu |
|---|---|
| `index.html` | Liste des profils trouvés : nom, sexe, âge, taille, dernier poids, date de la dernière pesée et nombre de pesées. Les profils configurés sans pesée y sont signalés. **S'il n'y a qu'un seul profil**, cette page redirige directement vers son rapport. |
| `profil-n/resultats.html` | Profil, cartes des 8 mesures principales de la dernière pesée avec leur variation, puis tableau de toutes les pesées. |
| `profil-n/details.html` | Détail d'une pesée choisie dans une liste déroulante : profil, composition globale avec variations, et répartition de la graisse et du muscle par segment (bras, jambes, buste). |
| `profil-n/evolution.html` | Pour une mesure choisie dans une liste déroulante : dernière valeur, minimum, maximum, variation totale, **graphique de l'évolution**, puis historique avec la variation entre chaque pesée. |

Dans les pages d'un profil, l'en-tête affiche le nom du profil, un lien « Changer » vers la page d'accueil (s'il y a plusieurs profils) et la navigation entre les trois pages.

Il suffit d'ouvrir `rapport/index.html` dans un navigateur. Aucune connexion Internet n'est nécessaire.

### Mise en forme

Les pages n'utilisent aucune librairie externe : la mise en forme est dans `rapport/assets/style.css`, le dessin des graphiques dans `rapport/assets/graphique.js`, tous deux versionnés avec le projet. Le reste du JavaScript (listes déroulantes) est écrit directement dans les templates.

- Les pages s'adaptent aux petits écrans et suivent le mode clair ou sombre du système.
- Les variations sont affichées avec une flèche et une couleur neutre : une hausse ou une baisse n'est ni bonne ni mauvaise en soi (une baisse de la graisse n'a pas le même sens qu'une baisse de la masse musculaire).

Si le dossier `rapport/assets/` est supprimé, il faut le récupérer depuis Git (`git checkout -- rapport/assets`).

### Graphique d'évolution

Le graphique de la page Évolution est une courbe SVG dessinée dans le navigateur par `graphique.js`, à partir des données intégrées à la page par le script Python.

- **Axe horizontal** : le vrai calendrier. L'écart entre deux points correspond au temps écoulé entre les pesées. Si une date est illisible, les pesées sont espacées régulièrement.
- **Axe vertical** : il ne part pas de zéro, il est cadré sur les valeurs de la mesure. Les graduations ne sont jamais plus précises que la balance (pas de 0,25 kg pour une mesure au dixième), et l'étendue couvre au moins 10 fois cette précision, pour qu'une variation de 0,1 kg n'apparaisse pas comme une chute vertigineuse.
- **Lecture** : la dernière valeur est écrite au bout de la courbe. Au survol, un curseur vertical et une bulle donnent la valeur, la date et l'heure de la pesée la plus proche. Au clavier, le graphique prend le focus avec Tab, et les flèches gauche et droite parcourent les pesées.
- **Couleur** : la courbe utilise la variable CSS `--serie` (`#2f6fde` en mode clair, `#5b8ff8` en mode sombre). Ces deux teintes ont été vérifiées contre leur fond (plage de luminosité, saturation et contraste d'au moins 3:1).
- Le tableau d'historique sous le graphique reste la version texte des mêmes valeurs.

## Données personnelles

Les pages générées contiennent des données de santé (poids, composition corporelle, âge…). Sont donc **exclus du dépôt** par le `.gitignore` :

- le dossier `TANITA` (copie de la carte SD) ;
- le fichier `profils.json` (noms des profils) ;
- les pages HTML de `rapport/` et les dossiers `rapport/profil-n/`.

Seuls le script, les templates, la feuille de style et le modèle `profils.example.json` sont versionnés.
