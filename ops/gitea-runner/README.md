# Gitea Docker Runner

This runner executes the repository's `ubuntu-latest` jobs in Gitea's official
Ubuntu job image. It is intentionally limited to one repository registration.

## Deploy

1. Create a repository-level registration token in:
   `Settings -> Actions -> Runners -> Create new Runner`.
2. Save only the token value in `registration-token` in this directory.
3. Start and verify the runner:

   ```bash
   docker compose up -d
   docker compose ps
   docker compose logs --tail=100 runner
   ```

The `data/` directory persists the runner registration. Both it and
`registration-token` are ignored by Git.

## Security boundary

The runner and its job containers receive the host Docker socket. Workflows can
therefore control the host Docker daemon. Register this runner only to trusted
repositories and do not run untrusted pull requests on it.
