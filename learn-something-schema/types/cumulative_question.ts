/**
 * Cumulative Quiz Question — cross-module question types (mcq, cloze, tf).
 * Schema: https://learn-something.dev/schemas/cumulative_question.json
 */

export interface CumulativeMCQ {
    /** Question ID: cum.N */
    id: string;
    type: "mcq";
    /** Question text */
    question: string;
    /** Module numbers this question covers */
    source_modules: number[];
    /** Answer options with uppercase keys: A, B, C, D */
    options: Record<string, string>;
    /** Correct answer key */
    answer: "A" | "B" | "C" | "D";
    /** Why this answer is correct */
    explanation: string;
    /** 1=recall, 2=comprehension, 3=application */
    difficulty: 1 | 2 | 3;
    /** Content tags */
    tags: string[];
}

export interface CumulativeCloze {
    /** Question ID: cum.N */
    id: string;
    type: "cloze";
    /** Sentence with {blank} for term to fill in */
    question: string;
    /** Module numbers this question covers */
    source_modules: number[];
    /** The term that fills the blank */
    answer: string;
    /** Why this term is correct */
    explanation: string;
    /** 1=recall, 2=comprehension, 3=application */
    difficulty: 1 | 2 | 3;
    /** Content tags */
    tags: string[];
}

export interface CumulativeTF {
    /** Question ID: cum.N */
    id: string;
    type: "tf";
    /** Statement to evaluate as true or false */
    statement: string;
    /** Module numbers this question covers */
    source_modules: number[];
    /** True if statement is correct, False if incorrect */
    answer: boolean;
    /** Why true/false, referencing concepts from source modules */
    explanation: string;
    /** 1=recall, 2=comprehension, 3=application */
    difficulty: 1 | 2 | 3;
    /** Content tags */
    tags: string[];
}

/** Discriminated union of all cumulative question types */
export type CumulativeQuestion = CumulativeMCQ | CumulativeCloze | CumulativeTF;

/** Cumulative quiz is an array of cross-module questions */
export type CumulativeQuiz = CumulativeQuestion[];
