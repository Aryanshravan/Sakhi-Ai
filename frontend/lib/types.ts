export type ReportLanguage = "en" | "te" | "hi";

export interface Profile {
  user_id: string;
  parent_name: string;
  child_name: string;
  grade: number;
  report_language: ReportLanguage;
}

export interface Progress {
  profile: Profile;
  in_progress: { id: string; lesson_id: string; current_step: number } | null;
  completed_lessons: string[];
  mastery: { skill: string; score: number; attempts: number }[];
  weak_skills: string[];
  recent_summaries: { lesson_id: string; summary: string; completed_at: string }[];
  recent_mistakes: { skill: string; question: string; answer: string }[];
}
