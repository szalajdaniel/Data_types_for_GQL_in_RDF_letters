import argparse
import random
import json
from rdflib import Graph, Namespace, Literal
from faker import Faker

EX = Namespace("http://example.org/data#")
GQL = Namespace("http://example.org/gql-types#")


def get_val(valid_val, invalid_val):

    return valid_val if random.random() > 0.1 else invalid_val


def generate_comprehensive_data(output_file, num_records):
    fake = Faker()
    g = Graph()
    g.bind("ex", EX)
    g.bind("gql", GQL)

    # --- DEFINICJE WSZYSTKICH KATEGORII TYPÓW GQL ---

    types_logic = ["BOOLEAN", "BOOL"]
    types_string = ["STRING", "VARCHAR"]
    types_char = ["CHAR"]  # Wymaga max 1 znaku

    types_bin_var = ["VARBINARY", "BYTES"]
    types_bin_strict = ["BINARY"]  # Wymaga dokładnie 2 znaków hex

    types_int_any = ["INT", "BIGINT", "SMALLINT", "INTEGER", "SIGNED_INTEGER",
                     "BIG_INTEGER", "SIGNED_BIG_INTEGER", "SMALL_INTEGER", "SIGNED_SMALL_INTEGER"]
    types_uint_any = ["UINT", "UBIGINT", "USMALLINT", "UNSIGNED_INTEGER",
                      "UNSIGNED_BIG_INTEGER", "UNSIGNED_SMALL_INTEGER"]

    types_decimal = ["DECIMAL", "DEC"]
    types_float = ["FLOAT", "REAL", "DOUBLE", "DOUBLE_PRECISION", "FLOAT16",
                   "FLOAT32", "FLOAT64", "FLOAT128", "FLOAT256"]

    # Typy liczbowe o zdefiniowanej precyzji bitowej (Typ, Min, Max)
    fixed_ints = [
        ("INT8", -128, 127), ("INT16", -32768, 32767), ("INT32", -2147483648, 2147483647),
        ("INT64", -9223372036854775808, 9223372036854775807),
        ("INT128", -10 ** 30, 10 ** 30), ("INT256", -10 ** 50, 10 ** 50)
    ]
    fixed_uints = [
        ("UINT8", 0, 255), ("UINT16", 0, 65535), ("UINT32", 0, 4294967295),
        ("UINT64", 0, 18446744073709551615),
        ("UINT128", 0, 10 ** 30), ("UINT256", 0, 10 ** 50)
    ]

    types_date = ["DATE"]
    types_local_time = ["LOCAL_TIME", "TIME_WITHOUT_TIME_ZONE"]
    types_zoned_time = ["ZONED_TIME", "TIME_WITH_TIME_ZONE"]
    types_local_dt = ["LOCAL_DATETIME", "TIMESTAMP", "TIMESTAMP_WITHOUT_TIME_ZONE"]
    types_zoned_dt = ["ZONED_DATETIME", "TIMESTAMP_WITH_TIME_ZONE"]

    types_dur_y2m = ["DURATION_YEAR_TO_MONTH"]
    types_dur_d2s = ["DURATION_DAY_TO_SECOND"]

    types_arrays = ["LIST", "ARRAY", "GROUP_LIST", "GROUP_ARRAY"]
    types_records = ["RECORD", "ANY_RECORD"]
    types_unit_record = ["UNIT_RECORD"]  # Musi być pustym JSON: {}
    types_vectors = ["VECTOR"]

    # --- PĘTLA GENERUJĄCA ---
    for i in range(num_records):
        subject = EX[f"Entity_{i}"]

        # 1. LOGICZNE
        for t in types_logic:
            val = get_val(random.choice(["TRUE", "FALSE", "1", "0"]), "prawda")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 2. ZNAKOWE
        for t in types_string:
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(fake.word(), datatype=GQL[t])))
        for t in types_char:
            val = get_val(fake.lexify("?"), fake.lexify("???"))  # 1 znak vs 3 znaki
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 3. BINARNE
        for t in types_bin_var:
            val = get_val(fake.hexify(text="^^^"), "not_hex!")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_bin_strict:
            val = get_val(fake.hexify(text="^^"), "A1B2")  # Dokładnie 2 znaki vs 4 znaki
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 4. CAŁKOWITE (BEZ ZDEFINIOWANYCH GRANIC)
        for t in types_int_any:
            val = get_val(str(fake.random_int(-1000, 1000)), "abc")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_uint_any:
            val = get_val(str(fake.random_int(0, 1000)), str(fake.random_int(-1000, -1)))  # Ujemne jako błąd
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 5. CAŁKOWITE BITOWE (Fasety min/max)
        for t, min_v, max_v in fixed_ints:
            val = get_val(str(random.randint(min_v, max_v)), str(max_v + 500))  # W 20% przekraczamy max
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t, min_v, max_v in fixed_uints:
            val = get_val(str(random.randint(min_v, max_v)), str(min_v - 500))  # W 20% schodzimy poniżej min (ujemne)
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 6. ZMIENNOPRZECINKOWE I STAŁOPOZYCYJNE
        for t in types_decimal:
            val = get_val(f"{random.uniform(-100, 100):.2f}", "100,50")  # Przecinek to błąd
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_float:
            val = get_val(f"{random.uniform(-10, 10):.3e}", "brak_liczby")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 7. CZASOWE
        for t in types_date:
            val = get_val(fake.date(), "Data: dzisiaj")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_local_time:
            val = get_val("14:30:00", "14-30-00")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_zoned_time:
            val = get_val("14:30:00+02:00", "14:30:00")  # Brak strefy jako błąd
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_local_dt:
            val = get_val("2026-05-22T14:30:00", "2026-05-22 14:30:00")  # Brak litery T
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_zoned_dt:
            val = get_val("2026-05-22T14:30:00Z", "2026-05-22T14:30:00")  # Brak Z/Offsetu
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 8. INTERWAŁOWE
        for t in types_dur_y2m:
            val = get_val("P2Y6M", "2 lata 6 miesiecy")
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_dur_d2s:
            val = get_val("P1DT12H30M0S", "P1D")  # Brakuje literki T i godzin
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 9. ZŁOŻONE (JSON)
        for t in types_arrays:
            val = get_val(json.dumps([1, 2, 3]), '{"a": 1}')  # Słownik to błąd dla tablicy
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_records:
            val = get_val(json.dumps({"key": "val"}), '["key", "val"]')  # Tablica to błąd dla rekordu
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_unit_record:
            val = get_val("{}", '{"pole": 1}')  # Musi być idealnie puste {}
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))
        for t in types_vectors:
            val = get_val(json.dumps([0.1, 0.5, 0.9]), "[0.1, 0.5, ")  # Ucięty składniowo JSON
            g.add((subject, EX[f"prop_{t.lower()}"], Literal(val, datatype=GQL[t])))

        # 10. TEST BRAKU MAPOWANIA
        if random.random() < 0.1:
            g.add((subject, EX.prop_unknown, Literal("test", datatype=GQL.SOME_WEIRD_TYPE)))

    g.serialize(destination=output_file, format="turtle")
    print(f"[Generator] Zakończono! Plik {output_file} !")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="test_data.ttl", help="Plik wyjściowy")
    parser.add_argument("--count", type=int, default=10, help="Liczba generowanych encji")
    args = parser.parse_args()
    generate_comprehensive_data(args.output, args.count)