# Datrics Text2SQL: Open-Source, High-Accuracy Natural Language to SQL Conversion

Datrics Text-to-SQL engine designed to understand databases effortlessly, turning plain English into accurate SQL queries. Our solution emphasizes advanced Retrieval-Augmented Generation (RAG) techniques rather than simply providing frameworks for developers to fine-tune models themselves and can work out-of-the-box.

# Whitepaper
[ResearchGate](https://www.researchgate.net/publication/389944067_Datrics_Text2SQL_A_Framework_for_Natural_Language_to_SQL_Query_Generation)
[ArXiv](https://arxiv.org/abs/2506.12234)

## What makes us stand out?
1. Semantic Layer: 
We leverage your database documentation and examples, extracting meaningful concepts to enhance precision.

2. Smart Example Matching: 
While other solutions struggle with unseen tables, our advanced search and reranking capabilities intelligently generalize from similar examples, ensuring reliable query generation.

3. Instant Documentation: 
Connect your database and instantly generate detailed documentation—no manual effort required.

4. Flexible AI Integration: 
Easily integrate with existing LLMs for enhanced, customized performance.

# Dependencies

Text2SQL agent uses chromadb to store vector embeddings and it relies on OpenAI Embeddings function
Support for other LLMs and Vector DBs is coming soon.

# Prerequsites

python >= 3.11
docker for running local test database

# Getting started

### Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

### Set-up LLM

1. open `descriptors/default/t2sql_descriptor.json` with any text editor
2. set litellm settings to [router_model_list](https://docs.litellm.ai/docs/routing#quick-start)


# Run streamlit application

```bash
docker-compose up -d
streamlit run main.py
```

In the app: open "Documentation" tab and click on "Run schema indexing" - this will create the semantic layer of the database
You can start asking question right after it's finished.

# Connecting to your database

open descriptors/default/t2sql_descriptor.json with any text editor
set access to your database "db" object
in case if you needd to use ssh tunnel, add ssh_tunnel to your descriptor:

```json
"ssh_tunnel": {
    "username": "",
    "private_key_path": "",    
}
```

You can provide the documentation in the "documentation" tab or click on "Run schema indexing" - this will create the semantic layer of the database.

You can start using app just right after that.

# Contributors

- Tetyana Hladkykh: FireFlyTy ([@FireFlyTy](https://github.com/FireFlyTy))
- Kirill Kirikov: kkirikov ([@kkirikov](https://github.com/kkirikov))

### Need AI Agent? 
Contact sales@datrics.ai

### Want to support project? 
Contact kk@datrics.ai 
