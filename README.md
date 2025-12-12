# CRA Protocol Automated Crypto Tracing Solution

## Project Goal
To develop a superior, automated, and scalable crypto tracing solution that leverages a Graph Database (Neo4j) and advanced graph heuristics to render traditional manual investigation services (like CNC Intel's) obsolete.

## Architecture Overview
The solution is built on a modular Python stack:
1.  **Data Layer:** Neo4j Graph Database for relational data storage.
2.  **Ingestion/Intelligence:** The Core Tracing Logic handles data loading, entity attribution, and risk scoring.
3.  **Analysis:** Advanced Cypher queries for heuristics (e.g., Peel Chain Detection).
4.  **Presentation:** A Flask REST API for consuming trace results structured for front-end graph visualization.

## Setup Instructions

### 1. Prerequisites
* Python 3.8+
* Docker (Recommended for Neo4j)
* Access to a running Neo4j instance (Default: bolt://localhost:7687)

### 2. Neo4j Setup (using Docker)
```bash
docker run \
    --name neo4j-tracer \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/your_strong_password \
    neo4j:5.0

NOTE: Change your_strong_password and update tracer_core.py accordingly.
3. Application Setup
# Clone the repository
git clone [https://github.com/your-username/cra-protocol-crypto-tracer.git](https://github.com/your-username/cra-protocol-crypto-tracer.git)
cd cra-protocol-crypto-tracer

# Install dependencies
pip install -r requirements.txt

# Run the API
python app.py

API Endpoints
 * Trace Initiation (Visualization Ready): /api/v1/trace_graph?start_address=<hash>
 * Address Intelligence: /api/v1/address/<hash>
<!-- end list -->

