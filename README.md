# RDF Patient Data Generator and Validator

This repository contains two Python scripts for working with RDF patient data:

- generating synthetic RDF data with a controlled error rate,
- validating RDF data against a GQL Datatypes ontology,
- exporting validation results to CSV and JSON reports.

The repository currently includes:

- `generator_real.py` - RDF patient data generator,
- `validator.py` - RDF validator driven by ontology rules.

## Requirements

- Python 3.8+
- `rdflib`
- `faker`

Install dependencies with:

```bash
pip install rdflib faker
```

If you prefer an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install rdflib faker
```

## Project Structure

- `generator_real.py` - creates a Turtle file with synthetic patient records.
- `validator.py` - reads RDF data and ontology rules, then checks literal values.
- `gql_datatypes.ttl` - ontology file that defines the GQL datatypes, mappings, and constraints used by the generator and validator.
- `README.md` - usage guide and CLI reference.

## Ontology File

`gql_datatypes.ttl` is the single source of truth for datatype definitions used in this project.

It provides:

- GQL datatype declarations,
- `owl:equivalentClass` mappings to XSD or RDF datatypes,
- OWL restrictions such as numeric bounds, length constraints, and regex patterns.

The validator reads this file dynamically and derives its rules from the ontology instead of relying on hard-coded datatype logic. The generator also uses the same datatype namespace when emitting typed RDF literals.

## Data Generator

`generator_real.py` creates sample patient data in Turtle format. Each record may contain a subset of optional fields, and selected fields can be intentionally corrupted to test validation.

### Usage

```bash
python generator_real.py [options]
```

### Options

- `-o`, `--output`
  - output file path,
  - default: `test_data.ttl`.
- `-c`, `--count`
  - number of records to generate,
  - if omitted, the script asks for the value interactively.
- `-e`, `--error-rate`
  - percentage of invalid data in the range `0-100`,
  - if omitted, the script asks for the value interactively.
- `--config`
  - path to a JSON file that overrides field probabilities,
  - if the file exists, its values are merged with the defaults.

### Interactive Mode

If you omit `--count` or `--error-rate`, the generator switches to interactive mode and prompts for the missing values in the terminal.

### Examples

Generate 100 records using the default output file:

```bash
python generator_real.py -c 100 -e 20
```

Generate data into a custom file:

```bash
python generator_real.py -o patients.ttl -c 500 -e 10
```

Use a custom probability configuration:

```bash
python generator_real.py -c 200 -e 15 --config probabilities.json
```

### What the Generator Produces

The generator writes RDF data in Turtle format and creates patient records with fields such as:

- `foaf:name`
- `foaf:age`
- `schema:birthDate`
- `schema:weight`
- `schema:height`
- `schema:requiresHealthPlan`
- `schema:dateAdmitted`
- `schema:arrivalTime`
- `dc:identifier`
- `schema:prescription`
- `foaf:gender`
- `schema:duration`
- `schema:baseSalary`
- `schema:Vector`
- `ex:metadata`
- `ex:testField`

It uses datatypes from `http://example.org/gql-types#`, including `STRING`, `UINT8`, `DATE`, `FLOAT`, `BOOLEAN`, `ARRAY`, `VECTOR`, and `UNIT_RECORD`.

### `--config` File

The JSON configuration file can contain selected keys from `DEFAULT_PROBS`.
You can keep it as `probabilities.json` and pass it directly with `--config`.

Example:

```json
{
  "age": 1.0,
  "birthDate": 1.0,
  "weight": 0.5,
  "unknown_type": 0.0
}
```

Each value represents the probability of including a given field in a record.

## Validator

`validator.py` checks RDF literals against ontology-derived rules and constraints read from a Turtle ontology file.

The validator:

- builds a mapping from GQL datatypes to XSD datatypes using `owl:equivalentClass`,
- reads OWL restrictions from the ontology,
- checks:
  - structural JSON types,
  - boolean values,
  - string lengths and regex patterns,
  - numeric ranges,
  - lexical compatibility with XSD datatypes,
  - unknown datatypes.

### Usage

```bash
python validator.py [options]
```

### Options

- `-d`, `--data`
  - RDF file to validate,
  - default: `test_data.ttl`.
- `-o`, `--ontology`
  - Turtle ontology file,
  - default: `gql_datatypes.ttl`.

### Examples

Validate data using the default filenames:

```bash
python validator.py
```

Validate a specific data file and ontology:

```bash
python validator.py -d patients.ttl -o gql_datatypes.ttl
```

### Validation Output

After running, the script:

- prints a list of errors to the terminal,
- prints a statistical summary,
- writes reports to:
  - `validation_report.csv`,
  - `validation_report.json`.

The CSV report includes fields such as:

- `subject`
- `predicate`
- `value`
- `original_dt`
- `base_dt`
- `reason`

The JSON report contains a `summary` section and the full list of errors.

## Recommended Workflow

1. Generate data:

```bash
python generator_real.py -c 1000 -e 20 -o test_data.ttl
```

2. Validate the generated file:

```bash
python validator.py -d test_data.ttl -o gql_datatypes.ttl
```

3. Review the reports:

- `validation_report.csv`
- `validation_report.json`

## Notes

- The generator runs interactively by default if you do not pass `--count` or `--error-rate`.
- The validator only analyzes literals with an explicit datatype.
- If a datatype is not recognized or mapped, it is reported as an error.
