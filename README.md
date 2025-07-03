
HERE, once the database is created in mysql after running doall.sh in data pipeline succesfully, then we have to move on to the backend. 

HERE, once the database is created in MySQL after running `doall.sh` in the data pipeline successfully, then we have to move on to the backend.

# Ticket Summary Backend

This backend system processes IT support tickets, summarizes them using LLMs (Large Language Models), assigns them to employees, and stores ticket embeddings for semantic search and retrieval. It integrates with MySQL for structured data and LanceDB for vector storage.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Environment Setup](#environment-setup)
- [Key Components](#key-components)
  - [Ticket Processing](#ticket-processing)
  - [LLM Integration](#llm-integration)
  - [Ticket Assignment](#ticket-assignment)
  - [Vector Embedding & Search (RAG)](#vector-embedding--search-rag)
  - [Ground Ticket Embedding](#ground-ticket-embedding)
- [Running the Backend](#running-the-backend)
- [Environment Variables](#environment-variables)
- [Dependencies](#dependencies)
- [Logging & Tracing](#logging--tracing)
- [Notes](#notes)

---

## Project Structure

---

## Environment Setup

1. **Install dependencies:**
   ```sh
   pip install -r requirements.txt

Ensure MySQL database is set up:

Run your data pipeline (doall.sh) to populate the database.

