# Layer10 Memory Graph System

An enterprise-grade, grounded organizational memory system. This pipeline ingests unstructured and structured data (GitHub issues/comments), uses LLMs to extract relational claims, canonicalizes entities to deduplicate assertions, and pushes the resulting knowledge graph to Neo4j.

---

## 1. Architecture & Design Decisions

### Ontology & Extraction Contract
The system relies on a strict, rigid structural contract defined via Pydantic ([step2_extraction.py]). 
* **Entities:** Are strictly typed (`USER`, `ISSUE`, `COMPONENT`, `CONCEPT`), forcing the LLM to categorize nodes cleanly. Each entity requires an [id] and a `name`.
* **Claims:** Must take the form of a `subject_id` ➡️ `relation` ➡️ `object_id`. Relations are restricted via enums (e.g., `REPORTED`, `RESOLVED`, `CHANGED_STATE`).
* **The Grounding Contract:** Every single claim requires an [Evidence] array. The contract mandates an exact `excerpt` string, a `url`, and an ISO-8601 `timestamp`. A built-in Quality Gate drops any claim with an LLM confidence score below `0.8`.

### Canonicalization & Deduplication Strategy
Redundant facts (e.g., three different users commenting about the same bug) are handled gracefully before hitting the database:
1. **Entity Dedup:** Entities are resolved by standardizing IDs (lowercase, stripped space). An `aliases` set is used to group variations of a single entity (e.g., "Shivraj", "shivraj_g").
2. **Claim Dedup:** Claims are signature-matched via [(Subject)-[Relation]->(Object)]. When a duplicate relational claim is found across different GitHub comments, the system **does not overwrite the claim**. Instead, it **merges the [Evidence]. arrays**, ensuring that multiple citations pointing to the same fact are preserved on a single canonical edge in the graph.

### Update Semantics
Because data streams continuously, the system is designed to be **idempotent**. 
* The ingestion script ([step4_graph_db.py]) uses Cypher `MERGE` commands exclusively. Running the pipeline twice on the same data will not duplicate nodes or edges. 
* *Updating Knowledge:* If a new comment is added to an existing GitHub issue, rerunning the pipeline will match the existing entities via `MERGE`, recognize the new claim signature (if novel), or simply append the new comment's `URL` and `excerpt` to the existing claim's Evidence array.

### Adapting to Layer10 (Enterprise Scale)
If this pipeline were adapted for a live enterprise environment (Layer10) handling Slack, Jira, and Email streams, several architectural shifts would be required:
1. **Streaming vs. Batch:** The current sequential loop must be replaced with stream processing (e.g., Kafka). Webhooks would trigger serverless functions to run the LLM extraction in parallel, dumping structured graphs into a canonicalization queue.
2. **First-Class Evidence Nodes:** Currently, evidence is serialized as JSON on the relationship edge for rapid prototyping. In Layer10, Evidence must be modeled as a distinct Graph Node [(Artifact)]. This allows strict Role-Based Access Control (RBAC)—a user cannot retrieve a claim if they do not have permissions to view the underlying `Artifact` node.
3. **Temporal Validity (Overrides/Conflicts):** If a bug is "OPEN" on Monday and "CLOSED" on Tuesday, the system must handle conflicting claims. The Graph Schema would need an `active: boolean` or `valid_until: timestamp` property on edges to map the state of truth over time, allowing the Retriever API to filter out stale claims.

---

## 🏛️ System Architecture

The system is designed with a clear separation between the Minimum Viable Product (MVP) built for this assignment (represented by solid lines) and the Layer10 Enterprise Scaling vision (represented by dotted lines).

![Layer10_memory_system (4)](https://github.com/user-attachments/assets/e7576fce-ffd1-4b29-af69-f06a373e218f)


## ⚙️ 2. Reproducibility & Setup

### Prerequisites
* Python 3.10+
* A Neo4j Database instance (Aura Cloud)
* Groq API Key
* GitHub API Token

### 1. Clone & Install Dependencies
Open a terminal in the project directory and run:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\Activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a .env file in the root directory and add your credentials:
```bash
GROQ_API_KEY="your_groq_api_key"
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
GITHUB_TOKEN="your_github_token"
```

### 3. Execute the End-to-End Pipeline
Run the numbered scripts sequentially to move data from raw text into the Memory Graph:
```bash
python step1_ingestion.py       # Pulls raw data from GitHub API
python step2_extraction.py      # LLM extraction & Quality Gates
python step3_deduplication.py   # Canonicalization and Evidence Merging
python step4_graph_db.py        # Pushes knowledge to Neo4j
```

### 4. Launch the User Interface
```bash
streamlit run step5_ui.py

```
This starts an interactive dashboard running on localhost where you can question the memory graph via the Agentic QA tab, or explore the raw PyVis visualization.
