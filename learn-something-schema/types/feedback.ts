/**
 * Module Feedback — learner ratings and content flags.
 * Schema: https://learn-something.dev/schemas/feedback.json
 */
export interface Feedback {
    ratings?: ModuleRating[];
    flags?: ContentFlag[];
}

export interface ModuleRating {
    /** Module directory name */
    module: string;
    /** Rating: 1=poor, 5=excellent */
    score: 1 | 2 | 3 | 4 | 5;
    /** ISO 8601 datetime of rating */
    date: string;
    /** Optional comment */
    comment?: string;
}

export interface ContentFlag {
    /** Module directory name */
    module: string;
    /** Flag type */
    type: "wrong" | "outdated" | "confusing";
    /** Details about the issue */
    detail?: string;
    /** ISO 8601 datetime of flag */
    date: string;
}
