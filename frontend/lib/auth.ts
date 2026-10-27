import { betterAuth } from "better-auth";
import { Pool } from "pg";

export const auth = betterAuth({
    database: new Pool({
        connectionString: process.env.DB_URL,
    }),
    socialProviders: {
        google: {
            clientId: process.env.GOOGLE_CLIENT!,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
        },
    },
    user: {
        additionalFields: {
            favoriteCategory: {
                type: "string",
                required: false,
                input: true,
                // "All" matches the feed's default (no filter applied).
                defaultValue: "All",
            },
            personalColor: {
                type: "string",
                required: false,
                input: true,
                // Same placeholder used across the app until a real
                // sign-up color picker exists.
                defaultValue: "oklch(0.64 0.26 322)",
            },
            onboardingComplete: {
                type: "boolean",
                required: false,
                input: true,
                defaultValue: false,
            },
        },
    },
});