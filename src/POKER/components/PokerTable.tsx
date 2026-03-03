import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { GameState, Player, GameStage, PlayerActionType, HandHistory } from '../types';
import { createDeck, determineWinners } from '../utils/pokerLogic';
import { getAgentDecision } from '../services/geminiService';
import PlayerSpot from './PlayerSpot';
import Card from './Card';
import { Play, Pause } from 'lucide-react';
import clsx from 'clsx';
import { logEvent, logStats } from '../utils/logger';

// --- Initial State ---
const INITIAL_STACK = 10000;
const SMALL_BLIND = 50;
const BIG_BLIND = 100;
const NUM_PLAYERS = 6;
const CLIENT_THINK_TIMEOUT_MS = 300000;

const PLAYER_PROFILES = [
  { name: 'Grok 4.1 Fast', model: 'x-ai/grok-4.1-fast' },
  { name: 'Gemini 3 Flash', model: 'google/gemini-3-flash-preview' },
  { name: 'GPT-5 Mini', model: 'openai/gpt-5-mini' },
  { name: 'Moonshot Kimi K2', model: 'moonshotai/kimi-k2-thinking' },
  { name: 'DeepSeek V3.2', model: 'deepseek/deepseek-v3.2' },
  { name: 'Qwen3 Max', model: 'qwen/qwen3-max' },
];

const normalizePlayerFlags = (player: Player): Player => {
  if (player.isFolded) {
    return { ...player, isAllIn: false };
  }
  if (player.isAllIn) {
    return { ...player, isFolded: false };
  }
  return player;
};

const generatePlayers = (): Player[] =>
  Array.from({ length: NUM_PLAYERS }, (_, i) => ({
    id: i + 1,
    name: PLAYER_PROFILES[i]?.name || `Bot ${i + 1}`,
    model: PLAYER_PROFILES[i]?.model || 'x-ai/grok-4.1-fast',
    chips: INITIAL_STACK,
    hand: [],
    currentBet: 0,
    isFolded: false,
    isAllIn: false,
    lastAction: null,
    status: 'waiting',
    totalWinnings: 0,
    thinkTotalMs: 0,
    thinkCount: 0,
    handsPlayed: 0,
    folds: 0,
    biggestWin: 0,
    biggestLoss: 0,
    vpipCount: 0
  }));

export interface TableStats {
  tableId: number;
  players: Player[];
  handHistory: HandHistory[];
  gameNumber: number;
  handNumber: number;
  pot: number;
  communityCards: { suit: string; rank: string; id: string }[];
  stage: string;
  dealerIndex: number;
  currentPlayerIndex: number;
  history: string[]; // Game log
}

export interface PokerTableRef {
  getStats: () => TableStats;
  setRunning: (running: boolean) => void;
  isRunning: () => boolean;
}

interface PokerTableProps {
  tableId: number;
  isGlobalRunning: boolean;
  onStatsUpdate?: (stats: TableStats) => void;
  compact?: boolean;
}

const PokerTable = forwardRef<PokerTableRef, PokerTableProps>(({ tableId, isGlobalRunning, onStatsUpdate, compact = false }, ref) => {
  const [isRunning, setIsRunning] = useState(false);
  const [handHistory, setHandHistory] = useState<HandHistory[]>([]);
  const [gameNumber, setGameNumber] = useState(1);

  // Game State
  const [gameState, setGameState] = useState<GameState>({
    players: generatePlayers(),
    pot: 0,
    communityCards: [],
    deck: [],
    dealerIndex: 0,
    currentPlayerIndex: -1,
    stage: GameStage.IDLE,
    currentBet: 0,
    minRaise: BIG_BLIND,
    winners: [],
    handNumber: 0,
    history: []
  });

  const gameStateRef = useRef(gameState);
  useEffect(() => { gameStateRef.current = gameState; }, [gameState]);
  const gameNumberRef = useRef(gameNumber);
  useEffect(() => { gameNumberRef.current = gameNumber; }, [gameNumber]);
  const handOpeningStacksRef = useRef<{[id: number]: number}>({});
  const handVpipRef = useRef<Set<number>>(new Set());
  const isRunningRef = useRef(isRunning);
  useEffect(() => { isRunningRef.current = isRunning; }, [isRunning]);
  const startingHandRef = useRef(false); // Guard against double-calling startNewHand
  const foldWinSurvivorsRef = useRef<number>(NUM_PLAYERS); // Track survivors after fold win
  const foldWinProcessedRef = useRef(false); // Guard against double-processing fold win

  // Sync with global running state
  useEffect(() => {
    setIsRunning(isGlobalRunning);
  }, [isGlobalRunning]);

  // Expose methods to parent
  useImperativeHandle(ref, () => ({
    getStats: () => ({
      tableId,
      players: gameStateRef.current.players,
      handHistory,
      gameNumber: gameNumberRef.current,
      handNumber: gameStateRef.current.handNumber,
      pot: gameStateRef.current.pot,
      communityCards: gameStateRef.current.communityCards,
      stage: gameStateRef.current.stage,
      dealerIndex: gameStateRef.current.dealerIndex,
      currentPlayerIndex: gameStateRef.current.currentPlayerIndex,
      history: gameStateRef.current.history
    }),
    setRunning: (running: boolean) => setIsRunning(running),
    isRunning: () => isRunningRef.current
  }));

  // Notify parent of stats updates
  useEffect(() => {
    if (onStatsUpdate) {
      onStatsUpdate({
        tableId,
        players: gameState.players,
        handHistory,
        gameNumber,
        handNumber: gameState.handNumber,
        pot: gameState.pot,
        communityCards: gameState.communityCards,
        stage: gameState.stage,
        dealerIndex: gameState.dealerIndex,
        currentPlayerIndex: gameState.currentPlayerIndex,
        history: gameState.history
      });
    }
  }, [gameState.players, handHistory, gameNumber, gameState.handNumber, gameState.pot, gameState.communityCards, gameState.stage, gameState.dealerIndex, gameState.currentPlayerIndex, gameState.history]);

  // --- Game Loop Helpers ---

  const addLog = (msg: string) => {
    logEvent('log_line', { table: tableId, game: gameNumberRef.current, hand: gameStateRef.current.handNumber, message: msg }, tableId);
    setGameState(prev => ({ ...prev, history: [...prev.history, msg] }));
  };

  const logSnapshot = (type: string, state: GameState = gameStateRef.current) => {
    logEvent(type, {
      table: tableId,
      game: gameNumberRef.current,
      hand: state.handNumber,
      stage: state.stage,
      pot: state.pot,
      community: state.communityCards.map(c => `${c.rank}${c.suit}`),
      players: state.players.map(p => ({
        id: p.id,
        name: p.name,
        model: p.model,
        chips: p.chips,
        currentBet: p.currentBet,
        isFolded: p.isFolded,
        isAllIn: p.isAllIn,
        status: p.status,
        totalWinnings: p.totalWinnings
      })),
      history: state.history.slice(-5),
    }, tableId);
  };

  const startNewGame = () => {
    const nextGame = gameNumberRef.current + 1;
    logEvent('new_game', { table: tableId, game: nextGame, reason: 'only one player left', carriedTotals: gameStateRef.current.players.map(p => ({ id: p.id, chips: p.chips, totalWinnings: p.totalWinnings })) }, tableId);
    setGameNumber(() => nextGame);
    handOpeningStacksRef.current = {};
    handVpipRef.current = new Set();
    // DO NOT clear handHistory - keep accumulating across games for chart continuity
    setGameState(prev => ({
      ...prev,
      players: prev.players.map(p => ({
        ...p,
        chips: INITIAL_STACK,
        hand: [],
        currentBet: 0,
        isFolded: false,
        isAllIn: false,
        lastAction: null,
        status: 'waiting' as const,
        handDescription: undefined,
        // Preserve cumulative stats across games - do NOT reset these:
        // totalWinnings, thinkTotalMs, thinkCount, handsPlayed, folds, biggestWin, biggestLoss, vpipCount
      })),
      pot: 0,
      communityCards: [],
      deck: [],
      dealerIndex: 0,
      currentPlayerIndex: -1,
      stage: GameStage.IDLE,
      currentBet: 0,
      minRaise: BIG_BLIND,
      winners: [],
      handNumber: 0,
      history: [`--- Table ${tableId}: New Game #${nextGame} ---`]
    }));
  };

  const startNewHand = () => {
    // Guard against double-calling
    if (startingHandRef.current) return;
    startingHandRef.current = true;

    // Reset refs for new hand
    handVpipRef.current = new Set();
    foldWinSurvivorsRef.current = NUM_PLAYERS; // Reset to all players
    foldWinProcessedRef.current = false; // Reset fold win guard

    setGameState(prev => {
      const anyBusted = prev.players.some(p => p.chips <= 0);
      let playersToUse = prev.players;

      if (anyBusted) {
        logEvent('stack_reset', {
          table: tableId,
          game: gameNumberRef.current,
          hand: prev.handNumber,
          reason: 'player_busted',
          players: prev.players.map(p => ({ id: p.id, chips: p.chips }))
        }, tableId);
        playersToUse = prev.players.map(p => ({
          ...p,
          chips: INITIAL_STACK
        }));
      }

      handOpeningStacksRef.current = Object.fromEntries(playersToUse.map(p => [p.id, p.chips]));
      const deck = createDeck();
      const dealerIndex = (prev.handNumber === 0) ? 0 : (prev.dealerIndex + 1) % NUM_PLAYERS;
      const sbIndex = (dealerIndex + 1) % NUM_PLAYERS;
      const bbIndex = (dealerIndex + 2) % NUM_PLAYERS;
      const firstActor = (dealerIndex + 3) % NUM_PLAYERS;

      const newPlayers = playersToUse.map(p => normalizePlayerFlags({
        ...p,
        hand: [deck.pop()!, deck.pop()!],
        currentBet: 0,
        isFolded: false,
        isAllIn: false,
        lastAction: null,
        status: 'waiting' as const,
        handDescription: undefined,
        handsPlayed: (p.handsPlayed || 0) + 1
      }));

      let pot = 0;
      if (newPlayers[sbIndex].chips > SMALL_BLIND) {
        newPlayers[sbIndex].chips -= SMALL_BLIND;
        newPlayers[sbIndex].currentBet = SMALL_BLIND;
        pot += SMALL_BLIND;
      } else {
        pot += newPlayers[sbIndex].chips;
        newPlayers[sbIndex].currentBet = newPlayers[sbIndex].chips;
        newPlayers[sbIndex].chips = 0;
        newPlayers[sbIndex].isAllIn = true;
      }

      if (newPlayers[bbIndex].chips > BIG_BLIND) {
        newPlayers[bbIndex].chips -= BIG_BLIND;
        newPlayers[bbIndex].currentBet = BIG_BLIND;
        pot += BIG_BLIND;
      } else {
        pot += newPlayers[bbIndex].chips;
        newPlayers[bbIndex].currentBet = newPlayers[bbIndex].chips;
        newPlayers[bbIndex].chips = 0;
        newPlayers[bbIndex].isAllIn = true;
      }

      const finalPlayers = newPlayers.map(normalizePlayerFlags);

      const nextState: GameState = {
        ...prev,
        deck,
        players: finalPlayers,
        pot,
        communityCards: [],
        dealerIndex,
        currentPlayerIndex: firstActor,
        stage: GameStage.PREFLOP,
        currentBet: BIG_BLIND,
        minRaise: BIG_BLIND,
        winners: [],
        handNumber: prev.handNumber + 1,
        history: [`Hand #${prev.handNumber + 1} Started. Blinds ${SMALL_BLIND}/${BIG_BLIND}.`]
      };
      logSnapshot('hand_start', nextState);
      return nextState;
    });

    // Reset the guard after a short delay to allow state to settle
    setTimeout(() => { startingHandRef.current = false; }, 100);
  };

  const nextStage = () => {
    setGameState(prev => {
      let nextStageVal = prev.stage;
      let communityCards = [...prev.communityCards];
      let deck = [...prev.deck];

      let pot = prev.pot;
      let players = prev.players.map(p => {
        return normalizePlayerFlags({ ...p, currentBet: 0, lastAction: null, status: 'waiting' as const });
      });

      if (prev.stage === GameStage.PREFLOP) {
        deck.pop();
        communityCards.push(deck.pop()!, deck.pop()!, deck.pop()!);
        nextStageVal = GameStage.FLOP;

        const vpipPlayers = players.filter(p => !p.isFolded && handVpipRef.current.has(p.id));
        players = players.map(p => {
          if (!p.isFolded && handVpipRef.current.has(p.id)) {
            return { ...p, vpipCount: (p.vpipCount || 0) + 1 };
          }
          return p;
        });
      } else if (prev.stage === GameStage.FLOP) {
        deck.pop();
        communityCards.push(deck.pop()!);
        nextStageVal = GameStage.TURN;
      } else if (prev.stage === GameStage.TURN) {
        deck.pop();
        communityCards.push(deck.pop()!);
        nextStageVal = GameStage.RIVER;
      } else if (prev.stage === GameStage.RIVER) {
        nextStageVal = GameStage.SHOWDOWN;
      }

      let nextPlayer = (prev.dealerIndex + 1) % NUM_PLAYERS;
      let count = 0;
      while (players[nextPlayer].isFolded || players[nextPlayer].isAllIn) {
        nextPlayer = (nextPlayer + 1) % NUM_PLAYERS;
        count++;
        if(count > NUM_PLAYERS) break;
      }

      const nextState: GameState = {
        ...prev,
        stage: nextStageVal,
        players,
        communityCards,
        deck,
        currentPlayerIndex: nextPlayer,
        currentBet: 0,
        minRaise: BIG_BLIND,
        history: [...prev.history, `--- ${nextStageVal} ---`]
      };
      logSnapshot('stage_transition', nextState);
      return nextState;
    });
  };

  const handleShowdown = async () => {
    const currentState = gameStateRef.current;

    const winners = determineWinners(currentState.players, currentState.communityCards);
    const share = Math.floor(currentState.pot / winners.length);

    let survivorsAfterHand = currentState.players.length;
    let snapshot: GameState | null = null;
    setGameState(prev => {
      const updatedPlayers = prev.players.map(p => {
        const opening = handOpeningStacksRef.current[p.id] ?? p.chips;
        const finalChips = winners.includes(p.id) ? p.chips + share : p.chips;
        const delta = finalChips - opening;
        const biggestWin = Math.max(p.biggestWin || 0, delta > 0 ? delta : 0);
        const biggestLoss = Math.min(p.biggestLoss || 0, delta < 0 ? delta : 0);
        return normalizePlayerFlags({
          ...p,
          chips: finalChips,
          totalWinnings: p.totalWinnings + delta,
          status: winners.includes(p.id) ? 'winner' as const : 'waiting' as const,
          biggestWin,
          biggestLoss
        });
      });

      const currentEarnings: {[id: number]: number} = {};
      updatedPlayers.forEach(p => currentEarnings[p.id] = p.totalWinnings);

      const newHistoryEntry: HandHistory = {
        handNumber: prev.handNumber,
        earnings: currentEarnings
      };

      setHandHistory(h => [...h, newHistoryEntry]);

      const nextState: GameState = {
        ...prev,
        players: updatedPlayers,
        stage: GameStage.SHOWDOWN,
        winners,
        history: [...prev.history, `Winners: ${winners.map(id => `Player ${id}`).join(', ')} win ${share}`]
      };
      survivorsAfterHand = updatedPlayers.filter(p => p.chips > 0).length;
      snapshot = nextState;
      return nextState;
    });

    if (snapshot) {
      logSnapshot('showdown', snapshot);
      // Log stats after hand completes
      logStats(tableId, gameNumberRef.current, snapshot.handNumber, snapshot.players);
    }

    const shouldResetGame = survivorsAfterHand <= 1;
    if (shouldResetGame) {
      setTimeout(() => startNewGame(), 100);
      // After startNewGame, the useEffect will handle starting new hand when it sees IDLE stage
      // So we don't need to schedule startNewHand here
    } else if (isRunningRef.current) {
      // Only call startNewHand directly if we didn't reset the game
      setTimeout(() => startNewHand(), 3000);
    }
  };

  const executeTurn = async () => {
    const state = gameStateRef.current;
    const player = state.players[state.currentPlayerIndex];

    if (player.isFolded || player.isAllIn) {
      setTimeout(() => advanceTurn(), 200);
      return;
    }

    setGameState(prev => ({
      ...prev,
      players: prev.players.map((p, i) => i === state.currentPlayerIndex ? { ...p, status: 'thinking' } : p)
    }));

    const startThink = Date.now();

    let decision;
    try {
      decision = await Promise.race([
        getAgentDecision(state, player),
        new Promise(resolve => setTimeout(() => resolve({ action: PlayerActionType.FOLD, amount: 0, reasoning: 'Auto-fold (client timeout)' }), CLIENT_THINK_TIMEOUT_MS + 1000))
      ]);
    } catch (err) {
      console.error(`Table ${tableId} decision error`, err);
      decision = { action: PlayerActionType.FOLD, amount: 0, reasoning: 'Auto-fold (error)' };
    }
    const thinkElapsed = Date.now() - startThink;

    setGameState(prev => {
      let newPlayers = [...prev.players];
      let p = { ...newPlayers[prev.currentPlayerIndex] };
      let newPot = prev.pot;
      let newCurrentBet = prev.currentBet;
      let minRaise = prev.minRaise;
      let contribution = 0;
      let actionType = decision.action;

      if (actionType === PlayerActionType.FOLD) {
        if (!p.isFolded) {
          p.folds = (p.folds || 0) + 1;
        }
        p.isFolded = true;
        p.isAllIn = false;
      } else {
        const desiredBet = decision.amount;
        const required = Math.max(0, desiredBet - p.currentBet);
        contribution = Math.min(required, p.chips);

        if (contribution > 0) {
          p.chips -= contribution;
          newPot += contribution;
          p.currentBet += contribution;
        }

        const wentAllIn = actionType === PlayerActionType.ALL_IN || p.chips === 0 || contribution < required;
        if (wentAllIn) {
          actionType = PlayerActionType.ALL_IN;
          p.isAllIn = true;
          p.isFolded = false;
        }

        if (p.currentBet > newCurrentBet) {
            const raiseDiff = p.currentBet - newCurrentBet;
            if (raiseDiff > minRaise) minRaise = raiseDiff;
            newCurrentBet = p.currentBet;
        }

        const isVpipAction = actionType === PlayerActionType.CALL ||
           actionType === PlayerActionType.RAISE ||
           actionType === PlayerActionType.ALL_IN;
        if (prev.stage === GameStage.PREFLOP && isVpipAction) {
          handVpipRef.current.add(p.id);
        }
      }

      p = normalizePlayerFlags(p);
      p.lastAction = { type: actionType, amount: p.currentBet, reasoning: decision.reasoning };
      p.status = 'acted';
      p.thinkTotalMs = (p.thinkTotalMs || 0) + thinkElapsed;
      p.thinkCount = (p.thinkCount || 0) + 1;
      newPlayers[prev.currentPlayerIndex] = p;

      const nextState: GameState = {
        ...prev,
        players: newPlayers,
        pot: newPot,
        currentBet: newCurrentBet,
        minRaise,
        history: [...prev.history, `P${p.id} ${actionType}${p.currentBet > 0 ? ` $${p.currentBet}` : ''}: ${decision.reasoning}`]
      };
      logEvent('action', { table: tableId, game: gameNumberRef.current, hand: nextState.handNumber, stage: prev.stage, playerId: p.id, model: p.model, action: p.lastAction, pot: nextState.pot }, tableId);
      return nextState;
    });

    setTimeout(() => advanceTurn(), 500);
  };

  const advanceTurn = () => {
    const prev = gameStateRef.current;

    const activePlayers = prev.players.filter(p => !p.isFolded);

    // Check if all active players are all-in (or only one player can still act)
    // In this case, skip directly to showdown since no more betting is possible
    const playersWhoCanAct = activePlayers.filter(p => !p.isAllIn);
    if (playersWhoCanAct.length <= 1 && activePlayers.length > 1 && prev.stage !== GameStage.SHOWDOWN && prev.stage !== GameStage.IDLE) {
      addLog('All players all-in - running out the board to showdown');

      setGameState(s => {
        let communityCards = [...s.communityCards];
        let deck = [...s.deck];
        let players = [...s.players];

        // Update VPIP if we're skipping from preflop
        if (s.stage === GameStage.PREFLOP) {
          players = players.map(p => {
            if (!p.isFolded && handVpipRef.current.has(p.id)) {
              return { ...p, vpipCount: (p.vpipCount || 0) + 1 };
            }
            return p;
          });
        }

        // Deal remaining community cards (with burn cards)
        while (communityCards.length < 5) {
          deck.pop(); // burn card
          communityCards.push(deck.pop()!);
        }

        const nextState: GameState = {
          ...s,
          players: players.map(p => normalizePlayerFlags({ ...p, currentBet: 0 })),
          communityCards,
          deck,
          stage: GameStage.SHOWDOWN,
          currentBet: 0,
          history: [...s.history, '--- All-in showdown: dealing remaining cards ---']
        };
        logSnapshot('all_in_showdown', nextState);
        return nextState;
      });
      return;
    }

    if (activePlayers.length === 1) {
        // Guard against double-processing
        if (foldWinProcessedRef.current) return;
        foldWinProcessedRef.current = true;

        const winnerId = activePlayers[0].id;
        setGameState(s => ({ ...s, winners: [winnerId], stage: GameStage.SHOWDOWN }));
        setTimeout(() => {
            setGameState(s => {
                // Skip if already processed (pot is 0) or wrong stage
                if (s.stage !== GameStage.SHOWDOWN || s.pot === 0) {
                    // Even on early return, calculate survivors from current state
                    foldWinSurvivorsRef.current = s.players.filter(p => p.chips > 0).length;
                    return s;
                }
                const nextPlayers = s.players.map(p => {
                  const opening = handOpeningStacksRef.current[p.id] ?? p.chips;
                  const finalChips = p.id === winnerId ? p.chips + s.pot : p.chips;
                  const delta = finalChips - opening;
                  const biggestWin = Math.max(p.biggestWin || 0, delta > 0 ? delta : 0);
                  const biggestLoss = Math.min(p.biggestLoss || 0, delta < 0 ? delta : 0);
                  return normalizePlayerFlags({ ...p, chips: finalChips, totalWinnings: p.totalWinnings + delta, biggestWin, biggestLoss });
                });
                const earnings: {[id: number]: number} = {};
                nextPlayers.forEach(p => { earnings[p.id] = p.totalWinnings; });
                setHandHistory(h => [...h, { handNumber: s.handNumber, earnings }]);

                // Calculate survivors inside the callback to avoid stale ref
                foldWinSurvivorsRef.current = nextPlayers.filter(p => p.chips > 0).length;

                const nextState: GameState = {
                    ...s,
                    players: nextPlayers,
                    pot: 0,
                    history: [...s.history, `Everyone folded. Player ${winnerId} wins.`]
                };
                logSnapshot('fold_win', nextState);
                // Log stats after hand completes (fold win)
                logStats(tableId, gameNumberRef.current, s.handNumber, nextPlayers);
                return nextState;
            });
            setTimeout(() => {
              // Use the ref that was set inside setGameState callback
              const survivors = foldWinSurvivorsRef.current;
              if (survivors <= 1) {
                startNewGame();
                // After startNewGame, the useEffect will handle starting new hand when it sees IDLE stage
              } else if (isRunningRef.current) {
                startNewHand();
              }
            }, 2000);
        }, 1000);
        return;
    }

    const allMatched = prev.players.every(p =>
        p.isFolded ||
        p.isAllIn ||
        (p.currentBet === prev.currentBet && p.status !== 'waiting')
    );

    if (allMatched && prev.stage !== GameStage.SHOWDOWN && prev.stage !== GameStage.IDLE) {
        nextStage();
    } else {
        let nextIndex = (prev.currentPlayerIndex + 1) % NUM_PLAYERS;
        let loopCount = 0;

        while(prev.players[nextIndex].isFolded || prev.players[nextIndex].isAllIn) {
            nextIndex = (nextIndex + 1) % NUM_PLAYERS;
            loopCount++;
            if (loopCount > NUM_PLAYERS) break;
        }
        setGameState(s => ({ ...s, currentPlayerIndex: nextIndex }));
    }
  };

  const showdownHandledRef = useRef(false);

  useEffect(() => {
    if (!isRunning) return;
    if (gameState.stage === GameStage.IDLE) {
        startNewHand();
        return;
    }
    if (gameState.stage === GameStage.SHOWDOWN) {
        if (!showdownHandledRef.current && gameState.winners.length === 0) {
            showdownHandledRef.current = true;
            handleShowdown();
        }
        return;
    }

    showdownHandledRef.current = false;

    const currentPlayer = gameState.players[gameState.currentPlayerIndex];

    if (currentPlayer && currentPlayer.status !== 'thinking') {
         executeTurn();
    }
  }, [gameState.currentPlayerIndex, gameState.stage, isRunning]);

  const getPositionClass = (index: number) => {
    const positions = [
        "top-[70%] left-1/2 -translate-x-1/2",
        "top-[60%] left-[5%]",
        "top-[15%] left-[5%]",
        "top-[-5%] left-1/2 -translate-x-1/2",
        "top-[15%] right-[5%]",
        "top-[60%] right-[5%]",
    ];
    return positions[index];
  };

  if (compact) {
    // Compact view for multi-table display
    return (
      <div className="bg-slate-900 rounded-xl border border-slate-700 p-3 h-full flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-bold text-white">Table {tableId}</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Hand #{gameState.handNumber}</span>
            <span className={clsx("w-2 h-2 rounded-full", isRunning ? "bg-green-500 animate-pulse" : "bg-red-500")} />
          </div>
        </div>

        {/* Mini table view */}
        <div className="relative flex-1 poker-table-felt rounded-xl border-4 border-amber-900 min-h-[180px]">
          {/* Pot */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
            <div className="bg-black/60 px-3 py-1 rounded-full text-yellow-400 font-mono text-sm">
              ${gameState.pot.toLocaleString()}
            </div>
            <div className="text-green-200/60 text-[10px] uppercase mt-1">{gameState.stage}</div>
          </div>

          {/* Community cards */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[120%] flex gap-0.5">
            {gameState.communityCards.map((card) => (
              <Card key={card.id} card={card} size="sm" />
            ))}
          </div>

          {/* Mini player indicators */}
          {gameState.players.map((player, index) => {
            const angles = [270, 210, 150, 90, 30, 330];
            const angle = angles[index] * (Math.PI / 180);
            const radiusX = 42;
            const radiusY = 38;
            const x = 50 + radiusX * Math.cos(angle);
            const y = 50 + radiusY * Math.sin(angle);

            return (
              <div
                key={player.id}
                className={clsx(
                  "absolute w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold transition-all",
                  player.isFolded ? "bg-slate-700 text-slate-500" :
                  gameState.winners.includes(player.id) ? "bg-green-500 text-white ring-2 ring-yellow-400" :
                  gameState.currentPlayerIndex === index ? "bg-yellow-500 text-black ring-2 ring-white" :
                  "bg-slate-600 text-white"
                )}
                style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}
                title={`${player.name}: $${player.chips}`}
              >
                P{player.id}
              </div>
            );
          })}
        </div>

        {/* Mini leaderboard */}
        <div className="mt-2 space-y-1">
          {[...gameState.players].sort((a, b) => b.chips - a.chips).slice(0, 3).map((p, idx) => (
            <div key={p.id} className="flex items-center justify-between text-[10px]">
              <span className="text-slate-400 truncate max-w-[80px]">{idx + 1}. {p.name}</span>
              <span className={clsx("font-mono", p.totalWinnings >= 0 ? "text-green-400" : "text-red-400")}>
                ${p.chips.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Full table view
  return (
    <div className="w-full h-full flex items-center justify-center p-4 relative">
      <div className="absolute top-4 left-4 bg-slate-800/80 px-3 py-1 rounded-lg">
        <span className="text-white font-bold">Table {tableId}</span>
        <span className="text-slate-400 ml-2">Hand #{gameState.handNumber}</span>
      </div>

      <div className="relative w-full max-w-4xl aspect-[1.8/1] poker-table-felt rounded-[120px] border-[12px] border-amber-900 shadow-2xl flex items-center justify-center">
        <div className="absolute text-green-800/30 font-black text-4xl tracking-widest select-none pointer-events-none">
          TABLE {tableId}
        </div>

        <div className="z-10 flex flex-col items-center space-y-3">
          <div className="flex items-center justify-center space-x-2 h-20">
            {gameState.communityCards.map((card) => (
              <div key={card.id} className="animate-[fadeSlideIn_0.5s_ease-out]">
                <Card card={card} size="md" />
              </div>
            ))}
            {Array.from({length: 5 - gameState.communityCards.length}).map((_, i) => (
              <div key={i} className="w-12 h-16 border-2 border-green-800/50 rounded-md"></div>
            ))}
          </div>

          <div className="bg-black/60 px-5 py-1.5 rounded-full text-yellow-400 font-mono text-lg border border-yellow-600/50 shadow-lg">
            <span className="text-yellow-600">$</span>
            <span>{gameState.pot.toLocaleString()}</span>
          </div>

          <div className="text-green-200/60 font-medium text-xs uppercase tracking-widest">
            {gameState.stage}
          </div>
        </div>

        {gameState.players.map((player, index) => (
          <PlayerSpot
            key={player.id}
            player={player}
            isActive={gameState.currentPlayerIndex === index && gameState.stage !== GameStage.SHOWDOWN}
            isDealer={gameState.dealerIndex === index}
            positionClass={getPositionClass(index)}
            winner={gameState.winners.includes(player.id)}
          />
        ))}
      </div>

      {/* Game Log */}
      <div className="absolute bottom-4 right-4 w-64 h-48 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-xl p-3 overflow-hidden flex flex-col shadow-xl z-40">
        <h3 className="text-slate-400 text-xs font-bold uppercase mb-2 flex items-center justify-between">
          <span>Log</span>
          <span className="text-blue-500">T{tableId}</span>
        </h3>
        <div className="flex-1 overflow-y-auto space-y-1 text-[10px] font-mono">
          {gameState.history.slice(-10).map((line, i) => (
            <div key={i} className="text-slate-300 border-b border-slate-800/50 pb-0.5 last:border-0">
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

PokerTable.displayName = 'PokerTable';

export default PokerTable;
