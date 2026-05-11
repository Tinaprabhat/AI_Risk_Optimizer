# AI Representation Optimizer

Audit how AI shopping agents see your Shopify store — and fix what's blocking you.

## Setup

### 1. Clone and install
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Start Ollama (optional — fallback LLM)
```bash
# Install Ollama from https://ollama.com
ollama pull mistral
ollama serve
```

### 4. Run
```bash
streamlit run app.py
```

---

## Architecture

```
MERCHANT INPUT (URL + description + 4 MCQs)
      ↓
L1  Crawlability          R1 R3 R5 R6       binary    0 LLM
L2  Structured Data       R7 R9 R11          mixed     0 LLM
L3  Semantic Content      R13 R15 R16 R17    mixed     0 LLM
L4  Trust Signals         R23 R25            binary    0 LLM
L5  AI-Era Protocols      R28 R30 R31        mixed     0 LLM
      ↓
L6  Semantic Gap          gap_IW gap_IS gap_WS         0 LLM
      ↓
L7  Aggregation           X/79 score + conclusion   1 Gemini call
      ↓
P2  Fix Engine            chatbot per failed check  ~5 Gemini calls/fix
```

**LLM fallback chain:** Gemini 2.5 Flash → Ollama Mistral → Rule-based

## Score System
- 7 scored checks (R7, R9, R13, R16, R17, R30, R31): 0–10 each = max 70
- 9 binary checks (R1, R3, R5, R6, R11, R15, R23, R25, R28): 0/1 each = max 9
- **Total: X / 79**

## Project Structure
```
ai_rep_optimizer/
├── app.py                  # Streamlit UI
├── requirements.txt
├── .env.example
├── src/
│   ├── auditor.py          # Main orchestrator
│   ├── layer1/
│   │   ├── r1_robots.py
│   │   └── r3_r5_r6.py
│   ├── layer2/
│   │   └── r7_r9_r11.py
│   ├── layer3/
│   │   └── r13_r15_r16_r17.py
│   ├── layer4/
│   │   └── r23_r25.py
│   ├── layer5/
│   │   └── r28_r30_r31.py
│   ├── layer6/
│   │   └── semantic_gap.py
│   ├── layer7/
│   │   └── aggregator.py
│   ├── part2/
│   │   └── fix_engine.py
│   └── utils/
│       ├── fetcher.py      # HTTP with correct timeouts
│       ├── llm.py          # Gemini + Ollama fallback
│       ├── embedder.py     # all-MiniLM-L6-v2 singleton
│       └── db.py           # SQLite with WAL mode
└── db/
    └── audits.db           # Auto-created on first run
```
