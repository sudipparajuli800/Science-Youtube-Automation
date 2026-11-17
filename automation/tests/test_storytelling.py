import unittest
from automation.media.motion_graphics import validate_animation


class StorytellingValidationTests(unittest.TestCase):
    def test_cycle_requires_a_loop_in_the_narration(self):
        spec = {'template': 'cycle', 'title': 'Water returns', 'nodes': [
            {'label': 'Water'}, {'label': 'clouds'}, {'label': 'rain'}]}
        self.assertIsNotNone(validate_animation(spec, 'Water, clouds and rain form a repeating cycle.'))
        self.assertIsNone(validate_animation(spec, 'Water, clouds and rain are visible.'))
        self.assertIsNone(validate_animation(spec, 'Water, clouds and rain do not repeat this cycle.'))

    def test_layers_require_structural_context_and_source_labels(self):
        spec = {'template': 'layers', 'title': 'Inside Earth', 'nodes': [
            {'label': 'crust'}, {'label': 'mantle'}, {'label': 'core'}]}
        self.assertIsNotNone(validate_animation(spec, 'Earth has layers: crust, mantle, core.'))
        spec['nodes'][2]['label'] = 'invented anatomy'
        self.assertIsNone(validate_animation(spec, 'Earth has layers: crust, mantle, core.'))

    def test_motion_treatment_is_a_closed_set_not_executable_model_output(self):
        spec = {'template': 'layers', 'title': 'Structure', 'nodes': [
            {'label': 'crust'}, {'label': 'core'}], 'treatment': {'onFrame': 'fetch(secrets)'}}
        clean = validate_animation(spec, 'The layers include crust and core.')
        self.assertNotIn('treatment', clean)
        spec['treatment'] = 'draw'
        self.assertEqual(validate_animation(spec, 'The layers include crust and core.')['treatment'], 'draw')
