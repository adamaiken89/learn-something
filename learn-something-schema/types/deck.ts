/**
 * SRS Deck — spaced repetition card collection.
 * Schema: https://learn-something.dev/schemas/deck.json
 */
import type { SRSCard } from "./card";

export interface SRSDeck {
    /** Card ID → Card mapping. Keys are '{courseId}-{moduleId}-{questionId}' */
    cards: Record<string, SRSCard>;
}
