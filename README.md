# n8n - Initialisation

## Démarrage (first time)

```bash
docker compose up -d --build
```

Accéder à n8n : http://localhost:5678

## Après un redémarrage du PC

Le service a `restart: unless-stopped` dans `docker-compose.yml`, donc le conteneur redémarre automatiquement avec Docker — pas besoin de relancer `docker compose up -d` à chaque fois.

1. Lancer Docker Desktop (s'il ne démarre pas tout seul avec Windows).
2. Vérifier que le conteneur tourne :
   ```bash
   docker compose ps
   ```
3. Ouvrir le navigateur sur http://localhost:5678

Astuce : dans Docker Desktop → Settings → General, activer "Start Docker Desktop when you log in" pour que tout redémarre automatiquement au démarrage de Windows.

## Notes

- L'image de base doit être `node:20-bullseye` (ou plus récent) — n8n récent nécessite Node ≥ 20. `node:18-bullseye` provoque des erreurs au démarrage ("File is not defined", "command start not found").
- L'utilisateur `node` existe déjà dans l'image de base Node — pas besoin de `useradd`.
