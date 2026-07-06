/**
 * Session Stats — quiz and review session history.
 * Schema: https://learn-something.dev/schemas/stats.json
 */
export interface SessionStats {
    sessions: StudySession[];
}

export interface StudySession {
    /** Session date: YYYY-MM-DD */
    date: string;
    /** Session type */
    type: "quiz" | "review";
    /** Course/topic directory name */
    topic: string;
    /** Module directory name (present for quiz sessions) */
    module: string | null;
    /** Number of correct answers */
    score: number | null;
    /** Total questions in session */
    total: number | null;
}
