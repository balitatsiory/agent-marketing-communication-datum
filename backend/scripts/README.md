# scripts/

`seed_dev.py` — données fictives de développement.

Ces données ne sont **jamais** écrites dans une migration : une migration part
en production. Le script refuse de s'exécuter si `ENVIRONMENT` n'est pas `local`.

Les adresses utilisent le domaine `.test`, réservé par la norme et qui ne peut
pas exister sur Internet : aucun courriel d'essai ne peut atteindre une vraie
personne — ce qui compte dès que le module Newsletters enverra des lots.
