import unittest
from unittest.mock import Mock, patch
from automation.media.asset_orchestrator import AssetOrchestrator


class VisualRepairTests(unittest.TestCase):
    def orchestrator(self):
        obj = AssetOrchestrator.__new__(AssetOrchestrator)
        obj._save_manifest = Mock()
        return obj

    def test_only_grounded_diagrams_replace_failed_stock(self):
        missing = {'visual_type': 'explainer_card', 'narration': 'Water carries particles.',
                   'asset_type': 'image', 'asset_path': 'card.png'}
        existing = {'visual_type': 'image', 'asset_type': 'video', 'asset_path': 'real.mp4'}
        manifest = {'topic': 'Water', 'scenes': [existing, missing]}
        plan = {'visual_type': 'animation', 'narration': missing['narration'],
                'animation': {'template': 'transport', 'title': 'Water carries particles',
                'nodes': [{'label': 'Water', 'icon': 'water'},
                          {'label': 'particles', 'icon': 'particle'}]}}
        obj = self.orchestrator()
        with patch('automation.media.asset_orchestrator.engine_ready', return_value=True):
            obj.repair_missing_visuals(manifest, Mock(return_value=[plan]))
        self.assertEqual(missing['asset_type'], 'animation')
        self.assertIsNone(missing['asset_path'])
        self.assertEqual(existing['asset_path'], 'real.mp4')
        self.assertEqual(manifest['repair_count'], 1)

    def test_invalid_diagram_cannot_bypass_quality_hold(self):
        scene = {'visual_type': 'explainer_card', 'narration': 'Water carries particles.',
                 'asset_path': 'card.png'}
        plan = {'visual_type': 'animation', 'narration': scene['narration'],
                'animation': {'template': 'flow', 'title': 'Mechanism',
                'nodes': [{'label': 'invented'}, {'label': 'unrelated'}]}}
        manifest = {'topic': 'Water', 'scenes': [scene]}
        with patch('automation.media.asset_orchestrator.engine_ready', return_value=True):
            self.orchestrator().repair_missing_visuals(manifest, Mock(return_value=[plan]))
        self.assertEqual(scene['visual_type'], 'explainer_card')
        self.assertEqual(manifest['repair_count'], 0)

    def test_reordered_narration_is_rejected(self):
        manifest = {'topic': 'Water', 'scenes': [
            {'visual_type': 'explainer_card', 'narration': 'Original words'}]}
        with patch('automation.media.asset_orchestrator.engine_ready', return_value=True):
            with self.assertRaises(ValueError):
                self.orchestrator().repair_missing_visuals(manifest,
                    Mock(return_value=[{'narration': 'Changed words'}]))
