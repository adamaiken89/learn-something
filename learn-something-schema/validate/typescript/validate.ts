/**
 * TypeScript validation for learn-something data files.
 * Uses Ajv for JSON Schema validation.
 *
 * Usage:
 *   import { validateDeck, validateQuiz } from '@learn-something/schema/validate';
 *   const errors = validateDeck(deckData);
 */

import Ajv, { ErrorObject } from "ajv";
import addFormats from "ajv-formats";

import cardSchema from "../../schemas/card.schema.json";
// Schema imports (bundled at build time or loaded from disk)
import deckSchema from "../../schemas/deck.schema.json";
import feedbackSchema from "../../schemas/feedback.schema.json";
import questionSchema from "../../schemas/question.schema.json";
import quizSchema from "../../schemas/quiz.schema.json";
import statsSchema from "../../schemas/stats.schema.json";
import syllabusSchema from "../../schemas/syllabus.schema.json";

const ajv = new Ajv({ allErrors: true, strict: false });
addFormats(ajv);

// Register all schemas
ajv.addSchema(deckSchema, "deck");
ajv.addSchema(cardSchema, "card");
ajv.addSchema(quizSchema, "quiz");
ajv.addSchema(questionSchema, "question");
ajv.addSchema(syllabusSchema, "syllabus");
ajv.addSchema(statsSchema, "stats");
ajv.addSchema(feedbackSchema, "feedback");

function formatErrors(errors: ErrorObject[] | null): string[] {
    if (!errors) return [];
    return errors.map((e) => {
        const path = e.instancePath.replace(/^\//, "").replace(/\//g, ".");
        return path ? `${path}: ${e.message}` : (e.message ?? "unknown error");
    });
}

export function validateDeck(data: unknown): string[] {
    const validate = ajv.getSchema("deck")!;
    return formatErrors(validate(data) ? null : validate.errors);
}

export function validateCard(data: unknown): string[] {
    const validate = ajv.getSchema("card")!;
    return formatErrors(validate(data) ? null : validate.errors);
}

export function validateQuiz(data: unknown): string[] {
    const validate = ajv.getSchema("quiz")!;
    return formatErrors(validate(data) ? null : validate.errors);
}

export function validateQuestion(data: unknown): string[] {
    const validate = ajv.getSchema("question")!;
    return formatErrors(validate(data) ? null : validate.errors);
}

export function validateSyllabus(data: unknown): string[] {
    const validate = ajv.getSchema("syllabus")!;
    return formatErrors(validate(data) ? null : validate.errors);
}

export function validateStats(data: unknown): string[] {
    const validate = ajv.getSchema("stats")!;
    return formatErrors(validate(data) ? null : validate.errors);
}

export function validateFeedback(data: unknown): string[] {
    const validate = ajv.getSchema("feedback")!;
    return formatErrors(validate(data) ? null : validate.errors);
}
