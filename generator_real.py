import argparse
import random
import json
from rdflib import Graph, Namespace, Literal
from faker import Faker

EX = Namespace("http://example.org/data#")
GQL = Namespace("http://example.org/gql-types#")

def get_val(valid_val, invalid_val):
    # W 80% (losowa liczba > 0.2) zwraca wartość poprawną
    # W 20% (losowa liczba <= 0.2) zwraca wartość błędną
    return valid_val if random.random() > 0.2 else invalid_val

def generate_patient_data(output_file, num_records):
    fake = Faker('pl_PL')
    g = Graph()
    g.bind("ex", EX)
    g.bind("gql", GQL)

    leki = ["Paracetamol", "Ibuprofen", "Insulina", "Euthyrox", "Ketonal", "Amoksycylina"]

    for i in range(num_records):
        pacjent = EX[f"Pacjent_{i}"]

        # 1. STRING (Imię i nazwisko - tutaj błędów nie wstrzykujemy, bo tekst to zawsze tekst)
        g.add((pacjent, EX.imieNazwisko, Literal(fake.name(), datatype=GQL.STRING)))

        # 2. UINT8 (Wiek 0-255)
        wiek_valid = str(fake.random_int(1, 100))
        wiek_invalid = str(random.choice([-15, 300]))  # Ujemny lub za duży dla unsignedByte
        g.add((pacjent, EX.wiek, Literal(get_val(wiek_valid, wiek_invalid), datatype=GQL.UINT8)))

        # 3. DATE (Data urodzenia)
        data_valid = fake.date_of_birth(minimum_age=1, maximum_age=100).strftime("%Y-%m-%d")
        data_invalid = fake.date_of_birth(minimum_age=1, maximum_age=100).strftime("%d-%m-%Y")  # Błędny format
        g.add((pacjent, EX.dataUrodzenia, Literal(get_val(data_valid, data_invalid), datatype=GQL.DATE)))

        # 4. FLOAT (Waga pacjenta)
        waga_valid = f"{random.uniform(40.0, 120.0):.1f}"
        waga_invalid = waga_valid.replace(".", ",")  # Błąd: przecinek zamiast kropki (lub tekst)
        g.add((pacjent, EX.waga, Literal(get_val(waga_valid, waga_invalid), datatype=GQL.FLOAT)))

        # 5. BOOLEAN (Zgoda na zabieg)
        bool_valid = random.choice(["true", "false", "1", "0"])
        bool_invalid = random.choice(["tak", "nie", "prawda"])  # Błędne słowa
        g.add((pacjent, EX.zgodaNaZabieg, Literal(get_val(bool_valid, bool_invalid), datatype=GQL.BOOLEAN)))

        # 6. TIMESTAMP (Data przyjęcia do szpitala)
        ts_valid = fake.date_time_this_year().strftime("%Y-%m-%dT%H:%M:%S")
        ts_invalid = fake.date_time_this_year().strftime("%Y-%m-%d %H:%M:%S")  # Błąd: spacja zamiast litery 'T'
        g.add((pacjent, EX.dataPrzyjecia, Literal(get_val(ts_valid, ts_invalid), datatype=GQL.TIMESTAMP)))

        # 7. BINARY (Identyfikator opaski z kodem kreskowym HEX)
        bin_valid = fake.hexify(text="^^^^")  # 4 znaki - parzysta liczba jest poprawna dla HEX
        bin_invalid = fake.hexify(text="^^^")  # 3 znaki - nieparzysta liczba wywoła błąd ill_typed
        g.add((pacjent, EX.idOpaskiHex, Literal(get_val(bin_valid, bin_invalid), datatype=GQL.BINARY)))

        # 8. ARRAY (Przepisane leki jako JSON Array)
        wybrane_leki = random.sample(leki, k=random.randint(1, 3))
        arr_valid = json.dumps(wybrane_leki)
        arr_invalid = random.choice([
            '{"lek": "Ibuprofen"}',  # Błąd: poprawny JSON, ale słownik (obiekt) a nie lista
            '["Paracetamol", '  # Błąd: składniowo ucięty JSON
        ])
        g.add((pacjent, EX.przepisaneLeki, Literal(get_val(arr_valid, arr_invalid), datatype=GQL.ARRAY)))

        # ====================================================================
        # NOWE ATRYBUTY TESTUJĄCE RESTRYKCJE Z ONTOLOGII (.ttl)
        # ====================================================================

        # 9. CHAR (Płeć - test na ograniczenie długości maxLength=1)
        plec_valid = random.choice(["M", "K"])
        plec_invalid = random.choice(["Mężczyzna", "Kobieta", "Brak Danych"])  # Zbyt długie słowa
        g.add((pacjent, EX.plec, Literal(get_val(plec_valid, plec_invalid), datatype=GQL.CHAR)))

        # 10. DURATION_YEAR_TO_MONTH (Czas trwania leczenia - test na wyrażenie xsd:pattern)
        dur_valid = f"P{random.randint(0, 5)}Y{random.randint(1, 11)}M"  # np. P1Y6M
        dur_invalid = f"{random.randint(1, 5)} lat i {random.randint(1, 11)} miesiecy"  # Tekst niezgodny z patternem ISO
        g.add((pacjent, EX.przewidywanyCzasLeczenia, Literal(get_val(dur_valid, dur_invalid), datatype=GQL.DURATION_YEAR_TO_MONTH)))

        # ====================================================================

        # 11. NIEZNANY TYP (Test na błąd "brak mapowania dla datatype")
        # W 20% przypadków symulujemy wstawienie dziwnego typu danych
        if random.random() < 0.2:
            g.add((pacjent, EX.poleTestowe, Literal("123", datatype=GQL.NIEZNANY_TYP)))

    g.serialize(destination=output_file, format="turtle")
    print(f"[Generator] Zakończono! Zapisano dane medyczne w pliku: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="test_data.ttl", help="Plik wyjściowy (np. test_data.ttl)")
    # Ustawienie 1000 pacjentów gwarantuje, że statystyki będą bardzo stabilne (~20%)
    parser.add_argument("--count", type=int, default=50, help="Liczba generowanych pacjentów")
    args = parser.parse_args()

    generate_patient_data(args.output, args.count)