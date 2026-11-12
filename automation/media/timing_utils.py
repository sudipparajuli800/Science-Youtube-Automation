import re

def calculate_adjusted_durations(scenes, fps=30) -> list[float]:
    """
    Calculates adjusted visual scene durations accounting for transitions.
    Formula:
    - Each flash adds 2/fps = 0.0667s to total duration
    - Each fade removes fade_overlap_seconds (0.5s)
    """
    durations = []
    transitions = []
    for i in range(len(scenes) - 1):
        next_type = scenes[i+1].get("visual_type")
        curr_type = scenes[i].get("visual_type")
        if next_type in ("hook_question", "kinetic_stat"):
            transitions.append("flash")
        elif (curr_type == "image" and next_type == "ai_video") or (curr_type == "ai_video" and next_type == "image"):
            transitions.append("fade")
        else:
            transitions.append("cut")
            
    for i, scene in enumerate(scenes):
        base_dur = 5.0 # default base visual duration if none specified
        before_t = transitions[i-1] if i > 0 else None
        after_t = transitions[i] if i < len(transitions) else None
        
        adj_dur = base_dur
        if before_t == "fade":
            adj_dur += 0.5
        if after_t == "flash":
            adj_dur += 0.0667
        durations.append(adj_dur)
    return durations

def match_scenes_to_timestamps(scenes, word_offsets, total_duration):
    """Align the whole narration once, then partition it into contiguous scenes."""
    if not scenes:
        return []
    from difflib import SequenceMatcher
    import numpy as np

    def tokens(text):
        return re.findall(r"[a-z0-9]+", str(text).lower())

    counts = [len(tokens(scene.get("narration", ""))) for scene in scenes]
    script_words = [word for scene in scenes for word in tokens(scene.get("narration", ""))]
    spoken, starts = [], []
    for offset in word_offsets:
        words = tokens(offset.get("word", ""))
        for i, word in enumerate(words):
            spoken.append(word)
            starts.append(float(offset["start"]) + i * float(offset.get("duration", 0)) / len(words))
    anchors = {0: 0.0, len(script_words): float(total_duration)}
    if script_words and spoken:
        matcher = SequenceMatcher(None, script_words, spoken, autojunk=False)
        for block in matcher.get_matching_blocks():
            for i in range(block.size):
                index = block.a + i
                if index:
                    anchors[index] = min(total_duration, max(0.0, starts[block.b + i]))
    positions = sorted(anchors)
    values = np.maximum.accumulate([anchors[index] for index in positions])
    boundaries = [0.0]
    count = 0
    for words in counts[:-1]:
        count += words
        boundaries.append(float(np.interp(count, positions, values)) if script_words
                          else len(boundaries) * total_duration / len(scenes))
    boundaries.append(float(total_duration))
    # Reserve a frame for each remaining scene, including malformed legacy plans.
    minimum = min(1 / 30, total_duration / max(1, len(scenes)))
    for i in range(1, len(boundaries) - 1):
        boundaries[i] = min(max(boundaries[i], boundaries[i-1] + minimum),
                            total_duration - (len(scenes)-i) * minimum)
    return [{"start": start, "end": end, "duration": end-start,
             "word_times": [max(0.0, t-start) for t in starts if start <= t < end]}
            for start, end in zip(boundaries, boundaries[1:])]
