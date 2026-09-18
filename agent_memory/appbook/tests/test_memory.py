"""Offline checks of real files and tools. No model responses are mocked."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import convert_to_tool, multiply, run_clock_diagnostics
from memory import MemoryStore, balanced_tools, message, uid


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = MemoryStore(self.directory.name)
        self.session = self.create()

    def create(self):
        return self.store.create("notes", "gpt-6-astra", "low", 6000, 2400, 120)

    def test_search_excludes_active_window_seeds_and_retrieved_copies(self):
        s = self.session
        self.store.append(s, message("Retry limit is 4. Original UTF-8: café."))
        self.store.rotate(s, [message("Retry limit is 99. Seed copy.")])
        self.store.append(s, message("Retry limit is 88. Retrieved copy."), "retrieval")
        self.store.append(s, message("Retry limit is now 6."))
        self.store.rotate(s, [])
        self.store.append(s, message("What is the retry limit?"))
        hits = self.store.search(s, "retry limit")
        self.assertEqual(len(hits), 2)
        self.assertIn("6", hits[0]["excerpt"])
        self.assertEqual(hits[0]["window_number"], 2)
        self.assertIn("café", hits[1]["excerpt"])
        self.assertEqual(self.store.search(self.create(), "retry limit"), [])

    def test_offload_round_trip_integrity_and_session_scope(self):
        s = self.session
        marker = uid()
        items = [message("Original marker: " + marker)]
        identifier = uid()
        self.store.store_offload(s, identifier, items)
        self.assertEqual(self.store.read_offload(s, identifier)["items"], items)
        self.assertIn(marker, self.store.retrieve(s, identifier, "marker")["excerpt"])
        with self.assertRaises(FileNotFoundError):
            self.store.read_offload(self.create(), identifier)
        with self.assertRaises(ValueError):
            self.store.read_offload(s, "../../elsewhere")
        path = self.store.root / "offloaded_context" / s["id"] / f"{identifier}.json"
        path.write_text(path.read_text(encoding="utf-8").replace(marker, uid()), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.store.read_offload(s, identifier)

    def test_balanced_protocol_and_generated_tool_validation(self):
        call = {"type": "function_call", "call_id": "a"}
        output = {"type": "function_call_output", "call_id": "a"}
        self.assertFalse(balanced_tools([call]))
        self.assertFalse(balanced_tools([output]))
        self.assertFalse(balanced_tools([call, call, output]))
        self.assertTrue(balanced_tools([call, output]))
        tool = convert_to_tool(multiply)
        values = tool["arguments"].model_validate_json('{"a":14,"b":19}')
        self.assertEqual(tool["function"](**values.model_dump())["product"], 266)
        self.assertEqual(tool["schema"]["parameters"]["properties"]["a"]["type"], "number")

    def test_diagnostic_executes_the_real_failure(self):
        result = run_clock_diagnostics(uid(), 120)
        self.assertFalse(result["passed"])
        self.assertEqual(result["error_message"], "Expected 7000 ms, got 9000 ms.")
        self.assertEqual(len(result["log"].splitlines()), 120)

    def test_journal_preserves_original_evidence_after_rotation(self):
        s = self.session
        self.store.append(s, message("A fact worth remembering."))
        old_window = s["window_id"]
        original = self.store.journal(s).read_bytes()
        self.store.rotate(s, [message("A carried fact.")])
        self.assertEqual(self.store.journal(s, old_window).read_bytes(), original)
        restored = self.store.load(s["id"])
        self.assertEqual(restored["notes_id"], restored["id"])
        self.assertEqual(self.store.events(restored)[0]["origin"], "seed")


if __name__ == "__main__":
    unittest.main()
