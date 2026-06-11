# Biopesticide Discovery Engine

Evidence-driven biopesticide discovery platform for Indian crop pests using 
scientific literature mining and NLP analysis.

## What This Does

This engine searches multiple scientific databases 
simultaneously, extracts relevant research papers, 
identifies natural compounds using NLP, and builds 
a structured knowledge base for Indian crop pest management.

## Indian Crop Pests Covered

- Whitefly on cotton
- Aphids on mustard  
- Stem borer on rice
- Brown planthopper on rice
- Thrips on chili

## How It Works

1. Searches PubMed, Semantic Scholar, and Europe PMC
2. Retrieves relevant biopesticide research papers
3. Extracts compound names using spaCy NLP
4. Saves structured knowledge to a local database
5. Queries and analyzes results by pest and crop

## Installation

pip install biopython requests spacy
python -m spacy download en_core_web_sm

## Usage

python day4.py    # Build knowledge database
python day5.py    # Query the database
python day8.py    # Extract compounds using NLP

## Built With

- Python 3.14
- Biopython (PubMed access)
- spaCy (NLP extraction)
- Semantic Scholar API
- Europe PMC API

## Author

Pragyan Handique  
Undergraduate Chemistry Student, Assam, India  
Building at the intersection of AI and chemistry.

## Status

Evidence-driven scientific discovery engine coming soon.  

## Current Capabilities

* Federated scientific literature search across PubMed, Semantic Scholar, Europe PMC, and OpenAlex
* Knowledge base built from 1,377+ scientific papers related to biopesticides and Indian crop pests
* Coverage of major Indian agricultural pests including *Helicoverpa armigera*, *Spodoptera frugiperda*, *Bemisia tabaci*, *Nilaparvata lugens*, and others
* Full-text XML extraction from open-access scientific publications
* Automated extraction of experimental tables and quantitative bioactivity data
* NLP-based compound extraction and normalization using spaCy
* Molecular descriptor and property analysis using RDKit
* SQLite-backed scientific database replacing JSON storage
* 4,500+ bioactivity records linking compounds, pests, crops, and experimental outcomes
* 120+ extracted natural and biopesticidal compounds
* Evidence grading system (A/B/C/D) based on quantitative bioactivity evidence
* Knowledge graph construction with 5,600+ nodes and 18,000+ relationships
* Compound–pest relationship mapping and evidence aggregation
* Interactive dashboard for searching, filtering, and exploring compound-pest evidence
* Automated deduplication and progress-tracked extraction pipelines
* Local research platform for evidence-driven biopesticide discovery

## Technology Stack

* Python
* SQLite
* spaCy
* RDKit
* PubMed API (Biopython)
* Semantic Scholar API
* Europe PMC API
* OpenAlex API
* Flask
* HTML/CSS/JavaScript

## In Development

* Improved pest assignment and entity resolution
* Advanced bioactivity re-extraction pipeline
* Cross-pest compound transfer prediction
* Scientific Jury reasoning framework
* Mechanism-of-action extraction
* Molecular docking integration (AutoDock Vina)
* Evidence-based hypothesis generation
* Compound intelligence pages with visual analytics


## Web Interface

Run locally: python app.py
Open browser at http://localhost:5000

Features:
- Search compounds and pests
- Filter by evidence grade (A/B/C/D)
- Card and table view
- 1177 papers, 93 compounds, 3694 bioactivity records
- 56 Grade A compound-pest pairs

                          
