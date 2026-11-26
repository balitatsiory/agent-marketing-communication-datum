# scripts/

`import_logos_organisations.py` — reprise des logos d'organisations (partenaires,
appartenances) comme médias de référence de nature « logo » :

    python -m scripts.import_logos_organisations organisations.json

Les logos ne sont rapatriés que depuis datumacademy.com et rangés sous
`organisations/{code}/logo-{sha12}.{ext}`. Relancer le script ne crée pas de
doublon et ne défait ni un archivage ni un retrait de référence.

`seed_dev.py` — données fictives de développement.

Ces données ne sont **jamais** écrites dans une migration : une migration part
en production. Le script refuse de s'exécuter si `ENVIRONMENT` n'est pas `local`.

Les adresses utilisent le domaine `.test`, réservé par la norme et qui ne peut
pas exister sur Internet : aucun courriel d'essai ne peut atteindre une vraie
personne — ce qui compte dès que le module Newsletters enverra des lots.
