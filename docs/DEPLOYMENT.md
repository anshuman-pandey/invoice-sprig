# Persistent local hosting and recovery

Run `python3 scripts/setup.py` once to create a private `.env` containing `SPRIG_OWNER_KEY`. It refuses to overwrite existing configuration. Read the key locally to unlock the workspace; do not share or commit it.

```sh
python3 scripts/setup.py
docker compose up --build -d
```

Open http://127.0.0.1:8126. The service uses Waitress, UID 10001, a read-only application filesystem and a persistent `/data` volume. Keep that volume: `docker compose down -v` deletes invoices and numbering history. Store the owner key separately from backups. A new empty database starts numbering from one; it must not replace an existing business ledger casually.

## Backup

Stop writes before copying the database:

```sh
docker compose stop
mkdir -m 700 backup
container=$(docker compose ps -aq invoice-sprig)
docker cp "$container:/data/invoices.sqlite3" backup/source.sqlite3
chmod 600 backup/source.sqlite3
python3 scripts/backup.py backup/source.sqlite3 backup/invoices.sqlite3
docker compose start
```

The helper uses SQLite's backup API, checks integrity and creates private mode-0600 output without overwriting a destination. The database includes immutable financial bodies, manual status history, the numbering sequence and issuance retry keys. JSON exports alone are not a restore mechanism.

Restore only while stopped into a **new empty volume**, at `/data/invoices.sqlite3`. Set the file owner/group to 10001 and permissions to 0600; `/data` must also be writable by that user. Use the original owner key. Compare invoice bodies, status history and PDF content before accepting writes. Keep the original volume until the restored service is verified. An old backup may omit newer invoices: reconcile those records before issuing again to avoid reusing historical numbers.

## Reproduce acceptance

```sh
docker build -t invoice-sprig:acceptance .
python3 scripts/container_acceptance.py
```

The check uses uniquely named disposable containers and volumes. It verifies restart, backup and clean-volume restore, PDF text, status history, repeated-request deduplication, the next invoice number and new status writes. Only its own test resources are removed.

For an administrator-approved private CA, pass `--secret id=pip_ca,src=/path/to/approved-ca.pem` to `docker build`. The CA is mounted temporarily during package installation. TLS verification stays enabled; no CA secret is copied into the image.

Public hosting is not configured or accepted. Remote access needs trusted HTTPS, request limits, a host firewall and private owner credentials. There are no public invoice links, customer accounts or team roles. Anyone holding the owner key can read invoices and change their manual status.
