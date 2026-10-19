import unittest
from meerk40t.camera.batch_progress import batch_progress

class ProgressTest(unittest.TestCase):
    def test_only_all_parts_count_and_duplicates_do_not(self):
        manifest = dict(passes=16, jobs=[dict(card=1),dict(card=1),dict(card=2),dict(card=2)])
        log = 'START pass 1/16 card 1 part 1\nCOMPLETED pass 1/16 card 1 part 1\n'
        self.assertEqual(batch_progress(log,manifest)['cards'][0]['completed'],0)
        log += 'COMPLETED pass 1/16 card 1 part 2\n'*2
        log += 'START pass 1/16 card 2 part 3\n'
        result = batch_progress(log,manifest)
        self.assertEqual(result['cards'],[dict(card=1,completed=1),dict(card=2,completed=0)])
        self.assertEqual(result['current'],dict(layer=1,card=2))
        self.assertFalse(result['complete'])
    def test_invalid_and_partial_records(self):
        m=dict(passes=1,jobs=[dict(card=1)])
        self.assertEqual(batch_progress('COMPLETED pass 2/1 card 1 part 1\nCOMPLETED pass 1/1 card 1 part',m)['cards'][0]['completed'],0)
        self.assertTrue(batch_progress('COMPLETED pass 1/1 card 1 part 1\n',m)['complete'])
