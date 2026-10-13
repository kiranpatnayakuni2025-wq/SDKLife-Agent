SDK SCOUT AGENT - START HERE
============================

What it does
------------
You choose a region and the kind of campus. The agent finds matching colleges, researches public
information about each one, finds signs that it needs a digital outpass system, scores it, and gives you
a ranked list. Every high-priority pick has links so you can check the evidence yourself.
It never contacts a college and never logs in anywhere.

First-time setup (about 10 minutes)
-----------------------------------
1. Install Python from https://www.python.org/downloads/
   On the first install screen, tick "Add python.exe to PATH". (Skip if Python is already installed.)
2. Get a Groq key at https://console.groq.com/keys (starts with gsk_).
3. Open the file  config.env  with Notepad.
   Replace  PASTE_YOUR_GROQ_API_KEY_HERE  with your key (no quotes, no spaces). Save the file.
4. Double-click  Start SDK Scout Agent.bat
   The first start installs what it needs and then opens the agent in your browser.

Trying it before you add a key
------------------------------
Skip step 3. The agent starts in Demo mode with INVENTED sample colleges, so you can click through every
screen at no cost.

Using it
--------
1. "Define search": the settings are already filled with the approved first run
   (Rajasthan, 500+ hostel students). Start with 3 to 5 colleges to see the cost.
2. Click "Start discovery" and wait. Each college takes a minute or two.
3. "Ranked prospects": see the list, open a college, read the evidence, and mark it
   Shortlisted, Review Later or Not Relevant. Download everything as Excel any time.

How scoring works
-----------------
It follows the approved "Ideal Customer & Scoring Sheet". The AI only reports what it finds. A separate
program, scout/scoring.py, does the maths. A signal only counts if its link really appeared in the search
results. A claim without a verifiable source is shown as a "lead to check by hand" and gets no points.

Where things are
----------------
config.env          your API key and settings
scout/scoring.py    weights and High/Medium/Low rules (change numbers here)
scout/prompts.py    what the agent is told to look for
data/               saved searches and your shortlist decisions (nothing leaves your computer except
                    the searches and the requests to Groq)

Good to know
------------
- Results depend on what is public. Some colleges publish little; they show as "Thin evidence".
- Some government tender sites block automated search. The agent reports gaps instead of guessing.
- Always check the links behind a High priority before reaching out.
- How research works on Groq: the agent runs the web searches itself (free DuckDuckGo search), gives Groq
  the result snippets as a numbered list, and Groq reads and judges them. It reads snippets, not whole
  pages, so it is shallower than a person reading the college's site. Every link shown came from a real
  search result.
- Groq's free plan allows only a few thousand tokens per minute and a daily cap, so expect a minute or two
  per college and roughly a few dozen colleges a day at most. The agent waits and retries on its own.
  Finished colleges are always saved.
- If searches come back empty, DuckDuckGo may be limiting you for a few minutes. A free Tavily key
  (tavily.com), pasted as TAVILY_API_KEY in config.env, makes search steadier.
- Dates are often missing from search snippets, so some signals show "date unknown" and score nothing for
  recency. Check them by hand before reaching out.
- The agent can also use Google Gemini or Anthropic Claude: change PROVIDER in config.env.
- After any change to config.env, close the black window and start the agent again.
