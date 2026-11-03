import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PIL import Image
from automation.media import visual_relevance as vr


class VisionFallbackTests(unittest.TestCase):
    def setUp(self):
        vr._UNAVAILABLE_KEYS.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'asset.png')
        Image.new('RGB', (20, 20)).save(self.path)

    def tearDown(self):
        self.temp.cleanup()
        vr._UNAVAILABLE_KEYS.clear()

    def test_groq_recovers_after_gemini_unavailable(self):
        with patch.object(vr, '_check_gemini', return_value=None), \
             patch.object(vr, '_check_groq', return_value=True) as groq:
            self.assertTrue(vr.is_visually_relevant(self.path, 'dinosaur eggs', strict=True))
            self.assertTrue(groq.call_args.args[0].startswith(bytes([255, 216])))

    def test_real_rejection_is_final(self):
        with patch.object(vr, '_check_gemini', return_value=False), \
             patch.object(vr, '_check_groq') as groq:
            self.assertFalse(vr.is_visually_relevant(self.path, 'dinosaur eggs', strict=True))
            groq.assert_not_called()

    def test_all_unavailable_has_distinct_error(self):
        with patch.object(vr, '_check_gemini', return_value=None), \
             patch.object(vr, '_check_groq', return_value=None):
            with self.assertRaises(vr.VerificationUnavailable):
                vr.is_visually_relevant(self.path, 'dinosaur eggs', strict=True)

    def test_key_rotation_and_circuit_breaker(self):
        failed = Mock()
        failed.models.generate_content.side_effect = RuntimeError('402 RESOURCE_EXHAUSTED')
        good = Mock()
        good.models.generate_content.return_value.text = 'YES'
        factory = Mock(side_effect=[failed, good, good])
        genai = SimpleNamespace(Client=factory)
        types = SimpleNamespace(Part=SimpleNamespace(from_bytes=lambda **kwargs: kwargs))
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'first', 'GEMINI_API_KEY2': 'second', 'GEMINI_API_KEY3': ''}), \
             patch.dict(sys.modules, {'google': SimpleNamespace(genai=genai), 'google.genai': SimpleNamespace(types=types)}):
            self.assertTrue(vr._check_gemini(b'jpeg', 'question'))
            self.assertTrue(vr._check_gemini(b'jpeg', 'question'))
        self.assertEqual(failed.models.generate_content.call_count, 1)
        self.assertEqual(factory.call_args_list[1].kwargs['api_key'], 'second')

    def test_groq_request_uses_vision_model(self):
        response = Mock()
        response.json.return_value = {'choices': [{'message': {'content': 'NO'}}]}
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test', 'GROQ_API_KEY2': '', 'GROQ_API_KEY3': ''}), \
             patch('requests.post', return_value=response) as post:
            self.assertFalse(vr._check_groq(b'jpeg', 'question'))
            self.assertIn('image_url', str(post.call_args.kwargs['json']))


if __name__ == '__main__':
    unittest.main()
