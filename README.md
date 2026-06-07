# Biopesticide Discovery Engine

An AI-powered system that automatically discovers natural 
biopesticide compounds for Indian crop pests using 
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

Active development. AI analysis layer coming soon.  





                          
