# Kardec Study Assistant

**Kardec Study Assistant** is the backend of the **Dialoguing with the Doctrine** project, created with the primary goal of disseminating the Spiritist doctrine in a structured and accessible way.

The frontend application is currently under development and will be released soon.

Kardec Study Assistant is a Retrieval-Augmented Generation (RAG) system designed to provide structured, contextual answers grounded exclusively in the foundational works of Spiritism. The system parses, structures, embeds, and serves doctrinal content through a clean and modular architecture — designed to evolve into a production-ready API.

This project focuses on the five core works codified by Allan Kardec and enables intelligent dialogue strictly grounded in the doctrine.

---

## Project Purpose

The goal of this project is to:

- Transform structured doctrinal texts into semantic embeddings  
- Enable contextual retrieval of relevant excerpts  
- Generate grounded responses using a Large Language Model (LLM)  
- Serve answers via an API layer  
- Maintain doctrinal traceability (book, part, chapter, item)  

This is **not** a chatbot trained on Spiritism. It is a **retrieval-grounded system** that answers strictly based on the original texts.

---

## Data Source & Copyright Status

The five doctrinal works were collected from Brazil’s public domain repository:

http://www.dominiopublico.gov.br/pesquisa/PesquisaObraForm.jsp

All books are publicly available and free of copyright restrictions.

### Processing Pipeline

1. The original public-domain PDFs were downloaded.
2. The PDFs were stored under: `data/books/`

3. The PDFs were converted into structured Markdown format using **LlamaCloud**.
4. The result is 5 structured `.md` files located in:


5. These Markdown files are then parsed into structured JSON for downstream embedding and retrieval.

---

## Project Structure

```
kardec-study-assistant/
│
├── data/
│   ├── books/              # Original public-domain PDF files (source material)
│   ├── embeddings/         # Vector database files and generated embeddings
│   ├── markdown_files/     # Markdown files generated from PDFs
│   └── json_files/         # Structured JSON chunks used for ingestion
│
├── src/
│   └── dialogue_with_the_doctrine/
│       ├── api/            # FastAPI application layer
│       │   ├── main.py
│       │   ├── routes.py
│       │   └── schemas.py
│       │
│       ├── parsing/        # Markdown cleaning and structural parsing
│       │   ├── parsing_pipeline.py
│       │   ├── cleaner.py
│       │   ├── parser.py
│       │   └── chunking.py
│       │
│       ├── ingestion/      # Embedding + vector database pipeline
│       │   ├── embeddings.py
│       │   ├── vectorstore.py
│       │   └── pipeline.py
│       │
│       ├── rag/            # Retrieval-Augmented Generation logic
│       │   ├── retriever.py
│       │   ├── prompt.py
│       │   └── generator.py
│       │
│       └── core/           # Configuration and shared utilities
│           ├── config.py
│           └── settings.py
│
├── pyproject.toml
└── README.md
```


---

## Architecture Overview

The system follows a clean separation of responsibilities:

**Parsing Layer**
- Cleans Markdown
- Extracts hierarchical structure (Part, Chapter, Item)
- Splits long items into sub-chunks
- Outputs structured JSON with metadata

**Ingestion Layer**
- Generates embeddings
- Stores vectors in a vector database
- Handles indexing and re-indexing

**RAG Layer**
- Retrieves relevant doctrinal passages
- Constructs prompts
- Calls the LLM
- Returns grounded answers

**API Layer**
- Exposes endpoints for user queries
- Validates input/output schemas
- Connects user requests to the RAG system

---

## Design Principles

- Clear separation of concerns  
- Traceable doctrinal references  
- Modular architecture  
- Production-ready scalability  
- Strict retrieval grounding (no hallucinated doctrine)  

---

## Future Roadmap

- Conversation memory support  
- Citation formatting improvements  
- Web interface  
- Multilingual support  
- Deployment infrastructure  

---

## License

All doctrinal texts used in this project are in the public domain.

The software architecture of this project is open for extension and research purposes.
