# Enterprise-Knowledge-Assistant-RAG
Enerprise Knowledge Assistant RAG is a full-stack, educational enterprise knowledge assistant that answers natural-language questions over uploaded organizational documents using retrieval-augmented generation (RAG).

# Create  virtual environment using conda
conda create -n venv python=3.12 -y

# Activate hte env
conda atcivate venv

# install requirements
pip install -r requirements.txt


## Implemention Plan

# Phase 1  - Infrastructure: Set up AWS Environment, PostgresSQL, Pinecone, Glassflow Rius

Set UP AWS infra setting by logging in to aws sign. we will use these below services.
1. Using IAM service, we will provision access to the user. - created iam user, and added accesskey to it
2. s3 bucket : create s3 bucket and give cors origin enbaled to access s3 bucket from local
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "PUT"
        ],
        "AllowedOrigins": [
            "http://127.0.0.1:8000",
            "http://localhost:8000"
        ],
        "ExposeHeaders": [
            "ETag"
        ],
        "MaxAgeSeconds": 3000
    }
]

bedrock servcie
EC2
ECR

3. PostgresSQL: create a postgressql db in render.com (free tier), create a db, 
give details and copy the server details which are in the form mentioned in DATABASE_URL in env file.

to conent to the pgdb ,either we can use pgadmin client downloaded and the nconenct
or can conenct in vs code by installing these two toools - SQLTools, SQLTools -postgresssql/cockroachdb tool.
install these two tools and connect to db by providing the ecessary details which are already there in the DB_Connection sting url.


4. Glassflow Rius:create an api key from glassflow.ai/rius and use in the env.

# Phase 2  -  AI Engineering: Implement RAG, Memory, Guardrails, Add observability using Glassflow, Human-In-The-Loop, Langraph
# Phase 3  - Create Frontend, Backend for App: API, HML, CSS, Javascript.
# Phase 4  - Integration and Testing: S3 CORS, Tests, documentaion, End to End Demonstration.