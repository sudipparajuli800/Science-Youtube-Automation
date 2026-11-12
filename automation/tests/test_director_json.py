import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch
from automation.content.script_writer import ScriptWriter
from automation.media.visual_quality import VisualQualityHold


class DirectorJsonRegressionTests(unittest.TestCase):
    def setUp(self):
        self.writer = ScriptWriter.__new__(ScriptWriter)
        self.narration = 'Water changes into vapor.'
        self.scene = {'narration': self.narration, 'visual_type': 'animation',
                      'image_cue': 'water steaming laboratory beaker', 'media_context': True,
                      'animation': {'template': 'flow', 'title': 'Water changes state',
                                    'nodes': [{'label': 'Water', 'icon': 'water'},
                                              {'label': 'Vapor', 'icon': 'particle'}]}}
        self.data = {'scenes': [self.scene], 'thumbnail_data': {'hook_phrase': 'Water changes state'}}

    def test_unfenced_nested_object_preserves_scenes_and_thumbnail(self):
        self.writer._call_with_retry = Mock(return_value=json.dumps(self.data))
        scenes = self.writer.generate_visual_scenes('Evaporation', self.narration)
        self.assertEqual(scenes[0]['animation'], self.scene['animation'])
        self.assertEqual(scenes[0]['image_cue'], self.scene['image_cue'])
        self.assertTrue(scenes[0]['media_context'])
        self.assertEqual(self.writer.last_thumbnail_data['hook_phrase'], 'Water changes state')
        self.writer._call_with_retry.assert_called_once()

    def test_fences_and_prose_preserve_outer_object(self):
        for text in ['```json\n'+json.dumps(self.data)+'\n```',
                     'Here is the plan:\n'+json.dumps(self.data)+'\nEnd.']:
            self.assertEqual(json.loads(self.writer.clean_json_response(text)), self.data)

    def test_legacy_scene_array_is_supported(self):
        self.writer._call_with_retry = Mock(return_value=json.dumps([self.scene]))
        scenes = self.writer.generate_visual_scenes('Evaporation', self.narration)
        self.assertEqual(scenes[0]['visual_type'], 'animation')
        self.assertEqual(scenes[0]['image_cue'], self.scene['image_cue'])

    def test_truncated_outer_object_is_not_replaced_with_nested_array(self):
        raw = json.dumps(self.data)[:-1]
        with self.assertRaises(ValueError):
            json.loads(self.writer.clean_json_response(raw))

    def test_bad_narration_is_retried_then_held_before_search(self):
        self.data['scenes'][0]['narration'] = 'Different words.'
        self.writer._call_with_retry = Mock(return_value=json.dumps(self.data))
        with self.assertRaises(VisualQualityHold):
            self.writer.generate_visual_scenes('Evaporation', self.narration)
        self.assertEqual(self.writer._call_with_retry.call_count, 2)

    def test_exhausted_gemini_key_is_not_retried_for_each_director_batch(self):
        bad, groq = Mock(), Mock()
        bad.models.generate_content.side_effect = RuntimeError('429 quota exceeded')
        groq.chat.completions.create.return_value.choices = [
            SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='ready', refusal=None))]
        self.writer.clients = [bad]
        self.writer.model_candidates, self.writer.model_id = ['test-model'], 'test-model'
        self.writer.groq_clients = [groq]
        self.writer.groq_model_candidates, self.writer.groq_model_id = ['groq-model'], 'groq-model'
        self.assertEqual(self.writer._call_with_retry('first'), 'ready')
        self.assertEqual(self.writer._call_with_retry('second'), 'ready')
        self.assertEqual(bad.models.generate_content.call_count, 1)

    def test_groq_json_mode_and_low_reasoning_are_requested(self):
        groq = Mock()
        groq.chat.completions.create.return_value.choices = [
            SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
                content=json.dumps(self.data), refusal=None))]
        self.writer.clients = []
        self.writer.groq_clients = [groq]
        self.writer.groq_model_candidates = ['openai/gpt-oss-120b']
        self.writer.groq_model_id = 'openai/gpt-oss-120b'
        self.assertEqual(json.loads(self.writer._call_with_retry('Return JSON', json_output=True)), self.data)
        request = groq.chat.completions.create.call_args.kwargs
        self.assertEqual(request['response_format'], {'type': 'json_object'})
        self.assertEqual(request['reasoning_effort'], 'low')

    def test_empty_groq_output_cannot_loop_forever(self):
        from automation.content.script_writer import LLM_FAILURE_SENTINEL
        groq = Mock()
        groq.chat.completions.create.return_value.choices = [
            SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='', refusal=None))]
        self.writer.clients = []
        self.writer.groq_clients = [groq]
        self.writer.groq_model_candidates = ['openai/gpt-oss-120b']
        self.writer.groq_model_id = 'openai/gpt-oss-120b'
        with patch('automation.content.script_writer.time.sleep'):
            self.assertEqual(self.writer._call_with_retry('Write'), LLM_FAILURE_SENTINEL)
        self.assertEqual(groq.chat.completions.create.call_count, 2)


class PublicationStatusRegressionTests(unittest.TestCase):
    def test_quality_hold_exits_unsuccessfully(self):
        import automation.main as entry
        pipeline = Mock()
        pipeline.run = AsyncMock(side_effect=VisualQualityHold('No contextual media'))
        with patch.object(entry, 'SciencePipeline', return_value=pipeline), patch.object(
                entry.ConfigLoader, 'load_config', return_value={}), patch.object(
                entry, 'report_hold') as report, patch.object(sys, 'argv', ['main', '--mode', 'daily']):
            coroutine = entry.main()
            with self.assertRaises(SystemExit) as raised:
                coroutine.send(None)
            coroutine.close()
        self.assertEqual(raised.exception.code, 2)
        report.assert_called_once_with('No contextual media')

    def test_empty_upload_result_is_not_success(self):
        from automation.pipelines.science_pipeline import SciencePipeline
        pipeline = SciencePipeline.__new__(SciencePipeline)
        pipeline.config, pipeline._video_asset_types = {}, None
        with patch('automation.pipelines.science_pipeline.YouTubeAuth.get_service'), patch(
                'automation.pipelines.science_pipeline.YouTubeUploader') as uploader:
            uploader.return_value.upload_video.return_value = None
            coroutine = pipeline._upload('video.mp4', 'Title', 'Script', 'Topic')
            with self.assertRaisesRegex(RuntimeError, 'no video ID'):
                coroutine.send(None)
            coroutine.close()


if __name__ == '__main__':
    unittest.main()
