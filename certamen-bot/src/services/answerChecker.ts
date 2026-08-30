/**
 * Normalizes text for Latin Certamen answer evaluation:
 * - strips macrons (ā -> a, etc.)
 * - converts diphthongs (æ -> ae, œ -> oe)
 * - removes non-alphanumeric characters except spaces
 * - trims and lowercases
 */
export function normalizeText(text: string): string {
  if (!text) return '';

  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // remove diacritics / macrons
    .replace(/æ/g, 'ae')
    .replace(/œ/g, 'oe')
    .replace(/['’"`.,\/#!$%\^&\*;:{}=\-_~()\[\]?]/g, ' ') // replace punctuation with spaces
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Removes common leading filler words like "the", "a", "an", "to" (for verbs)
 */
export function stripFillers(text: string): string {
  const fillers = ['the ', 'a ', 'an ', 'to '];
  let cleaned = text.trim();
  for (const filler of fillers) {
    if (cleaned.startsWith(filler)) {
      cleaned = cleaned.substring(filler.length).trim();
    }
  }
  return cleaned;
}

export interface MatchResult {
  isCorrect: boolean;
  matchedAnswer?: string;
  cleanedUserAnswer: string;
  feedback: string;
}

/**
 * Checks if the user's answer is correct according to Certamen rules:
 * "As long as the user's inputted answers contains one of the (possibly multiple) correct answers, it should be marked correct."
 */
export function checkAnswer(userAnswer: string, acceptableAnswers: string[]): MatchResult {
  if (!userAnswer || !userAnswer.trim()) {
    return {
      isCorrect: false,
      cleanedUserAnswer: '',
      feedback: 'No answer provided.',
    };
  }

  const normalizedUser = normalizeText(userAnswer);
  const strippedUser = stripFillers(normalizedUser);

  if (!normalizedUser) {
    return {
      isCorrect: false,
      cleanedUserAnswer: userAnswer,
      feedback: 'No valid characters in answer.',
    };
  }

  for (const accepted of acceptableAnswers) {
    const normalizedAccepted = normalizeText(accepted);
    const strippedAccepted = stripFillers(normalizedAccepted);

    if (!normalizedAccepted) continue;

    // 1. Direct equality after normalization
    if (normalizedUser === normalizedAccepted || strippedUser === strippedAccepted) {
      return {
        isCorrect: true,
        matchedAnswer: accepted,
        cleanedUserAnswer: normalizedUser,
        feedback: `Exact match with "${accepted}"!`,
      };
    }

    // 2. Substring containment: user answer contains the accepted answer
    if (normalizedUser.includes(normalizedAccepted) || (strippedAccepted && normalizedUser.includes(strippedAccepted))) {
      return {
        isCorrect: true,
        matchedAnswer: accepted,
        cleanedUserAnswer: normalizedUser,
        feedback: `Correct! Contains "${accepted}".`,
      };
    }

    // 3. Reverse containment: accepted answer contains user answer (if user gave a strong core term, e.g. "Caesar" for "Julius Caesar")
    // Only apply if user gave at least 4 chars or substantial word
    if (normalizedAccepted.includes(normalizedUser) && normalizedUser.length >= 4) {
      // Check if user answer is a standalone word in the accepted answer
      const words = normalizedAccepted.split(' ');
      if (words.some((w) => w === normalizedUser || w === strippedUser)) {
        return {
          isCorrect: true,
          matchedAnswer: accepted,
          cleanedUserAnswer: normalizedUser,
          feedback: `Correct! Matched "${accepted}".`,
        };
      }
    }

    // 4. Roman numeral and numeric equivalency check
    const numberEquivalents: Record<string, string[]> = {
      '1': ['first', 'one', 'i', 'primus', 'prima', 'primum', 'unus', 'una', 'unum'],
      '2': ['second', 'two', 'ii', 'secundus', 'secunda', 'secundum', 'duo', 'duae'],
      '3': ['third', 'three', 'iii', 'tertius', 'tertia', 'tertium', 'tres', 'tria'],
      '4': ['fourth', 'four', 'iv', 'quartus', 'quarta', 'quartum', 'quattuor'],
      '5': ['fifth', 'five', 'v', 'quintus', 'quinta', 'quintum', 'quinque'],
      '6': ['sixth', 'six', 'vi', 'sextus', 'sexta', 'sextum', 'sex'],
      '7': ['seventh', 'seven', 'vii', 'septimus', 'septima', 'septimum', 'septem'],
      '8': ['eighth', 'eight', 'viii', 'octavus', 'octava', 'octavum', 'octo'],
      '9': ['ninth', 'nine', 'ix', 'nonus', 'nona', 'nonum', 'novem'],
      '10': ['tenth', 'ten', 'x', 'decimus', 'decima', 'decimum', 'decem'],
    };

    for (const [digit, aliases] of Object.entries(numberEquivalents)) {
      if (
        (normalizedAccepted === digit || aliases.includes(normalizedAccepted)) &&
        (normalizedUser === digit || aliases.includes(normalizedUser))
      ) {
        return {
          isCorrect: true,
          matchedAnswer: accepted,
          cleanedUserAnswer: normalizedUser,
          feedback: `Correct numeric match with "${accepted}".`,
        };
      }
    }
  }

  return {
    isCorrect: false,
    cleanedUserAnswer: normalizedUser,
    feedback: `Incorrect. Acceptable answers were: ${acceptableAnswers.join(', ')}`,
  };
}
