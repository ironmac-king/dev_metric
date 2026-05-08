"""
Graph Query Interface
Query the knowledge graph for metric relationships
"""

import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CausalChain:
    """Represents a causal chain between two metrics"""
    source: str
    target: str
    chain: List[str]  # List of metric codes in the chain
    total_hops: int


@dataclass
class RelatedMetric:
    """Represents a related metric"""
    metric_code: str
    name: str
    relation_type: str
    weight: float
    distance: int  # Number of hops


class GraphQuery:
    """Query interface for the metric knowledge graph"""

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None
    ):
        """Initialize graph query interface"""
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
        """Close the driver"""
        if self._driver:
            self._driver.close()
            self._driver = None

    def find_related_metrics(
        self,
        metric_code: str,
        depth: int = 2,
        relation_type: str = None
    ) -> List[RelatedMetric]:
        """
        Find metrics related to the given metric

        Args:
            metric_code: The metric code to find relations for
            depth: Maximum depth of traversal (1-3 recommended)
            relation_type: Filter by specific relation type (optional)

        Returns:
            List of RelatedMetric objects
        """
        with self._get_driver().session() as session:

            if relation_type:
                cypher = f"""
                    MATCH path = (m:Metric {{metric_code: $code}})-[r:{relation_type}*1..{depth}]-(related)
                    WHERE m.metric_code <> related.metric_code
                    WITH related, relationships(path) as rels, length(path) as pathLen
                    RETURN related.metric_code as metric_code,
                           related.name as name,
                           [x IN rels | type(x)][0] as relation_type,
                           [x IN rels | coalesce(x.weight, 1.0)][0] as weight,
                           pathLen as distance
                    LIMIT 50
                """
                result = session.run(cypher, code=metric_code)
            else:
                cypher = f"""
                    MATCH path = (m:Metric {{metric_code: $code}})-[r*1..{depth}]-(related)
                    WHERE m.metric_code <> related.metric_code
                    WITH related, relationships(path) as rels, length(path) as pathLen
                    RETURN related.metric_code as metric_code,
                           related.name as name,
                           [x IN rels | type(x)][0] as relation_type,
                           [x IN rels | coalesce(x.weight, 1.0)][0] as weight,
                           pathLen as distance
                    LIMIT 50
                """
                result = session.run(cypher, code=metric_code)

            related = []
            for record in result:
                related.append(RelatedMetric(
                    metric_code=record["metric_code"],
                    name=record["name"] or "",
                    relation_type=record["relation_type"] or "",
                    weight=float(record["weight"] or 1.0),
                    distance=int(record["distance"] or 1)
                ))

            return related

    def find_upstream_metrics(
        self,
        metric_code: str,
        depth: int = 2
    ) -> List[RelatedMetric]:
        """
        Find upstream (ancestor) metrics that influence this metric

        Args:
            metric_code: Target metric code
            depth: Maximum depth to traverse

        Returns:
            List of upstream RelatedMetric objects
        """
        with self._get_driver().session() as session:
            cypher = f"""
                MATCH path = (upstream:Metric)-[r:DERIVES_FROM|IMPACTS*1..{depth}]->(m:Metric {{metric_code: $code}})
                WITH upstream, relationships(path) as rels, length(path) as pathLen
                RETURN upstream.metric_code as metric_code,
                       upstream.name as name,
                       [x IN rels | type(x)][0] as relation_type,
                       [x IN rels | coalesce(x.weight, 1.0)][0] as weight,
                       pathLen as distance
                LIMIT 50
            """
            result = session.run(cypher, code=metric_code)

            upstream = []
            for record in result:
                upstream.append(RelatedMetric(
                    metric_code=record["metric_code"],
                    name=record["name"] or "",
                    relation_type=record["relation_type"] or "",
                    weight=float(record["weight"] or 1.0),
                    distance=int(record["distance"] or 1)
                ))

            return upstream

    def find_downstream_metrics(
        self,
        metric_code: str,
        depth: int = 2
    ) -> List[RelatedMetric]:
        """
        Find downstream (descendant) metrics that this metric influences

        Args:
            metric_code: Source metric code
            depth: Maximum depth to traverse

        Returns:
            List of downstream RelatedMetric objects
        """
        with self._get_driver().session() as session:
            cypher = f"""
                MATCH path = (m:Metric {{metric_code: $code}})-[r:DERIVES_FROM|IMPACTS*1..{depth}]->(downstream:Metric)
                WITH downstream, relationships(path) as rels, length(path) as pathLen
                RETURN downstream.metric_code as metric_code,
                       downstream.name as name,
                       [x IN rels | type(x)][0] as relation_type,
                       [x IN rels | coalesce(x.weight, 1.0)][0] as weight,
                       pathLen as distance
                LIMIT 50
            """
            result = session.run(cypher, code=metric_code)

            downstream = []
            for record in result:
                downstream.append(RelatedMetric(
                    metric_code=record["metric_code"],
                    name=record["name"] or "",
                    relation_type=record["relation_type"] or "",
                    weight=float(record["weight"] or 1.0),
                    distance=int(record["distance"] or 1)
                ))

            return downstream

    def find_causal_chain(
        self,
        source_code: str,
        target_code: str
    ) -> Optional[CausalChain]:
        """
        Find the shortest causal chain between two metrics

        Args:
            source_code: Source metric code
            target_code: Target metric code

        Returns:
            CausalChain object or None if no path exists
        """
        with self._get_driver().session() as session:
            cypher = """
                MATCH path = shortestPath(
                    (s:Metric {metric_code: $source})-[r:DERIVES_FROM|IMPACTS|CORRELATES_WITH*]->(t:Metric {metric_code: $target})
                )
                RETURN [n IN NODES(path) | n.metric_code] as chain,
                       LENGTH(path) as hops
            """
            result = session.run(cypher, source=source_code, target=target_code)

            record = result.single()
            if record:
                chain = record["chain"]
                return CausalChain(
                    source=source_code,
                    target=target_code,
                    chain=chain,
                    total_hops=record["hops"]
                )

            return None

    def find_correlated_metrics(
        self,
        metric_code: str,
        depth: int = 1
    ) -> List[RelatedMetric]:
        """
        Find metrics correlated with this metric

        Args:
            metric_code: Metric code
            depth: Traversal depth (default 1 for direct correlations)

        Returns:
            List of correlated RelatedMetric objects
        """
        return self.find_related_metrics(
            metric_code,
            depth=depth,
            relation_type="CORRELATES_WITH"
        )

    def get_metric_context(self, metric_code: str) -> Dict:
        """
        Get full context for a metric including upstream, downstream, and correlations

        Args:
            metric_code: Metric code

        Returns:
            Dictionary with upstream, downstream, correlated metrics
        """
        return {
            "metric_code": metric_code,
            "upstream": [
                {
                    "metric_code": r.metric_code,
                    "name": r.name,
                    "relation_type": r.relation_type,
                    "weight": r.weight,
                    "distance": r.distance
                }
                for r in self.find_upstream_metrics(metric_code)
            ],
            "downstream": [
                {
                    "metric_code": r.metric_code,
                    "name": r.name,
                    "relation_type": r.relation_type,
                    "weight": r.weight,
                    "distance": r.distance
                }
                for r in self.find_downstream_metrics(metric_code)
            ],
            "correlated": [
                {
                    "metric_code": r.metric_code,
                    "name": r.name,
                    "weight": r.weight,
                    "distance": r.distance
                }
                for r in self.find_correlated_metrics(metric_code)
            ]
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # Test query
    with GraphQuery() as query:
        # Test finding related metrics
        related = query.find_related_metrics("MKI-02-0001", depth=2)
        print(f"Found {len(related)} related metrics")

        # Test getting context
        context = query.get_metric_context("MKI-02-0001")
        print(f"Upstream: {len(context['upstream'])}")
        print(f"Downstream: {len(context['downstream'])}")
        print(f"Correlated: {len(context['correlated'])}")
