import random
import json
from rdflib import Graph, Namespace, Literal
from faker import Faker

# =====================================================================
# NAMESPACES (Using real Semantic Web vocabularies)
# =====================================================================
EX = Namespace("http://example.org/data#")
GQL = Namespace("http://example.org/gql-types#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
SCHEMA = Namespace("https://schema.org/")
DC = Namespace("http://purl.org/dc/elements/1.1/")


def get_val(valid_val, invalid_val, error_rate):

    return invalid_val if random.random() < error_rate else valid_val


def generate_patient_data(output_file, num_records, error_rate):
    # Initialize Faker with default English locale
    fake = Faker('en_US')
    g = Graph()

    # Bind prefixes to make the .ttl file readable
    g.bind("ex", EX)
    g.bind("gql", GQL)
    g.bind("foaf", FOAF)
    g.bind("schema", SCHEMA)
    g.bind("dc", DC)

    drugs_list = ["Paracetamol", "Ibuprofen", "Insulin", "Amoxicillin", "Aspirin", "Omeprazole"]

    for i in range(num_records):
        # Patient URI
        patient = EX[f"Patient_{i}"]

        # ---------------------------------------------------------------------
        # MANDATORY PROPERTY (Every patient has a name)
        # ---------------------------------------------------------------------
        # 1. STRING
        g.add((patient, FOAF.name, Literal(fake.name(), datatype=GQL.STRING)))

        # ---------------------------------------------------------------------
        # OPTIONAL PROPERTIES (Irregular data - randomly skipped)
        # ---------------------------------------------------------------------

        # 2. UINT8 (Age) - 90% chance to be included
        if random.random() < 0.90:
            age_valid = str(fake.random_int(1, 100))
            age_invalid = str(random.choice([-10, 300]))  # Negative or out of bounds for UINT8
            g.add((patient, FOAF.age, Literal(get_val(age_valid, age_invalid, error_rate), datatype=GQL.UINT8)))

        # 3. DATE (Birth Date) - 85% chance
        if random.random() < 0.85:
            date_valid = fake.date_of_birth(minimum_age=1, maximum_age=100).strftime("%Y-%m-%d")
            date_invalid = fake.date_of_birth().strftime("%d-%m-%Y")  # Invalid ISO format
            g.add(
                (patient, SCHEMA.birthDate, Literal(get_val(date_valid, date_invalid, error_rate), datatype=GQL.DATE)))

        # 4. FLOAT (Weight) - 80% chance
        if random.random() < 0.80:
            weight_valid = f"{random.uniform(40.0, 120.0):.1f}"
            weight_invalid = weight_valid.replace(".", ",")  # Comma instead of dot
            g.add((patient, SCHEMA.weight,
                   Literal(get_val(weight_valid, weight_invalid, error_rate), datatype=GQL.FLOAT)))

        # 5. INT16 (Height in cm) - 75% chance
        if random.random() < 0.75:
            height_valid = str(fake.random_int(100, 220))
            height_invalid = str(random.choice([-40000, 40000]))  # Exceeds 16-bit limits (-32768 to 32767)
            g.add((patient, SCHEMA.height,
                   Literal(get_val(height_valid, height_invalid, error_rate), datatype=GQL.INT16)))

        # 6. BOOLEAN (Requires health plan / Insurance) - 90% chance
        if random.random() < 0.90:
            bool_valid = random.choice(["true", "false", "1", "0"])
            bool_invalid = random.choice(["yes", "no", "TRUE"])  # Invalid words
            g.add((patient, SCHEMA.requiresHealthPlan,
                   Literal(get_val(bool_valid, bool_invalid, error_rate), datatype=GQL.BOOLEAN)))

        # 7. TIMESTAMP (Admission Date & Time) - 70% chance
        if random.random() < 0.70:
            ts_valid = fake.date_time_this_year().strftime("%Y-%m-%dT%H:%M:%S")
            ts_invalid = fake.date_time_this_year().strftime("%Y-%m-%d %H:%M:%S")  # Missing 'T'
            g.add((patient, SCHEMA.dateAdmitted,
                   Literal(get_val(ts_valid, ts_invalid, error_rate), datatype=GQL.TIMESTAMP)))

        # 8. LOCAL_TIME (Time of arrival) - 60% chance
        if random.random() < 0.60:
            time_valid = fake.time()  # Generates HH:MM:SS
            time_invalid = fake.time().replace(":", "-")  # Invalid separator
            g.add((patient, SCHEMA.arrivalTime,
                   Literal(get_val(time_valid, time_invalid, error_rate), datatype=GQL.LOCAL_TIME)))

        # 9. BINARY (Hospital bracelet ID / Hex) - 80% chance
        if random.random() < 0.80:
            bin_valid = fake.hexify(text="^^^^")  # 4 characters (even number is valid hex)
            bin_invalid = fake.hexify(text="^^^")  # 3 characters (odd number throws ill_typed)
            g.add((patient, DC.identifier, Literal(get_val(bin_valid, bin_invalid, error_rate), datatype=GQL.BINARY)))

        # 10. ARRAY (Prescribed drugs JSON) - 65% chance
        if random.random() < 0.65:
            prescribed = random.sample(drugs_list, k=random.randint(1, 3))
            arr_valid = json.dumps(prescribed)
            arr_invalid = '{"drug": "Ibuprofen"}'  # Valid JSON, but it's an Object, not an Array
            g.add((patient, SCHEMA.prescription,
                   Literal(get_val(arr_valid, arr_invalid, error_rate), datatype=GQL.ARRAY)))

        # 11. CHAR (Gender) - 85% chance
        if random.random() < 0.85:
            gender_valid = random.choice(["M", "F", "X"])
            gender_invalid = random.choice(["Male", "Female", "Unknown"])  # Exceeds maxLength=1
            g.add((patient, FOAF.gender, Literal(get_val(gender_valid, gender_invalid, error_rate), datatype=GQL.CHAR)))

        # 12. DURATION_YEAR_TO_MONTH (Treatment duration) - 50% chance
        if random.random() < 0.50:
            dur_valid = f"P{random.randint(0, 5)}Y{random.randint(1, 11)}M"  # e.g., P1Y6M
            dur_invalid = f"{random.randint(1, 5)} years and {random.randint(1, 11)} months"  # Invalid pattern
            g.add((patient, SCHEMA.duration,
                   Literal(get_val(dur_valid, dur_invalid, error_rate), datatype=GQL.DURATION_YEAR_TO_MONTH)))

        # 13. DECIMAL (Treatment cost) - 40% chance
        if random.random() < 0.40:
            cost_valid = f"{random.uniform(500.0, 5000.0):.2f}"
            cost_invalid = f"{random.uniform(500.0, 5000.0):.2f}".replace(".", ",")  # Comma instead of dot
            g.add((patient, SCHEMA.baseSalary,
                   Literal(get_val(cost_valid, cost_invalid, error_rate), datatype=GQL.DECIMAL)))

        # 14. VECTOR (Patient health embedding vector) - 30% chance
        if random.random() < 0.30:
            vector_valid = json.dumps([round(random.random(), 3) for _ in range(3)])  # e.g., [0.123, 0.456, 0.789]
            vector_invalid = "[0.123, 0.456, "  # Syntax error (truncated JSON array)
            g.add((patient, SCHEMA.Vector,
                   Literal(get_val(vector_valid, vector_invalid, error_rate), datatype=GQL.VECTOR)))

        # ---------------------------------------------------------------------
        # UNKNOWN DATATYPE ERROR (Simulate mapping mismatch)
        # ---------------------------------------------------------------------
        if random.random() < error_rate:
            g.add((patient, EX.testField, Literal("123", datatype=GQL.UNKNOWN_TYPE)))

    g.serialize(destination=output_file, format="turtle")
    print("-" * 50)
    print(f"[Generator] Finished successfully!")
    print(f"[Generator] Saved {num_records} patient records to: {output_file}")
    print(f"[Generator] Error rate applied: {error_rate * 100}%")
    print("-" * 50)


if __name__ == "__main__":
    print("=== RDF Patient Data Generator ===")

    # 1. Pytanie o procent błędów (z pętlą sprawdzającą poprawność wpisania)
    while True:
        try:
            err_input = input("Enter the percentage of invalid data (e.g. 20 for 20%): ")
            error_rate_pct = float(err_input)
            if 0 <= error_rate_pct <= 100:
                error_rate = error_rate_pct / 100.0
                break
            else:
                print("Please enter a value between 0 and 100.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # 2. Pytanie o liczbę rekordów
    while True:
        try:
            count_input = input("Enter the number of patient records to generate (e.g. 1000): ")
            num_records = int(count_input)
            if num_records > 0:
                break
            else:
                print("Please enter a positive integer.")
        except ValueError:
            print("Invalid input. Please enter a whole number.")

    output_file = "test_data.ttl"

    print(f"\nGenerating {num_records} records with a {error_rate_pct}% error rate...")
    generate_patient_data(output_file, num_records, error_rate)