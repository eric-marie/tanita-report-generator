/* ==========================================================================
   Page Évolution — choix de la mesure et de la précision, synthèse, graphique
   et historique. Les pesées sont lues dans <script id="donnees-graphiques">.

   Précisions :
     mesures   chaque pesée telle quelle
     jour      moyenne des pesées de chaque journée (par défaut)
     semaine   moyenne des pesées de chaque semaine (du lundi au dimanche)
     mois      moyenne des pesées de chaque mois
   Les instants sont des ms comptées comme des heures UTC : on lit donc les dates
   avec getUTC*, sans décalage de fuseau horaire.
   ========================================================================== */
(function () {
    "use strict";

    var source = document.getElementById("donnees-graphiques");
    if (!source) return;
    var series = JSON.parse(source.textContent);

    var JOUR = 86400000;
    var MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                "août", "septembre", "octobre", "novembre", "décembre"];
    var LIBELLES_PERIODE = { mesures: "Date", jour: "Jour", semaine: "Semaine", mois: "Mois" };

    var selectMesure = document.getElementById("mesureSelect");
    var radios = document.querySelectorAll("input[name=precision]");
    var cartes = document.getElementById("cartesEvolution");
    var titre = document.getElementById("titreGraphique");
    var conteneurGraphique = document.getElementById("graphique");
    var tableau = document.getElementById("tableauEvolution");

    var etat = { mesure: 0, precision: "jour", serie: null };

    function deuxChiffres(n) { return (n < 10 ? "0" : "") + n; }

    // Arrondi au plus proche, la moitié s'éloignant de zéro. toFixed seul arrondirait
    // 100,05 en 100,0 car ce nombre vaut en réalité 100,04999… en binaire.
    function arrondi(v, decimales) {
        var p = Math.pow(10, decimales);
        return Math.sign(v) * Math.round(Math.abs(v) * p + 1e-7) / p;
    }
    function nombreFr(v, decimales) { return v.toFixed(decimales).replace(".", ","); }
    function dateFr(ms) {
        var d = new Date(ms);
        return deuxChiffres(d.getUTCDate()) + "/" + deuxChiffres(d.getUTCMonth() + 1) + "/" + d.getUTCFullYear();
    }

    // Les moyennes d'une mesure entière (ex. graisse viscérale 9 et 10) gardent une décimale,
    // sauf pour les grandes valeurs comme l'apport calorique
    function decimalesMoyenne(serie) {
        if (serie.decimales > 0) return serie.decimales;
        var max = Math.max.apply(null, serie.points.map(function (p) { return Math.abs(p.v); }).concat([0]));
        return max < 100 ? 1 : 0;
    }

    // Période qui contient un instant : clé, début, fin et libellé
    function periode(t, precision) {
        var d = new Date(t), a = d.getUTCFullYear(), m = d.getUTCMonth(), j = d.getUTCDate();
        var debut;
        if (precision === "jour") {
            debut = Date.UTC(a, m, j);
            return { debut: debut, fin: debut + JOUR, libelle: dateFr(debut), court: dateFr(debut) };
        }
        if (precision === "semaine") {
            debut = Date.UTC(a, m, j - (d.getUTCDay() + 6) % 7);
            return { debut: debut, fin: debut + 7 * JOUR, libelle: "Semaine du " + dateFr(debut), court: dateFr(debut) };
        }
        debut = Date.UTC(a, m, 1);
        return { debut: debut, fin: Date.UTC(a, m + 1, 1), libelle: MOIS[m] + " " + a, court: MOIS[m] + " " + a };
    }

    // Série à la précision choisie, au format attendu par TanitaGraphique
    function serieAffichee(serie, precision) {
        if (precision === "mesures") {
            return {
                nom: serie.nom, unite: serie.unite, decimales: serie.decimales,
                points: serie.points.map(function (p) {
                    return { t: p.t, v: p.v, texte: p.texte, libelle: p.date, detail: p.date + " à " + p.heure,
                             date: p.date, heure: p.heure, nb: 1 };
                })
            };
        }
        var groupes = [], parCle = {};
        serie.points.forEach(function (p) {
            var per = periode(p.t, precision);
            var g = parCle[per.debut];
            if (!g) {
                g = parCle[per.debut] = { periode: per, somme: 0, nb: 0 };
                groupes.push(g);
            }
            g.somme += p.v;
            g.nb++;
        });
        var decimales = decimalesMoyenne(serie);
        return {
            nom: serie.nom, unite: serie.unite, decimales: decimales,
            points: groupes.map(function (g) {
                var v = arrondi(g.somme / g.nb, decimales);
                return {
                    t: (g.periode.debut + g.periode.fin) / 2, v: v, texte: nombreFr(v, decimales),
                    libelle: g.periode.court, periode: g.periode.libelle, nb: g.nb,
                    detail: g.periode.libelle + (g.nb > 1 ? " · moyenne de " + g.nb + " pesées" : " · 1 pesée")
                };
            })
        };
    }

    // Variation entre deux valeurs : { texte: "+0,1", sens: "hausse|baisse|stable" }
    function variation(a, b, decimales) {
        var ecart = arrondi(a - b, decimales);
        if (ecart === 0) return { texte: "=", sens: "stable" };
        return { texte: (ecart > 0 ? "+" : "-") + nombreFr(Math.abs(ecart), decimales), sens: ecart > 0 ? "hausse" : "baisse" };
    }

    // Petits constructeurs d'éléments HTML (textes insérés avec textContent)
    function el(nom, classe, texte) {
        var e = document.createElement(nom);
        if (classe) e.className = classe;
        if (texte !== undefined) e.textContent = texte;
        return e;
    }
    function valeurAvecUnite(texte, unite) {
        var f = document.createDocumentFragment();
        f.appendChild(document.createTextNode(texte));
        if (unite) f.appendChild(el("span", "unite", unite));
        return f;
    }
    function pastille(v) {
        return v ? el("span", "variation " + v.sens, v.texte) : el("span", "sans-valeur", "—");
    }

    // Cartes de synthèse : dernière valeur, minimum, maximum, variation totale
    function remplirCartes(serie) {
        cartes.textContent = "";
        var points = serie.points;
        function carte(libelle, texte, pied) {
            var c = el("div", "carte");
            c.appendChild(el("div", "carte-libelle", libelle));
            var v = el("div", "carte-valeur");
            if (texte === null) v.appendChild(el("span", "sans-valeur", "—"));
            else v.appendChild(valeurAvecUnite(texte, serie.unite));
            c.appendChild(v);
            if (pied) c.appendChild(el("div", "carte-pied", pied));
            cartes.appendChild(c);
        }
        if (!points.length) {
            ["Dernière valeur", "Minimum", "Maximum", "Variation totale"].forEach(function (l) { carte(l, null); });
            return;
        }
        var dernier = points[points.length - 1];
        var min = points.reduce(function (a, p) { return p.v < a.v ? p : a; });
        var max = points.reduce(function (a, p) { return p.v > a.v ? p : a; });
        carte("Dernière valeur", dernier.texte, dernier.libelle);
        carte("Minimum", min.texte, min.libelle);
        carte("Maximum", max.texte, max.libelle);
        carte("Variation totale", points.length > 1 ? variation(dernier.v, points[0].v, serie.decimales).texte : null,
              points.length > 1 ? "depuis " + points[0].libelle : "un seul point");
    }

    // Historique, du plus récent au plus ancien
    function remplirTableau(serie, precision) {
        tableau.textContent = "";
        var thead = el("thead"), entete = el("tr");
        entete.appendChild(el("th", "", LIBELLES_PERIODE[precision]));
        var thValeur = el("th", "", precision === "mesures" ? "Valeur" : "Moyenne");
        if (serie.unite) thValeur.appendChild(el("span", "unite", serie.unite));
        entete.appendChild(thValeur);
        if (precision !== "mesures") entete.appendChild(el("th", "", "Pesées"));
        var thVariation = el("th", "", "Variation");
        thVariation.appendChild(el("span", "unite", precision === "mesures" ? "vs précédente" : "vs période précédente"));
        entete.appendChild(thVariation);
        thead.appendChild(entete);

        var tbody = el("tbody");
        var points = serie.points;
        if (!points.length) {
            var vide = el("tr"), td = el("td", "sans-valeur", "Aucune valeur enregistrée pour cette mesure.");
            td.colSpan = precision === "mesures" ? 3 : 4;
            vide.appendChild(td);
            tbody.appendChild(vide);
        }
        for (var i = points.length - 1; i >= 0; i--) {
            var p = points[i], tr = el("tr");
            var cellule = el("td", "date", precision === "mesures" ? p.date : p.periode);
            if (precision === "mesures") cellule.appendChild(el("span", "heure", p.heure));
            tr.appendChild(cellule);
            tr.appendChild(el("td", "", p.texte));
            if (precision !== "mesures") tr.appendChild(el("td", "", String(p.nb)));
            var tdVariation = el("td");
            tdVariation.appendChild(pastille(i > 0 ? variation(p.v, points[i - 1].v, serie.decimales) : null));
            tr.appendChild(tdVariation);
            tbody.appendChild(tr);
        }
        tableau.appendChild(thead);
        tableau.appendChild(tbody);
    }

    function afficher() {
        var brute = series[etat.mesure];
        etat.serie = serieAffichee(brute, etat.precision);
        titre.textContent = brute.nom + (brute.unite ? " (" + brute.unite + ")" : "") +
            (etat.precision === "mesures" ? "" : " · moyenne par " + { jour: "jour", semaine: "semaine", mois: "mois" }[etat.precision]);
        remplirCartes(etat.serie);
        remplirTableau(etat.serie, etat.precision);
        TanitaGraphique.dessiner(conteneurGraphique, etat.serie);
    }

    // Sans date lisible, seules les pesées brutes peuvent être affichées
    var datesLisibles = series.every(function (s) { return s.points.every(function (p) { return p.t !== null; }); });
    radios.forEach(function (radio) {
        if (!datesLisibles && radio.value !== "mesures") radio.disabled = true;
        radio.addEventListener("change", function () {
            if (this.checked) { etat.precision = this.value; afficher(); }
        });
    });
    if (!datesLisibles) etat.precision = "mesures";
    radios.forEach(function (radio) { radio.checked = radio.value === etat.precision; });

    selectMesure.addEventListener("change", function () {
        etat.mesure = +this.value;
        afficher();
    });
    etat.mesure = +selectMesure.value;

    afficher();

    // Redessiner le graphique quand sa largeur change
    var derniereLargeur = conteneurGraphique.clientWidth;
    function redimensionner() {
        if (conteneurGraphique.clientWidth !== derniereLargeur) {
            derniereLargeur = conteneurGraphique.clientWidth;
            TanitaGraphique.dessiner(conteneurGraphique, etat.serie);
        }
    }
    if ("ResizeObserver" in window) new ResizeObserver(redimensionner).observe(conteneurGraphique);
    else window.addEventListener("resize", redimensionner);
})();
