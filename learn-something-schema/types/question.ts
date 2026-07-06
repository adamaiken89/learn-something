/**
 * Quiz Question — single multiple choice question.
 * Schema: https://learn-something.dev/schemas/question.json
 */
export interface QuizQuestion {
    /** Question ID: {moduleNum}.{questionNum}, e.g. '1.2' */
    id: string;
    /** Question text */
    question: string;
    /** Answer options with lowercase keys: a, b, c, d */
    options: Record<string, string>;
    /** Correct answer key */
    answer: "a" | "b" | "c" | "d";
    /** Why this answer is correct */
    explanation: string;
    /** 1=recall, 2=comprehension, 3=application */
    difficulty: 1 | 2 | 3;
    /** Content tags */
    tags: string[];
}

/** Quiz is an array of questions */
export type Quiz = QuizQuestion[];
