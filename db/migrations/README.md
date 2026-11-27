# DALILA reference contract deployment

## Canonical sources

The versioned CSV files in `db/reference/` and `db/corrections/` are the
canonical application references. MariaDB tables are mirrors used by SQL views
and other database consumers; they must not be edited independently.

- Governorate codes and labels: `db/reference/gouvernorats.csv` (24 records).
  Code 8 is Gafsa / `قفصة`, sourced from AFI `zones.code_zone=932001`
  (`gouv_id=8`, `GAFSA`, `قفصة`). This is explicitly recorded in the CSV.
- Regions and aliases: `regions.csv` and `corrections/alias_zones.csv`.
- Regional groups: `groupes_developpement_regional.csv`, sourced to the FIPA
  2024 map and checked against the 30 AFI zones marked regional.
- Historical and AFI-site prices: the corresponding CSVs preserve their source
  text. The application extracts the recorded read date from that provenance;
  it does not infer a date when none is present.
- Current zone tariff and regional-development indicator remain sourced from
  the AFI SQL views. Neither is a lot-specific published price or a regional
  group number.

## Existing database deployment

Do not run the full historical migration sequence or the explicit replacement
mode of `charger.py` against an existing database. `001_dalila_tables.sql`
contains table drops. The standard `charger.py` command performs upserts and
does not delete persisted rows or run migrations.

1. Back up the database and save `SHOW CREATE VIEW` for the public views.
2. Verify that `v_dalila_zones`, `v_dalila_lots`, `dalila_etape_statut`,
   `dalila_corrections`, and the other referenced AFI views/tables exist.
   Confirm the zone-key collations used by those views are compatible with the
   DALILA mirrors (`utf8mb4_general_ci`, as configured by Compose).
3. Apply only the reference-contract migration:

   ```powershell
   py -3.12 -m dalila.connaissances.migrer --migration 004_reference_contract.sql
   ```

   It creates missing DALILA reference tables, the evaluation-sample table,
   the least-privilege `dalila_ingest` account, and three versioned views:
   `v_pub_lots_v2`, `v_pub_lots_disponibles_v2`, and `v_pub_zones_v2`.
   Existing `v_pub_*` definitions and their grants are not replaced. The new
   views use explicit columns, expose source/date only for historical prices,
   and leave current tariffs and AFI-site prices distinct. Applying this
   migration does not seed reference rows or write AFI tables. MariaDB DDL is
   not transactional; validate on a disposable MariaDB 11.8 database and back
   up before deployment.
4. After reviewing the source CSVs and confirming the preflight, synchronize
   only the DALILA reference mirrors and the sourced lot-confirmation flags,
   using `dalila_ingest` rather than root:

   ```powershell
   py -3.12 -m dalila.connaissances.synchroniser_references
   ```

   This is an idempotent upsert; it does not delete rows. References removed
   from the CSVs remain in MariaDB until explicitly reconciled. The account
   can read only required public views/source tables and write DALILA mirrors;
   its only `DELETE` privilege is on the replaceable evaluation-sample table.
   It has no `DROP`, `CREATE`, `ALTER`, or AFI-table write privilege.
   Add `--surfaces` only when intentionally recomputing optional contour-derived
   zone surfaces. Invalid or absent KML contours are skipped with a warning;
   surface upserts do not delete a zone row when a contour is absent.
5. For a full corpus load, run `python -m dalila.connaissances.charger`. It
   uses `dalila_ingest`, upserts passages and sources, and does not remove rows
   absent from current inputs. It does not recompute contours unless `--surfaces`
   is explicitly passed. Run the ABox and vectorization steps separately.
6. Read back the view columns, group/source/date values, and lot counts before
   deploying application code.

The migration runner requires an explicit selection. `--all` additionally
requires `--allow-destructive-history` and is reserved for a new database. It
also refuses to run if DALILA tables/views or the `dalila_ro`, `dalila_rw`, or
`dalila_ingest` accounts already exist, preventing a mistaken rerun over an
initialized installation. Set a unique `DB_INGEST_PASSWORD` in `.env` before
applying migration 004; the migration creates the account only if absent and
does not rotate an existing account's password. Root is used for migrations,
the explicit replacement mode, and the separate AFI-copy maintenance tools;
normal loading, reference sync, sampling, ABox construction, and vectorization
use `dalila_ingest` or read-only `dalila_ro`.
Replacing DALILA mirror data additionally requires both
`--replace-dalila-data` and `--confirm-replace-dalila-data`. The Compose
`build` profile runs the non-destructive loader; the clearly named
`fresh-database` profile is the destructive bootstrap path and also requires
the explicit shell variable
`DALILA_CONFIRM_FRESH_DATABASE=I_ACCEPT_DESTRUCTIVE_FRESH_DATABASE`. Do not
select it for an existing database. The targeted migration is repeatable on the
expected schema. Existing public view definitions are not changed; to roll back
application adoption, point consumers back to the legacy views. The new v2
views, account, and nullable date columns may be left unused. Dropping them is
not part of the automatic rollback procedure.

No migration or synchronization has been executed against the current AFI
database. The SQL migration was executed twice on a disposable MariaDB 11.8
test schema; that fixture does not replace validation against a test copy of
the actual AFI schema and data.
