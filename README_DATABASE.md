# Digimon database (Phase 1)

DigiTree keeps a local SQLite copy of every Digimon's **text** profile from
[Wikimon](https://wikimon.net): Level, Type, Attribute, Field, attack
techniques, Digimon Reference Book description, and Evolves From / Evolves To.
No images are downloaded in bulk.

The database lives at `%APPDATA%\DigiTree\wikimon_cache.db`.

## Importing

In the app: **Tools > Import Digimon Database…**, then **Start**. You can stop
and resume at any time.

From a terminal (same thing, with more options):

```
python -m digitree.wikimon.importer            # import / resume
python -m digitree.wikimon.importer --status   # how far along it is
python -m digitree.wikimon.importer --show Volcamon
python -m digitree.wikimon.importer --debug-page Volcamon   # parse one page, print result
python -m digitree.wikimon.importer --reparse  # re-run the parser on stored pages, offline
python -m digitree.wikimon.importer --refresh  # re-download everything
```

Requests go to Wikimon's API one at a time, 2 seconds apart (the
`wikimon_rate_limit` config value), 50 pages per request, with `maxlag` and
`Retry-After` respected. A full import is a few dozen requests.

## Using the data from code

```python
from digitree.db.cache import CacheDB
db = CacheDB()
db.search(level="Perfect", attribute="Data", field="Metal Empire")
db.search("greymon", evolves_from="Greymon")
db.get_evolves_to("Agumon"); db.get_attacks("Volcamon"); db.get_traits("Volcamon")
db.distinct_values("field")   # for filter dropdowns
```

## Tests

```
python -m pytest
```
