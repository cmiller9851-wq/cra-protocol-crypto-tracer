from neo4j import GraphDatabase, basic_auth
from typing import Dict, Any
from datetime import datetime

# --- Configuration (Copied here for standalone clarity, but will be used by tracer_core) ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_strong_password" 
DATABASE_NAME = "neo4j"

# Helper function placeholder for load_transaction used below
# NOTE: This relies on the actual load_transaction logic being in the CORE object
def load_transaction_placeholder(core, tx_data):
    """Placeholder to call the core loader, handles datetime conversion."""
    from tracer_core import CRAProtocolCore # Import here to avoid circular dependency issues
    
    # Ensure datetime object is converted for the Neo4j driver
    tx_data_copy = tx_data.copy()
    tx_data_copy['block_timestamp'] = tx_data_copy['block_timestamp'].isoformat()
    
    # Use the core's driver and method
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
    
    try:
        core.driver.execute_write(lambda tx: tx.run(cypher_query, tx_data_copy), database_=DATABASE_NAME)
        return True
    except Exception as e:
        print(f"❌ Load failed for TX {tx_data.get('transaction_hash')}: {e}")
        return False


def seed_mixer_analysis_data(core):
    """
    Creates sample data to simulate a fund flow through a mixing service 
    where source and destination amounts/timestamps are correlated.
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # 1. Clear database
    with driver.session(database=DATABASE_NAME) as session:
        session.run("MATCH (n) DETACH DELETE n")

    # 2. Setup Mixer Entity (using the core's attribution logic)
    core.attribute_entity('0xMixerService_Address_1', 'CryptoBlender Mixer', 'Mixer')
    core.attribute_entity('0xMixerService_Address_2', 'CryptoBlender Mixer', 'Mixer')

    # 3. Define transactions (normalized format for core.load_transaction)
    
    # Source A deposits 1000 into the mixer at T=0
    tx_deposit_A = {
        "source_address": '0xIllicitSource_A',
        "destination_address": '0xMixerService_Address_1',
        "transaction_hash": 'Tx_MIX_Deposit_A',
        "value_usd": 1000.0,
        "blockchain_type": "ETH",
        "block_timestamp": datetime(2025, 12, 12, 10, 0, 0) # T=0
    }
    
    # Source B deposits 500 into the mixer at T=1 (Distractor/Noise)
    tx_deposit_B = {
        "source_address": '0xLegitSource_B',
        "destination_address": '0xMixerService_Address_1',
        "transaction_hash": 'Tx_MIX_Deposit_B',
        "value_usd": 500.0,
        "blockchain_type": "ETH",
        "block_timestamp": datetime(2025, 12, 12, 10, 1, 0) # T=1
    }

    # Destination X withdraws 990 from the mixer at T=5 (Correlated with A: 1000 - 10 fee)
    tx_withdrawal_X = {
        "source_address": '0xMixerService_Address_2',
        "destination_address": '0xDestination_X',
        "transaction_hash": 'Tx_MIX_Withdrawal_X',
        "value_usd": 990.0,
        "blockchain_type": "ETH",
        "block_timestamp": datetime(2025, 12, 12, 10, 5, 0) # T=5
    }

    # Destination Y withdraws 495 from the mixer at T=6 (Correlated with B: 500 - 5 fee)
    tx_withdrawal_Y = {
        "source_address": '0xMixerService_Address_2',
        "destination_address": '0xDestination_Y',
        "transaction_hash": 'Tx_MIX_Withdrawal_Y',
        "value_usd": 495.0,
        "blockchain_type": "ETH",
        "block_timestamp": datetime(2025, 12, 12, 10, 6, 0) # T=6
    }
    
    # Use the placeholder function to call the actual loader logic
    load_transaction_placeholder(core, tx_deposit_A)
    load_transaction_placeholder(core, tx_deposit_B)
    load_transaction_placeholder(core, tx_withdrawal_X)
    load_transaction_placeholder(core, tx_withdrawal_Y)

    core.attribute_entity('0xIllicitSource_A', 'Source', 'Illicit')
    core.attribute_entity('0xDestination_X', 'Target Exchange', 'VASP')
    
    driver.close()
    print("\n✅ Mixer Analysis demo data seeded: Deposits and withdrawals created.")

# --- Utility Function for Data Seeding (Used by app.py for quick startup) ---
# This ensures that when app.py calls seed_demo_data, the comprehensive mixer data is used.
def seed_demo_data(core):
    """Dummy function to be called by app.py to initiate data seeding."""
    seed_mixer_analysis_data(core)
    
