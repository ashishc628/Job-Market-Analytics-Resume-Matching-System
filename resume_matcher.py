import pandas as pd
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import string

class ResumeMatcher:
    def __init__(self, jobs_csv_path: str):
        # ✅ Read compressed CSV (.csv.gz)
        self.jobs = pd.read_csv(jobs_csv_path, compression="gzip")

        # Combine text columns for semantic similarity
        text_cols = [col for col in ["title", "skills", "domains", "soft_skills"] if col in self.jobs.columns]
        self.jobs["job_text"] = self.jobs[text_cols].fillna("").agg(" ".join, axis=1)

        # Build global skills set
        self.global_skills = set()
        for col in ["skills", "domains", "soft_skills"]:
            if col in self.jobs.columns:
                for s in self.jobs[col].dropna():
                    for skill in str(s).split(","):
                        skill_clean = skill.strip().lower()
                        if skill_clean:
                            self.global_skills.add(skill_clean)

        # Map common variations to standard skill names
        self.skill_aliases = {
            "python3": "python",
            "python programming": "python",
            "ms excel": "excel",
            "microsoft excel": "excel",
            "data analytics": "data analysis",
            "ai": "artificial intelligence",
            "ml": "machine learning",
        }

        # TF-IDF for semantic similarity
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.job_tfidf = self.vectorizer.fit_transform(self.jobs["job_text"])

    def normalize_text(self, text):
        text = text.lower()
        text = text.translate(str.maketrans("", "", string.punctuation))
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def map_skill_alias(self, skill):
        return self.skill_aliases.get(skill.lower(), skill.lower())

    def extract_skills_from_text(self, text):
        if not text:
            return []

        text_norm = self.normalize_text(text)
        detected = set()

        for skill in self.global_skills:
            skill_std = self.map_skill_alias(skill)
            skill_norm = self.normalize_text(skill_std)
            pattern = r"\b" + re.escape(skill_norm) + r"\b"
            if re.search(pattern, text_norm):
                detected.add(skill_std)

        return list(detected)

    def match(self, resume_text, job_description=None, job_row=None, weight_skills=0.6):
        if not resume_text:
            return {
                "match_score": 0.0,
                "matched_skills": [],
                "missing_skills": [],
                "detected_skills": [],
                "matched_jd_cv": [],
                "missing_jd_cv": []
            }

        detected_skills = self.extract_skills_from_text(resume_text)

        # Job description text
        jd_text = job_description or (job_row["job_text"] if job_row is not None else "")
        jd_skills = self.extract_skills_from_text(jd_text)

        matched_jd_cv = [s for s in jd_skills if s in detected_skills]
        missing_jd_cv = [s for s in jd_skills if s not in detected_skills]

        skill_score = len(matched_jd_cv) / len(jd_skills) if jd_skills else 0.0

        similarity = 0.0
        if jd_text.strip():
            resume_tfidf = self.vectorizer.transform([resume_text])
            jd_tfidf = self.vectorizer.transform([jd_text])
            similarity = cosine_similarity(resume_tfidf, jd_tfidf).flatten()[0]

        final_score = (weight_skills * skill_score) + ((1 - weight_skills) * similarity)

        return {
            "match_score": round(final_score * 100, 2),
            "matched_skills": detected_skills,
            "missing_skills": [],
            "detected_skills": detected_skills,
            "matched_jd_cv": matched_jd_cv,
            "missing_jd_cv": missing_jd_cv
        }

    def top_similar_jobs(self, resume_text, top_k=5):
        if not resume_text:
            return pd.DataFrame(columns=["title", "company", "location", "type", "level", "posted_on", "similarity"])

        jobs_unique = self.jobs.drop_duplicates(subset=["title", "company"])
        job_tfidf_unique = self.vectorizer.transform(jobs_unique["job_text"])

        query_tfidf = self.vectorizer.transform([resume_text])
        sim_scores = cosine_similarity(query_tfidf, job_tfidf_unique).flatten()
        top_idx = sim_scores.argsort()[::-1][:top_k]

        return pd.DataFrame({
            "title": jobs_unique.iloc[top_idx]["title"].values if "title" in jobs_unique.columns else "",
            "company": jobs_unique.iloc[top_idx]["company"].values if "company" in jobs_unique.columns else "",
            "location": jobs_unique.iloc[top_idx]["location"].values if "location" in jobs_unique.columns else "",
            "type": jobs_unique.iloc[top_idx]["type"].values if "type" in jobs_unique.columns else "",
            "level": jobs_unique.iloc[top_idx]["level"].values if "level" in jobs_unique.columns else "",
            "posted_on": jobs_unique.iloc[top_idx]["posted_on"].values if "posted_on" in jobs_unique.columns else "",
            "similarity": (sim_scores[top_idx] * 100).round(2)
        })
