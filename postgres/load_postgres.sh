#!/usr/bin/env bash
# Load data/csv/*.csv into the Brindle Fiber Postgres source. Optional AWS track.
#
# Needs the standard libpq variables: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE.
#   set -a; source aws/.brindle-pg-credentials; set +a
#   postgres/load_postgres.sh
#
# The \copy option null '\N' is what keeps blanks as empty strings. In Postgres
# CSV mode an unquoted empty field is NULL by default. With null '\N', only a
# literal \N is NULL and ,, loads as ''.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
csv="$here/../data/csv"

psql -v ON_ERROR_STOP=1 -q -f "$here/ddl.sql"
for t in markets hubsites service_areas pon_zones locations_passed subscribers; do
  psql -v ON_ERROR_STOP=1 -q -c "\copy brindle_src.$t from '$csv/$t.csv' with (format csv, header true, null '\N')"
done

psql -v ON_ERROR_STOP=1 -At <<'SQL'
select 'markets '          || count(*) from brindle_src.markets
union all select 'hubsites '         || count(*) from brindle_src.hubsites
union all select 'service_areas '    || count(*) from brindle_src.service_areas
union all select 'pon_zones '        || count(*) from brindle_src.pon_zones
union all select 'locations_passed ' || count(*) from brindle_src.locations_passed
union all select 'subscribers '      || count(*) from brindle_src.subscribers
union all select 'blank in_service_date ' || count(*) from brindle_src.locations_passed where in_service_date = '';
SQL
