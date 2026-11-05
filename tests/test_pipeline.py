import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from invest_research.core import load_facts, DataError
from invest_research.pipeline import run

ROOT=Path(__file__).resolve().parents[1]

class PipelineTests(unittest.TestCase):
    def test_export_and_independent_recomputation(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"run"
            result=run(ROOT/"examples"/"demo.csv",date(2026,11,5),out,demo=True)
            self.assertEqual(result["data_kind"],"synthetic_demo")
            manifest=json.loads((out/"manifest.json").read_text())
            for name,digest in manifest["files"].items():
                self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)
            unpack=Path(folder)/"unpacked"
            with zipfile.ZipFile(out/"review_pack.zip") as archive:
                self.assertNotIn(".env",archive.namelist())
                archive.extractall(unpack)
            p=subprocess.run([sys.executable,str(unpack/"recompute.py")],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn("Recomputation passed",p.stdout)

    def test_scale_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"facts.csv"
            with (ROOT/"examples"/"demo.csv").open(encoding="utf-8") as fixture:
                rows=list(csv.DictReader(fixture))
            rows[0]["scale"]="10000"
            with path.open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=rows[0].keys())
                writer.writeheader();writer.writerows(rows)
            self.assertEqual(load_facts(path)[0].value,int(rows[0]["value"])*10000)
            rows[0]["value"]="NaN"
            with path.open("w",encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=rows[0].keys())
                writer.writeheader();writer.writerows(rows)
            with self.assertRaises(DataError):
                load_facts(path)

