from datetime import datetime, timezone

from nexis.platform.discovery import folded


class Catalog:
    def __init__(self, db):
        self.db = db

    def update(self, apps):
        with self.db.lock, self.db.connection:
            self.db.connection.execute("UPDATE app_catalog SET available=0")
            for app in apps:
                self.db.connection.execute(
                    "INSERT OR REPLACE INTO app_catalog VALUES (?,?,?,?,?,?)",
                    tuple(
                        app[key] for key in ("id", "name", "target", "kind", "source", "available")
                    ),
                )
        self.db.set_setting("catalog_scanned_at", datetime.now(timezone.utc).isoformat())

    def rows(self, include_hidden=False):
        rows = self.db.rows(
            "SELECT c.*, COALESCE(p.alias,'') AS alias, COALESCE(p.hidden,0) AS hidden, COALESCE(p.removed,0) AS removed FROM app_catalog c LEFT JOIN app_preferences p ON c.id=p.id ORDER BY c.name"
        )
        return [r for r in rows if not r["removed"] and (include_hidden or not r["hidden"])]

    def preferences(self, identifier, alias="", hidden=False, removed=False):
        alias = alias.strip()
        if len(alias) > 100 or any(not (c.isalnum() or c in " ._-()") for c in alias):
            raise ValueError(
                "Use an alias of up to 100 letters, digits, spaces, dots, dashes or parentheses."
            )
        self.db.execute(
            "INSERT OR REPLACE INTO app_preferences VALUES (?,?,?,?)",
            (identifier, alias, int(hidden), int(removed)),
        )

    def matches(self, text):
        query = folded(text)
        rows = [r for r in self.rows() if r["available"]]
        exact = [r for r in rows if query in {folded(r["name"]), folded(r["alias"])}]
        if exact:
            return exact
        return [r for r in rows if query and query in folded(r["name"]).split()]
