#!/usr/bin/env python3
"""Synthetic unit tests for the optional Worker checkpoint helper."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import action_protocol as p
import bridge as b
import ppp_checkpoint as h
from test_action_protocol import config


class CheckpointHelperTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.root, self.target, self.outside = base / 'run', base / 'Test-project', base / 'Test-tmp'
        self.work = self.root / 'work'
        for path in (self.work, self.target / 'src', self.outside):
            path.mkdir(parents=True)
        c = config()
        c.update(worker_model='Test-worker', review_model='Test-reviewer', task='TASK.md', thread_id='Test-thread',
                 wall_seconds=10, review_seconds=5, cycle_seconds=5)
        c['execution_contract']['target'] = str(self.target)
        (self.root / 'TASK.md').write_text('Test task')
        p.durable(self.root / 'config.json', c)
        p.durable(self.work / 'cycle-context.json', {**p.header(c['run_id']), 'cycle': 3, 'action_id': 'footer'})
        (self.target / 'ledger.py').write_text('Test ledger root')
        (self.work / 'Test-tests.txt').write_text('Test exit=0')
        self.c = {**c, 'root': str(self.root)}
        env = patch.dict(os.environ, PPP_WORK_DIR=str(self.work))
        env.start()
        self.addCleanup(env.stop)
        cwd = os.getcwd()
        os.chdir(self.target / 'src')
        self.addCleanup(os.chdir, cwd)

    def run_helper(self, *evidence, status='ready'):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = h.main(['--status', status, '--summary', 'Test summary', '--next-step', 'Test next', *evidence])
        return code, err.getvalue()

    def checkpoint(self):
        return json.loads((self.work / 'checkpoint.json').read_text())

    def test_resolves_bare_target_name_work_prefix_and_is_accepted_by_core(self):
        code, err = self.run_helper('ledger.py', 'work/Test-tests.txt')
        self.assertEqual(code, 0, err)
        cp = self.checkpoint()
        self.assertEqual(cp['evidence'], [str(self.target / 'ledger.py'), 'Test-tests.txt'])
        self.assertEqual((cp['protocol_version'], cp['schema_version'], cp['run_id'], cp['cycle'], cp['action_id']), (2, 1, 'action-test', 3, 'footer'))
        b.validate_checkpoint(self.c, 3)

    def test_outside_file_is_copied_into_work_evidence(self):
        (self.outside / 'run.out').write_text('Test output')
        code, err = self.run_helper(str(self.outside / 'run.out'))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.checkpoint()['evidence'], ['evidence/run.out'])
        self.assertEqual((self.work / 'evidence/run.out').read_text(), 'Test output')

    def test_missing_file_reports_tried_paths_and_keeps_previous_checkpoint(self):
        self.assertEqual(self.run_helper('Test-tests.txt')[0], 0)
        before = (self.work / 'checkpoint.json').read_bytes()
        code, err = self.run_helper('Test-absent.txt')
        self.assertEqual(code, 2)
        self.assertIn(str(self.work / 'Test-absent.txt'), err)
        self.assertIn(str(self.target / 'Test-absent.txt'), err)
        self.assertEqual((self.work / 'checkpoint.json').read_bytes(), before)

    def test_secret_like_outside_file_is_not_copied(self):
        for name in ('.env', 'auth.json', 'credentials.json'):
            (self.outside / name).write_text('Test secret')
            code, err = self.run_helper(str(self.outside / name))
            self.assertEqual(code, 2)
            self.assertIn('Secret-bearing', err)
        self.assertFalse((self.work / 'evidence').exists())
        self.assertFalse((self.work / 'checkpoint.json').exists())

    def test_rejected_checkpoint_is_not_left_behind_and_limit_is_reported(self):
        code, err = self.run_helper()
        self.assertEqual(code, 2)
        self.assertIn('Results need evidence', err)
        self.assertFalse((self.work / 'checkpoint.json').exists())
        code, err = self.run_helper(*(['Test-tests.txt'] * 21))
        self.assertEqual(code, 2)
        self.assertIn('max_evidence_files=20', err)

    def test_identity_comes_only_from_core_context(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            h.main(['--status', 'ready', '--summary', 'Test', '--run-id', 'Test-forged', 'Test-tests.txt'])
        # A context for another run is refused by Core's check, not written as accepted.
        p.durable(self.work / 'cycle-context.json', {**p.header('Test-foreign'), 'cycle': 3, 'action_id': 'footer'})
        code, err = self.run_helper('Test-tests.txt')
        self.assertEqual(code, 2)
        self.assertIn('Stale/wrong checkpoint identity', err)
        self.assertFalse((self.work / 'checkpoint.json').exists())


if __name__ == '__main__':
    unittest.main()
