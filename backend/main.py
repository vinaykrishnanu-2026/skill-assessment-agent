from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

client = OpenAI()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class SkillSchema(BaseModel):
    name: str
    importance: int

class SkillList(BaseModel):
    skills: List[SkillSchema]

class SkillScore(BaseModel):
    name: str
    score: float

class InitialScores(BaseModel):
    scores: List[SkillScore]

class QuestionOutput(BaseModel):
    question: str

class EvaluationOutput(BaseModel):
    quality: str = Field(description="strong, moderate, weak, wrong, or hallucination")
    reason: str

class LearningResource(BaseModel):
    title: str
    url: str
    time_estimate: str

class SkillGap(BaseModel):
    skill_name: str
    gap_description: str
    recommended_adjacent_skills: List[str]
    resources: List[LearningResource]

class FinalReport(BaseModel):
    gaps: List[SkillGap]
    overall_summary: str
    weighted_total_score: float 

# --- STATE ---
class SkillState(BaseModel):
    name: str
    importance: int
    initial_score: float
    final_score: float
    questions_asked: int = 0
    needs_verification: bool = False
    asked_questions: List[str] = []
    reason: str = ""
    is_follow_up: bool = False

class InterviewState(BaseModel):
    skills: List[SkillState]
    current_idx: int = 0
    resume: str
    jd: str

# --- CORE LOGIC ---

def generate_next_step(state: InterviewState):
    if state.current_idx >= len(state.skills):
        total_points = sum(s.final_score * s.importance for s in state.skills)
        total_importance = sum(s.importance for s in state.skills)
        weighted_score = round(total_points / total_importance, 2) if total_importance > 0 else 0

        report_comp = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Generate a personalized learning plan. Time scale: 3.0+ (1-2h), 1.0-2.5 (5-10h), <1.0 (20h+)."},
                {"role": "user", "content": f"JD: {state.jd}. Audit Results: {state.skills}. Weighted Total: {weighted_score}"}
            ],
            response_format=FinalReport,
        )
        report = report_comp.choices[0].message.parsed
        report.weighted_total_score = weighted_score
        return {"result": state.dict(), "learning_plan": report.dict()}

    skill = state.skills[state.current_idx]
    
    if skill.initial_score <= 1.5 and skill.questions_asked == 0 and not skill.asked_questions:
        skill.needs_verification = True
        return {"question": f"I didn't see {skill.name} on your resume. Do you have hands-on experience?", "state": state}

    diff = "Easy" if skill.final_score < 3 else "Medium" if skill.final_score == 3 else "Hard"
    comp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": f"Ask ONE concise {diff} question for {skill.name}."}],
        response_format=QuestionOutput,
    )
    q = comp.choices[0].message.parsed.question
    skill.asked_questions.append(q)
    return {"question": q, "state": state}

@app.post("/start")
def start(req: dict):
    skill_comp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Extract 3 skills from JD: {req['job_description']}"}],
        response_format=SkillList,
    )
    extracted = skill_comp.choices[0].message.parsed.skills[:3]

    score_comp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Score 1-5. Be STRICT. If not in resume, score is 1.0."},
                  {"role": "user", "content": f"Resume: {req['resume']}. Skills: {[s.name for s in extracted]}"}],
        response_format=InitialScores,
    )
    score_map = {s.name: s.score for s in score_comp.choices[0].message.parsed.scores}

    skills = [SkillState(name=s.name, importance=s.importance, initial_score=score_map.get(s.name, 1.0), final_score=score_map.get(s.name, 1.0)) for s in extracted]
    return generate_next_step(InterviewState(skills=skills, resume=req['resume'], jd=req['job_description']))

@app.post("/answer")
def answer(req: dict):
    state = InterviewState(**req['state'])
    skill = state.skills[state.current_idx]
    ans = req['answer'].lower().strip()
    last_q = skill.asked_questions[-1] if skill.asked_questions else "Verification"

    idk_phrases = ["don't know", "not sure", "no idea"]
    if any(p in ans for p in idk_phrases):
        quality, score_change, reason = "idk", -0.5, "Candidate admitted lack of knowledge."
    else:
        eval_comp = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Evaluate accuracy. Use 'hallucination' for fake features."},
                      {"role": "user", "content": f"Q: {last_q}. A: {ans} for {skill.name}"}],
            response_format=EvaluationOutput,
        )
        res = eval_comp.choices[0].message.parsed
        quality, reason = res.quality, res.reason
        
        if quality == "hallucination":
            skill.final_score = 0.5
            skill.reason = f"TRUST RISK: {reason}"
            state.current_idx += 1
            return generate_next_step(state)
        
        mapping = {"strong": 1.0, "moderate": 0.5, "weak": -0.5, "wrong": -1.0}
        score_change = mapping.get(quality, -1.0)

    if (skill.initial_score <= 1.5 or skill.needs_verification) and score_change < 0:
        skill.final_score = 0.0
        skill.reason = f"Audit Failed: {reason}"
        state.current_idx += 1
    else:
        skill.needs_verification = False
        skill.final_score = max(0, min(5, skill.final_score + score_change))
        skill.reason += f" [{quality.upper()}]: {reason}"
        skill.questions_asked += 1
        
        if quality == "moderate" and not skill.is_follow_up and skill.questions_asked < 2:
            skill.is_follow_up = True
        else:
            state.current_idx += 1
            
    return generate_next_step(state)
