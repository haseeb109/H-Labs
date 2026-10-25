"""Voiceover text helpers (word counts are REAL counts, per Rule 3)."""
import re

BANNED_VO = ["let me know in the comments", "smash that like button", "don't forget to subscribe",
             "hit the bell", "welcome back to the channel", "in today's video", "before we get started"]


def words(text):
    return [w for w in text.split() if re.search(r"[A-Za-z0-9]", w)]


def n_words(text):
    return len(words(text))


def sentences(text):
    parts = re.split(r"(?<=[.!?])[\"'”]?\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def norm_sentence(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def split_bridge(text, after_sentence=None):
    """-> (closing_part, opening_part). after_sentence is 1-based; None = nearest the word midpoint."""
    sents = sentences(text)
    if len(sents) < 2:
        return text, ""
    if after_sentence is None:
        total = n_words(text)
        run, best, bd = 0, 1, 10 ** 9
        for i, s in enumerate(sents[:-1], 1):
            run += n_words(s)
            if abs(run - total / 2) < bd:
                bd, best = abs(run - total / 2), i
        after_sentence = best
    k = max(1, min(int(after_sentence), len(sents) - 1))
    return " ".join(sents[:k]), " ".join(sents[k:])


def ngrams(text, n=5):
    w = [x.lower().strip(".,!?\"'") for x in words(text)]
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def est_seconds(text, wps=2.6):
    return n_words(text) / wps + 0.5


# ---- AI-voice clip limit (Trial Tales lock): every generated clip must be <= CLIP_MAX seconds ----
CLIP_MAX = 18.0          # hard ceiling for any single AI-voice clip
CLIP_TARGET = 17.0       # what the splitter aims for so measured audio stays under the ceiling


def split_clips(text, max_s=CLIP_TARGET, wps=2.6):
    """Split a VO into the fewest sentence-aligned clips, each estimated <= max_s seconds.
    Returns list[str]. A single sentence that is too long stays alone (validator flags it)."""
    sents = sentences(text)
    if not sents:
        return [text]
    cap = max(8, int((max_s - 0.5) * wps))          # words per clip
    # fewest clips, then balance
    k = 1
    while True:
        # greedy by balanced target
        total = n_words(text)
        tgt = total / k
        groups, cur, cw = [], [], 0
        for i, s in enumerate(sents):
            sw = n_words(s)
            remaining_groups = k - len(groups)
            if cur and (cw + sw > cap or (cw >= tgt * 0.95 and remaining_groups > 1)):
                groups.append(cur)
                cur, cw = [], 0
            cur.append(s)
            cw += sw
        if cur:
            groups.append(cur)
        ok = all(sum(n_words(s) for s in g) <= cap for g in groups)
        if ok or k >= len(sents):
            return [" ".join(g) for g in groups]
        k += 1


def clip_issues(text, max_s=CLIP_TARGET, wps=2.6):
    """Names the sentences that alone cannot fit in one clip."""
    cap = max(8, int((max_s - 0.5) * wps))
    return [s for s in sentences(text) if n_words(s) > cap]
