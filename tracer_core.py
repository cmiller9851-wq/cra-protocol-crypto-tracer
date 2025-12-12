import os
from neo4j import GraphDatabase, basic_auth
from typing import Dict, Any, List
from datetime import datetime, timedelta
# Import the custom seeding function
from tracer_core_test_data import seed_demo_data 

# --- Configuration ---
# NOTE: In a real environment, always configure these via environment variables
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_strong_password")
DATABASE_NAME = "neo4j"
# --- End Configuration ---

class CRAProtocolCore:
    """
    Consolidated class for Data Loading, Risk Scoring, and Advanced Tracing Algorithms.
    """
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD))
        print(f"✅ CRA Protocol Core initialized and connected to Neo4j.")

    def close(self):
        # NOTE: This is called by the Flask teardown hook in app.py
        self.driver.close()

    # --- Data Loading / Ingestion ---
    def load_transaction(self, tx_data: Dict[str, Any]) -> bool:
        """Loads a normalized transaction into the graph using MERGE."""
        cypher_query = """
        MERGE (source:Address {hash: $source_address})
        ON CREATE SET source.first_seen = datetime($block_timestamp)
        ON MATCH SET source.last_seen = datetime($block_timestamp)
        
        MERGE (dest:Address {hash: $destination_address})
        ON CREATE SET dest.first_seen = datetime($block_timestamp)
        ON MATCH SET dest.last_seen = datetime($block_timestamp)

        MERGE (source)-[s:SENT {tx_hash: $transaction_hash}]->(dest)
        ON CREATE SET 
            s.amount_usd = $value_usd, 
            s.timestamp = datetime($block_timestamp), 
            s.blockchain = $blockchain_type
        
        RETURN s.tx_hash AS txId
        """
        
        tx_data_copy = tx_data.copy()
        tx_data_copy['block_timestamp'] = tx_data_copy['block_timestamp'].isoformat() if isinstance(tx_data_copy['block_timestamp'], datetime) else tx_data_copy['block_timestamp']
        
        try:
            self.driver.execute_write(lambda tx: tx.run(cypher_query, tx_data_copy), database_=DATABASE_NAME)
            return True
        except Exception as e:
            # print(f"❌ Load failed for TX {tx_data.get('transaction_hash')}: {e}")
            return False

    # --- Entity/Risk Scoring ---
    def attribute_entity(self, address_hash: str, entity_name: str, entity_type: str):
        """Creates an Entity node and links the Address to it, and sets a high risk score."""
        cypher_query = """
        MERGE (a:Address {hash: $address_hash})
        MERGE (e:Entity {name: $entity_name})
        ON CREATE SET e.type = $entity_type, e.is_attributed = TRUE
        MERGE (a)-[r:OWNED_BY]->(e)
        SET a.risk_score = 0.99, a.is_attributed = TRUE
        """
        self.driver.execute_write(lambda tx: tx.run(cypher_query, address_hash=address_hash, entity_name=entity_name, entity_type=entity_type), database_=DATABASE_NAME)

    # --- Advanced Tracing Algorithm 1: Peel Chain Detection (Graph Formatter) ---
    def trace_and_format_graph(self, start_address: str, max_hops: int = 5) -> Dict[str, Any]:
        """
        Runs the Peel Chain heuristic and formats the result into a Nodes/Edges structure
        for front-end visualization.
        """
        # The query finds paths where the flow is dominated by the 'change' address.
        cypher_query = f"""
        MATCH (start:Address {{hash: $start_address}})
        MATCH path = (start)-[s:SENT*1..{max_hops}]->(end)
        
        // Simplified Peel Chain Heuristic: Follow paths with large transfers (> $500)
        WHERE ALL(rel IN s WHERE rel.amount_usd > 500)

        // Extract and collect unique Nodes and Relationships on the path
        WITH collect(nodes(path)) AS all_nodes, collect(relationships(path)) AS all_relationships
        UNWIND all_nodes AS node_list UNWIND all_relationships AS rel_list
        WITH DISTINCT node_list AS node, DISTINCT rel_list AS rel
        
        // 1. Project Nodes with Entity data
        OPTIONAL MATCH (node)-[:OWNED_BY]->(e:Entity)
        WITH 
            collect(DISTINCT {{
                id: node.hash, 
                label: coalesce(node.label, node.hash), 
                group: labels(node)[0], 
                risk_score: coalesce(node.risk_score, 0.0),
                entity_type: e.type,
                first_seen: toString(node.first_seen)
            }}) AS nodes,
            rel
            
        // 2. Project Edges
        WITH nodes, 
            collect(DISTINCT {{
                id: rel.tx_hash, 
                from: startNode(rel).hash, 
                to: endNode(rel).hash, 
                label: "$" + toString(rel.amount_usd), 
                amount_usd: rel.amount_usd,
                is_peel_chain: (rel.amount_usd > 900) // Flag the dominant path
            }}) AS edges

        RETURN nodes, edges
        """

        with self.driver.session(database=DATABASE_NAME) as session:
            result = session.run(cypher_query, start_address=start_address).single()
            
            if not result or not result['nodes']:
                 return {"nodes": [], "edges": [], "summary": {"conclusion": "No Peel Chain path found.", "risk_level": "LOW", "total_value_usd": 0}}

            total_value = sum(edge['amount_usd'] for edge in result['edges'])
            
            return {
                "nodes": result['nodes'],
                "edges": result['edges'],
                "summary": {
                    "conclusion": "Potential Peel Chain pattern detected.",
                    "risk_level": "HIGH",
                    "total_value_usd": round(total_value, 2)
                }
            }
            
    # --- Advanced Tracing Algorithm 2: Mixer Analysis Heuristic ---
    def analyze_mixer_flow(self, start_address: str, mixer_name: str) -> Dict[str, Any]:
        """
        Identifies potential deposit/withdrawal correlations (Money Laundering)
        through a specific mixer entity within a short time window.
        """
        # 
        
        # The core logic: Find an input (deposit) from A into the mixer. 
        # Then find an output (withdrawal) to B from the mixer, where the amounts 
        # are close (within 5% tolerance for fees) and the withdrawal happens shortly after 
        # the deposit (within 30 minutes).

        cypher_query = f"""
        MATCH (source:Address)-[dep:SENT]->(mixer_in)
        WHERE source.hash = $start_address
        AND (mixer_in)-[:OWNED_BY]->(:Entity {{name: $mixer_name}})
        
        // Find correlated withdrawal
        MATCH (mixer_out)-[wdr:SENT]->(destination:Address)
        WHERE (mixer_out)-[:OWNED_BY]->(:Entity {{name: $mixer_name}})
        
        // CORRELATION HEURISTICS
        // 1. Amount Correlation (within 5% tolerance for fees)
        AND abs(dep.amount_usd - wdr.amount_usd) <= 0.05 * dep.amount_usd
        
        // 2. Temporal Correlation (withdrawal must happen within 30 minutes after deposit)
        AND duration.between(dep.timestamp, wdr.timestamp).minutes >= 0
        AND duration.between(dep.timestamp, wdr.timestamp).minutes <= 30
        
        RETURN 
            source.hash AS DepositSource, 
            dep.amount_usd AS DepositAmount,
            wdr.amount_usd AS WithdrawalAmount,
            destination.hash AS WithdrawalTarget,
            dep.timestamp AS DepositTime,
            wdr.timestamp AS WithdrawalTime
        ORDER BY DepositTime
        LIMIT 10
        """
        
        try:
            with self.driver.session(database=DATABASE_NAME) as session:
                results = [record for record in session.run(cypher_query, start_address=start_address, mixer_name=mixer_name)]
                
                if not results:
                    return {"status": "No Correlation Found", "correlations": []}
                
                correlations = []
                for record in results:
                    # Calculate time difference in minutes for the final output
                    time_diff = record["WithdrawalTime"] - record["DepositTime"]
                    time_diff_minutes = time_diff.total_seconds() / 60
                    
                    correlations.append({
                        "deposit_source": record["DepositSource"],
                        "deposit_amount_usd": round(record["DepositAmount"], 2),
                        "withdrawal_amount_usd": round(record["WithdrawalAmount"], 2),
                        "withdrawal_target": record["WithdrawalTarget"],
                        "time_difference_minutes": round(time_diff_minutes, 2)
                    })
                    
                return {
                    "status": "CORRELATION DETECTED",
                    "mixer": mixer_name,
                    "count": len(correlations),
                    "correlations": correlations
                }
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

