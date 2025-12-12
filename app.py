from flask import Flask, jsonify, request
import os
from tracer_core import CRAProtocolCore, seed_demo_data # Import our core logic and the seeder function

app = Flask(__name__)

# Initialize the core tracing system globally
try:
    CORE = CRAProtocolCore()
    
    # Seed data on startup for easy local testing
    seed_demo_data(CORE)

    @app.teardown_appcontext
    def close_core_connection(exception=None):
        """Ensures the Neo4j driver connection is closed after each request."""
        if CORE:
            CORE.close()
            
except Exception as e:
    print(f"FATAL ERROR: Failed to initialize CORE. Check tracer_core.py and Neo4j connection. Error: {e}")
    # Exit the application if the core service fails to start
    exit(1)


@app.route('/api/v1/address/<address_hash>', methods=['GET'])
def get_address_details(address_hash):
    """
    Endpoint 1: Retrieves stored intelligence (risk score, entity link) for an Address.
    """
    query = """
    MATCH (a:Address {hash: $hash})
    OPTIONAL MATCH (a)-[:OWNED_BY]->(e:Entity)
    RETURN properties(a) AS address_data, properties(e) AS entity_data
    """
    
    try:
        with CORE.driver.session(database="neo4j") as session:
            result = session.run(query, hash=address_hash).single()
            
            if not result:
                return jsonify({"error": "Address not found in graph"}, 404)
            
            address_data = result["address_data"]
            entity_data = result["entity_data"]

            response = {
                "address": address_data["hash"],
                "risk_score": address_data.get("risk_score", 0.0),
                "is_high_risk": address_data.get("is_high_risk", False),
                "attributed_entity": entity_data if entity_data else None,
                "first_seen": address_data.get("first_seen"),
                "last_seen": address_data.get("last_seen"),
            }
            
            return jsonify(response)
            
    except Exception as e:
        return jsonify({"error": "Database query failed", "details": str(e)}, 500)


@app.route('/api/v1/trace_graph', methods=['GET'])
def run_trace_graph():
    """
    Endpoint 2: Runs the Peel Chain Heuristic and returns a structured 
    graph object (Nodes/Edges) for front-end visualization.
    """
    start_address = request.args.get('start_address')
    
    if not start_address:
        return jsonify({"error": "Missing 'start_address' parameter"}, 400)

    try:
        # Call the Peel Chain/Graph formatting logic
        graph_data = CORE.trace_and_format_graph(start_address)
        
        response = {
            "trace_id": f"TRACE-{os.urandom(4).hex()}",
            "status": "COMPLETED",
            "start_address": start_address,
            "visualization_data": {
                "nodes": graph_data['nodes'],
                "edges": graph_data['edges']
            },
            "summary": graph_data['summary']
        }
            
        return jsonify(response)
            
    except Exception as e:
        return jsonify({"error": "Tracing execution failed", "details": str(e)}, 500)

@app.route('/api/v1/analyze_mixer', methods=['GET'])
def analyze_mixer_route():
    """
    Endpoint 3: Runs the Mixer Analysis Heuristic for deposit/withdrawal correlation.
    """
    source_address = request.args.get('source_address')
    mixer_name = request.args.get('mixer_name')
    
    if not source_address or not mixer_name:
        return jsonify({"error": "Missing 'source_address' or 'mixer_name' parameter"}, 400)

    try:
        # Call the Mixer Analysis logic
        analysis_result = CORE.analyze_mixer_flow(source_address, mixer_name)
        return jsonify(analysis_result)
        
    except Exception as e:
        return jsonify({"error": "Mixer analysis failed", "details": str(e)}, 500)


if __name__ == '__main__':
    print("\n🚀 Starting the CRA Protocol Web API...")
    print("--- Test Endpoints (Start Neo4j Docker container first!) ---")
    print(f"Peel Chain Trace: http://127.0.0.1:5000/api/v1/trace_graph?start_address=0xIllicitSource_A")
    print(f"Mixer Analysis: http://127.0.0.1:5000/api/v1/analyze_mixer?source_address=0xIllicitSource_A&mixer_name=CryptoBlender Mixer")
    print(f"Address Details: http://127.0.0.1:5000/api/v1/address/0xDestination_X")
    app.run(debug=True, port=5000)
