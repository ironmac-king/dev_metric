"""
Neo4j Graph Database Loader
Loads metric nodes and relationships into Neo4j
"""

import os
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class MetricNode:
    """Metric node data"""
    metric_code: str
    name: str
    name_en: str = ""
    domain: str = ""
    category_1: str = ""
    category_2: str = ""
    category_3: str = ""


@dataclass
class MetricRelation:
    """Metric relation edge data"""
    source_metric_code: str
    target_metric_code: str
    relation_type: str  # DERIVES_FROM, IMPACTS, CORRELATES_WITH
    weight: float = 1.0
    description: str = ""


class Neo4jLoader:
    """Neo4j Graph Database Loader"""

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None
    ):
        """
        Initialize Neo4j connection

        Args:
            uri: Bolt URI (default: bolt://localhost:7687)
            user: Neo4j username (default: neo4j)
            password: Neo4j password (default: from env NEO4J_PASSWORD)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "dev_metric123")
        self._driver = None

    def _get_driver(self):
        """Lazy load the Neo4j driver"""
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
        return self._driver

    def close(self):
        """Close the Neo4j driver"""
        if self._driver:
            self._driver.close()
            self._driver = None

    def test_connection(self) -> bool:
        """Test Neo4j connection"""
        try:
            with self._get_driver().session() as session:
                result = session.run("RETURN 1 AS test")
                return result.single()["test"] == 1
        except Exception as e:
            print(f"[Neo4j] Connection failed: {e}")
            return False

    def load_metrics(self, metrics: List[Dict]) -> int:
        """
        Load metric nodes into Neo4j

        Args:
            metrics: List of metric dictionaries with keys:
                     metric_code, name, name_en, domain, category_1, category_2, category_3

        Returns:
            Number of metrics loaded
        """
        if not metrics:
            return 0

        loaded = 0
        with self._get_driver().session() as session:
            for m in metrics:
                session.run("""
                    MERGE (n:Metric {metric_code: $code})
                    SET n.name = $name,
                        n.name_en = $name_en,
                        n.domain = $domain,
                        n.category_1 = $cat1,
                        n.category_2 = $cat2,
                        n.category_3 = $cat3
                """,
                    code=m['metric_code'],
                    name=m.get('name', ''),
                    name_en=m.get('name_en', ''),
                    domain=m.get('domain', ''),
                    cat1=m.get('category_1', ''),
                    cat2=m.get('category_2', ''),
                    cat3=m.get('category_3', '')
                )
                loaded += 1

        print(f"[Neo4j] Loaded {loaded} metric nodes")
        return loaded

    def load_relations(self, relations: List[Dict]) -> int:
        """
        Load metric relations into Neo4j

        Args:
            relations: List of relation dictionaries with keys:
                       source_metric_code, target_metric_code, relation_type, weight, description

        Returns:
            Number of relations loaded
        """
        if not relations:
            return 0

        loaded = 0
        with self._get_driver().session() as session:
            for r in relations:
                rel_type = r['relation_type'].upper()
                # Map relation type to Neo4j relationship type
                if rel_type == "DERIVES_FROM":
                    rel_cypher = "DERIVES_FROM"
                elif rel_type == "IMPACTS":
                    rel_cypher = "IMPACTS"
                elif rel_type == "CORRELATES_WITH":
                    rel_cypher = "CORRELATES_WITH"
                else:
                    rel_cypher = rel_type

                session.run(f"""
                    MATCH (s:Metric {{metric_code: $source}})
                    MATCH (t:Metric {{metric_code: $target}})
                    MERGE (s)-[r:{rel_cypher}]->(t)
                    SET r.weight = $weight,
                        r.description = $desc
                """,
                    source=r['source_metric_code'],
                    target=r['target_metric_code'],
                    weight=float(r.get('weight', 1.0)),
                    desc=r.get('description', '')
                )
                loaded += 1

        print(f"[Neo4j] Loaded {loaded} relations")
        return loaded

    def clear_all(self):
        """Clear all nodes and relationships in the graph"""
        with self._get_driver().session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("[Neo4j] Cleared all nodes and relationships")

    def get_node_count(self) -> int:
        """Get total number of Metric nodes"""
        with self._get_driver().session() as session:
            result = session.run("MATCH (n:Metric) RETURN count(n) as count")
            return result.single()["count"]

    def get_relation_count(self) -> int:
        """Get total number of relationships"""
        with self._get_driver().session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            return result.single()["count"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Test connection
    with Neo4jLoader() as loader:
        if loader.test_connection():
            print("[Neo4j] Connection successful!")
        else:
            print("[Neo4j] Connection failed!")
