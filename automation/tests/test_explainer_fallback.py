import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from automation.media.asset_orchestrator import AssetOrchestrator
from automation.media.visual_relevance import VerificationUnavailable
from automation.media.explainer_card import create_explainer_card


class ExplainerFallbackTests(unittest.TestCase):
    def test_quota_outage_finishes_all_scenes_without_unverified_stock(self):
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                candidate = str(Path(directory) / 'stock.png')
                Image.new('RGB', (40, 40)).save(candidate)
                scenes = [{'narration': 'Rock reacts with rainwater over time.',
                           'visual_type': 'image', 'image_cue': 'rock rainwater'}] * 2
                with patch('automation.media.asset_orchestrator.stock_media.has_stock_api_keys', return_value=True), \
                     patch('automation.media.asset_orchestrator.stock_media.fetch_real_videos', return_value=[candidate]), \
                     patch('automation.media.asset_orchestrator.stock_media.fetch_real_photos') as photos, \
                     patch('automation.media.asset_orchestrator.visual_relevance.is_visually_relevant',
                           side_effect=VerificationUnavailable('quota')) as verify:
                    manifest = AssetOrchestrator().fetch_all(scenes, 'Silicate weathering', '9:16')
                self.assertEqual(len(manifest['scenes']), 2)
                self.assertEqual(verify.call_count, 1)
                photos.assert_not_called()
                for scene in manifest['scenes']:
                    self.assertEqual(scene['visual_type'], 'explainer_card')
                    self.assertNotEqual(scene['asset_path'], candidate)
                    self.assertFalse(scene['source']['photographic_evidence'])
                    with Image.open(scene['asset_path']) as image:
                        self.assertEqual(image.size, (1080, 1920))
            finally:
                os.chdir(previous)

    def test_retired_final_model_is_not_retried(self):
        from unittest.mock import Mock
        from automation.content.script_writer import ScriptWriter, LLM_FAILURE_SENTINEL
        writer = ScriptWriter.__new__(ScriptWriter)
        writer.model_candidates = ['retired-model']
        writer.model_id = 'retired-model'
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError('404 model no longer available')
        writer.clients = [client]
        writer.groq_clients = []
        with patch('automation.content.script_writer.time.sleep') as sleep:
            self.assertEqual(writer._call_with_retry('test'), LLM_FAILURE_SENTINEL)
        self.assertEqual(client.models.generate_content.call_count, 1)
        sleep.assert_not_called()

    def test_landscape_card_fits_long_topic_and_narration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'card.png')
            create_explainer_card({'narration': 'Rainwater reacts with silicate rocks and gradually changes their composition over long periods of time.'},
                                  'Silicate Weathering on Exoplanet Super-Earths', path)
            with Image.open(path) as image:
                self.assertEqual(image.size, (1920, 1080))


if __name__ == '__main__':
    unittest.main()
