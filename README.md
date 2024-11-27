# SJM Integrator [![DOI](https://zenodo.org/badge/728133494.svg)](https://zenodo.org/doi/10.5281/zenodo.10307556)

SJM Integrator - A python application with GUI that allows to import XES logs into Neo4J providing a Event Knowledge Graph (EKG) representation of the customer journeys provide in the Customer Journey Modelling Language (CJML) format.

## Use

When application opened, it requires login credentials for Neo4J instance. After they are provided, the session is initatied with the Neo4j instance. Then, XES file is required to be selected for application. It parses all fields stored in XES file. The application starts automaticlly map fields based on the name structure. If the mapper skips the fields, user must assign if they are primary field, their type. When assigment is done, the application will ask to select fields, that express time. After that application starts running automaticly generated queries on Neo4J instance creating the graph. 

## Installation

To prepare the requirements in a Python 3.11 environment execute:

```
pip install -r requirements.txt
```

## Launching

To run application, you need to run: 

```
python start.py
```
