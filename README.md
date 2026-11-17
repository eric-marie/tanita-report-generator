# Tanita Report Generator

Génère un petit rapport HTML consultable dans un navigateur à partir des mesures enregistrées par une balance impédancemètre **Tanita BC-601** sur sa carte SD.

## But du projet

La balance BC-601 enregistre chaque pesée sur une carte SD, dans des fichiers CSV peu lisibles où chaque valeur est précédée d'un code (`Wk,100.1`, `FW,22.1`…). Ce projet transforme ces données brutes en pages HTML claires pour :

- retrouver les différents profils de la balance (4 sur la BC-601) ;
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
│       │   └── PROF1.CSV … PROF4.CSV   ← configuration des profils 1 à 4 (PROF5 à PROF8 restent vides)
│       └── DATA/
│           └── DATA1.CSV … DATA4.CSV   ← pesées des profils 1 à 4 (DATA5 à DATA8 restent vides)
├── rapport/                 ← pages générées (ignorées par Git)
│   └── assets/              ← versionné
│       ├── style.css        ← feuille de style des pages
│       ├── graphique.js     ← dessin des graphiques de la page Évolution
│       └── evolution.js     ← page Évolution : précision, moyennes, synthèse et historique
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

La balance ne stocke aucun nom : les profils sont seulement numérotés de 1 à 4 et s'affichent par défaut comme « Profil 1 », « Profil 2 »… Pour leur donner un nom, copier le modèle `profils.example.json` en `profils.json` et l'adapter :

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

1. **Il détecte les profils.** La BC-601 a 4 touches personnelles, donc 4 profils. Pour chaque numéro de 1 à 4, il regarde deux fichiers de la carte SD :
   - `SYSTEM/PROFn.CSV` : non vide si le profil est configuré sur la balance (modèle, date de naissance, sexe, type de corps, taille, niveau d'activité) ;
   - `DATA/DATAn.CSV` : non vide si le profil a des pesées enregistrées.

   Un profil qui a **au moins une pesée** est considéré comme utilisé et reçoit son propre rapport. Un profil configuré mais sans pesée est seulement signalé sur la page d'accueil. Les autres sont ignorés. La carte prévoit 8 fichiers de chaque sorte : si l'un des fichiers 5 à 8 n'est pas vide, le script le signale et l'ignore.
2. **Il lit les pesées** de chaque profil, une ligne par pesée. Chaque valeur est précédée de son code dans le fichier (`Wk,100.1` pour un poids de 100,1 kg) : le script lit les valeurs **par leur code**, pas par leur position, et en extrait 27 indicateurs : date, heure, sexe, âge, taille, niveau d'activité, type de corps, poids, IMC, masse grasse (totale et par bras, jambe et buste), masse musculaire (totale et par segment), masse osseuse, graisse viscérale, apport calorique quotidien, âge métabolique et eau corporelle. Une valeur absente de la ligne reste vide (voir *Contrôles à la lecture*).
3. **Il calcule des mesures complémentaires et des repères** à partir du guide de la balance (voir *Mesures calculées* et *Repères du guide Tanita*).
4. **Il calcule les variations.** Les pesées sont classées de la plus récente à la plus ancienne et, pour chaque mesure, il calcule la variation par rapport à la pesée précédente. Pour la page d'évolution, il intègre à la page les pesées de chaque mesure (date et heure, valeur, précision de la mesure) : la synthèse, les moyennes et l'historique sont ensuite calculés dans le navigateur.
5. **Il génère les pages HTML** à partir des templates Jinja2 du dossier `templates/`. Les nombres sont affichés avec une virgule décimale, et les codes de la balance en clair, d'après le manuel :
   - sexe : 1 = Homme, 2 = Femme ;
   - niveau d'activité : 1 = peu ou pas d'exercice, 2 = activité modérée, 3 = activité intense ;
   - type de corps : 0 = Standard, autre valeur = Athlète (la balance n'a que ces deux types ; en mode athlète, elle fixe le niveau d'activité à 3).

   Les dossiers de profil d'une génération précédente sont supprimés au préalable, pour ne pas garder un profil qui n'existe plus.

Le script affiche ensuite les profils trouvés, le nombre de pesées de chacun, et les remarques éventuelles des contrôles ci-dessous.

### Contrôles à la lecture

- **Somme de contrôle** : chaque ligne de la carte se termine par `CS,xx`, la somme des octets de la ligne jusqu'à la virgule qui précède `CS`, modulo 256, en hexadécimal. Une ligne dont la somme ne correspond pas (ligne abîmée, par exemple si la carte a été retirée pendant une écriture) est ignorée avec un message.
- **Unités** : la balance peut afficher en kg, en livres ou en stones. Le script vérifie l'unité grâce à l'IMC (poids en kg / taille en m²) : si l'IMC enregistré ne correspond qu'à un poids en livres (et éventuellement une taille en pouces), les masses sont converties en kg et la taille en cm. Si rien ne correspond, les valeurs sont affichées telles quelles avec un avertissement.
- **Format des dates** : le script détecte le format des dates de chaque fichier (jj/mm/aaaa, mm/jj/aaaa ou aaaa/mm/jj) grâce aux jours supérieurs à 12, et les affiche toujours en jj/mm/aaaa. Si aucune date ne lève l'ambiguïté, jj/mm/aaaa est retenu avec une remarque.
- **Valeurs absentes** : pour un enfant (5 à 17 ans), la balance ne fournit que le poids, la graisse corporelle et l'IMC. Les autres mesures restent vides dans les pages, et le graphique l'indique. Une ligne sans poids est ignorée.
- **Mesures réservées aux adultes** : d'après le guide, la masse musculaire, la masse osseuse, l'eau corporelle, l'apport calorique et l'âge métabolique ne s'appliquent qu'entre 18 et 99 ans. Avant 18 ans, elles sont ignorées même si la ligne en contient, ainsi que les mesures calculées et les repères qui en dépendent.

### Mesures calculées

Le script ajoute 4 mesures calculées à partir des valeurs de la balance. Elles apparaissent comme les autres dans les pages (cartes, détails, évolution) :

| Mesure | Calcul |
|---|---|
| Masse grasse (kg) | poids × graisse corporelle (%) |
| Masse maigre (kg) | poids − masse grasse. Pour Tanita, poids = masse grasse + masse musculaire + masse osseuse, et la masse musculaire comprend l'eau des muscles : la masse maigre correspond donc aux muscles et aux os (à l'arrondi près). |
| Métabolisme de base (kcal) | apport calorique quotidien ÷ facteur d'activité. Le guide donne apport = métabolisme de base × facteur, avec les facteurs de l'OMS : homme 1,55 / 1,78 / 2,10 et femme 1,56 / 1,64 / 1,82 pour les niveaux d'activité 1 / 2 / 3. |
| Indice de masse musculaire (kg/m²) | masse musculaire ÷ taille², l'indice de muscle selon la taille cité par le guide |

La page Résultats indique aussi comment se répartit la variation de poids depuis la première pesée : « le poids a varié de −0,1 kg, dont +1,0 kg de masse grasse et −1,1 kg de masse maigre ».

### Repères du guide Tanita

Pour un adulte, les pages Résultats et Détails affichent sous certaines mesures un repère tiré du guide de la balance (`TANITA/GRAPHV1/MANUAL/BC_Guide.pdf`). Ces repères sont indicatifs et ne remplacent pas l'avis d'un médecin, ce que les pages rappellent.

| Mesure | Repère | Source citée par le guide |
|---|---|---|
| Graisse corporelle (%) | Selon le sexe et l'âge, à partir de 20 ans : masse grasse insuffisante, **standard**, excessive ou obésité. Seuils de début du standard / de l'excès / de l'obésité : homme 8 / 20 / 25 % (20-39 ans), 11 / 22 / 28 % (40-59 ans), 13 / 25 / 30 % (60-99 ans) ; femme 21 / 33 / 39 %, 23 / 34 / 40 %, 24 / 36 / 42 %. | Gallagher D. et al., *Am J Clin Nutr* 2000. Le guide présente ces plages sous forme de graphique ; les seuils chiffrés sont ceux de cette étude. |
| Graisse viscérale | 1 à 12 : niveau sain ; 13 à 59 : excès | Columbia University et Tanita Institute |
| Eau corporelle (%) | Moyenne d'un adulte en bonne santé : homme 50 à 65 %, femme 45 à 60 % | Recherche interne Tanita |
| Masse osseuse (kg) | Comparaison avec la moyenne estimée des 20-40 ans pour le même poids (homme : 2,66 kg sous 65 kg, 3,29 kg de 65 à 95 kg, 3,69 kg au-delà ; femme : 1,95 kg sous 50 kg, 2,40 kg de 50 à 75 kg, 2,95 kg au-delà) | Tanita Body Weight Science Institute |
| Âge métabolique | Comparaison avec l'âge réel (« 6 ans de plus que l'âge réel ») | — |

Le statut est toujours indiqué par une **icône et un libellé**, la couleur n'étant qu'un complément : ✓ vert dans la plage, ! ambre à surveiller (graisse insuffisante, eau hors de la moyenne), ! orange en excès, ! rouge pour l'obésité. La masse osseuse et l'âge métabolique n'ont pas de statut, seulement une comparaison.

Sur la page Évolution, la plage du repère (graisse corporelle, graisse viscérale, eau) est dessinée en bande verte discrète derrière la courbe, d'après la pesée la plus récente. L'échelle reste cadrée sur les valeurs : si la plage est en dehors de la zone affichée, la légende le précise.

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
    ├── graphique.js
    └── evolution.js
```

| Fichier | Contenu |
|---|---|
| `index.html` | Liste des profils trouvés : nom, sexe, âge, taille, dernier poids, date de la dernière pesée et nombre de pesées. Les profils configurés sans pesée y sont signalés. **S'il n'y a qu'un seul profil**, cette page redirige directement vers son rapport. |
| `profil-n/resultats.html` | Tableau de bord de la dernière pesée (voir *Page Résultats*). |
| `profil-n/details.html` | Détail d'une pesée choisie dans une liste déroulante : profil (avec, en dessous, la définition du manuel pour le niveau d'activité et le type de corps de la pesée), composition globale avec variations, repères et mesures calculées, et répartition de la graisse et du muscle par segment (bras, jambes, buste). La composition globale est une grille de 9 cases ; certaines regroupent une mesure et ses compléments : IMC et indice de masse musculaire ; graisse corporelle (%) et masse grasse (kg) ; masse maigre, masse musculaire et masse osseuse. L'apport calorique quotidien et le métabolisme de base ont une courte explication en dessous (calories à consommer par jour pour garder ce poids ; énergie dépensée au repos complet). |
| `profil-n/evolution.html` | Pour une mesure choisie dans une liste déroulante et une **précision** au choix (mesures, jour, semaine ou mois) : dernière valeur, minimum, maximum, variation totale, **graphique de l'évolution**, puis historique avec la variation entre chaque point. |

Dans les pages d'un profil, l'en-tête affiche le nom du profil, un lien « Changer » vers la page d'accueil (s'il y a plusieurs profils) et la navigation entre les trois pages.

Il suffit d'ouvrir `rapport/index.html` dans un navigateur. Aucune connexion Internet n'est nécessaire.

### Page Résultats

De haut en bas :

1. **Profil** : modèle, sexe, âge, taille.
2. **Bilan depuis la première pesée** : variation du poids et sa répartition entre masse grasse et masse maigre (muscles et os).
3. **Cartes de la dernière pesée**, regroupées comme les cases de la page Détails : poids ; IMC et indice de masse musculaire ; graisse corporelle (%) et masse grasse (kg) ; masse maigre, masse musculaire et masse osseuse ; eau corporelle ; graisse viscérale ; apport calorique quotidien ; métabolisme de base ; âge métabolique. Chaque carte affiche :
   - la **variation par rapport à la moyenne des pesées des 7 jours glissants qui précèdent la dernière pesée** : toutes les pesées faites entre l'instant de la dernière pesée moins 7 jours et cette dernière pesée (exclue), y compris une pesée faite quelques minutes plus tôt le même jour. S'il n'y en a aucune, la page le signale et n'affiche pas de variation. Les mesures entières (graisse viscérale, âge métabolique) gagnent une décimale, puisqu'on les compare à une moyenne ;
   - une **mini-courbe de tendance** : moyenne par jour sur les 60 derniers jours de pesée, affichée à partir de 2 jours. Comme pour le graphique d'évolution, son échelle couvre au moins 10 fois la précision de la balance, pour qu'une infime variation ne fasse pas un pic ;
   - le **repère** du guide Tanita le cas échéant.

   Un clic sur une carte ouvre la page Évolution sur sa mesure principale (lien `evolution.html#mesure=…`).
4. **Dernières pesées** : les 10 dernières pesées avec les mesures des cartes, et un lien vers l'historique complet de la page Évolution (précision « Mesures »).

La page Évolution lit aussi l'adresse (`#mesure=Poids%20(kg)&precision=semaine`) et la met à jour quand on change de mesure ou de précision : on peut donc garder un lien vers un affichage précis.

### Mise en forme

Les pages n'utilisent aucune librairie externe : la mise en forme est dans `rapport/assets/style.css`, le dessin des graphiques dans `rapport/assets/graphique.js` et la logique de la page Évolution dans `rapport/assets/evolution.js`, tous versionnés avec le projet. Le reste du JavaScript (liste déroulante de la page Détails) est écrit directement dans les templates.

- Les pages s'adaptent aux petits écrans et suivent le mode clair ou sombre du système.
- Les variations sont affichées avec une flèche et une couleur neutre : une hausse ou une baisse n'est ni bonne ni mauvaise en soi (une baisse de la graisse n'a pas le même sens qu'une baisse de la masse musculaire).

Si le dossier `rapport/assets/` est supprimé, il faut le récupérer depuis Git (`git checkout -- rapport/assets`).

### Précision de la page Évolution

Un choix en haut de la page Évolution règle la précision de l'affichage :

| Précision | Ce qui est affiché |
|---|---|
| **Mesures** | Chaque pesée telle quelle, avec sa date et son heure. |
| **Jour** *(par défaut)* | La moyenne de toutes les pesées de chaque journée. |
| **Semaine** | La moyenne de toutes les pesées de chaque semaine, du lundi au dimanche (« Semaine du 12/08/2024 »). |
| **Mois** | La moyenne de toutes les pesées de chaque mois (« août 2024 »). |

Les cartes de synthèse, le graphique et l'historique suivent la précision choisie. En moyenne, l'historique indique le nombre de pesées de chaque période, et la bulle du graphique le rappelle (« moyenne de 3 pesées »). Les moyennes gardent la précision de la balance (0,1 kg, 0,1 %…). Les mesures entières comme la graisse viscérale ou l'âge métabolique gagnent une décimale, sauf l'apport calorique. Sur le graphique, chaque période est placée en son milieu. Si une date de pesée est illisible, seule la précision « Mesures » est disponible.

### Graphique d'évolution

Le graphique de la page Évolution est une courbe SVG dessinée dans le navigateur par `graphique.js`, à partir des données intégrées à la page par le script Python.

- **Axe horizontal** : le vrai calendrier. L'écart entre deux points correspond au temps écoulé entre les pesées. Si une date est illisible, les pesées sont espacées régulièrement.
- **Axe vertical** : il ne part pas de zéro, il est cadré sur les valeurs de la mesure. Les graduations ne sont jamais plus précises que la balance (pas de 0,25 kg pour une mesure au dixième), et l'étendue couvre au moins 10 fois cette précision, pour qu'une variation de 0,1 kg n'apparaisse pas comme une chute vertigineuse.
- **Lecture** : la dernière valeur est écrite au bout de la courbe. Au survol, un curseur vertical et une bulle donnent la valeur du point le plus proche, avec la date et l'heure de la pesée, ou la période et le nombre de pesées moyennées. Au clavier, le graphique prend le focus avec Tab, et les flèches gauche et droite parcourent les points.
- **Couleur** : la courbe utilise la variable CSS `--serie` (`#2f6fde` en mode clair, `#5b8ff8` en mode sombre). Ces deux teintes ont été vérifiées contre leur fond (plage de luminosité, saturation et contraste d'au moins 3:1).
- Le tableau d'historique sous le graphique reste la version texte des mêmes valeurs.

## Données personnelles

Les pages générées contiennent des données de santé (poids, composition corporelle, âge…). Sont donc **exclus du dépôt** par le `.gitignore` :

- le dossier `TANITA` (copie de la carte SD) ;
- le fichier `profils.json` (noms des profils) ;
- les pages HTML de `rapport/` et les dossiers `rapport/profil-n/`.

Seuls le script, les templates, les fichiers de `rapport/assets/` (feuille de style et scripts) et le modèle `profils.example.json` sont versionnés.
