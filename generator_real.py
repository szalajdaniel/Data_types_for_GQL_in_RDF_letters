import argparse
import sys
import random
import json
from rdflib import Graph, Namespace, Literal
from faker import Faker
import os

EX = Namespace("http://example.org/data#")
GQL = Namespace("http://example.org/gql-types#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
SCHEMA = Namespace("https://schema.org/")
DC = Namespace("http://purl.org/dc/elements/1.1/")

# Default probability of a field being present for a patient (1.0 = 100% chance)
DEFAULT_PROBS = {
    "age": 0.90,
    "birthDate": 0.85,
    "weight": 0.80,
    "height": 0.75,
    "requiresHealthPlan": 0.90,
    "dateAdmitted": 0.70,
    "arrivalTime": 0.60,
    "identifier": 0.80,
    "prescription": 0.65,
    "gender": 0.85,
    "duration": 0.50,
    "baseSalary": 0.40,
    "vector": 0.30,
    "unit_record": 0.30,  # Added for UNIT_RECORD testing
    "unknown_type": 0.10  # Overall chance to insert a completely unrecognized mapping
}


def get_val(valid_val, invalid_val, error_rate):
    return invalid_val if random.random() < error_rate else valid_val


def generate_patient_data(output_file, num_records, error_rate, field_probs):
    fake = Faker('en_US')
    g = Graph()

    g.bind("ex", EX)
    g.bind("gql", GQL)
    g.bind("foaf", FOAF)
    g.bind("schema", SCHEMA)
    g.bind("dc", DC)

    drugs_list = ["Paracetamol", "Ibuprofen", "Insulin", "Amoxicillin", "Aspirin", "Omeprazole"]

    for i in range(num_records):
        patient = EX[f"Patient_{i}"]

        # Mandatory
        g.add((patient, FOAF.name, Literal(fake.name(), datatype=GQL.STRING)))

        # Optional fields based on parameterized probabilities
        if random.random() < field_probs.get("age", 0.0):
            age_valid = str(fake.random_int(1, 100))
            age_invalid = str(random.choice([-10, 300]))
            g.add((patient, FOAF.age, Literal(get_val(age_valid, age_invalid, error_rate), datatype=GQL.UINT8)))

        if random.random() < field_probs.get("birthDate", 0.0):
            date_valid = fake.date_of_birth(minimum_age=1, maximum_age=100).strftime("%Y-%m-%d")
            date_invalid = fake.date_of_birth().strftime("%d-%m-%Y")
            g.add(
                (patient, SCHEMA.birthDate, Literal(get_val(date_valid, date_invalid, error_rate), datatype=GQL.DATE)))

        if random.random() < field_probs.get("weight", 0.0):
            weight_valid = f"{random.uniform(40.0, 120.0):.1f}"
            weight_invalid = weight_valid.replace(".", ",")
            g.add((patient, SCHEMA.weight,
                   Literal(get_val(weight_valid, weight_invalid, error_rate), datatype=GQL.FLOAT)))

        if random.random() < field_probs.get("height", 0.0):
            height_valid = str(fake.random_int(100, 220))
            height_invalid = str(random.choice([-40000, 40000]))
            g.add((patient, SCHEMA.height,
                   Literal(get_val(height_valid, height_invalid, error_rate), datatype=GQL.INT16)))

        if random.random() < field_probs.get("requiresHealthPlan", 0.0):
            bool_valid = random.choice(["true", "false", "1", "0"])
            bool_invalid = random.choice(["yes", "no", "TRUE"])
            g.add((patient, SCHEMA.requiresHealthPlan,
                   Literal(get_val(bool_valid, bool_invalid, error_rate), datatype=GQL.BOOLEAN)))

        if random.random() < field_probs.get("dateAdmitted", 0.0):
            ts_valid = fake.date_time_this_year().strftime("%Y-%m-%dT%H:%M:%S")
            ts_invalid = fake.date_time_this_year().strftime("%Y-%m-%d %H:%M:%S")
            g.add((patient, SCHEMA.dateAdmitted,
                   Literal(get_val(ts_valid, ts_invalid, error_rate), datatype=GQL.TIMESTAMP)))

        if random.random() < field_probs.get("arrivalTime", 0.0):
            time_valid = fake.time()
            time_invalid = fake.time().replace(":", "-")
            g.add((patient, SCHEMA.arrivalTime,
                   Literal(get_val(time_valid, time_invalid, error_rate), datatype=GQL.LOCAL_TIME)))

        if random.random() < field_probs.get("identifier", 0.0):
            bin_valid = fake.hexify(text="^^")  # Exact length 2 (1 byte)
            bin_invalid = fake.hexify(text="^^^^")  # Will fail exact_len requirement
            g.add((patient, DC.identifier, Literal(get_val(bin_valid, bin_invalid, error_rate), datatype=GQL.BINARY)))

        if random.random() < field_probs.get("prescription", 0.0):
            prescribed = random.sample(drugs_list, k=random.randint(1, 3))
            arr_valid = json.dumps(prescribed)
            arr_invalid = '{"drug": "Ibuprofen"}'  # Fails because it's a dict, not a list
            g.add((patient, SCHEMA.prescription,
                   Literal(get_val(arr_valid, arr_invalid, error_rate), datatype=GQL.ARRAY)))

        if random.random() < field_probs.get("gender", 0.0):
            gender_valid = random.choice(["M", "F", "X"])
            gender_invalid = random.choice(["Male", "Female", "Unknown"])
            g.add((patient, FOAF.gender, Literal(get_val(gender_valid, gender_invalid, error_rate), datatype=GQL.CHAR)))

        if random.random() < field_probs.get("duration", 0.0):
            dur_valid = f"P{random.randint(0, 5)}Y{random.randint(1, 11)}M"
            dur_invalid = f"{random.randint(1, 5)} years and {random.randint(1, 11)} months"
            g.add((patient, SCHEMA.duration,
                   Literal(get_val(dur_valid, dur_invalid, error_rate), datatype=GQL.DURATION_YEAR_TO_MONTH)))

        if random.random() < field_probs.get("baseSalary", 0.0):
            cost_valid = f"{random.uniform(500.0, 5000.0):.2f}"
            cost_invalid = f"{random.uniform(500.0, 5000.0):.2f}".replace(".", ",")
            g.add((patient, SCHEMA.baseSalary,
                   Literal(get_val(cost_valid, cost_invalid, error_rate), datatype=GQL.DECIMAL)))

        if random.random() < field_probs.get("vector", 0.0):
            vector_valid = json.dumps([round(random.random(), 3) for _ in range(3)])
            vector_invalid = '{"x": 1.0, "y": 2.0}'  # Fails because it's a dict, not a list
            g.add((patient, SCHEMA.Vector,
                   Literal(get_val(vector_valid, vector_invalid, error_rate), datatype=GQL.VECTOR)))

        if random.random() < field_probs.get("unit_record", 0.0):
            unit_valid = json.dumps({})
            unit_invalid = json.dumps({"status": "active"})  # Fails because it's not empty
            g.add((patient, EX.metadata,
                   Literal(get_val(unit_valid, unit_invalid, error_rate), datatype=GQL.UNIT_RECORD)))

        if random.random() < field_probs.get("unknown_type", 0.0):
            g.add((patient, EX.testField, Literal("123", datatype=GQL.UNKNOWN_TYPE)))

    g.serialize(destination=output_file, format="turtle")
    print("-" * 50)
    print(f"[Generator] Finished successfully!")
    print(f"[Generator] Saved {num_records} patient records to: {output_file}")
    print(f"[Generator] Error rate applied: {error_rate * 100}%")
    print("-" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RDF Patient Data Generator")
    parser.add_argument("-o", "--output", default="test_data.ttl", help="Output file path")
    parser.add_argument("-c", "--count", type=int, help="Number of records")
    parser.add_argument("-e", "--error-rate", type=float, help="Percentage of invalid data (0-100)")
    parser.add_argument("--config", type=str, help="Path to a JSON file overriding field probabilities")
    args = parser.parse_args()

    # Load custom probabilities if provided
    active_probs = DEFAULT_PROBS.copy()
    if args.config:
        if os.path.exists(args.config):
            with open(args.config, 'r') as f:
                custom_probs = json.load(f)
                active_probs.update(custom_probs)
                print(f"Loaded custom field probabilities from {args.config}")
        else:
            print(f"Warning: Config file {args.config} not found. Using defaults.")

    print("=== RDF Patient Data Generator ===")

    error_rate_pct = args.error_rate
    if error_rate_pct is None:
        while True:
            try:
                err_input = input("Enter the percentage of invalid data (e.g. 20 for 20%): ")
                error_rate_pct = float(err_input)
                if 0 <= error_rate_pct <= 100:
                    break
                else:
                    print("Please enter a value between 0 and 100.")
            except ValueError:
                print("Invalid input.")

    error_rate = error_rate_pct / 100.0

    num_records = args.count
    if num_records is None:
        while True:
            try:
                count_input = input("Enter the number of records to generate (e.g. 1000): ")
                num_records = int(count_input)
                if num_records > 0:
                    break
                else:
                    print("Please enter a positive integer.")
            except ValueError:
                print("Invalid input.")

    generate_patient_data(args.output, num_records, error_rate, active_probs)