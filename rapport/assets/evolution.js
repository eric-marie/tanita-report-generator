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
    var legende = document.getElementById("legendeRepere");

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
                nom: serie.nom, unite: serie.unite, decimales: serie.decimales, repere: serie.repere,
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
            nom: serie.nom, unite: serie.unite, decimales: decimales, repere: serie.repere,
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

    // Jauge colorée de l'IMC pour la dernière valeur affichée : même construction que la macro
    // jauge_imc_html des templates (classes et seuils transmis par le script Python)
    var definitionJauge = JSON.parse((document.getElementById("jauge-imc-definition") || {}).textContent || "null");
    var conteneurJauge = document.getElementById("jaugeImc");

    function remplirJaugeImc(serie, brute) {
        conteneurJauge.textContent = "";
        var dernier = serie.points[serie.points.length - 1];
        conteneurJauge.hidden = !definitionJauge || brute.nom !== "IMC" || !dernier;
        if (conteneurJauge.hidden) return;

        var bas = definitionJauge.bas, haut = definitionJauge.haut, segments = definitionJauge.segments;
        var classe = segments.filter(function (s) { return s.numero === 1 || dernier.v >= s.debut; }).pop();
        var curseur = (Math.min(Math.max(dernier.v, bas), haut) - bas) / (haut - bas) * 100;

        conteneurJauge.appendChild(el("div", "carte-libelle", "Classe d'IMC · " + dernier.texte + " kg/m² (" + dernier.libelle + ")"));
        var jauge = el("div", "jauge-imc");
        jauge.setAttribute("role", "meter");
        jauge.setAttribute("aria-valuemin", bas);
        jauge.setAttribute("aria-valuemax", haut);
        jauge.setAttribute("aria-valuenow", dernier.v);
        jauge.setAttribute("aria-label", "IMC " + dernier.texte + " kg/m² : " + classe.complet);

        var barre = el("div", "jauge-imc-barre");
        segments.forEach(function (s) {
            var seg = el("span", "jauge-imc-segment" + (s.numero === classe.numero ? " actif" : ""));
            seg.style.flex = s.largeur;
            seg.style.background = "var(--imc-" + s.numero + ")";
            seg.title = s.complet;
            barre.appendChild(seg);
        });
        var marque = el("span", "jauge-imc-curseur");
        marque.style.left = curseur.toFixed(2) + "%";
        barre.appendChild(marque);
        jauge.appendChild(barre);

        var graduations = el("div", "jauge-imc-graduations");
        graduations.setAttribute("aria-hidden", "true");
        segments.slice(1).forEach(function (s) {
            var g = el("span", "", s.graduation);
            g.style.left = s.position.toFixed(2) + "%";
            graduations.appendChild(g);
        });
        jauge.appendChild(graduations);

        var nomClasse = el("div", "jauge-imc-classe");
        var pastilleClasse = el("span", "jauge-imc-pastille");
        pastilleClasse.style.background = "var(--imc-" + classe.numero + ")";
        nomClasse.appendChild(pastilleClasse);
        nomClasse.appendChild(document.createTextNode(classe.complet));
        jauge.appendChild(nomClasse);
        conteneurJauge.appendChild(jauge);
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
        remplirJaugeImc(etat.serie, brute);
        remplirTableau(etat.serie, etat.precision);
        dessinerGraphique();
    }

    // Dessiner le graphique et sa légende de repère (bande verte = plage du guide Tanita)
    function dessinerGraphique() {
        var rendu = TanitaGraphique.dessiner(conteneurGraphique, etat.serie);
        var repere = etat.serie.repere;
        legende.hidden = !repere || !etat.serie.points.length;
        legende.classList.toggle("hors-zone", !!repere && !rendu.repereVisible);
        legende.textContent = repere ? "Repère du guide Tanita : " + repere.plage.replace(/\./g, ",") +
            (rendu.repereVisible ? "" : " (hors de la zone affichée)") : "";
    }

    // Choix initial lu dans l'adresse, ex. evolution.html#mesure=Poids%20(kg)&precision=semaine
    // (liens des cartes de la page Résultats), puis tenu à jour quand on change de choix
    var parametres = new URLSearchParams(location.hash.slice(1));
    var mesureDemandee = parametres.get("mesure");
    if (mesureDemandee) {
        var option = Array.prototype.find.call(selectMesure.options, function (o) { return o.text === mesureDemandee; });
        if (option) selectMesure.value = option.value;
    }
    if (LIBELLES_PERIODE[parametres.get("precision")]) etat.precision = parametres.get("precision");

    function memoriserChoix() {
        var p = new URLSearchParams();
        p.set("mesure", selectMesure.options[selectMesure.selectedIndex].text);
        p.set("precision", etat.precision);
        history.replaceState(null, "", "#" + p.toString());
    }

    // Sans date lisible, seules les pesées brutes peuvent être affichées
    var datesLisibles = series.every(function (s) { return s.points.every(function (p) { return p.t !== null; }); });
    radios.forEach(function (radio) {
        if (!datesLisibles && radio.value !== "mesures") radio.disabled = true;
        radio.addEventListener("change", function () {
            if (this.checked) { etat.precision = this.value; memoriserChoix(); afficher(); }
        });
    });
    if (!datesLisibles) etat.precision = "mesures";
    radios.forEach(function (radio) { radio.checked = radio.value === etat.precision; });

    selectMesure.addEventListener("change", function () {
        etat.mesure = +this.value;
        memoriserChoix();
        afficher();
    });
    etat.mesure = +selectMesure.value;

    afficher();

    // Redessiner le graphique quand sa largeur change
    var derniereLargeur = conteneurGraphique.clientWidth;
    function redimensionner() {
        if (conteneurGraphique.clientWidth !== derniereLargeur) {
            derniereLargeur = conteneurGraphique.clientWidth;
            dessinerGraphique();
        }
    }
    if ("ResizeObserver" in window) new ResizeObserver(redimensionner).observe(conteneurGraphique);
    else window.addEventListener("resize", redimensionner);
})();
