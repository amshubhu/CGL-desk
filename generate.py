"""Build data/latest.json for the day.
Source order: (1) a manual file in inbox/ dated today, else (2) The Hindu's public editorial RSS feed
(headline + one-line summary only). Uses GitHub Models with the built-in GITHUB_TOKEN."""
import glob, json, os, datetime, requests
import xml.etree.ElementTree as ET

today = datetime.date.today().isoformat()
RSS = "https://www.thehindu.com/opinion/editorial/feeder/default.rss"

def from_inbox():
    f = sorted(glob.glob("inbox/*.txt"), key=os.path.getmtime)
    if f and datetime.date.fromtimestamp(os.path.getmtime(f[-1])).isoformat() == today:
        return "FULL EDITORIAL TEXT (paraphrase it, do not copy):\n" + open(f[-1], encoding="utf-8").read().strip()

def from_rss():
    r = requests.get(RSS, headers={"User-Agent": "Mozilla/5.0 personal-study-bot"}, timeout=60)
    r.raise_for_status()
    items = []
    for it in ET.fromstring(r.content).iter("item"):
        t = (it.findtext("title") or "").strip()
        d = (it.findtext("description") or "").strip()
        if t:
            items.append(f"- {t}: {d}")
        if len(items) == 3:
            break
    if not items:
        raise SystemExit("RSS feed returned no editorials")
    return ("TODAY'S EDITORIAL HEADLINES AND ONE-LINE SUMMARIES (this is all you are given):\n" + "\n".join(items) +
            "\nPick the most exam-friendly topic. Use only these facts plus well-established general background. "
            "Do not invent statistics, quotes, names or dates.")

source_note = from_inbox()
label = "Based on a The Hindu editorial"
if not source_note:
    source_note, label = from_rss(), "Inspired by today's The Hindu editorial headlines"

prompt = f"""You are an SSC CGL Tier 2 English tutor. Create practice material from the input below.
Write an ORIGINAL passage of 350-450 words in clear, formal exam-style prose; never copy long stretches of any article.
Return ONLY JSON with this shape:
{{"date":"{today}","title":"...","source":"{label}",
"passage":"paragraphs separated by \\n\\n",
"cloze":{{"text":"~120-word paragraph with blanks written as __1__ to __5__","options":[[4 options] x5],"answers":[index of correct option x5]}},
"mcq":[10 items: {{"tag":"Passage"|"Vocab"|"Inference"|"Idiom","q":"...","options":[4],"answer":index,"explain":"one line"}}]}}
Include 4 vocab questions (meaning, synonym or antonym of words used in the passage). Each question must have exactly one defensible answer.

INPUT:
{source_note}"""

import time, re
headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
           "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}
body = {"model": "openai/gpt-4.1-mini", "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4, "max_tokens": 4000}
data = None
for attempt in range(3):
    r = requests.post("https://models.github.ai/inference/chat/completions", headers=headers, json=body, timeout=180)
    print(f"Attempt {attempt+1}: HTTP {r.status_code}, {len(r.text)} chars")
    if r.status_code == 200 and r.text.strip():
        try:
            txt = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", txt, re.S)
            data = json.loads(m.group(0))
            break
        except Exception as e:
            print("Could not parse reply:", e, r.text[:500])
    else:
        print("Reply body:", r.text[:500])
    time.sleep(5)
if data is None:
    raise SystemExit("Model call failed - see the reply body printed above")
assert data.get("passage") and len(data.get("mcq", [])) >= 5, "Model output looks incomplete"
os.makedirs("data", exist_ok=True)
for name in ("latest.json", f"{today}.json"):
    json.dump(data, open(f"data/{name}", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Wrote data/latest.json")
