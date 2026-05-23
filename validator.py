import logging
import json
import warnings
import re
from rdflib import Graph, Literal, XSD, RDF, OWL

# Suppress warnings from rdflib
warnings.filterwarnings("ignore", category=UserWarning, module="rdflib")
logging.getLogger("rdflib").setLevel(logging.ERROR)

JSON_TYPES = [
    "LIST", "ARRAY", "GROUP_LIST", "GROUP_ARRAY",
    "RECORD", "ANY_RECORD", "UNIT_RECORD", "VECTOR"
]


def build_xsd_mapping(ont_g):

    mapping = {}

    # KROK 1: Odczyt bezpośrednich mapowań do XSD (np. gql:INT -> xsd:integer)
    for s, p, o in ont_g.triples((None, OWL.equivalentClass, None)):
        if str(o).startswith(str(XSD)) or str(o).startswith(str(RDF)):
            name = str(s).split('#')[-1]
            mapping[name] = o

    # KROK 2: Odczyt aliasów (np. gql:INTEGER -> gql:INT -> xsd:integer)
    for s, p, o in ont_g.triples((None, OWL.equivalentClass, None)):
        if str(o).startswith("http://example.org/gql-types#"):
            alias_name = str(s).split('#')[-1]
            target_name = str(o).split('#')[-1]
            if target_name in mapping:
                mapping[alias_name] = mapping[target_name]

    return mapping


def build_rules(ont_g):
    rules = {}
    for dt in ont_g.subjects(RDF.type, None):
        name = str(dt).split('#')[-1]
        rules[name] = {"min": None, "max": None, "min_len": None, "max_len": None, "pattern": None}

        for restr in ont_g.objects(dt, OWL.withRestrictions):
            curr = restr
            while curr and curr != RDF.nil:
                first = ont_g.value(curr, RDF.first)
                if first:
                    if (min_v := ont_g.value(first, XSD.minInclusive)): rules[name]["min"] = float(str(min_v))
                    if (max_v := ont_g.value(first, XSD.maxInclusive)): rules[name]["max"] = float(str(max_v))
                    if (min_l := ont_g.value(first, XSD.minLength)): rules[name]["min_len"] = int(str(min_l))
                    if (max_l := ont_g.value(first, XSD.maxLength)): rules[name]["max_len"] = int(str(max_l))
                    if (pat := ont_g.value(first, XSD.pattern)): rules[name]["pattern"] = str(pat)
                curr = ont_g.value(curr, RDF.rest)
    return rules


def validate_data(data_file, ontology_file):
    ont_g = Graph().parse(ontology_file, format="turtle")

    # Ładujemy mapowania z ontologii!
    gql_to_xsd = build_xsd_mapping(ont_g)
    rules = build_rules(ont_g)

    data_g = Graph().parse(data_file, format="turtle")

    errors = []
    total_literals = 0

    for s, p, o in data_g:
        if isinstance(o, Literal) and o.datatype:
            total_literals += 1
            dtype_name = str(o.datatype).split('#')[-1]
            raw_val = str(o)

            # Korzystamy z dynamicznie zbudowanego słownika
            base_xsd_uri = gql_to_xsd.get(dtype_name)
            base_xsd_str = str(base_xsd_uri).split('#')[
                -1] if base_xsd_uri else "No mapping (JSON structure or unknown)"

            error_data = {
                "subject": str(s),
                "predicate": str(p),
                "value": raw_val,
                "original_dt": dtype_name,
                "base_dt": base_xsd_str
            }

            # 1. JSON Validation
            if dtype_name in JSON_TYPES:
                try:
                    json.loads(raw_val)
                except Exception as e:
                    error_data["reason"] = f"JSON format parsing error: {e}"
                    errors.append(error_data)

            # 2. Boolean Validation
            elif dtype_name in ["BOOLEAN", "BOOL"]:
                if raw_val.lower() not in ["true", "false", "1", "0"]:
                    error_data["reason"] = "Value is not a valid boolean (expected true/false/1/0)"
                    errors.append(error_data)

            # 3. Validation via XSD mapping and Ontology Rules
            elif dtype_name in gql_to_xsd:
                try:
                    val_lit = Literal(raw_val, datatype=base_xsd_uri)
                    error_found = False

                    # A. Verify Ontology Rules (min/max, length, pattern)
                    if dtype_name in rules:
                        r = rules[dtype_name]

                        if r["pattern"] is not None:
                            if not re.fullmatch(r["pattern"], raw_val):
                                error_data[
                                    "reason"] = f"Value does not match the required ontology pattern: {r['pattern']}"
                                errors.append(error_data.copy())
                                error_found = True

                        if not error_found and r["min_len"] is not None and len(raw_val) < r["min_len"]:
                            error_data[
                                "reason"] = f"String length ({len(raw_val)}) is below the minimum allowed ({r['min_len']})"
                            errors.append(error_data.copy())
                            error_found = True

                        if not error_found and r["max_len"] is not None and len(raw_val) > r["max_len"]:
                            error_data[
                                "reason"] = f"String length ({len(raw_val)}) exceeds the maximum allowed ({r['max_len']})"
                            errors.append(error_data.copy())
                            error_found = True

                        if not error_found and (r["min"] is not None or r["max"] is not None):
                            try:
                                val_float = float(raw_val)
                                if r["min"] is not None and val_float < r["min"]:
                                    error_data["reason"] = f"Value is below the allowed minimum ({r['min']})"
                                    errors.append(error_data.copy())
                                    error_found = True
                                elif r["max"] is not None and val_float > r["max"]:
                                    error_data["reason"] = f"Value is above the allowed maximum ({r['max']})"
                                    errors.append(error_data.copy())
                                    error_found = True
                            except ValueError:
                                pass

                                # B. Strict format check via ill_typed mechanism
                    if not error_found and val_lit.ill_typed:
                        error_data["reason"] = f"Lexical form is not valid for XSD data format ({base_xsd_str})"
                        errors.append(error_data.copy())

                except Exception as e:
                    error_data["reason"] = f"Data verification error: {e}"
                    errors.append(error_data)

            # 4. Unknown type
            else:
                error_data["reason"] = "Type was neither recognized nor explicitly mapped in the validator"
                errors.append(error_data)

    # =====================================================================
    # PRINTING ERROR RESULTS
    # =====================================================================
    print(f"\nErrors found: {len(errors)}\n")
    for idx, err in enumerate(errors, 1):
        print(f"Error #{idx}:")
        print(f"   - subject: {err['subject']}")
        print(f"   - predicate: {err['predicate']}")
        print(f"   - literal value: {err['value']}")
        print(f"   - original datatype: {err['original_dt']}")
        print(f"   - base datatype used for validation: {err['base_dt']}")
        print(f"   - reason: {err['reason']}")
        print("-" * 60)

    # =====================================================================
    # STATISTICAL SUMMARY
    # =====================================================================
    if total_literals > 0:
        error_count = len(errors)
        correct_count = total_literals - error_count

        error_percent = (error_count / total_literals) * 100
        correct_percent = (correct_count / total_literals) * 100

        print("\n" + "=" * 60)
        print("VALIDATION STATISTICAL SUMMARY")
        print("=" * 60)
        print(f"Total literals evaluated: {total_literals}")
        print(f"Valid:   {correct_count} ({correct_percent:.1f}%)")
        print(f"Invalid: {error_count} ({error_percent:.1f}%)")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    validate_data("test_data.ttl", "gql_datatypes.ttl")