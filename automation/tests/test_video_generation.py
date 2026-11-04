import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation.content.editorial import prepare_scenes
from automation.media.video_generation import VideoGenerator
from automation.media.visual_bank import find_bank_clip


class VideoGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.env = patch.dict(os.environ, {'VIDEO_GEN_PROVIDER': 'kie', 'KIE_API_KEY': 'test-secret',
            'VIDEO_GEN_MAX_CLIPS': '1', 'VIDEO_GEN_DAILY_LIMIT': '2',
            'VISUAL_BANK_MANIFEST': str(Path(self.temp.name) / 'absent.json'),
            'VIDEO_GEN_CACHE_DIR': str(Path(self.temp.name) / 'clips')})
        self.env.start()
        self.scene = {'narration': 'Rainwater flows across rocks.', 'image_cue': 'silicate rocks rainwater'}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def generator(self):
        generator = VideoGenerator()
        generator.ledger_path = Path(self.temp.name) / 'ledger.json'
        return generator

    def test_kie_success_and_cache_reuse_without_second_purchase(self):
        generator = self.generator()
        def download(url, path):
            path.write_bytes(b'video')
        with patch.object(generator, '_json', side_effect=[{'taskId': 'task-1'},
                {'state': 'success', 'resultJson': json.dumps({'resultUrls': ['https://cdn.example/video.mp4']})}]) as api, \
             patch.object(generator, '_download', side_effect=download), \
             patch('automation.media.video_generation.valid_video', return_value=True):
            first = generator.generate(self.scene, 'weathering', '9:16')
            second = generator.generate(self.scene, 'weathering', '9:16')
            self.assertEqual(first, second)
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args_list[0].kwargs['json']['input']['duration'], '5')

    def test_failed_submission_still_consumes_job_budget(self):
        generator = self.generator()
        with patch.object(generator, '_submit', side_effect=ValueError('insufficient credits')) as submit:
            self.assertIsNone(generator.generate(self.scene, 'weathering'))
            self.assertIsNone(generator.generate(self.scene, 'another subject'))
            self.assertEqual(submit.call_count, 1)
        ledger = json.loads(generator.ledger_path.read_text())
        self.assertEqual(next(iter(ledger.values()))['state'], 'failed')

    def test_pending_task_resumes_without_submit(self):
        generator = self.generator()
        with patch.object(generator, '_submit', return_value={'taskId': 'one'}) as submit, \
             patch.object(generator, '_result', return_value=None), \
             patch('automation.media.video_generation.time.monotonic', side_effect=[0, 0, 1000]), \
             patch('automation.media.video_generation.time.sleep'):
            self.assertIsNone(generator.generate(self.scene, 'weathering'))
            submit.assert_called_once()
        resumed = self.generator()
        with patch.object(resumed, '_submit') as submit, \
             patch.object(resumed, '_result', return_value='https://cdn.example/video.mp4'), \
             patch.object(resumed, '_download', side_effect=lambda url, path: path.write_bytes(b'clip')):
            self.assertIsNotNone(resumed.generate(self.scene, 'weathering'))
            submit.assert_not_called()

    def test_fal_uses_returned_status_and_result_urls(self):
        with patch.dict(os.environ, {'VIDEO_GEN_PROVIDER': 'fal', 'FAL_KEY': 'fal-secret'}):
            generator = self.generator()
        task = {'status_url': 'https://queue.fal.run/fal-ai/wan/requests/one/status',
                'response_url': 'https://queue.fal.run/fal-ai/wan/requests/one'}
        with patch.object(generator, '_json', side_effect=[{'status': 'COMPLETED'},
                {'video': {'url': 'https://cdn.example/clip.mp4'}}]) as api:
            self.assertEqual(generator._result(task), 'https://cdn.example/clip.mp4')
            self.assertEqual(api.call_args_list[1].args[1], task['response_url'])

    def test_api_credentials_never_sent_to_untrusted_origin(self):
        generator = self.generator()
        with patch('requests.request') as request:
            with self.assertRaises(ValueError):
                generator._json('GET', 'https://other.example/results')
            request.assert_not_called()

    def test_ai_scene_with_specific_prompt_survives_editorial_checks(self):
        scene = {**self.scene, 'visual_type': 'ai_video',
                 'ai_video_prompt': 'Macro shot of water flowing across silicate rocks, slow push in.'}
        self.assertEqual(prepare_scenes([scene], scene['narration'], 'weathering')[0]['visual_type'], 'ai_video')

    def test_orchestrator_uses_video_before_text_card_during_outage(self):
        from automation.media.asset_orchestrator import AssetOrchestrator
        orchestrator = AssetOrchestrator()
        entry = {'scene_idx': 0, 'visual_type': 'image', **self.scene}
        with patch.object(orchestrator.video_generator, 'generate', return_value={
                'asset_path': 'generated.mp4', 'source': {'generated': True}}):
            orchestrator._use_explainer_card(entry, 'weathering', self.temp.name, '9:16')
        self.assertEqual(entry['asset_type'], 'ai_video')
        self.assertEqual(entry['visual_type'], 'ai_video')

    def test_bank_import_rejects_path_traversal(self):
        import io
        import zipfile
        from unittest.mock import Mock
        from automation.media.visual_bank import download_bank
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../outside.json', '{}')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [buffer.getvalue()]
        with patch('requests.get', return_value=response):
            with self.assertRaises(ValueError):
                download_bank('https://example.com/bank.zip', str(Path(self.temp.name) / 'bank'))
        self.assertFalse((Path(self.temp.name) / 'outside.json').exists())

    def test_unreviewed_cloud_bank_is_ignored(self):
        root = Path(self.temp.name)
        (root / 'clip.mp4').write_bytes(b'clip')
        manifest = root / 'bank.json'
        clip = {'file': 'clip.mp4', 'tags': ['silicate', 'rocks', 'rainwater'], 'approved': False}
        manifest.write_text(json.dumps({'clips': [clip]}))
        with patch.dict(os.environ, {'VISUAL_BANK_MANIFEST': str(manifest)}):
            self.assertIsNone(find_bank_clip(self.scene, 'weathering'))
            clip['approved'] = True
            manifest.write_text(json.dumps({'clips': [clip]}))
            self.assertEqual(find_bank_clip(self.scene, 'weathering')['asset_path'], str(root / 'clip.mp4'))


if __name__ == '__main__':
    unittest.main()
