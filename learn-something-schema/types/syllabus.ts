/**
 * Course Syllabus — course skeleton with module metadata.
 * Schema: https://learn-something.dev/schemas/syllabus.json
 */
export interface Syllabus {
    /** Course title */
    subject: string;
    /** Course language code */
    language?: string;
    /** Total estimated study hours */
    time_budget_hours?: number;
    /** Expected learner level */
    target_level?: string;
    /** Subject domain category */
    domain?: string;
    /** Required prior knowledge */
    prerequisites?: string[];
    /** Course-level intended learning outcomes */
    learning_objectives?: string[];
    /** Module list */
    modules: SyllabusModule[];
}

export interface SyllabusModule {
    /** Module number (1-indexed) */
    id: number;
    /** Module directory name (e.g. '01-intro') */
    name: string;
    /** Estimated study hours for this module */
    time_hours: number;
    /** Module IDs this module depends on (forms DAG) */
    prerequisites: number[];
    /** Subtopics covered in this module */
    topics: string[];
}
