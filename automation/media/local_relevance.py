"""CPU CLIP fallback for broad b-roll matching, not scientific fact checking."""
import os
from functools import lru_cache

_failed = False


@lru_cache(maxsize=1)
def load_model():
    import torch
    from transformers import CLIPModel, CLIPProcessor
    torch.set_num_threads(2)
    name = 'openai/clip-vit-base-patch32'
    processor = CLIPProcessor.from_pretrained(name, use_auth_token=False)
    model = CLIPModel.from_pretrained(name, use_auth_token=False).to('cpu').eval()
    return processor, model


def score_image(image_bytes, description):
    from io import BytesIO
    import torch
    from PIL import Image
    processor, model = load_model()
    labels = ['A documentary image of ' + description,
              'Unrelated generic stock footage.',
              'A title card with text, logos or a watermark.',
              'An unrelated person posing for the camera.']
    with Image.open(BytesIO(image_bytes)) as source:
        inputs = processor(text=labels, images=source.convert('RGB'), return_tensors='pt',
                           padding=True, truncation=True, max_length=77)
    with torch.inference_mode():
        output = model(**inputs)
        return (output.image_embeds @ output.text_embeds.T)[0].tolist()


def accept_scores(scores):
    # Absolute similarity plus contrast. Never accept just because it ranks first.
    return scores[0] >= .28 and scores[0] - max(scores[1:]) >= .03


def check_local(image_bytes, description):
    global _failed
    if os.getenv('LOCAL_VISUAL_RELEVANCE', '').lower() != 'true' or _failed:
        return None
    try:
        scores = score_image(image_bytes, description)
        accepted = accept_scores(scores)
        print(f'[LocalRelevance] CPU similarity {scores[0]:.3f}: {"accept" if accepted else "reject"}.')
        return accepted
    except Exception as error:
        _failed = True
        print(f'[LocalRelevance] Model unavailable ({type(error).__name__}); no asset approved.')
        return None
