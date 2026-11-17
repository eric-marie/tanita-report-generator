/* ==========================================================================
   Graphique d'évolution — courbe SVG d'une mesure, sans librairie externe.
   Les données sont lues dans <script type="application/json" id="donnees-graphiques">,
   chaque conteneur .graphique indique sa série avec data-index.
   Survol : curseur vertical et bulle sur la pesée la plus proche.
   Clavier : le graphique prend le focus, flèches gauche/droite pour changer de pesée.
   ========================================================================== */
(function () {
    "use strict";

    var SVG = "http://www.w3.org/2000/svg";
    var HAUTEUR = 260;
    var MARGES = { haut: 16, droite: 64, bas: 32, gauche: 52 };
    var source = document.getElementById("donnees-graphiques");
    if (!source) return;
    var series = JSON.parse(source.textContent);

    // Créer un élément SVG avec ses attributs
    function element(nom, attributs, parent) {
        var e = document.createElementNS(SVG, nom);
        for (var cle in attributs) e.setAttribute(cle, attributs[cle]);
        if (parent) parent.appendChild(e);
        return e;
    }

    // Pas « rond » (1, 2, 2,5 ou 5 × 10^n) pour environ n graduations
    function pasRond(etendue, n) {
        var brut = etendue / n;
        var puissance = Math.pow(10, Math.floor(Math.log10(brut)));
        var r = brut / puissance;
        return (r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10) * puissance;
    }

    // Nombre de décimales nécessaires pour écrire un pas (0,5 -> 1 ; 2,5 -> 1 ; 10 -> 0)
    function decimalesDe(pas) {
        var d = 0;
        while (d < 6 && Math.abs(Math.round(pas * Math.pow(10, d)) - pas * Math.pow(10, d)) > 1e-9) d++;
        return d;
    }

    // Échelle verticale arrondie autour des valeurs (la courbe ne part pas de zéro).
    // La précision de la balance (ex. 0,1 kg) fixe le pas minimum, et l'étendue couvre au moins
    // 10 fois cette précision, pour ne pas faire d'une variation de 0,1 kg une chute vertigineuse.
    function echelleVerticale(valeurs, decimalesDonnees) {
        var min = Math.min.apply(null, valeurs), max = Math.max.apply(null, valeurs);
        var precision = Math.pow(10, -decimalesDonnees);
        var etendueMin = 10 * precision;
        if (max - min < etendueMin) {
            var centre = (min + max) / 2;
            min = centre - etendueMin / 2;
            max = centre + etendueMin / 2;
        }
        var pas = Math.max(pasRond(max - min, 4), precision);
        // Pas de graduation plus précise que la balance (ex. 0,25 kg -> 0,5 kg)
        if (decimalesDe(pas) > decimalesDonnees) pas *= 2;
        var bas = Math.floor(min / pas) * pas, haut = Math.ceil(max / pas) * pas;
        var decimales = decimalesDe(pas), graduations = [];
        for (var v = bas; v <= haut + pas / 2; v += pas) graduations.push(v);
        return { bas: bas, haut: haut, graduations: graduations, decimales: decimales };
    }

    function nombreFr(v, decimales) {
        return v.toFixed(decimales).replace(".", ",").replace("-", "−");
    }

    function deuxChiffres(n) { return (n < 10 ? "0" : "") + n; }

    // Libellé d'une date de l'axe horizontal (instant en ms, compté comme une heure UTC)
    function libelleDate(ms, etendue) {
        var d = new Date(ms);
        var jour = deuxChiffres(d.getUTCDate()) + "/" + deuxChiffres(d.getUTCMonth() + 1);
        if (etendue < 2 * 86400000) return jour + " " + deuxChiffres(d.getUTCHours()) + ":" + deuxChiffres(d.getUTCMinutes());
        return jour + "/" + String(d.getUTCFullYear()).slice(2);
    }

    function dessiner(conteneur) {
        var serie = series[+conteneur.dataset.index];
        var largeur = conteneur.clientWidth;
        if (!serie || !largeur || !serie.points.length) return;
        if (conteneur._largeur === largeur) return;
        conteneur._largeur = largeur;
        while (conteneur.firstChild) conteneur.removeChild(conteneur.firstChild);

        var points = serie.points;
        var temporel = points.every(function (p) { return p.t !== null; });
        var gauche = MARGES.gauche, droite = largeur - MARGES.droite;
        var haut = MARGES.haut, bas = HAUTEUR - MARGES.bas;

        // Échelle horizontale : selon le temps réel, sinon pesées régulièrement espacées
        var tMin = temporel ? points[0].t : 0;
        var tMax = temporel ? points[points.length - 1].t : points.length - 1;
        function x(p, i) {
            var t = temporel ? p.t : i;
            return tMax === tMin ? (gauche + droite) / 2 : gauche + (t - tMin) / (tMax - tMin) * (droite - gauche);
        }
        var ech = echelleVerticale(points.map(function (p) { return p.v; }), serie.decimales);
        function y(v) { return bas - (v - ech.bas) / (ech.haut - ech.bas) * (bas - haut); }

        var dernier = points[points.length - 1];
        var svg = element("svg", {
            width: largeur, height: HAUTEUR, viewBox: "0 0 " + largeur + " " + HAUTEUR,
            role: "img", tabindex: "0",
            "aria-label": "Évolution de " + serie.nom + " : " + points.length + " pesée(s), dernière valeur " +
                dernier.texte + (serie.unite ? " " + serie.unite : "") + " le " + dernier.date +
                ". Flèches gauche et droite pour parcourir les pesées."
        }, conteneur);

        // Grille horizontale et graduations verticales
        ech.graduations.forEach(function (v) {
            element("line", { x1: gauche, x2: droite, y1: y(v), y2: y(v), "class": "g-grille" }, svg);
            element("text", { x: gauche - 10, y: y(v), dy: "0.32em", "text-anchor": "end", "class": "g-texte" }, svg)
                .textContent = nombreFr(v, ech.decimales);
        });

        // Graduations horizontales : dates réparties sur la période, sinon numéro de pesée
        if (temporel && tMax > tMin) {
            var nb = Math.max(2, Math.min(6, Math.floor((droite - gauche) / 110) + 1));
            for (var k = 0; k < nb; k++) {
                var t = tMin + (tMax - tMin) * k / (nb - 1);
                element("text", {
                    x: gauche + (t - tMin) / (tMax - tMin) * (droite - gauche), y: bas + 20,
                    "text-anchor": k === 0 ? "start" : k === nb - 1 ? "end" : "middle", "class": "g-texte"
                }, svg).textContent = libelleDate(t, tMax - tMin);
            }
        } else {
            var etiquettes = points.length === 1 ? [0] : [0, points.length - 1];
            etiquettes.forEach(function (i) {
                element("text", {
                    x: x(points[i], i), y: bas + 20, "class": "g-texte",
                    "text-anchor": points.length === 1 ? "middle" : i === 0 ? "start" : "end"
                }, svg).textContent = points[i].date;
            });
        }

        // Aire légère sous la courbe, puis la courbe
        var trace = points.map(function (p, i) { return x(p, i).toFixed(1) + "," + y(p.v).toFixed(1); });
        if (points.length > 1) {
            element("path", {
                d: "M" + x(points[0], 0).toFixed(1) + "," + bas + "L" + trace.join("L") + "L" + x(dernier, points.length - 1).toFixed(1) + "," + bas + "Z",
                "class": "g-aire"
            }, svg);
            element("path", { d: "M" + trace.join("L"), "class": "g-ligne" }, svg);
        }
        element("line", { x1: gauche, x2: droite, y1: bas, y2: bas, "class": "g-axe" }, svg);

        // Points (masqués au-delà de 60 pesées, sauf le dernier)
        points.forEach(function (p, i) {
            if (points.length <= 60 || i === points.length - 1) {
                element("circle", { cx: x(p, i), cy: y(p.v), r: 4, "class": "g-point" }, svg);
            }
        });

        // Valeur de la dernière pesée, au bout de la courbe
        element("text", { x: x(dernier, points.length - 1) + 10, y: y(dernier.v), dy: "0.32em", "class": "g-valeur" }, svg)
            .textContent = dernier.texte;

        // Survol : curseur vertical, point mis en avant et bulle d'information
        var curseur = element("line", { y1: haut, y2: bas, "class": "g-curseur", visibility: "hidden" }, svg);
        var repere = element("circle", { r: 6, "class": "g-point g-repere", visibility: "hidden" }, svg);
        var bulle = document.createElement("div");
        bulle.className = "infobulle";
        bulle.hidden = true;
        var bulleValeur = document.createElement("strong");
        var bulleDate = document.createElement("span");
        bulle.appendChild(bulleValeur);
        bulle.appendChild(bulleDate);
        conteneur.appendChild(bulle);

        var actif = -1;
        function montrer(i) {
            actif = i;
            var p = points[i], px = x(p, i), py = y(p.v);
            curseur.setAttribute("x1", px);
            curseur.setAttribute("x2", px);
            curseur.setAttribute("visibility", "visible");
            repere.setAttribute("cx", px);
            repere.setAttribute("cy", py);
            repere.setAttribute("visibility", "visible");
            bulleValeur.textContent = p.texte + (serie.unite ? " " + serie.unite : "");
            bulleDate.textContent = p.date + " à " + p.heure;
            bulle.hidden = false;
            var gauchePx = Math.min(Math.max(px - bulle.offsetWidth / 2, 0), largeur - bulle.offsetWidth);
            bulle.style.left = gauchePx + "px";
            bulle.style.top = Math.max(py - bulle.offsetHeight - 14, 0) + "px";
        }
        function cacher() {
            actif = -1;
            curseur.setAttribute("visibility", "hidden");
            repere.setAttribute("visibility", "hidden");
            bulle.hidden = true;
        }
        function plusProche(px) {
            var meilleur = 0, ecart = Infinity;
            points.forEach(function (p, i) {
                var d = Math.abs(x(p, i) - px);
                if (d < ecart) { ecart = d; meilleur = i; }
            });
            return meilleur;
        }

        // Zone de survol couvrant toute la surface du graphique (plus grande que les points)
        var zone = element("rect", { x: 0, y: 0, width: largeur, height: HAUTEUR, fill: "transparent" }, svg);
        zone.addEventListener("pointermove", function (e) {
            var cadre = svg.getBoundingClientRect();
            montrer(plusProche(e.clientX - cadre.left));
        });
        zone.addEventListener("pointerleave", cacher);
        svg.addEventListener("focus", function () { montrer(points.length - 1); });
        svg.addEventListener("blur", cacher);
        svg.addEventListener("keydown", function (e) {
            if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                var i = actif < 0 ? points.length - 1 : actif + (e.key === "ArrowRight" ? 1 : -1);
                montrer(Math.min(Math.max(i, 0), points.length - 1));
            } else if (e.key === "Escape") {
                cacher();
            }
        });
    }

    // Dessiner les graphiques visibles : au chargement, à chaque changement de mesure
    // (window.dessinerGraphiques, appelée par la page) et quand la largeur change
    var conteneurs = document.querySelectorAll(".graphique[data-index]");
    function toutDessiner() { conteneurs.forEach(dessiner); }
    window.dessinerGraphiques = toutDessiner;
    toutDessiner();
    if ("ResizeObserver" in window) {
        var observateur = new ResizeObserver(function (entrees) {
            entrees.forEach(function (entree) { dessiner(entree.target); });
        });
        conteneurs.forEach(function (c) { observateur.observe(c); });
    } else {
        window.addEventListener("resize", toutDessiner);
    }
})();
