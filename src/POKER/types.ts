export type Suit = 'H' | 'D' | 'C' | 'S';
export type Rank = '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | '10' | 'J' | 'Q' | 'K' | 'A';

export interface Card {
  suit: Suit;
  rank: Rank;
  id: string; // Unique ID for keys
}

export enum PlayerActionType {
  FOLD = 'FOLD',
  CHECK = 'CHECK',
  CALL = 'CALL',
  RAISE = 'RAISE',
  ALL_IN = 'ALL_IN'
}

export interface PlayerAction {
  type: PlayerActionType;
  amount: number; // For raise/call/all-in (total bet amount in the round)
  reasoning?: string;
}

export interface Player {
  id: number;
  name: string;
  model: string;
  chips: number;
  hand: Card[];
  currentBet: number; // Amount bet in current round
  isFolded: boolean;
  isAllIn: boolean;
  lastAction: PlayerAction | null;
  status: 'waiting' | 'thinking' | 'acted' | 'winner' | 'out';
  handDescription?: string; // e.g., "Two Pair"
  totalWinnings: number; // For leaderboard
  thinkTotalMs?: number;
  thinkCount?: number;
  handsPlayed?: number;
  folds?: number;
  biggestWin?: number;
  biggestLoss?: number;
  vpipCount?: number;
}

export enum GameStage {
  IDLE = 'IDLE',
  PREFLOP = 'PREFLOP',
  FLOP = 'FLOP',
  TURN = 'TURN',
  RIVER = 'RIVER',
  SHOWDOWN = 'SHOWDOWN'
}

export interface GameState {
  players: Player[];
  pot: number;
  communityCards: Card[];
  deck: Card[];
  dealerIndex: number;
  currentPlayerIndex: number;
  stage: GameStage;
  currentBet: number; // Highest bet in the current round
  minRaise: number;
  winners: number[];
  handNumber: number;
  history: string[]; // Log of actions
}

export interface HandHistory {
  handNumber: number;
  earnings: { [playerId: number]: number };
}
