# MITxPRO: RAG AND CONTEXT ENGINEERING CAPSTONE PROJECT

Capstone Project for RAG and Context Engineering Production-Grade AI Systems

## Project 1: Research Paper Navigator [NOT IMPLEMENTED]

Develop a conversational interface that helps users answer questions about a collection of research papers. The system should be able to retrieve information from individual papers, compare ideas across multiple papers, identify trends or changes over time, and provide direct quotations from source documents in support of its responses.

This scenario is intended to model retrieval systems that support research, knowledge management, policy analysis, and other document-intensive environments.

## Project 2: Wikipedia Retrieval Engine [SELECTED/IMPLEMENTED]

Develop a conversational interface that answers questions about significant people, places, and topics using information retrieved from a collection of Wikipedia articles. The system should support both single-document and multi-document questions and provide direct quotations from source material to improve reliability and reduce hallucinations.

This scenario is intended to model retrieval systems that provide trustworthy access to large information repositories while maintaining transparency about where information originates.

## Setup

This project uses a local Python virtual environment in `.venv`.

**Use Python 3.11 or 3.12.** macOS’s `/usr/bin/python3` is often 3.9, which cannot install Checkpoint 3.1 pins such as `python-dotenv==1.2.2`. If Homebrew Python 3.12 is installed, create the venv with `python3.12`.

### 1. Create and activate the virtual environment

From the project root (`capstone/rag_and_context_engineering`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Your prompt should show `(.venv)`.

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r "wikipedia_retrieval_engine/Capstone Checkpoint 3.1/requirements.txt"
```



### 3. Add your OpenRouter API key

Get a free key at [https://openrouter.ai/keys](https://openrouter.ai/keys). Create a `.env` file in this folder with:

```
OPENROUTER_API_KEY=sk-or-v1-...
```



### 4. Verify the setup

```bash
python3 test_setup.py
```

A successful run prints a short model reply and `Setup verification completed successfully.`

### Later sessions

If the prompt no longer shows `(.venv)`, reactivate from the project root:

```bash
source .venv/bin/activate
```

Then confirm you are using the project interpreter (`which python` should end in `.venv/bin/python`). In Cursor, choose **Python: Select Interpreter** and pick `.venv` in this folder.