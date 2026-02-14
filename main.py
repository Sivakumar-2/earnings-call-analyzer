from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import io
import os
from dotenv import load_dotenv
from groq import Groq

# ---------------- LOAD ENV ----------------

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in environment variables")

client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Earnings Transcript Analyzer")

# ---------------- CORS ----------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- ROOT ----------------

@app.get("/")
def home():
    return {"status": "Earnings Transcript Analyzer Running"}

# ---------------- TRANSCRIPT CHECK ----------------

def looks_like_transcript(text: str):
    keywords = [
        "earnings call",
        "conference call",
        "operator",
        "q&a",
        "question and answer",
        "management discussion",
        "analyst"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)

# ---------------- AI SUMMARY FUNCTION ----------------

def generate_summary(text: str):

    prompt = f"""
You are a professional equity research analyst.

Create a structured earnings call summary using ONLY information
explicitly stated in the transcript.

Follow this exact format:

EARNINGS CALL SUMMARY

Management Tone:
<optimistic / cautious / neutral / pessimistic>

Confidence Level:
<high / medium / low>

Key Positives:
• Point 1
• Point 2
• Point 3
• Point 4

Key Concerns:
• Point 1
• Point 2
• Point 3
• Point 4

Forward Guidance:

Revenue Outlook:
<text or "Not mentioned in transcript">

Margin Outlook:
<text or "Not mentioned in transcript">

Capex Outlook:
<text or "Not mentioned in transcript">

Capacity Utilization Trends:
<text or "Not mentioned in transcript">

Growth Initiatives:
• Initiative 1
• Initiative 2
• Initiative 3

RULES:
- Only use information explicitly stated in transcript
- Do NOT assume or infer
- If section missing → write "Not mentioned in transcript"
- Maintain professional equity research tone
- No extra commentary outside format

Transcript:
{text}
"""

    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1500
    )

    return completion.choices[0].message.content.strip()

# ---------------- FILE UPLOAD ENDPOINT ----------------

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        return {"error": "Only PDF files are supported"}

    pdf_bytes = await file.read()
    extracted_text = ""

    # -------- Extract Text --------
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        return {"error": f"PDF extraction failed: {str(e)}"}

    if not extracted_text.strip():
        return {
            "error": "Could not extract text. Ensure PDF contains selectable text."
        }

    # Limit size for free hosting safety
    extracted_text = extracted_text[:15000]

    # -------- Check Transcript --------
    if not looks_like_transcript(extracted_text):
        return {
            "filename": file.filename,
            "analysis": "Document does not appear to be an earnings call transcript."
        }

    # -------- Generate Summary --------
    try:
        summary = generate_summary(extracted_text)
    except Exception as e:
        return {"error": f"AI processing failed: {str(e)}"}

    return {
        "filename": file.filename,
        "analysis": summary
    }
