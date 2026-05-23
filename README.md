# GQL Datatypes RDF Validator & Generator

This project provides a robust, data-driven Semantic Web engine for generating and validating RDF data against a custom Graph Query Language (GQL) Datatypes Ontology. 

The system is highly dynamic: the Python validator reads all constraints, limits, regex patterns, and standard W3C XSD mappings directly from the `.ttl` ontology file using `owl:equivalentClass` and OWL restrictions.

## Project Structure

* `gql_datatypes.ttl`: The core ontology file. It serves as the Single Source of Truth (SSOT), defining all types, mappings to `xsd:`, length restrictions, and regex patterns.
* `generator.py`: An interactive CLI tool that generates synthetic, highly irregular patient medical records using real Semantic Web vocabularies (`foaf`, `schema`, `dc`). It allows you to dynamically inject a specific percentage of lexical and structural errors for testing purposes.
* `validator.py`: The validation engine. It dynamically builds rules from the ontology and validates the generated RDF dataset, providing a detailed statistical report.

## Prerequisites

To run the scripts, you need Python 3.8+ and the following libraries:

```bash
pip install rdflib faker