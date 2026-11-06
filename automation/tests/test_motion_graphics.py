import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation.content.editorial import prepare_scenes
from automation.media.motion_graphics import validate_animation, infer_animation, animation_cues
from automation.media.visual_quality import check_visual_quality, VisualQualityHold


class MotionGraphicsTests(unittest.TestCase):
    narration = 'Saharan dust travels across the Atlantic and reaches the Amazon.'
    spec = {'template': 'transport', 'title': 'Dust delivers nutrients', 'nodes': [
        {'label': 'Saharan dust', 'icon': 'particle'},
        {'label': 'Atlantic', 'icon': 'ocean'}, {'label': 'Amazon', 'icon': 'leaf'}]}

    def test_specific_animation_survives_scene_planning(self):
        scene = {'visual_type': 'animation', 'narration': self.narration, 'animation': self.spec}
        result = prepare_scenes([scene], self.narration, 'Saharan dust')
        self.assertEqual(result[0]['visual_type'], 'animation')
        self.assertEqual(result[0]['animation']['template'], 'transport')

    def test_fallback_recognizes_transport_without_llm_scene_json(self):
        result = prepare_scenes([], self.narration, 'Saharan dust')
        self.assertEqual(result[0]['animation']['template'], 'transport')

    def test_unknown_templates_and_unmentioned_subjects_rejected(self):
        self.assertIsNone(validate_animation({'template': 'eval'}, self.narration))
        bad = {**self.spec, 'nodes': [{'label': 'Dinosaurs'}, {'label': 'Moon'}]}
        self.assertIsNone(validate_animation(bad, self.narration))

    def test_animation_data_cannot_supply_executable_hooks(self):
        clean = validate_animation({**self.spec, 'onFrame': 'process.exit()',
                                    'image_path': '/secrets'}, self.narration)
        self.assertNotIn('onFrame', clean)
        self.assertNotIn('image_path', clean)

    def test_chart_rejects_unspoken_values_and_accepts_shared_units(self):
        narration = 'Mercury takes about 88 days. Earth takes about 365 days.'
        spec = {'template': 'bars', 'title': 'Two orbital years', 'unit': 'days',
                'items': [{'label': 'Mercury', 'value': 88}, {'label': 'Earth', 'value': 365}]}
        self.assertIsNotNone(validate_animation(spec, narration))
        spec['items'][1]['value'] = 999
        self.assertIsNone(validate_animation(spec, narration))

    def test_refraction_does_not_silently_use_wrong_materials(self):
        spec = {'template': 'refraction', 'title': 'Light changes direction'}
        self.assertIsNotNone(validate_animation(spec, 'Light bends from air into water.'))
        self.assertIsNone(validate_animation(spec, 'Light travels through glass.'))

    def test_malformed_model_fields_do_not_crash_the_pipeline(self):
        self.assertIsNone(validate_animation({'template': []}, self.narration))
        spec = {**self.spec, 'nodes': [{'label': 'Atlantic', 'icon': []}, {'label': 'Amazon', 'icon': 'leaf'}]}
        self.assertEqual(validate_animation(spec, self.narration)['nodes'][0]['icon'], 'particle')

    def test_refraction_is_not_used_for_an_explicit_no_bending_statement(self):
        spec = {'template': 'refraction', 'title': 'Normal incidence'}
        self.assertIsNone(validate_animation(spec, "Light does not bend from air into water at normal incidence."))

    def test_reveals_follow_scene_word_timestamps(self):
        words = [{'word': w, 'start': 10+i*.5} for i,w in enumerate(self.narration.split())]
        cues = animation_cues(self.spec, words, scene_start=10, duration=8)
        self.assertEqual(cues, [0, 75, 135])

    def test_orchestrator_does_not_download_stock_for_a_valid_diagram(self):
        from automation.media.asset_orchestrator import AssetOrchestrator
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, {'VIDEO_GEN_PROVIDER': 'none'}), \
                     patch('automation.media.asset_orchestrator.engine_ready', return_value=True), \
                     patch('automation.media.asset_orchestrator.stock_media.fetch_real_photos') as photos, \
                     patch('automation.media.asset_orchestrator.stock_media.fetch_real_videos') as videos:
                    result = AssetOrchestrator().fetch_all([{'visual_type': 'animation',
                        'narration': self.narration, 'animation': self.spec}], 'Saharan dust', '9:16')
                self.assertEqual(result['scenes'][0]['asset_type'], 'animation')
                photos.assert_not_called()
                videos.assert_not_called()
            finally:
                os.chdir(previous)

    def test_quality_gate_accepts_valid_ready_animation_not_arbitrary_motion(self):
        manifest = {'topic': 'Saharan dust', 'scenes': [{'asset_type': 'animation',
            'visual_type': 'animation', 'narration': self.narration, 'animation': self.spec}]}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with patch('automation.media.motion_graphics.engine_ready', return_value=True):
                    check_visual_quality(manifest)
                    report = json.loads(Path('automation/storage/visual_quality_report.json').read_text())
                    self.assertEqual(report['animation_scenes'], 1)
                    self.assertEqual(report['footage_scenes'], 0)
                with patch('automation.media.motion_graphics.engine_ready', return_value=False):
                    with self.assertRaises(VisualQualityHold):
                        check_visual_quality(manifest)
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
