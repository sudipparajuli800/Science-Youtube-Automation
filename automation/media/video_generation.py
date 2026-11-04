"""Bounded hosted video generation. Credentials never leave their API origin."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

import requests


def visual_prompt(scene, topic):
    subject = scene.get('ai_video_prompt') or scene.get('image_cue') or topic
    return (f'Science documentary illustration of {topic}. Shot: {subject}. '
            f'Illustrate this narration: {scene.get("narration", "")}. '
            'One coherent shot, subtle natural subject motion, slow camera movement, '
            'clear subject, realistic lighting. Preserve physical plausibility. '
            'No text, captions, logos, narration or music. Conceptual illustration, '
            'not claimed observational evidence.')[:4500]


def valid_video(path):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'json', str(path)],
            capture_output=True, text=True, timeout=20)
        streams = json.loads(result.stdout).get('streams', [])
        return result.returncode == 0 and bool(streams) and min(
            streams[0].get('width', 0), streams[0].get('height', 0)) >= 240
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


class VideoGenerator:
    def __init__(self):
        provider = os.getenv('VIDEO_GEN_PROVIDER', 'auto').lower()
        if provider == 'auto':
            provider = 'kie' if os.getenv('KIE_API_KEY') else 'fal' if os.getenv('FAL_KEY') else 'none'
        if provider not in ('none', 'kie', 'fal'):
            raise ValueError('VIDEO_GEN_PROVIDER must be auto, none, kie or fal')
        self.provider = provider
        self.key = os.getenv('KIE_API_KEY' if provider == 'kie' else 'FAL_KEY', '')
        self.model = 'wan/2-6-text-to-video' if provider == 'kie' else 'fal-ai/wan/v2.2-a14b/text-to-video'
        self.limit = max(0, min(10, int(os.getenv('VIDEO_GEN_MAX_CLIPS', '1'))))
        self.daily_limit = max(0, int(os.getenv('VIDEO_GEN_DAILY_LIMIT', '2')))
        self.timeout = max(1, min(1200, int(os.getenv('VIDEO_GEN_TIMEOUT', '600'))))
        self.root = Path(os.getenv('VIDEO_GEN_CACHE_DIR', 'automation/storage/generated_clips'))
        self.ledger_path = Path('automation/storage/video_generation_jobs.json')
        self.submissions = 0
        self.disabled = False
        self.used_bank_paths = set()

    def _load(self):
        if not self.ledger_path.exists():
            return {}
        # A corrupt ledger must not reset spending history.
        return json.loads(self.ledger_path.read_text(encoding='utf-8'))

    def _save(self, ledger):
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.ledger_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(ledger, indent=2), encoding='utf-8')
        temporary.replace(self.ledger_path)

    def _json(self, method, url, **kwargs):
        origin = urlsplit(url)
        allowed = 'api.kie.ai' if self.provider == 'kie' else 'queue.fal.run'
        if origin.scheme != 'https' or origin.hostname != allowed:
            raise ValueError('Unexpected video API origin')
        authorization = ('Bearer ' if self.provider == 'kie' else 'Key ') + self.key
        response = requests.request(method, url, headers={'Authorization': authorization},
                                    timeout=30, allow_redirects=False, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if self.provider == 'kie' and payload.get('code') != 200:
            raise ValueError(f'Kie API code {payload.get("code")}')
        return payload.get('data', {}) if self.provider == 'kie' else payload

    def _submit(self, prompt, aspect):
        if self.provider == 'kie':
            return self._json('POST', 'https://api.kie.ai/api/v1/jobs/createTask', json={
                'model': self.model, 'input': {'prompt': prompt, 'duration': '5',
                'resolution': '720p', 'multi_shots': False}})
        return self._json('POST', 'https://queue.fal.run/' + self.model, json={
            'prompt': prompt, 'aspect_ratio': aspect, 'resolution': '720p',
            'num_frames': 81, 'frames_per_second': 16,
            'enable_safety_checker': True, 'enable_output_safety_checker': True})

    def _result(self, task):
        if self.provider == 'kie':
            status = self._json('GET', 'https://api.kie.ai/api/v1/jobs/recordInfo',
                                params={'taskId': task['taskId']})
            if status.get('state') == 'fail':
                raise ValueError('Kie task failed')
            if status.get('state') == 'success':
                return json.loads(status['resultJson'])['resultUrls'][0]
        else:
            status = self._json('GET', task['status_url'])
            if status.get('error') or status.get('status') == 'FAILED':
                raise ValueError('fal task failed')
            if status.get('status') == 'COMPLETED':
                return self._json('GET', task['response_url'])['video']['url']
        return None

    def _download(self, url, path):
        if urlsplit(url).scheme != 'https':
            raise ValueError('Video download requires HTTPS')
        # No Authorization headers on the output CDN.
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            size = 0
            temporary = path.with_suffix('.part')
            try:
                with temporary.open('wb') as output:
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 150 * 1024 * 1024:
                            raise ValueError('Generated video exceeds 150 MB')
                        output.write(chunk)
                if not valid_video(temporary):
                    raise ValueError('Generated output is not a usable video')
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)

    def generate(self, scene, topic, aspect='16:9'):
        from .visual_bank import find_bank_clip
        bank = find_bank_clip(scene, topic, self.used_bank_paths)
        if bank and valid_video(bank['asset_path']):
            self.used_bank_paths.add(bank['asset_path'])
            return bank
        if self.provider == 'none' or not self.key or not self.limit or self.disabled:
            return None
        prompt = visual_prompt(scene, topic)
        fingerprint = hashlib.sha256(json.dumps([self.provider, self.model, prompt, aspect]).encode()).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / (fingerprint + '.mp4')
        source = {'provider': self.provider, 'model': self.model, 'generated': True,
                  'label': 'AI-generated illustration', 'prompt': prompt}
        if path.exists() and valid_video(path):
            return {'asset_path': str(path), 'source': source}
        ledger = self._load()
        record = ledger.get(fingerprint)
        today = time.strftime('%Y-%m-%d', time.gmtime())
        if record and record.get('state') in ('failed', 'submitting'):
            return None  # Never repeat an ambiguous or failed billable submission.
        if not record:
            daily = sum(r.get('date') == today for r in ledger.values())
            if self.submissions >= self.limit or daily >= self.daily_limit:
                return None
            self.submissions += 1
            record = {'date': today, 'state': 'submitting', 'provider': self.provider}
            ledger[fingerprint] = record
            self._save(ledger)  # Reserve attempt before network I/O; no POST retries.
        try:
            if record['state'] == 'submitting':
                record.update(task=self._submit(prompt, aspect), state='pending')
                self._save(ledger)
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                url = self._result(record['task'])
                if url:
                    self._download(url, path)
                    record['state'] = 'complete'
                    self._save(ledger)
                    return {'asset_path': str(path), 'source': source}
                time.sleep(10)
            # Keep pending task ID so the next run resumes instead of purchasing twice.
            self.disabled = True
            print(f'[VideoGen] {self.provider} still processing; task saved for resume.')
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            # A polling/network/download failure retains a resumable task.
            if 'task' not in record:
                record['state'] = 'failed'
            self._save(ledger)
            self.disabled = True
            print(f'[VideoGen] {self.provider} unavailable ({type(error).__name__}, HTTP {status or "n/a"}); using other visuals.')
        return None
