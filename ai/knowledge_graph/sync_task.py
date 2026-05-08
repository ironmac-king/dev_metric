"""
Graph Sync Task
Synchronizes data from PostgreSQL to Neo4j
"""

import os
import time
from typing import List, Dict, Optional
from datetime import datetime


class GraphSyncTask:
    """Synchronize PostgreSQL data to Neo4j"""

    def __init__(
        self,
        pg_config: Dict = None,
        neo4j_loader=None
    ):
        """
        Initialize sync task

        Args:
            pg_config: PostgreSQL config dict (host, port, user, password, database)
            neo4j_loader: Neo4jLoader instance
        """
        self.pg_config = pg_config or self._get_pg_config()
        self._pg_conn = None
        self.neo4j = neo4j_loader

    def _get_pg_config(self) -> Dict:
        """Get PostgreSQL config from environment"""
        return {
            "host": os.getenv("PG_HOST", "localhost"),
            "port": os.getenv("PG_PORT", "5432"),
            "user": os.getenv("PG_USER", "postgres"),
            "password": os.getenv("PG_PASSWORD", ""),
            "database": os.getenv("PG_DATABASE", "dev_metric")
        }

    def _get_pg_connection(self):
        """Get PostgreSQL connection"""
        if self._pg_conn is None:
            import psycopg2
            self._pg_conn = psycopg2.connect(
                host=self.pg_config["host"],
                port=self.pg_config["port"],
                user=self.pg_config["user"],
                password=self.pg_config["password"],
                database=self.pg_config["database"]
            )
        return self._pg_conn

    def _get_neo4j_loader(self):
        """Get or create Neo4j loader"""
        if self.neo4j is None:
            from .neo4j_loader import Neo4jLoader
            self.neo4j = Neo4jLoader()
        return self.neo4j

    def load_metrics_from_pg(self) -> List[Dict]:
        """Load metrics from PostgreSQL"""
        conn = self._get_pg_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT metric_code, name, name_en, domain,
                   category_1, category_2, category_3,
                   business_definition, business_rule
            FROM metrics
            WHERE status = '在用'
        """)

        columns = [desc[0] for desc in cursor.description]
        metrics = []

        for row in cursor.fetchall():
            metric = dict(zip(columns, row))
            metrics.append(metric)

        cursor.close()
        print(f"[Sync] Loaded {len(metrics)} metrics from PostgreSQL")
        return metrics

    def load_relations_from_pg(self) -> List[Dict]:
        """Load relations from PostgreSQL"""
        conn = self._get_pg_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT source_metric_code, target_metric_code, relation_type,
                   weight, description
            FROM metric_relations
            WHERE status = 1
        """)

        columns = [desc[0] for desc in cursor.description]
        relations = []

        for row in cursor.fetchall():
            relation = dict(zip(columns, row))
            relations.append(relation)

        cursor.close()
        print(f"[Sync] Loaded {len(relations)} relations from PostgreSQL")
        return relations

    def get_metric_name_map(self) -> Dict[str, str]:
        """Get mapping from metric name to metric code"""
        conn = self._get_pg_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name, metric_code FROM metrics WHERE status = '在用'")

        name_map = {}
        for row in cursor.fetchall():
            name_map[row[0]] = row[1]

        cursor.close()
        return name_map

    def full_sync(self, clear_existing: bool = True) -> Dict:
        """
        Perform full sync from PostgreSQL to Neo4j

        Args:
            clear_existing: Whether to clear existing Neo4j data first

        Returns:
            Sync result dictionary with counts
        """
        start_time = time.time()
        neo4j = self._get_neo4j_loader()

        print(f"[Sync] Starting full sync at {datetime.now()}")

        # Test Neo4j connection
        if not neo4j.test_connection():
            raise RuntimeError("Cannot connect to Neo4j")

        # Clear existing data if requested
        if clear_existing:
            neo4j.clear_all()

        # Load and sync metrics
        metrics = self.load_metrics_from_pg()
        metric_count = neo4j.load_metrics(metrics)

        # Load and sync relations
        relations = self.load_relations_from_pg()
        relation_count = neo4j.load_relations(relations)

        elapsed = time.time() - start_time
        result = {
            "metrics_loaded": metric_count,
            "relations_loaded": relation_count,
            "elapsed_seconds": elapsed
        }

        print(f"[Sync] Full sync completed in {elapsed:.2f}s: "
              f"{metric_count} metrics, {relation_count} relations")

        return result

    def incremental_sync(self) -> Dict:
        """
        Perform incremental sync (only new/changed data)

        Returns:
            Sync result dictionary
        """
        # TODO: Implement incremental sync based on updated_at timestamp
        print("[Sync] Incremental sync not yet implemented, falling back to full sync")
        return self.full_sync(clear_existing=False)

    def sync_single_metric(self, metric_code: str) -> int:
        """
        Sync a single metric and its relations to Neo4j

        Args:
            metric_code: Metric code to sync

        Returns:
            Number of relations synced
        """
        neo4j = self._get_neo4j_loader()

        # Get metric data
        conn = self._get_pg_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT metric_code, name, name_en, domain,
                   category_1, category_2, category_3
            FROM metrics
            WHERE metric_code = %s AND status = '在用'
        """, (metric_code,))

        row = cursor.fetchone()
        if not row:
            cursor.close()
            return 0

        metric = {
            "metric_code": row[0],
            "name": row[1],
            "name_en": row[2] or "",
            "domain": row[3] or "",
            "category_1": row[4] or "",
            "category_2": row[5] or "",
            "category_3": row[6] or ""
        }

        # Load metric
        neo4j.load_metrics([metric])

        # Get and load relations
        cursor.execute("""
            SELECT source_metric_code, target_metric_code, relation_type,
                   weight, description
            FROM metric_relations
            WHERE (source_metric_code = %s OR target_metric_code = %s)
              AND status = 1
        """, (metric_code, metric_code))

        columns = [desc[0] for desc in cursor.description]
        relations = []

        for row in cursor.fetchall():
            relation = dict(zip(columns, row))
            relations.append(relation)

        cursor.close()

        relation_count = neo4j.load_relations(relations)
        print(f"[Sync] Synced metric {metric_code}: 1 metric, {relation_count} relations")

        return relation_count

    def close(self):
        """Close connections"""
        if self._pg_conn:
            self._pg_conn.close()
            self._pg_conn = None
        if self.neo4j:
            self.neo4j.close()
            self.neo4j = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Test sync
    with GraphSyncTask() as task:
        result = task.full_sync()
        print(f"Result: {result}")
