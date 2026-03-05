import { Card, Rank, Suit } from '../types';

const SUITS: Suit[] = ['H', 'D', 'C', 'S'];
const RANKS: Rank[] = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];

export const createDeck = (): Card[] => {
  const deck: Card[] = [];
  SUITS.forEach(suit => {
    RANKS.forEach(rank => {
      deck.push({ suit, rank, id: `${rank}${suit}` });
    });
  });
  // Fisher-Yates shuffle
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
};

// --- Hand Evaluation Logic ---

const RANK_VALUE: Record<Rank, number> = {
  '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
  '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
};

type HandRank = 
  | 'High Card' 
  | 'Pair' 
  | 'Two Pair' 
  | 'Three of a Kind' 
  | 'Straight' 
  | 'Flush' 
  | 'Full House' 
  | 'Four of a Kind' 
  | 'Straight Flush' 
  | 'Royal Flush';

const HAND_SCORES: Record<HandRank, number> = {
  'High Card': 1,
  'Pair': 2,
  'Two Pair': 3,
  'Three of a Kind': 4,
  'Straight': 5,
  'Flush': 6,
  'Full House': 7,
  'Four of a Kind': 8,
  'Straight Flush': 9,
  'Royal Flush': 10
};

interface EvaluatedHand {
  rank: HandRank;
  score: number;
  tieBreakers: number[]; // Values of cards to break ties
  description: string;
}

export const evaluateHand = (holeCards: Card[], communityCards: Card[]): EvaluatedHand => {
  const allCards = [...holeCards, ...communityCards];
  const ranks = allCards.map(c => RANK_VALUE[c.rank]).sort((a, b) => b - a);
  const suits = allCards.map(c => c.suit);
  
  // Frequency maps
  const rankCounts: Record<number, number> = {};
  ranks.forEach(r => rankCounts[r] = (rankCounts[r] || 0) + 1);
  const suitCounts: Record<string, number> = {};
  suits.forEach(s => suitCounts[s] = (suitCounts[s] || 0) + 1);

  const isFlush = Object.values(suitCounts).some(count => count >= 5);
  
  // Check Straight
  const uniqueRanks = Array.from(new Set(ranks)).sort((a, b) => b - a);
  let straightHigh = 0;
  for (let i = 0; i <= uniqueRanks.length - 5; i++) {
    const slice = uniqueRanks.slice(i, i + 5);
    if (slice[0] - slice[4] === 4) {
      straightHigh = slice[0];
      break;
    }
  }
  // Wheel case A-2-3-4-5
  if (!straightHigh && uniqueRanks.includes(14) && uniqueRanks.includes(2) && uniqueRanks.includes(3) && uniqueRanks.includes(4) && uniqueRanks.includes(5)) {
    straightHigh = 5;
  }

  // Check Straight Flush
  let isStraightFlush = false;
  let sfHigh = 0;
  if (isFlush && straightHigh > 0) {
     // Detailed check needed for straight flush (must be same suit)
     // Optimization: filter by flush suit then check straight again
     const flushSuit = Object.keys(suitCounts).find(key => suitCounts[key] >= 5);
     if (flushSuit) {
        const flushCards = allCards.filter(c => c.suit === flushSuit).map(c => RANK_VALUE[c.rank]).sort((a,b) => b-a);
        const uniqueFlushRanks = Array.from(new Set(flushCards));
        for (let i = 0; i <= uniqueFlushRanks.length - 5; i++) {
            const slice = uniqueFlushRanks.slice(i, i + 5);
            if (slice[0] - slice[4] === 4) {
               isStraightFlush = true;
               sfHigh = slice[0];
               break;
            }
        }
        if (!isStraightFlush && uniqueFlushRanks.includes(14) && uniqueFlushRanks.includes(2) && uniqueFlushRanks.includes(3) && uniqueFlushRanks.includes(4) && uniqueFlushRanks.includes(5)) {
             isStraightFlush = true;
             sfHigh = 5;
        }
     }
  }

  // Multiples
  const pairs = Object.entries(rankCounts).filter(([_, count]) => count === 2).map(([r]) => parseInt(r)).sort((a, b) => b - a);
  const trips = Object.entries(rankCounts).filter(([_, count]) => count === 3).map(([r]) => parseInt(r)).sort((a, b) => b - a);
  const quads = Object.entries(rankCounts).filter(([_, count]) => count === 4).map(([r]) => parseInt(r)).sort((a, b) => b - a);

  // Decision Tree
  if (isStraightFlush) {
    return { 
      rank: sfHigh === 14 ? 'Royal Flush' : 'Straight Flush', 
      score: HAND_SCORES[sfHigh === 14 ? 'Royal Flush' : 'Straight Flush'], 
      tieBreakers: [sfHigh],
      description: sfHigh === 14 ? 'Royal Flush' : `Straight Flush, ${sfHigh} High`
    };
  }
  if (quads.length > 0) {
    const kicker = ranks.find(r => r !== quads[0]) || 0;
    return { rank: 'Four of a Kind', score: HAND_SCORES['Four of a Kind'], tieBreakers: [quads[0], kicker], description: `Four of a Kind` };
  }
  if (trips.length > 0 && (pairs.length > 0 || trips.length > 1)) {
    const tripVal = trips[0];
    const pairVal = trips.length > 1 ? trips[1] : pairs[0];
    return { rank: 'Full House', score: HAND_SCORES['Full House'], tieBreakers: [tripVal, pairVal], description: `Full House` };
  }
  if (isFlush) {
    const flushSuit = Object.keys(suitCounts).find(key => suitCounts[key] >= 5);
    const flushRanks = allCards.filter(c => c.suit === flushSuit).map(c => RANK_VALUE[c.rank]).sort((a,b) => b-a).slice(0, 5);
    return { rank: 'Flush', score: HAND_SCORES['Flush'], tieBreakers: flushRanks, description: `Flush` };
  }
  if (straightHigh > 0) {
    return { rank: 'Straight', score: HAND_SCORES['Straight'], tieBreakers: [straightHigh], description: `Straight, ${straightHigh} High` };
  }
  if (trips.length > 0) {
     const kickers = ranks.filter(r => r !== trips[0]).slice(0, 2);
    return { rank: 'Three of a Kind', score: HAND_SCORES['Three of a Kind'], tieBreakers: [trips[0], ...kickers], description: `Three of a Kind` };
  }
  if (pairs.length >= 2) {
    const kicker = ranks.find(r => r !== pairs[0] && r !== pairs[1]) || 0;
    return { rank: 'Two Pair', score: HAND_SCORES['Two Pair'], tieBreakers: [pairs[0], pairs[1], kicker], description: `Two Pair` };
  }
  if (pairs.length === 1) {
    const kickers = ranks.filter(r => r !== pairs[0]).slice(0, 3);
    return { rank: 'Pair', score: HAND_SCORES['Pair'], tieBreakers: [pairs[0], ...kickers], description: `Pair` };
  }

  return { rank: 'High Card', score: HAND_SCORES['High Card'], tieBreakers: ranks.slice(0, 5), description: `High Card` };
};

// Compare hands to find winner(s)
export const determineWinners = (players: {id: number, hand: Card[], isFolded: boolean}[], communityCards: Card[]): number[] => {
  const activePlayers = players.filter(p => !p.isFolded);
  if (activePlayers.length === 0) return [];
  if (activePlayers.length === 1) return [activePlayers[0].id];

  const evaluations = activePlayers.map(p => ({
    id: p.id,
    eval: evaluateHand(p.hand, communityCards)
  }));

  // Sort by score desc, then tiebreakers
  evaluations.sort((a, b) => {
    if (b.eval.score !== a.eval.score) return b.eval.score - a.eval.score;
    // Compare tie breakers
    for (let i = 0; i < b.eval.tieBreakers.length; i++) {
        const valA = a.eval.tieBreakers[i] || 0;
        const valB = b.eval.tieBreakers[i] || 0;
        if (valB !== valA) return valB - valA;
    }
    return 0;
  });

  const bestEval = evaluations[0];
  // Check for ties
  const winners = evaluations.filter(e => {
      if (e.eval.score !== bestEval.eval.score) return false;
      for (let i = 0; i < bestEval.eval.tieBreakers.length; i++) {
          if (e.eval.tieBreakers[i] !== bestEval.eval.tieBreakers[i]) return false;
      }
      return true;
  }).map(e => e.id);

  return winners;
};