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

    def test_one_video_does_not_allow_a_mostly_card_video(self):
        scenes = [{'asset_type': 'video'}] + [
            {'asset_type': 'image', 'visual_type': 'explainer_card'} for _ in range(3)]
        with self.assertRaises(VisualQualityHold):
            check_visual_quality({'scenes': scenes})

    def test_diagrams_alone_do_not_fill_an_entire_multi_scene_video(self):
        spec = {'template': 'flow', 'title': 'Heat moves',
                'nodes': [{'label': 'Water', 'icon': 'water'},
                          {'label': 'Vapor', 'icon': 'particle'}]}
        scenes = [{'narration': 'Water changes into vapor.', 'asset_type': 'animation',
                   'visual_type': 'animation', 'animation': spec} for _ in range(6)]
        with patch('automation.media.motion_graphics.engine_ready', return_value=True):
            with self.assertRaises(VisualQualityHold):
                check_visual_quality({'scenes': scenes})
            scenes[0]['context_path'] = 'verified-water.jpg'
            scenes[1]['context_path'] = 'verified-vapor.mp4'
            check_visual_quality({'scenes': scenes})

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
    def test_all_card_plan_stops_before_render_or_upload(self):
        from automation.pipelines.science_pipeline import SciencePipeline
        from automation.media.asset_orchestrator import AssetOrchestrator
        pipeline = SciencePipeline.__new__(SciencePipeline)
        pipeline.script_writer = Mock()
        pipeline.script_writer.generate_science_facts.return_value = 'Rainwater reacts with rocks.'
        pipeline.script_writer.generate_shorts_visual_scenes.return_value = [{'narration': 'Rainwater reacts with rocks.'}]
        pipeline.config = {}
        pipeline.tts = AsyncMock()
        pipeline.tts.generate_audio.return_value = ("test.mp3", [])
        pipeline.vgen = Mock()
        pipeline._upload = AsyncMock()
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch('automation.media.hume_tts.get_audio_duration', return_value=20), patch.object(AssetOrchestrator, 'fetch_all', return_value={'scenes': [
                        {'asset_type': 'image', 'visual_type': 'explainer_card'}]}):
                    coroutine = pipeline._run_shorts('Weathering', is_test=False)
                    try:
                        # The immediate mocked TTS await completes before visual preflight.
                        with self.assertRaises(VisualQualityHold):
                            coroutine.send(None)
                    finally:
                        coroutine.close()
            finally:
                os.chdir(previous)
        pipeline.tts.generate_audio.assert_awaited_once()
        pipeline.vgen.create_shorts_from_scenes.assert_not_called()
        pipeline._upload.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
