import logging
import json
import csv
import warnings
import re
import argparse
import os
from rdflib import Graph, Literal, XSD, RDF, OWL, RDFS

# Suppress warnings from rdflib
warnings.filterwarnings("ignore", category=UserWarning, module="rdflib")
logging.getLogger("rdflib").setLevel(logging.ERROR)


def local_name(uri):
    if not uri:
        return None
    return str(uri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def build_xsd_mapping(ont_g):
    mapping = {}
    for s, p, o in ont_g.triples((None, OWL.equivalentClass, None)):
        if str(o).startswith(str(XSD)) or str(o).startswith(str(RDF)):
            name = local_name(s)
            mapping[name] = o

    for s, p, o in ont_g.triples((None, OWL.equivalentClass, None)):
        if "http://example.org/gql-types" in str(o):
            alias_name = local_name(s)
            target_name = local_name(o)
            if target_name in mapping:
                mapping[alias_name] = mapping[target_name]

    return mapping


def build_rules(ont_g):
    rules = {}
    for dt in ont_g.subjects(RDF.type, RDFS.Datatype):
        name = local_name(dt)
        rules[name] = {"min": None, "max": None, "min_len": None, "max_len": None, "exact_len": None, "pattern": None}

        for restr in ont_g.objects(dt, OWL.withRestrictions):
            curr = restr
            while curr and curr != RDF.nil:
                first = ont_g.value(curr, RDF.first)
                if first:
                    if (min_v := ont_g.value(first, XSD.minInclusive)): rules[name]["min"] = float(str(min_v))
                    if (max_v := ont_g.value(first, XSD.maxInclusive)): rules[name]["max"] = float(str(max_v))
                    if (min_l := ont_g.value(first, XSD.minLength)): rules[name]["min_len"] = int(str(min_l))
                    if (max_l := ont_g.value(first, XSD.maxLength)): rules[name]["max_len"] = int(str(max_l))
                    if (exact_l := ont_g.value(first, XSD.length)): rules[name]["exact_len"] = int(str(exact_l))
                    if (pat := ont_g.value(first, XSD.pattern)): rules[name]["pattern"] = str(pat)
                curr = ont_g.value(curr, RDF.rest)
    return rules


def validate_data(data_file, ontology_file, report_prefix="validation_report"):
    if not os.path.exists(ontology_file):
        raise FileNotFoundError(f"Ontology file is missing or path is incorrect: '{ontology_file}'")

    if not os.path.exists(data_file):
        raise FileNotFoundError(f"RDF data file is missing or path is incorrect: '{data_file}'")

    ont_g = Graph().parse(ontology_file, format="turtle")
    gql_to_xsd = build_xsd_mapping(ont_g)
    rules = build_rules(ont_g)
    data_g = Graph().parse(data_file, format="turtle")

    errors = []
    total_literals = 0
    invalid_literals_count = 0

    for s, p, o in data_g:
        if isinstance(o, Literal) and o.datatype:
            total_literals += 1

            dtype_name = local_name(o.datatype)
            raw_val = str(o)

            base_xsd_uri = gql_to_xsd.get(dtype_name)
            base_xsd_str = local_name(base_xsd_uri) if base_xsd_uri else "No mapping"

            error_data = {
                "subject": str(s),
                "predicate": str(p),
                "value": raw_val,
                "original_dt": dtype_name,
                "base_dt": base_xsd_str
            }

            initial_errors_len = len(errors)

            # 1. JSON / Structural Types Validation
            json_types_lists = ["LIST", "ARRAY", "GROUP_LIST", "GROUP_ARRAY", "VECTOR"]
            json_types_objects = ["RECORD", "ANY_RECORD"]
            json_types_unit = ["UNIT_RECORD"]

            if dtype_name in json_types_lists + json_types_objects + json_types_unit:
                # Wąski blok try-except-else
                try:
                    parsed_json = json.loads(raw_val)
                except json.JSONDecodeError as e:
                    error_data["reason"] = f"JSON format parsing error: {e}"
                    errors.append(error_data.copy())
                else:
                    if dtype_name in json_types_lists:
                        if not isinstance(parsed_json, list):
                            error_data["reason"] = f"Expected a JSON Array (list), but got {type(parsed_json).__name__}"
                            errors.append(error_data.copy())
                        elif dtype_name == "VECTOR":
                            if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in parsed_json):
                                error_data["reason"] = "Expected VECTOR to contain only numbers, but found other data types"
                                errors.append(error_data.copy())

                    elif dtype_name in json_types_objects:
                        if not isinstance(parsed_json, dict):
                            error_data["reason"] = f"Expected a JSON Object (dict), but got {type(parsed_json).__name__}"
                            errors.append(error_data.copy())

                    elif dtype_name in json_types_unit:
                        if not isinstance(parsed_json, dict) or len(parsed_json) > 0:
                            error_data["reason"] = f"Expected an EMPTY JSON Object for UNIT_RECORD, but got a populated structure"
                            errors.append(error_data.copy())

            # 2. Boolean Validation
            elif dtype_name in ["BOOLEAN", "BOOL"]:
                if raw_val.lower() not in ["true", "false", "1", "0"]:
                    error_data["reason"] = "Value is not a valid boolean (expected true/false/1/0)"
                    errors.append(error_data.copy())  # <-- POPRAWIONO na .copy()

            # 3. Validation via XSD mapping and Ontology Rules
            elif dtype_name in gql_to_xsd:
                try:
                    val_lit = Literal(raw_val, datatype=base_xsd_uri)
                    error_found = False

                    if dtype_name in rules:
                        r = rules[dtype_name]

                        # A. Regex Pattern
                        if r["pattern"] is not None:
                            if not re.fullmatch(r["pattern"], raw_val):
                                error_data["reason"] = f"Value does not match the required ontology pattern: {r['pattern']}"
                                errors.append(error_data.copy())
                                error_found = True

                        # B. String Length Constraints
                        if not error_found and r["exact_len"] is not None and len(raw_val) != r["exact_len"]:
                            error_data["reason"] = f"String length ({len(raw_val)}) does not match the exact required length ({r['exact_len']})"
                            errors.append(error_data.copy())
                            error_found = True

                        if not error_found and r["min_len"] is not None and len(raw_val) < r["min_len"]:
                            error_data["reason"] = f"String length ({len(raw_val)}) is below the minimum allowed ({r['min_len']})"
                            errors.append(error_data.copy())
                            error_found = True

                        if not error_found and r["max_len"] is not None and len(raw_val) > r["max_len"]:
                            error_data["reason"] = f"String length ({len(raw_val)}) exceeds the maximum allowed ({r['max_len']})"
                            errors.append(error_data.copy())
                            error_found = True

                        if not error_found and val_lit.ill_typed:
                            error_data[
                                "reason"] = f"Lexical form '{raw_val}' is not valid for XSD data format ({base_xsd_str})"
                            errors.append(error_data.copy())
                            error_found = True

                        if not error_found and (r["min"] is not None or r["max"] is not None):
                            val_num = val_lit.value
                            if val_num is not None:
                                if r["min"] is not None and val_num < r["min"]:
                                    error_data[
                                        "reason"] = f"Value ({val_num}) is below the allowed minimum ({r['min']})"
                                    errors.append(error_data.copy())
                                    error_found = True
                                elif r["max"] is not None and val_num > r["max"]:
                                    error_data[
                                        "reason"] = f"Value ({val_num}) is above the allowed maximum ({r['max']})"
                                    errors.append(error_data.copy())
                                    error_found = True

                except Exception as e:
                    error_data["reason"] = f"Data verification error: {e}"
                    errors.append(error_data.copy())  # <-- POPRAWIONO na .copy()

            # 4. Unknown type
            else:
                error_data["reason"] = "Type was neither recognized nor explicitly mapped in the validator"
                errors.append(error_data.copy())  # <-- POPRAWIONO na .copy()

            if len(errors) > initial_errors_len:
                invalid_literals_count += 1

    print(f"\nErrors found: {len(errors)}\n")
    for idx, err in enumerate(errors, 1):
        print(f"Error #{idx}:")
        print(f"   - subject:   {err['subject']}")
        print(f"   - predicate: {err['predicate']}")
        print(f"   - value:     {err['value']}")
        print(f"   - reason:    {err['reason']}")
        print("-" * 60)

    if total_literals > 0:
        correct_count = total_literals - invalid_literals_count
        error_percent = (invalid_literals_count / total_literals) * 100
        correct_percent = (correct_count / total_literals) * 100

        print("\n" + "=" * 60)
        print("VALIDATION STATISTICAL SUMMARY")
        print("=" * 60)
        print(f"Total literals evaluated: {total_literals}")
        print(f"Valid literals:   {correct_count} ({correct_percent:.1f}%)")
        print(f"Invalid literals: {invalid_literals_count} ({error_percent:.1f}%)")
        print(f"Total error triggers: {len(errors)}")
        print("=" * 60)

        csv_filename = f"{report_prefix}.csv"
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['subject', 'predicate', 'value', 'original_dt', 'base_dt', 'reason']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(errors)
        print(f"\n[Export] Detailed error list saved to: {csv_filename}")

        json_filename = f"{report_prefix}.json"
        report_data = {
            "summary": {
                "total_literals_evaluated": total_literals,
                "valid_literals_count": correct_count,
                "invalid_literals_count": invalid_literals_count,
                "total_error_triggers": len(errors),
                "error_rate_percent": round(error_percent, 2)
            },
            "errors": errors
        }
        with open(json_filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(report_data, jsonfile, indent=4, ensure_ascii=False)
        print(f"[Export] Full report with summary saved to: {json_filename}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GQL Datatypes RDF Validator")
    parser.add_argument("-d", "--data", default="test_data.ttl", help="RDF data file to validate")
    parser.add_argument("-o", "--ontology", default="gql_datatypes.ttl", help="GQL ontology TTL file")
    parser.add_argument("-p", "--report-prefix", default="validation_report", help="Prefix for the output report files")

    args = parser.parse_args()

    print("=== GQL Datatypes RDF Validator ===")
    print(f"Ontology file: {args.ontology}")
    print(f"Data file:     {args.data}")
    print(f"Report prefix: {args.report_prefix}.[csv|json]")
    print("-" * 60)

    validate_data(args.data, args.ontology, args.report_prefix)