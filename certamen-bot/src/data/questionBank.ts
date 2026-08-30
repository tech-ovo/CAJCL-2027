import { Question } from '../types/certamen';

export const INITIAL_QUESTION_BANK: Question[] = [
  // GRAMMAR - NOVICE
  {
    id: 'gram-nov-1',
    category: 'grammar',
    difficulty: 'novice',
    tossup: 'What Latin verb, meaning "to love", belongs to the first conjugation and has the principal parts amo, amare, amavi, amatus?',
    answers: ['amo', 'amare'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'Give the third person plural present active indicative of amo.',
        answers: ['amant'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'Give the first person singular imperfect active indicative of amo.',
        answers: ['amabam'],
        points: 5,
      },
    ],
    explanation: 'Amo, amare, amavi, amatus is the standard first conjugation model verb.',
    source: 'Classical Repository',
  },
  {
    id: 'gram-nov-2',
    category: 'grammar',
    difficulty: 'novice',
    tossup: 'What Latin case is primarily used for the direct object of an active transitive verb?',
    answers: ['accusative', 'accusative case'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What Latin case is primarily used for the indirect object?',
        answers: ['dative', 'dative case'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What Latin case is used for direct address or calling someone by name?',
        answers: ['vocative', 'vocative case'],
        points: 5,
      },
    ],
    explanation: 'The accusative case expresses the direct object in Latin syntax.',
    source: 'Classical Repository',
  },
  {
    id: 'gram-nov-3',
    category: 'grammar',
    difficulty: 'novice',
    tossup: 'Translate into English the Latin sentence: "Puer in horto currit."',
    answers: ['The boy runs in the garden', 'A boy is running in the garden', 'The boy is running in the garden', 'A boy runs in the garden'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'Change "currit" to the plural in the same sentence.',
        answers: ['currunt', 'Pueri in horto currunt'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'Change "in horto currit" to mean "runs into the garden".',
        answers: ['in hortum currit', 'in hortum'],
        points: 5,
      },
    ],
    explanation: 'In + ablative denotes location (in the garden); in + accusative denotes motion into.',
    source: 'Classical Repository',
  },

  // GRAMMAR - INTERMEDIATE
  {
    id: 'gram-int-1',
    category: 'grammar',
    difficulty: 'intermediate',
    tossup: 'What Latin grammatical construction consists of a noun or pronoun and a participle, both in the ablative case, functioning adverbially without grammatical connection to the main clause?',
    answers: ['ablative absolute', 'the ablative absolute'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'Translate the ablative absolute in the phrase: "Urbe capta, milites gaudebant."',
        answers: ['With the city having been captured', 'When the city was captured', 'After the city was captured', 'Since the city was captured'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'Translate the ablative absolute "Caesare duce" into English.',
        answers: ['With Caesar as leader', 'Under Caesar\'s leadership', 'With Caesar as commander'],
        points: 5,
      },
    ],
    explanation: 'The ablative absolute typically uses a perfect passive or present active participle with a noun.',
    source: 'Classical Repository',
  },
  {
    id: 'gram-int-2',
    category: 'grammar',
    difficulty: 'intermediate',
    tossup: 'What subjunctive clause in Latin is introduced by "ut" or "ne" and expresses the goal or purpose of the main action?',
    answers: ['purpose clause', 'clause of purpose', 'final clause'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What clause is introduced by "ut" or "ut non" and signaled by words like "tam", "ita", "sic", or "tantus"?',
        answers: ['result clause', 'consecutive clause'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What type of clause is introduced by verbs of asking, begging, or commanding followed by "ut" or "ne"?',
        answers: ['indirect command', 'substantive clause of purpose', 'jussive noun clause'],
        points: 5,
      },
    ],
    explanation: 'Purpose clauses take ut/ne + present or imperfect subjunctive.',
    source: 'Classical Repository',
  },

  // GRAMMAR - ADVANCED
  {
    id: 'gram-adv-1',
    category: 'grammar',
    difficulty: 'advanced',
    tossup: 'What Latin verbal noun has only four case forms (genitive, dative, accusative, ablative), lacks a plural, and expresses the English "-ing" action?',
    answers: ['gerund'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What passive verbal adjective is used instead of a gerund when an accusative object is modified?',
        answers: ['gerundive', 'future passive participle'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What construction expresses necessary action using the gerundive and a form of the verb "sum"?',
        answers: ['passive periphrastic', 'gerundive of obligation'],
        points: 5,
      },
    ],
    explanation: 'Gerunds are active verbal nouns; gerundives are passive verbal adjectives.',
    source: 'Classical Repository',
  },

  // MYTHOLOGY - NOVICE
  {
    id: 'myth-nov-1',
    category: 'mythology',
    difficulty: 'novice',
    tossup: 'Who was the Roman king of the gods, associated with the thunderbolt and the eagle, and equated with the Greek god Zeus?',
    answers: ['Jupiter', 'Jove', 'Iuppiter'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'Who was Jupiter\'s wife and queen of the gods?',
        answers: ['Juno', 'Iuno'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What sister of Jupiter and goddess of the hearth was served by six priestesses in Rome?',
        answers: ['Vesta'],
        points: 5,
      },
    ],
    explanation: 'Jupiter Optimus Maximus was the supreme Roman deity.',
    source: 'Classical Repository',
  },
  {
    id: 'myth-nov-2',
    category: 'mythology',
    difficulty: 'novice',
    tossup: 'What Greek hero, the son of Zeus and Alcmene, was famous for performing Twelve Labors?',
    answers: ['Hercules', 'Heracles', 'Herakles'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What monster with impenetrable hide did Hercules slay as his first labor?',
        answers: ['Nemean Lion', 'the Nemean lion'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What many-headed serpent of Lake Lerna did Hercules slay with the help of Iolaus?',
        answers: ['Lernaean Hydra', 'the Hydra'],
        points: 5,
      },
    ],
    explanation: 'Hercules was compelled to serve Eurystheus and complete the 12 Labors.',
    source: 'Classical Repository',
  },

  // MYTHOLOGY - INTERMEDIATE
  {
    id: 'myth-int-1',
    category: 'mythology',
    difficulty: 'intermediate',
    tossup: 'What winged horse sprang from the neck of Medusa after she was beheaded by Perseus?',
    answers: ['Pegasus', 'Pegasos'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What hero tamed Pegasus with a golden bridle to defeat the Chimera?',
        answers: ['Bellerophon', 'Bellerophontes'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What spring on Mount Helicon was created when Pegasus struck the earth with his hoof?',
        answers: ['Hippocrene'],
        points: 5,
      },
    ],
    explanation: 'Pegasus was born from Medusa and later served Bellerophon.',
    source: 'Classical Repository',
  },
  {
    id: 'myth-int-2',
    category: 'mythology',
    difficulty: 'intermediate',
    tossup: 'Which of the Gorgons was the only mortal one, possessing snakes for hair and a gaze that turned onlookers to stone?',
    answers: ['Medusa'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'Name either of the other two immortal Gorgon sisters.',
        answers: ['Stheno', 'Euryale'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What three gray-haired sisters shared a single eye and tooth, and guided Perseus to the Gorgons?',
        answers: ['Graeae', 'the Graeae', 'Phorcides'],
        points: 5,
      },
    ],
    explanation: 'Medusa was the only mortal Gorgon slain by Perseus.',
    source: 'Classical Repository',
  },

  // MYTHOLOGY - ADVANCED
  {
    id: 'myth-adv-1',
    category: 'mythology',
    difficulty: 'advanced',
    tossup: 'What youth fell in love with his own reflection in a pool of water and wasted away into a flower after rejecting the nymph Echo?',
    answers: ['Narcissus'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What blind prophet of Thebes foretold that Narcissus would live a long life as long as he did not know himself?',
        answers: ['Tiresias', 'Teiresias'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What goddess of retribution cursed Narcissus to suffer unrequited self-love?',
        answers: ['Nemesis'],
        points: 5,
      },
    ],
    explanation: 'Narcissus was punished by Nemesis for spurning lovers like Echo and Ameinias.',
    source: 'Classical Repository',
  },

  // HISTORY - NOVICE
  {
    id: 'hist-nov-1',
    category: 'history',
    difficulty: 'novice',
    tossup: 'According to Roman tradition, who was the legendary founder and first king of Rome, reigning from 753 BC to 716 BC?',
    answers: ['Romulus'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What twin brother did Romulus slay during the founding of the city?',
        answers: ['Remus'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What she-wolf nursed Romulus and Remus on the banks of the Tiber?',
        answers: ['Lupa', 'the she-wolf'],
        points: 5,
      },
    ],
    explanation: 'Romulus founded Rome on the Palatine Hill in 753 BC.',
    source: 'Classical Repository',
  },
  {
    id: 'hist-nov-2',
    category: 'history',
    difficulty: 'novice',
    tossup: 'Who became the first Roman Emperor after defeating Mark Antony and Cleopatra at Actium in 31 BC, taking the title Augustus in 27 BC?',
    answers: ['Augustus', 'Octavian', 'Gaius Julius Caesar Octavianus'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What grand uncle and adoptive father of Augustus was assassinated on the Ides of March in 44 BC?',
        answers: ['Julius Caesar', 'Gaius Julius Caesar'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'Who was Augustus\'s trusted general and son-in-law who won the Battle of Actium and built the original Pantheon?',
        answers: ['Marcus Vipsanius Agrippa', 'Agrippa'],
        points: 5,
      },
    ],
    explanation: 'Octavian became Augustus, ruling from 27 BC to 14 AD.',
    source: 'Classical Repository',
  },

  // HISTORY - INTERMEDIATE
  {
    id: 'hist-int-1',
    category: 'history',
    difficulty: 'intermediate',
    tossup: 'In 216 BC, what Carthaginian general annihilated eight Roman legions at the Battle of Cannae using a double envelopment maneuver?',
    answers: ['Hannibal', 'Hannibal Barca'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What Roman general finally defeated Hannibal at the Battle of Zama in 202 BC?',
        answers: ['Scipio Africanus', 'Publius Cornelius Scipio Africanus'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What Roman dictator employed delaying tactics against Hannibal, earning the agnomen "Cunctator"?',
        answers: ['Quintus Fabius Maximus', 'Fabius Maximus', 'Fabius'],
        points: 5,
      },
    ],
    explanation: 'Hannibal defeated the Romans at Cannae during the Second Punic War.',
    source: 'Classical Repository',
  },
  {
    id: 'hist-int-2',
    category: 'history',
    difficulty: 'intermediate',
    tossup: 'What river did Julius Caesar cross in 49 BC, uttering "Alea iacta est" and precipitating the Great Roman Civil War?',
    answers: ['Rubicon', 'the Rubicon', 'Rubico'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What political and military rival did Caesar defeat at the Battle of Pharsalus in 48 BC?',
        answers: ['Pompey', 'Pompey the Great', 'Pompeius', 'Gnaeus Pompeius Magnus'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'In what year and month did Caesar famously proclaim "Veni, Vidi, Vici" after defeating Pharnaces II at Zela?',
        answers: ['47 BC', 'August 47 BC'],
        points: 5,
      },
    ],
    explanation: 'Caesar crossed the Rubicon boundary between Cisalpine Gaul and Italy.',
    source: 'Classical Repository',
  },

  // HISTORY - ADVANCED
  {
    id: 'hist-adv-1',
    category: 'history',
    difficulty: 'advanced',
    tossup: 'In what year did the "Year of the Four Emperors" take place, during which Galba, Otho, Vitellius, and Vespasian all claimed the purple?',
    answers: ['69 AD', '69'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What imperial dynasty was founded by Vespasian following his victory in 69 AD?',
        answers: ['Flavian', 'Flavian dynasty'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'Which son of Vespasian captured Jerusalem in 70 AD and dedicated the Colosseum in 80 AD?',
        answers: ['Titus', 'Titus Flavius Vespasianus'],
        points: 5,
      },
    ],
    explanation: 'The crisis of 69 AD followed the suicide of Nero in 68 AD.',
    source: 'Classical Repository',
  },

  // CULTURE - NOVICE
  {
    id: 'cult-nov-1',
    category: 'culture',
    difficulty: 'novice',
    tossup: 'What garment made of wool was the distinctive national dress of male Roman citizens, draped over the tunic?',
    answers: ['toga'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What special toga with a broad purple border was worn by curule magistrates and freeborn boys?',
        answers: ['toga praetexta'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What all-white toga was assumed by a Roman youth upon reaching manhood around age 16?',
        answers: ['toga virilis', 'toga pura'],
        points: 5,
      },
    ],
    explanation: 'The toga was the formal dress of Roman citizens.',
    source: 'Classical Repository',
  },
  {
    id: 'cult-nov-2',
    category: 'culture',
    difficulty: 'novice',
    tossup: 'What Roman dining room consisted of three couches arranged in a U-shape around a central table?',
    answers: ['triclinium'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What was the central reception hall or atrium of a Roman domus containing an impluvium for catching rainwater?',
        answers: ['atrium'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What colonnaded open-air courtyard garden lay at the rear of a wealthy Roman townhouse?',
        answers: ['peristylium', 'peristyle'],
        points: 5,
      },
    ],
    explanation: 'Romans reclined on three couches (lecti) in the triclinium.',
    source: 'Classical Repository',
  },

  // CULTURE - INTERMEDIATE
  {
    id: 'cult-int-1',
    category: 'culture',
    difficulty: 'intermediate',
    tossup: 'What ancient chariot-racing stadium located in Rome between the Aventine and Palatine Hills could accommodate over 150,000 spectators?',
    answers: ['Circus Maximus'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What was the central dividing spine running down the middle of the circus track called?',
        answers: ['spina', 'euripus'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What turning posts stood at either end of the spina, around which charioteers made tight turns?',
        answers: ['metae', 'meta'],
        points: 5,
      },
    ],
    explanation: 'The Circus Maximus was Rome\'s premier chariot racing venue.',
    source: 'Classical Repository',
  },

  // CULTURE - ADVANCED
  {
    id: 'cult-adv-1',
    category: 'culture',
    difficulty: 'advanced',
    tossup: 'In Roman public baths (thermae), what was the name of the unheated cold plunge pool room?',
    answers: ['frigidarium'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What was the warm transition room in the baths, often decorated with mosaics?',
        answers: ['tepidarium'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What underfloor heating system used raised pillars and furnaces to circulate hot air beneath Roman baths and villas?',
        answers: ['hypocaust', 'hypocaustum'],
        points: 5,
      },
    ],
    explanation: 'Roman baths followed a sequence: apodyterium -> tepidarium -> caldarium -> frigidarium.',
    source: 'Classical Repository',
  },

  // LITERATURE - NOVICE
  {
    id: 'lit-nov-1',
    category: 'literature',
    difficulty: 'novice',
    tossup: 'What Roman poet composed the national epic "The Aeneid", celebrating the Trojan prince Aeneas and the destiny of Rome?',
    answers: ['Vergil', 'Virgil', 'Publius Vergilius Maro'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What Queen of Carthage falls in love with Aeneas and dies upon a pyre in Book 4 of the Aeneid?',
        answers: ['Dido', 'Elissa'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'Name either of Vergil\'s other two major poetic works before the Aeneid.',
        answers: ['Eclogues', 'Bucolics', 'Georgics'],
        points: 5,
      },
    ],
    explanation: 'Vergil (70-19 BC) was Rome\'s epic master.',
    source: 'Classical Repository',
  },

  // LITERATURE - INTERMEDIATE
  {
    id: 'lit-int-1',
    category: 'literature',
    difficulty: 'intermediate',
    tossup: 'What Roman lyric poet wrote the "Odes", "Epodes", and "Satires", and coined the famous Latin phrase "Carpe Diem"?',
    answers: ['Horace', 'Quintus Horatius Flaccus'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What wealthy equestrian friend and patron of Horace and Vergil gave his name to modern arts patronage?',
        answers: ['Maecenas', 'Gaius Maecenas'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What famous phrase from Horace\'s Odes 3.2 means "It is sweet and fitting to die for one\'s country"?',
        answers: ['Dulce et decorum est pro patria mori', 'Dulce et decorum est'],
        points: 5,
      },
    ],
    explanation: 'Horace wrote "carpe diem, quam minimum credula postero" in Odes 1.11.',
    source: 'Classical Repository',
  },

  // LITERATURE - ADVANCED
  {
    id: 'lit-adv-1',
    category: 'literature',
    difficulty: 'advanced',
    tossup: 'What Roman poet composed the mythological masterwork "Metamorphoses" in fifteen books before being exiled by Augustus to Tomis on the Black Sea in 8 AD?',
    answers: ['Ovid', 'Publius Ovidius Naso'],
    boni: [
      {
        boniNumber: 1,
        prompt: 'What two reasons did Ovid famously give for his exile, usually translated as "a poem and a mistake"?',
        answers: ['carmen et error', 'a poem and a mistake'],
        points: 5,
      },
      {
        boniNumber: 2,
        prompt: 'What elegiac didactic poem on romance and seduction was the likely "carmen" that offended Augustus?',
        answers: ['Ars Amatoria', 'The Art of Love'],
        points: 5,
      },
    ],
    explanation: 'Ovid was banished to Tomis by Augustus due to "carmen et error".',
    source: 'Classical Repository',
  },
];
