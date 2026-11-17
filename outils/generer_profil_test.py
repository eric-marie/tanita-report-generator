"""Générer un profil de test fictif au format de la carte SD Tanita BC-601.

Écrit SYSTEM/PROFn.CSV et DATA/DATAn.CSV dans le dossier TANITA du projet (créé s'il
n'existe pas), avec une pesée par matin entre deux dates, et donne éventuellement un nom
au profil dans profils.json. Utile pour essayer le rapport sans balance, ou pour avoir
un historique de plusieurs semaines.

Le profil simule une perte (ou une prise) de poids régulière, répartie à environ 70 % en
graisse et 30 % en masse maigre, avec un peu de bruit quotidien (hydratation). Les autres
mesures (eau, graisse viscérale, métabolisme, âge métabolique, segments) en découlent de
façon plausible. Les valeurs sont fictives : elles ne reproduisent pas les calculs de la balance.

Exemples (depuis le dossier du projet) :
    python outils/generer_profil_test.py
    python outils/generer_profil_test.py --profil 3 --nom Test --sexe femme --poids 75 --perte-semaine 0.5
    python outils/generer_profil_test.py --debut 01/01/2026 --fin 31/03/2026 --forcer

Par sécurité, le script refuse d'écraser un profil qui contient déjà des données, sauf avec --forcer.
"""
import argparse
import json
import os
import random
import sys
from datetime import date, datetime, timedelta

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPHV1 = os.path.join(RACINE, "TANITA", "GRAPHV1")
PROFILS_JSON = os.path.join(RACINE, "profils.json")

ENTETE_DATA = "{0,16,~0,2,~1,2,~2,3,~3,4,"
ENTETE_PROF = "{0,16,~1,2,~3,4,"

# Apport calorique = métabolisme de base × facteur d'activité (guide Tanita, source OMS)
FACTEURS_ACTIVITE = {"homme": {1: 1.55, 2: 1.78, 3: 2.10}, "femme": {1: 1.56, 2: 1.64, 3: 1.82}}


def date_fr(texte):
    return datetime.strptime(texte, "%d/%m/%Y").date()


def lire_arguments():
    p = argparse.ArgumentParser(description="Générer un profil de test fictif au format de la carte SD Tanita BC-601.")
    p.add_argument("--profil", type=int, default=2, choices=[1, 2, 3, 4], help="numéro du profil sur la balance (défaut : 2)")
    p.add_argument("--nom", default="Test", help="nom du profil dans profils.json (défaut : Test ; vide pour ne rien écrire)")
    p.add_argument("--sexe", default="homme", choices=["homme", "femme"], help="défaut : homme")
    p.add_argument("--naissance", type=date_fr, default=date(1986, 3, 15), help="date de naissance jj/mm/aaaa (défaut : 15/03/1986)")
    p.add_argument("--taille", type=float, default=180.0, help="taille en cm (défaut : 180)")
    p.add_argument("--activite", type=int, default=2, choices=[1, 2, 3], help="niveau d'activité (défaut : 2)")
    p.add_argument("--poids", type=float, default=100.0, help="poids de départ en kg (défaut : 100)")
    p.add_argument("--graisse", type=float, help="graisse corporelle de départ en %% (défaut : 28,5 pour un homme, 38 pour une femme)")
    p.add_argument("--perte-semaine", type=float, default=2.0, help="perte de poids par semaine en kg, négative pour une prise (défaut : 2)")
    p.add_argument("--debut", type=date_fr, default=date(2026, 9, 1), help="première pesée jj/mm/aaaa (défaut : 01/09/2026)")
    p.add_argument("--fin", type=date_fr, default=date.today(), help="dernière pesée jj/mm/aaaa (défaut : aujourd'hui)")
    p.add_argument("--graine", type=int, default=20260901, help="graine du hasard, pour obtenir les mêmes valeurs à chaque fois")
    p.add_argument("--forcer", action="store_true", help="écraser le profil même s'il contient déjà des données")
    args = p.parse_args()
    if args.fin < args.debut:
        p.error("la date de fin est antérieure à la date de début")
    if args.graisse is None:
        args.graisse = 28.5 if args.sexe == "homme" else 38.0
    return args


def avec_somme(corps):
    """Ajoute la somme de contrôle de la balance : somme des octets jusqu'à la virgule finale, modulo 256."""
    return corps + "CS,%02X" % (sum(corps.encode("ascii")) % 256)


def ligne(paires):
    return ",".join(f"{code},{valeur}" for code, valeur in paires) + ","


def age_le(naissance, jour):
    return jour.year - naissance.year - ((jour.month, jour.day) < (naissance.month, naissance.day))


def generer_pesees(a):
    random.seed(a.graine)
    sexe_code = 1 if a.sexe == "homme" else 2
    femme = a.sexe == "femme"
    nb_jours = (a.fin - a.debut).days
    grasse_0 = a.poids * a.graisse / 100
    maigre_0 = a.poids - grasse_0
    os_0 = maigre_0 * (0.052 if femme else 0.0517)

    lignes = []
    for i in range(nb_jours + 1):
        jour = a.debut + timedelta(days=i)
        age = age_le(a.naissance, jour)
        # Perte régulière qui ralentit un peu avec le temps, plus le bruit d'hydratation du jour
        perte = a.perte_semaine / 7 * i * (1 - 0.08 * i / max(nb_jours, 1))
        grasse = max(2.0, grasse_0 - 0.70 * perte + random.gauss(0, 0.25))
        maigre = maigre_0 - 0.30 * perte + random.gauss(0, 0.35)
        poids = grasse + maigre
        graisse = grasse / poids * 100
        os_ = os_0 * maigre / maigre_0 + random.gauss(0, 0.03)
        muscle = maigre - os_

        moment = datetime.combine(jour, datetime.min.time()) + timedelta(hours=7, minutes=random.randint(0, 45), seconds=random.randint(0, 59))
        metabolisme = 370 + 21.6 * maigre                       # formule de Katch-McArdle
        apport = metabolisme * FACTEURS_ACTIVITE[a.sexe][a.activite]
        eau = maigre * 0.73 / poids * 100
        viscerale = max(1, round(grasse * (0.30 if femme else 0.42) + random.gauss(0, 0.3)))
        age_metabolique = round(min(90, max(12, age + (graisse - (28 if femme else 18)) * 1.3 + random.gauss(0, 0.6))))

        def segment(facteur):
            return f"{max(1.0, graisse * facteur + random.gauss(0, 0.3)):.1f}"

        def muscles(part):
            return f"{muscle * part + random.gauss(0, 0.05):.1f}"

        poids_txt = f"{poids:.1f}"
        lignes.append(avec_somme(ENTETE_DATA + ligne([
            ("MO", '"BC-601"'), ("DT", f'"{jour:%d/%m/%Y}"'), ("Ti", f'"{moment:%H:%M:%S}"'),
            ("Bt", 0), ("GE", sexe_code), ("AG", age), ("Hm", f"{a.taille:.1f}"), ("AL", a.activite),
            ("Wk", poids_txt), ("MI", f"{float(poids_txt) / (a.taille / 100) ** 2:.1f}"),
            ("FW", f"{graisse:.1f}"),
            ("Fr", segment(0.92)), ("Fl", segment(0.95)), ("FR", segment(0.78 if not femme else 1.05)),
            ("FL", segment(0.80 if not femme else 1.07)), ("FT", segment(1.18 if not femme else 0.95)),
            ("mW", f"{muscle:.1f}"),
            ("mr", muscles(0.058)), ("ml", muscles(0.056)), ("mR", muscles(0.178)), ("mL", muscles(0.174)), ("mT", muscles(0.534)),
            ("bW", f"{os_:.1f}"), ("IF", viscerale), ("rD", f"{apport:.0f}"), ("rA", age_metabolique), ("ww", f"{eau:.1f}"),
        ])))
    profil = avec_somme(ENTETE_PROF + ligne([("MO", '"BC-601"'), ("DB", f'"{a.naissance:%d/%m/%Y}"'), ("Bt", 0),
                                             ("GE", sexe_code), ("Hm", f"{a.taille:.1f}"), ("AL", a.activite)]))
    return profil, lignes


def contient_des_donnees(chemin):
    if not os.path.exists(chemin):
        return False
    with open(chemin, "rb") as f:
        return bool(f.read().strip())


def ecrire(chemin, lignes):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    if os.path.exists(chemin):
        os.chmod(chemin, 0o666)  # les fichiers copiés depuis la carte peuvent être en lecture seule
    with open(chemin, "w", encoding="ascii", newline="") as f:
        f.write("".join(l + "\r\n" for l in lignes))


def nommer_profil(numero, nom):
    noms = {}
    if os.path.exists(PROFILS_JSON):
        with open(PROFILS_JSON, encoding="utf-8") as f:
            noms = json.load(f)
    noms[str(numero)] = nom
    with open(PROFILS_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(noms.items())), f, ensure_ascii=False, indent=4)
        f.write("\n")


def main():
    a = lire_arguments()
    chemin_prof = os.path.join(GRAPHV1, "SYSTEM", f"PROF{a.profil}.CSV")
    chemin_data = os.path.join(GRAPHV1, "DATA", f"DATA{a.profil}.CSV")

    if not a.forcer and (contient_des_donnees(chemin_prof) or contient_des_donnees(chemin_data)):
        raise SystemExit(f"Le profil {a.profil} contient déjà des données ({os.path.relpath(chemin_data, RACINE)}). "
                         "Choisissez un autre numéro avec --profil, ou utilisez --forcer pour l'écraser.")

    profil, pesees = generer_pesees(a)
    ecrire(chemin_prof, [profil])
    ecrire(chemin_data, pesees)
    if a.nom:
        nommer_profil(a.profil, a.nom)

    premiere, derniere = pesees[0], pesees[-1]
    poids = lambda l: l.split(",Wk,")[1].split(",")[0].replace(".", ",")
    print(f"Profil {a.profil}{' « ' + a.nom + ' »' if a.nom else ''} : {len(pesees)} pesées du {a.debut:%d/%m/%Y} au {a.fin:%d/%m/%Y}, "
          f"de {poids(premiere)} à {poids(derniere)} kg.")
    print("Lancez ensuite : python generate_report.py")
    print("Attention : ne recopiez pas ce dossier TANITA sur la carte SD de la balance.")


if __name__ == "__main__":
    # Messages en UTF-8 (accents corrects dans Git Bash, comme generate_report.py)
    if not os.environ.get("PYTHONIOENCODING") and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    main()
