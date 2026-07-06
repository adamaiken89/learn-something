/**
 * SRS Card — single spaced repetition card.
 * Schema: https://learn-something.dev/schemas/card.json
 */
export interface SRSCard {
    /** Card ID: {courseId}-{moduleId}-{questionId} */
    id: string;
    /** Original quiz question ID, e.g. '1.2' */
    questionId: string;
    /** Module directory name, e.g. '01-intro' */
    moduleId: string;
    /** Course directory name, e.g. 'python-basics' */
    courseId: string;
    /** Question text */
    question: string;
    /** Format: '{key}. {option text}', e.g. 'a. Python' */
    answer: string;
    /** Why this answer is correct */
    explanation: string;
    /** SM-2 ease factor. Starts at 2.5, min 1.3 */
    easeFactor: number;
    /** Days until next review */
    interval: number;
    /** Count of consecutive correct reviews */
    repetitions: number;
    /** ISO 8601 datetime when card is next due */
    nextReviewDate: string;
    /** ISO 8601 datetime of last review, or null if never reviewed */
    lastReviewed: string | null;
    /** Whether user has starred this card */
    isStarred: boolean;
}
