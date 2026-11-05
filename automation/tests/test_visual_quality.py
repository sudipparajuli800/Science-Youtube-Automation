import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock, AsyncMock
from automation.media.visual_quality import check_visual_quality, VisualQualityHold
from automation.media import local_relevance


class VisualQualityTests(unittest.TestCase):
    def setUp(self):
        self.previous = Path.cwd()
        self.temp = tempfile.TemporaryDirectory(dir=self.previous)
        os.chdir(self.temp.name)
        local_relevance._failed = False

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()
        local_relevance._failed = False

    def test_all_cards_is_held_but_test_preview_is_allowed(self):
        manifest = {'scenes': [{'asset_type': 'image', 'visual_type': 'explainer_card'}]}
        with self.assertRaises(VisualQualityHold):
            check_visual_quality(manifest)
        self.assertTrue(Path('automation/storage/visual_quality_report.json').is_file())
        check_visual_quality(manifest, is_test=True)

    def test_video_allows_production(self):
        check_visual_quality({'scenes': [{'asset_type': 'video'}]})

    def test_local_matching_rejects_weak_absolute_or_contrast_scores(self):
        self.assertFalse(local_relevance.accept_scores([.21, .1, .1, .1]))
        self.assertFalse(local_relevance.accept_scores([.30, .31, .1, .1]))
        self.assertTrue(local_relevance.accept_scores([.32, .18, .15, .14]))

    def test_local_matching_failure_does_not_approve_or_repeat_loading(self):
        with patch.dict(os.environ, {'LOCAL_VISUAL_RELEVANCE': 'true'}), \
             patch.object(local_relevance, 'score_image', side_effect=ImportError('missing model')) as score:
            self.assertIsNone(local_relevance.check_local(b'image', 'forest'))
            self.assertIsNone(local_relevance.check_local(b'image', 'forest'))
            self.assertEqual(score.call_count, 1)


class ShortsPreflightTests(unittest.TestCase):
    def test_all_card_plan_does_not_buy_voice_or_render(self):
        from automation.pipelines.science_pipeline import SciencePipeline
        from automation.media.asset_orchestrator import AssetOrchestrator
        pipeline = SciencePipeline.__new__(SciencePipeline)
        pipeline.script_writer = Mock()
        pipeline.script_writer.generate_science_facts.return_value = 'Rainwater reacts with rocks.'
        pipeline.script_writer.generate_shorts_visual_scenes.return_value = [{'narration': 'Rainwater reacts with rocks.'}]
        pipeline.tts = AsyncMock()
        pipeline.vgen = Mock()
        pipeline._upload = AsyncMock()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch.object(AssetOrchestrator, 'fetch_all', return_value={'scenes': [
                        {'asset_type': 'image', 'visual_type': 'explainer_card'}]}):
                    coroutine = pipeline._run_shorts('Weathering', is_test=False)
                    try:
                        # Preflight must raise before this coroutine reaches any await.
                        with self.assertRaises(VisualQualityHold):
                            coroutine.send(None)
                    finally:
                        coroutine.close()
            finally:
                os.chdir(previous)
        pipeline.tts.generate_audio.assert_not_awaited()
        pipeline.vgen.create_shorts_from_scenes.assert_not_called()
        pipeline._upload.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
