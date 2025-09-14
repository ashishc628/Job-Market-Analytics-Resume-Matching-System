import gradio as gr
from resume_matcher import ResumeMatcher
import PyPDF2
import docx

def extract_text_from_file(file_obj):
    name = getattr(file_obj, "name", None) or ""
    if name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file_obj)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif name.endswith(".docx"):
        doc = docx.Document(file_obj)
        return "\n".join([p.text for p in doc.paragraphs])
    elif name.endswith(".txt"):
        return file_obj.read().decode("utf-8")
    else:
        raise ValueError("Unsupported file type. Please upload PDF, DOCX, or TXT.")

def create_gradio_app(jobs_csv_path: str):
    matcher = ResumeMatcher(jobs_csv_path)

    with gr.Blocks() as demo:
        gr.Markdown("## 📊 Resume vs Job Matching + Skill Detection")

        with gr.Row():
            with gr.Column():
                resume_file = gr.File(label="Upload Resume (txt, pdf, docx)", type="filepath")
                job_desc = gr.Textbox(lines=6, label="Paste Job Description (optional)")
                weight_slider = gr.Slider(minimum=0.0, maximum=1.0, step=0.05, value=0.6,
                                          label="Weight: Skill overlap vs Semantic similarity",
                                          info="Higher weight prioritizes skills matching from JD & CV; lower weight prioritizes semantic similarity")
                top_k = gr.Slider(minimum=1, maximum=20, step=1, value=5, label="Top K similar jobs to show")
                run_btn = gr.Button("Analyze Resume")
            with gr.Column():
                detected_skills_out = gr.Textbox(label="Detected Skills in Resume", lines=6)
                score_out = gr.Number(label="Match Score (%)", value=0)
                matched_jd_cv_out = gr.Textbox(label="Matched Skills (from JD & CV)", lines=6)
                missing_jd_cv_out = gr.Textbox(label="Missing Skills (from JD & CV)", lines=6)
                detail_table = gr.Dataframe(
                    headers=["title", "company", "location", "type", "level", "posted_on", "similarity"],
                    label="Top Similar Jobs"
                )

        def process_and_match(resume_file, job_desc, weight_slider, top_k):
            resume_text = ""
            if resume_file:
                try:
                    with open(resume_file, "rb") as f:
                        resume_text = extract_text_from_file(f)
                except Exception:
                    resume_text = ""

            result = matcher.match(
                resume_text=resume_text,
                job_description=job_desc,
                job_row=None,
                weight_skills=float(weight_slider)
            )

            top_jobs_df = matcher.top_similar_jobs(resume_text, top_k=int(top_k))

            detected_skills = ", ".join(result["detected_skills"]) if result["detected_skills"] else "No skills detected"
            matched_jd_cv = ", ".join(result["matched_jd_cv"]) if result["matched_jd_cv"] else "No skills matched"
            missing_jd_cv = ", ".join(result["missing_jd_cv"]) if result["missing_jd_cv"] else "No missing skills"

            return detected_skills, result["match_score"], matched_jd_cv, missing_jd_cv, top_jobs_df

        run_btn.click(
            process_and_match,
            inputs=[resume_file, job_desc, weight_slider, top_k],
            outputs=[detected_skills_out, score_out, matched_jd_cv_out, missing_jd_cv_out, detail_table]
        )

    return demo

if __name__ == "__main__":
    app = create_gradio_app("jobs_merged_for_NLP.csv.gz")
    app.launch(server_name="0.0.0.0", server_port=7860)
