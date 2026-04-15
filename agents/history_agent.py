"""
History Agent (A2A-compliant)
Now searches patients by name if no ID is given.
Creates new patients only when truly not found.
Always returns complete data.

Runs on port 8001.
"""



import os, json, re, httpx
from fastapi import FastAPI
from common.a2a_models import (
    AgentCard, AgentSkill, TaskSendRequest, TaskSendResponse,
    TaskState, Artifact, TextPart, DataPart,
)
from common.llm_client import chat, chat_json
from datetime import datetime

app = FastAPI(title="History Agent", version="2.0.0")
AGENT_PORT = int(os.getenv("HISTORY_AGENT_PORT", 8001))
PATIENT_MCP_URL = f"http://localhost:{os.getenv('PATIENT_WIKI_MCP_PORT', 9001)}"

AGENT_CARD = AgentCard(
    name="History Agent",
    description="Retrieves and summarizes patient medical history. Searches by ID or name. Creates new patients from case descriptions with full data extraction. Always produces complete clinical summaries.",
    url=f"http://localhost:{AGENT_PORT}",
    version="2.0.0",
    skills=[AgentSkill(
        id="patient_history_summary",
        name="Patient History Summary",
        description="Fetches or creates patient records and produces clinical summaries.",
        tags=["clinical", "history", "patient", "create-patient"],
        examples=["Get history for patient P001", "Summarize Rohan Verma's record", "New patient with fever and low platelets"],
    )],
)

@app.get("/.well-known/agent.json")
async def agent_card():
    return AGENT_CARD.model_dump()


@app.post("/a2a/tasks/send")
async def handle_task(request: TaskSendRequest) -> TaskSendResponse:
    task_text = "".join(p.text for p in request.message.parts if hasattr(p, "text"))

    patient_id = None
    patient_data = None
    wiki_updated = False
    created_new = False

    # STEP 1: Find by ID
    pid = _extract_pid(task_text)
    if pid:
        patient_data = await _fetch(pid)
        if patient_data:
            patient_id = pid

    # STEP 2: Find by Name
    if not patient_data:
        name = _extract_name(task_text)
        if name:
            found = await _search_name(name)
            if found:
                patient_id = found["patient_id"]
                patient_data = found["patient"]

    # STEP 3: Create new patient
    if not patient_data:
        patient_data, patient_id, created_new = await _create_from_case(task_text)
        wiki_updated = True

    if not patient_data:
        return _fail(request.id, "Could not find or create patient record.")

    # STEP 4: Update wiki with follow-up data (runs for BOTH new and existing patients)
    if patient_id and patient_id != "UNKNOWN":
        try:
            new_data = await _extract_updates(task_text)
            if new_data:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    await client.post(f"{PATIENT_MCP_URL}/mcp/tools/update_patient",
                        json={"patient_id": patient_id, "updates": new_data})
                    wiki_updated = True
                patient_data = await _fetch(patient_id) or patient_data
        except:
            pass
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{PATIENT_MCP_URL}/mcp/tools/ingest_record",
                    json={"patient_id": patient_id, "record": {
                        "date": datetime.now().isoformat(), "type": "follow_up",
                        "note": task_text[:800], "source": "history-agent",
                    }})
                wiki_updated = True
        except:
            pass

    # STEP 5: Generate summary
    system_prompt = """You are a clinical documentation specialist.

ABSOLUTE RULES — VIOLATION IS A CRITICAL ERROR:
1. Use ONLY data from the patient record JSON and case text provided below.
2. NEVER invent ANY information. No fabricated vitals, labs, allergies, history, or demographics.
3. Use the EXACT name from the data. Do NOT add or change names.
4. Use the EXACT age. If the data says 23, write 23.
5. If a vital sign is null in the data, write "Not recorded" — do NOT make up a number.
6. If allergies list is empty, write "No known allergies" — do NOT invent allergies.
7. If medical_history is empty, write "No significant medical history."
8. If lab_results_recent is empty, write "No lab results available."
9. CROSS-CHECK every fact you write: Is it in the JSON or case text? If NO, do not write it.

Sections:
1. PATIENT OVERVIEW (ONLY name, age, gender from data)
2. CURRENT PRESENTATION (ONLY complaints and vitals that are NOT null)
3. MEDICAL HISTORY (ONLY if present in data)
4. ALLERGIES (EXACTLY as listed — empty means none)
5. LAB FINDINGS (ONLY if present — empty means none)
6. FAMILY & SOCIAL HISTORY (ONLY if present)
7. TRAVEL/SOCIAL CONTEXT (if mentioned)
8. KEY CLINICAL FLAGS (based ONLY on actual data provided)"""
    user_msg = f"Patient record:\n{json.dumps(patient_data, indent=2)}\n\nCurrent case:\n{task_text}"
    try:
        summary = chat(system_prompt, user_msg)
    except:
        summary = f"Patient: {patient_data.get('name')}, Age: {patient_data.get('age')}, Gender: {patient_data.get('gender')}\n\n{json.dumps(patient_data, indent=2)}"

    tools_used = ["create_patient"] if created_new else ["query_patient"]
    if wiki_updated and not created_new:
        tools_used.extend(["update_patient", "ingest_record"])

    artifacts = [Artifact(type="text", parts=[TextPart(text=summary)], metadata={
        "source_agent": "history-agent", "patient_id": patient_id, "mcp_tools_used": tools_used,
        "wiki_updated": wiki_updated, "new_patient_created": created_new, "timestamp": datetime.now().isoformat(),
    })]

    if wiki_updated:
        msg = f"New patient {patient_id} ({patient_data.get('name')}) created." if created_new else f"Patient {patient_id} ({patient_data.get('name')}) wiki updated with follow-up data."
        artifacts.append(Artifact(type="data", parts=[DataPart(data={
            "wiki_update": msg, "patient_id": patient_id, "new_patient": created_new, "storage_location": "data/patients.json",
        })], metadata={"type": "wiki_update_notification"}))

    return TaskSendResponse(id=request.id, state=TaskState.COMPLETED, artifacts=artifacts,
        metadata={"agent": "history-agent", "patient_id": patient_id, "patient_name": patient_data.get("name"),
                   "wiki_updated": wiki_updated, "new_patient_created": created_new})


async def _fetch(pid: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f"{PATIENT_MCP_URL}/mcp/tools/query_patient", json={"patient_id": pid})
            d = r.json()
            if d.get("status") == "success":
                return d["result"]
    except:
        pass
    return None

async def _search_name(name: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{PATIENT_MCP_URL}/mcp/tools/search_patient", json={"name": name})
            d = r.json()
            if d.get("status") == "success":
                return d["result"]
    except:
        pass
    return None

async def _extract_updates(case_text: str) -> dict | None:
    """Extract ONLY explicitly mentioned new vitals, labs, complaints from text."""
    try:
        result = chat_json(
            """Extract ONLY medical values that are EXPLICITLY written in this text.

RULES:
1. If a vital sign is NOT mentioned, do NOT include it in the output.
2. Do NOT invent or assume any values.
3. Only include fields where you can point to the exact text that states the value.
4. Return {} if no clinical values are explicitly stated.

Return ONLY valid JSON with these possible fields (include ONLY what is mentioned):
{
    "vitals_latest": {},
    "lab_results_recent": {},
    "current_complaints": []
}

EXAMPLES:
- Text says "BP 155/60" → include blood_pressure_systolic: 155, blood_pressure_diastolic: 60
- Text does NOT mention BP → do NOT include any BP fields
- Text says "stomach pain" → include in current_complaints
- Text does NOT mention temperature → do NOT include temperature""",
            case_text
        )
        # Remove any null or empty values to prevent overwriting good data with nulls
        if result:
            cleaned = {}
            for key, value in result.items():
                if isinstance(value, dict):
                    clean_sub = {k: v for k, v in value.items() if v is not None and v != "null" and v != ""}
                    if clean_sub:
                        cleaned[key] = clean_sub
                elif isinstance(value, list) and len(value) > 0:
                    cleaned[key] = value
            return cleaned if cleaned else None
        return None
    except:
        return None
async def _create_from_case(case_text: str) -> tuple:
    prompt = """Extract patient information from this clinical case text.
Return ONLY valid JSON with no explanation.

CRITICAL RULES:
1. Extract ONLY information that is EXPLICITLY stated in the text.
2. If a value is NOT mentioned in the text, use null for numbers and "Not documented" for strings.
3. Do NOT copy the example values below — they are null placeholders.
4. Do NOT invent temperature, blood pressure, heart rate, SpO2, lab values, or allergies.
5. Age must be the EXACT number from the text. "23" means 23 — not 32 or any other number.
6. If no allergies are mentioned, use an empty list [].
7. If no medications are mentioned, use an empty list [].
8. If no vitals are mentioned, leave all vital fields as null.
9. If no lab results are mentioned, use an empty object {}.

{
    "name": null,
    "age": null,
    "gender": null,
    "blood_group": null,
    "demographics": {},
    "vitals_latest": {
        "temperature_fahrenheit": null,
        "temperature_celsius": null,
        "blood_pressure_systolic": null,
        "blood_pressure_diastolic": null,
        "heart_rate": null,
        "spo2": null,
        "respiratory_rate": null
    },
    "medical_history": [],
    "allergies": [],
    "surgical_history": [],
    "family_history": [],
    "lab_results_recent": {},
    "current_complaints": [],
    "travel_history": null,
    "social_history": null
}

EXAMPLES OF CORRECT EXTRACTION:
- Text says "age 23" → "age": 23
- Text does NOT mention BP → "blood_pressure_systolic": null, "blood_pressure_diastolic": null
- Text does NOT mention temperature → "temperature_fahrenheit": null, "temperature_celsius": null
- Text says "no medical history" → "medical_history": []
- Text does NOT mention allergies → "allergies": []
- Text says "stomach pain and headache" → "current_complaints": ["stomach pain", "headache"]
- Text says "traveled last week" → "travel_history": "traveled in last week"

WRONG EXTRACTION (NEVER DO THIS):
- Text does NOT mention BP but you write 160/90 → WRONG
- Text says age 23 but you write 32 → WRONG
- Text does NOT mention allergies but you write "Penicillin" → WRONG
- Text does NOT mention temperature but you write 101 → WRONG"""

    try:
        data = chat_json(prompt, case_text)
    except:
        data = {"name": "Unknown", "age": "Unknown", "current_complaints": [case_text[:200]]}

    # Hard validation with regex fallbacks
    if data.get("age") in (0, None, "null", "", "Unknown"):
        m = re.search(r'(\d{1,3})[-\s]?year[-\s]?old', case_text.lower())
        if m:
            data["age"] = int(m.group(1))

    if not data.get("gender") or data["gender"] in ("Unknown", "null"):
        tl = case_text.lower()
        if any(x in tl for x in [" male ", "male patient", "-year-old male", " man ", " boy "]):
            data["gender"] = "Male"
        elif any(x in tl for x in [" female ", "female patient", "-year-old female", " woman ", " girl "]):
            data["gender"] = "Female"

    if not data.get("name") or data["name"] in ("Unknown", "Unknown Patient", "null"):
        for pat in [r'named\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:presents|returns|comes|reports)']:
            m = re.search(pat, case_text)
            if m:
                data["name"] = m.group(1)
                break

    print(f"\n--- Extracted: {data.get('name')} | Age: {data.get('age')} | Gender: {data.get('gender')} ---\n")

    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(f"{PATIENT_MCP_URL}/mcp/tools/create_patient", json={"patient_data": data})
            d = r.json()
            if d.get("status") == "success":
                data["patient_id"] = d["patient_id"]
                return data, d["patient_id"], True
    except:
        pass
    return data, "UNKNOWN", False


def _fail(tid, msg):
    return TaskSendResponse(id=tid, state=TaskState.FAILED,
        artifacts=[Artifact(type="text", parts=[TextPart(text=msg)])],
        metadata={"agent": "history-agent", "error": msg})

def _extract_pid(text):
    m = re.search(r'\b(P\d{3})\b', text.upper())
    return m.group(1) if m else None

def _extract_name(text):
    for pat in [r'named\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', r'patient\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:presents|returns|comes|reports)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:a\s+)?\d{1,3}[-\s]?year']:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


@app.get("/health")
async def health():
    return {"status": "ok", "service": "history-agent", "port": AGENT_PORT}

if __name__ == "__main__":
    import uvicorn
    print(f"History Agent on port {AGENT_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)