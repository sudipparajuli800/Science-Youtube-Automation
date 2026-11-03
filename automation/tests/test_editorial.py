import unittest
from unittest.mock import patch
from automation.content.editorial import prepare_scenes, _words
from automation.media.visual_relevance import is_visually_relevant


class EditorialTests(unittest.TestCase):
    def test_missing_ending_repaired_and_decimal_preserved(self):
        script = 'A sample measures 4.5 mm. The final sentence explains why.'
        result = prepare_scenes([{'narration': 'A sample measures 4.5 mm.'}], script, 'sample')
        self.assertEqual(_words(' '.join(s['narration'] for s in result)), _words(script))
        self.assertIn('4.5', result[0]['narration'])

    def test_unspoken_chart_removed(self):
        scene = {'narration': 'These planets differ.', 'visual_type': 'data_bars',
                 'bar_data': [{'value': 2}, {'value': 4}, {'value': 6}]}
        self.assertEqual(prepare_scenes([scene], scene['narration'], 'planets')[0]['visual_type'], 'image')

    def test_spoken_stat_kept(self):
        scene = {'narration': 'It takes 8 minutes.', 'visual_type': 'kinetic_stat',
                 'stat_data': {'value': 8, 'unit': 'minutes', 'label': 'travel time'}}
        self.assertEqual(prepare_scenes([scene], scene['narration'], 'light')[0]['visual_type'], 'kinetic_stat')

    def test_number_substring_is_not_evidence(self):
        scene = {'narration': 'It takes 18 minutes.', 'visual_type': 'kinetic_stat',
                 'stat_data': {'value': 8, 'unit': 'minutes'}}
        self.assertEqual(prepare_scenes([scene], scene['narration'], 'light')[0]['visual_type'], 'image')

    def test_long_hold_split_without_losing_words(self):
        script = ' '.join('word' + str(i) for i in range(60))
        result = prepare_scenes([{'narration': script}], script, 'test')
        self.assertTrue(all(len(s['narration'].split()) <= 18 for s in result))
        self.assertEqual(' '.join(s['narration'] for s in result), script)

    def test_strict_relevance_rejects_missing_asset_and_missing_client(self):
        self.assertFalse(is_visually_relevant('missing.jpg', 'a cell', strict=True))
        with patch('automation.media.visual_relevance.os.path.exists', return_value=True), \
             patch('automation.media.visual_relevance._get_client', return_value=None):
            self.assertFalse(is_visually_relevant('cell.jpg', 'a cell', strict=True))


if __name__ == '__main__':
    unittest.main()
