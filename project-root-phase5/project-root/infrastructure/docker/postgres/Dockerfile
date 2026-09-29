# The pgvector/pgvector image only ships pgvector; the postgis/postgis
# image only ships PostGIS. We need both extensions in one Postgres
# instance, so build a small combined image on top of the official
# PostGIS image (which already includes the Postgres apt repo needed
# to install postgresql-16-pgvector).
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
