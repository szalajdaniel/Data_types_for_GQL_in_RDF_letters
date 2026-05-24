import unittest
import subprocess
import os
import json


class TestCLI(unittest.TestCase):

    def setUp(self):

        # Mock bad config (probability > 1.0)
        self.bad_config_path = "bad_config_test.json"
        with open(self.bad_config_path, "w") as f:
            json.dump({"age": 1.5}, f)

        # Mock minimal ontology for the validator
        self.test_ontology = "test_ontology.ttl"
        with open(self.test_ontology, "w") as f:
            f.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")

        self.test_output_ttl = "test_out.ttl"

    def tearDown(self):
        files_to_remove = [
            self.bad_config_path,
            self.test_ontology,
            self.test_output_ttl,
            "report_A.csv",
            "report_A.json",
            "report_B.csv",
            "report_B.json"
        ]
        for file in files_to_remove:
            if os.path.exists(file):
                os.remove(file)

    def test_valid_input(self):

        result = subprocess.run(
            ["python", "generator_real.py", "-c", "5", "-e", "10", "-o", self.test_output_ttl],
            capture_output=True, text=True
        )
        # Should exit with code 0 (success)
        self.assertEqual(result.returncode, 0)
        # Output file should be created
        self.assertTrue(os.path.exists(self.test_output_ttl))

    def test_error_rate_too_high(self):
        result = subprocess.run(
            ["python", "generator_real.py", "-c", "5", "-e", "150"],
            capture_output=True, text=True
        )
        # Argparse should exit with code 2 for argument errors
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Value must be between 0 and 100", result.stderr)

    def test_count_less_than_one(self):
        result = subprocess.run(
            ["python", "generator_real.py", "-c", "-1", "-e", "10"],
            capture_output=True, text=True
        )
        # Argparse should exit with code 2
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Value must be a positive integer", result.stderr)

    def test_invalid_config(self):
        result = subprocess.run(
            ["python", "generator_real.py", "-c", "5", "-e", "10", "--config", self.bad_config_path],
            capture_output=True, text=True
        )
        # Should exit with our custom sys.exit(1) code
        self.assertEqual(result.returncode, 1)
        self.assertIn("Invalid probability", result.stdout)

    def test_validator_report_generation(self):

        # First, generate a small valid TTL file
        subprocess.run(
            ["python", "generator_real.py", "-c", "2", "-e", "0", "-o", self.test_output_ttl],
            capture_output=True
        )

        # Run validator with prefix 'report_A'
        res_a = subprocess.run(
            ["python", "validator.py", "-d", self.test_output_ttl, "-o", self.test_ontology, "-p", "report_A"],
            capture_output=True, text=True
        )
        self.assertEqual(res_a.returncode, 0, f"Błąd walidatora: {res_a.stderr}")
        self.assertTrue(os.path.exists("report_A.csv"))
        self.assertTrue(os.path.exists("report_A.json"))

        # Run validator with prefix 'report_B'
        res_b = subprocess.run(
            ["python", "validator.py", "-d", self.test_output_ttl, "-o", self.test_ontology, "-p", "report_B"],
            capture_output=True, text=True
        )
        self.assertEqual(res_b.returncode, 0)
        self.assertTrue(os.path.exists("report_B.csv"))
        self.assertTrue(os.path.exists("report_B.json"))

        # Ensure report_A was NOT overwritten/deleted by the second run
        self.assertTrue(os.path.exists("report_A.json"))


if __name__ == '__main__':
    unittest.main()