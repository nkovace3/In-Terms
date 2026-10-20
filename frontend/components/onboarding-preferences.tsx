"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { FieldDescription, FieldLegend, FieldSet } from "@/components/ui/field";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { authClient } from "@/lib/auth-client";

// Keep in sync with article-feed-view.tsx's category list.
const CATEGORIES = [
  "All",
  "NBA",
  "NFL",
  "MLB",
  "Reality TV",
  "US Politics",
  "Business",
];

const DEFAULT_COLOR = "#c026d3";

export function OnboardingPreferences() {
  const router = useRouter();
  const [favoriteCategory, setFavoriteCategory] = useState<string[]>([]);
  const [personalColor, setPersonalColor] = useState(DEFAULT_COLOR);

  const handleUserCustomization = async () => {
    await authClient.updateUser({
      favoriteCategory: favoriteCategory[0],
      personalColor: personalColor,
    });

    router.push("/");
    router.refresh();
  }

  return (
    <div className="flex w-full max-w-xl flex-col items-center gap-10 text-center">
      <div className="flex flex-col items-center gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Make it yours
        </h1>
        <p className="text-sm text-muted-foreground">
          Pick a default category and a color that describes you — you can
          change these anytime.
        </p>
      </div>

      <FieldSet className="w-full items-center gap-4">
        <FieldLegend variant="label" className="sr-only">
          Favorite category
        </FieldLegend>

        <ToggleGroup
          value={favoriteCategory}
          onValueChange={setFavoriteCategory}
          className="w-full flex-wrap justify-center"
        >
          {CATEGORIES.map((category) => (
            <ToggleGroupItem
              key={category}
              value={category}
              variant="outline"
              size="sm"
            >
              {category}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        <FieldDescription className="text-center text-xs">
          Your feed opens here by default — you can switch anytime.
        </FieldDescription>
      </FieldSet>

      <FieldSet className="w-full items-center gap-4">
        <FieldLegend variant="label" className="sr-only">
          Personal color
        </FieldLegend>

        <label className="flex cursor-pointer flex-col items-center gap-3">
          <span
            className="size-16 rounded-full border-4 border-border shadow-sm transition-transform hover:scale-105"
            style={{ backgroundColor: personalColor }}
          />
          <input
            type="color"
            value={personalColor}
            onChange={(event) => setPersonalColor(event.target.value)}
            className="sr-only"
          />
          <span className="text-xs text-muted-foreground">Tap to change</span>
        </label>

        <FieldDescription className="text-center text-xs">
          Translated stories turn this color — think of it as your signature.
        </FieldDescription>
      </FieldSet>

      <Button
        type="button"
        disabled={favoriteCategory.length === 0}
        className="w-full max-w-xs"
        onClick = {handleUserCustomization}
      >
        Continue
      </Button>
    </div>
  );
}
