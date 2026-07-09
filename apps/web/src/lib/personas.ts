/**
 * Demo traveler personas — real high-signal user ids from the Yelp Open
 * Dataset interactions table, so personalization visibly reshapes results.
 * (Names are ours; the ids are the dataset's.)
 */
export interface Persona {
  yelpUserId: string;
  name: string;
  flavor: string;
  interactions: number;
}

export const DEMO_PERSONAS: Persona[] = [
  {
    yelpUserId: "fCvMnJU1Z-XhAjKg99wK3Q",
    name: "The Gourmand",
    flavor: "four thousand meals deep — trusts no star rating blindly",
    interactions: 4184,
  },
  {
    yelpUserId: "_BcWyKQL16ndpBdggh2kNA",
    name: "The Regular",
    flavor: "knows every barista by name across three cities",
    interactions: 3051,
  },
  {
    yelpUserId: "-G7Zkl1wIWBBmD0KRy_sCw",
    name: "The Night Owl",
    flavor: "the evening is young; the reviews are long",
    interactions: 2717,
  },
  {
    yelpUserId: "qjfMBIZpQT9DDtw_BWCopQ",
    name: "The Wanderer",
    flavor: "collects neighborhoods the way others collect stamps",
    interactions: 2554,
  },
];
