import logging
import json
import warnings
import re  # <--- DODANO: Biblioteka do obsługi wyrażeń regularnych (pattern)
from rdflib import Graph, Literal, XSD, RDF, OWL

# Suppress warnings from rdflib
warnings.filterwarnings("ignore", category=UserWarning, module="rdflib")
logging.getLogger("rdflib").setLevel(logging.ERROR)

# =====================================================================
# EXPLICIT TYPE MAPPING TO XSD
# Structural types (JSON) are excluded from XSD mapping.
# =====================================================================
GQL_TO_XSD = {
    "BOOLEAN": XSD.boolean, "BOOL": XSD.boolean,
    "STRING": XSD.string, "VARCHAR": XSD.string, "CHAR": XSD.string,
    "VARBINARY": XSD.hexBinary, "BYTES": XSD.hexBinary, "BINARY": XSD.hexBinary,
    "INT": XSD.integer, "BIGINT": XSD.integer, "SMALLINT": XSD.integer, "INTEGER": XSD.integer,
    "SIGNED_INTEGER": XSD.integer, "BIG_INTEGER": XSD.integer, "SIGNED_BIG_INTEGER": XSD.integer,
    "SMALL_INTEGER": XSD.integer, "SIGNED_SMALL_INTEGER": XSD.integer,
    "UINT": XSD.nonNegativeInteger, "UBIGINT": XSD.nonNegativeInteger, "USMALLINT": XSD.nonNegativeInteger,
    "UNSIGNED_INTEGER": XSD.nonNegativeInteger, "UNSIGNED_BIG_INTEGER": XSD.nonNegativeInteger,
    "UNSIGNED_SMALL_INTEGER": XSD.nonNegativeInteger,
    "INT8": XSD.byte, "INT16": XSD.short, "INT32": XSD.int, "INT64": XSD.long,
    "INT128": XSD.integer, "INT256": XSD.integer,
    "UINT8": XSD.unsignedByte, "UINT16": XSD.unsignedShort, "UINT32": XSD.unsignedInt,
    "UINT64": XSD.unsignedLong, "UINT128": XSD.nonNegativeInteger, "UINT256": XSD.nonNegativeInteger,
    "DECIMAL": XSD.decimal, "DEC": XSD.decimal,
    "FLOAT": XSD.double, "REAL": XSD.double, "DOUBLE": XSD.double, "DOUBLE_PRECISION": XSD.double,
    "FLOAT16": XSD.float, "FLOAT32": XSD.float, "FLOAT64": XSD.double, "FLOAT128": XSD.double, "FLOAT256": XSD.double,
    "DATE": XSD.date,
    "LOCAL_TIME": XSD.time, "TIME_WITHOUT_TIME_ZONE": XSD.time,
    "ZONED_TIME": XSD.time, "TIME_WITH_TIME_ZONE": XSD.time,
    "LOCAL_DATETIME": XSD.dateTime, "TIMESTAMP": XSD.dateTime, "TIMESTAMP_WITHOUT_TIME_ZONE": XSD.dateTime,
    "ZONED_DATETIME": XSD.dateTime, "TIMESTAMP_WITH_TIME_ZONE": XSD.dateTime,
    "DURATION_YEAR_TO_MONTH": XSD.duration, "DURATION_DAY_TO_SECOND": XSD.duration
}

JSON_TYPES = [
    "LIST", "ARRAY", "GROUP_LIST", "GROUP_ARRAY",
    "RECORD", "ANY_RECORD", "UNIT_RECORD", "VECTOR"
]


def build_rules(ont_g):
    rules = {}
    for dt in ont_g.subjects(RDF.type, None):
        name = str(dt).split('#')[-1]
        # DODANO: Nowe klucze dla długości tekstu i wzorców
        rules[name] = {"min": None, "max": None, "min_len": None, "max_len": None, "pattern": None}

        for restr in ont_g.objects(dt, OWL.withRestrictions):
            curr = restr
            while curr and curr != RDF.nil:
                first = ont_g.value(curr, RDF.first)
                if first:
                    if (min_v := ont_g.value(first, XSD.minInclusive)): rules[name]["min"] = float(str(min_v))
                    if (max_v := ont_g.value(first, XSD.maxInclusive)): rules[name]["max"] = float(str(max_v))
                    # DODANO: Pobieranie restrykcji tekstowych i wyrażeń regularnych
                    if (min_l := ont_g.value(first, XSD.minLength)): rules[name]["min_len"] = int(str(min_l))
                    if (max_l := ont_g.value(first, XSD.maxLength)): rules[name]["max_len"] = int(str(max_l))
                    if (pat := ont_g.value(first, XSD.pattern)): rules[name]["pattern"] = str(pat)
                curr = ont_g.value(curr, RDF.rest)
    return rules


def validate_data(data_file, ontology_file):
    ont_g = Graph().parse(ontology_file, format="turtle")
    rules = build_rules(ont_g)
    data_g = Graph().parse(data_file, format="turtle")

    errors = []
    total_literals = 0

    for s, p, o in data_g:
        if isinstance(o, Literal) and o.datatype:
            total_literals += 1

            dtype_name = str(o.datatype).split('#')[-1]
            raw_val = str(o)

            base_xsd_uri = GQL_TO_XSD.get(dtype_name)
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
            elif dtype_name in GQL_TO_XSD:
                try:
                    val_lit = Literal(raw_val, datatype=base_xsd_uri)
                    error_found = False

                    # KROK 1: Najpierw sprawdzamy precyzyjne reguły z ontologii (.ttl)
                    if dtype_name in rules:
                        r = rules[dtype_name]

                        # A. Sprawdzanie wyrażeń regularnych (Pattern check)
                        if r["pattern"] is not None:
                            if not re.fullmatch(r["pattern"], raw_val):
                                error_data[
                                    "reason"] = f"Value does not match the required ontology pattern: {r['pattern']}"
                                errors.append(error_data.copy())
                                error_found = True

                        # B. Sprawdzanie długości (String length boundaries check)
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

                        # C. Sprawdzanie limitów numerycznych (Numerical boundaries check)
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
                                pass  # Omijamy błąd float(), bo ill_typed złapie zły format poniżej

                    # KROK 2: Jeśli ontologia nie zgłosiła błędu, używamy mechanizmu ill_typed (Fallback)
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