import React, { useState, useEffect, useRef } from 'react';
import { GameState, Player, GameStage, PlayerActionType, HandHistory } from './types';
import { createDeck, determineWinners } from './utils/pokerLogic';
import { getAgentDecision } from './services/geminiService';
import PlayerSpot from './components/PlayerSpot';
import Card from './components/Card';
import StatsView from './components/StatsView';
import { Play, Pause, BarChart2, Table as TableIcon, Layers } from 'lucide-react';
import clsx from 'clsx';
import { logEvent } from './utils/logger';

// --- Initial State ---
const INITIAL_STACK = 10000;
const SMALL_BLIND = 50;
const BIG_BLIND = 100;
const NUM_PLAYERS = 6;
const CLIENT_THINK_TIMEOUT_MS = 60000;

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

const App: React.FC = () => {
  const [view, setView] = useState<'game' | 'stats'>('game');
  const [isRunning, setIsRunning] = useState(false);
  const [speed, setSpeed] = useState(1500); // ms delay between turns
  const [handHistory, setHandHistory] = useState<HandHistory[]>([]);
  const [gameNumber, setGameNumber] = useState(1);
  const [apiKeyOk] = useState<boolean>(() => Boolean(process.env.OPENROUTER_POKER_API || process.env.OPENROUTER_API_KEY));
  
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

  const gameStateRef = useRef(gameState); // Ref for async access
  useEffect(() => { gameStateRef.current = gameState; }, [gameState]);
  const gameNumberRef = useRef(gameNumber);
  useEffect(() => { gameNumberRef.current = gameNumber; }, [gameNumber]);
  const handOpeningStacksRef = useRef<{[id: number]: number}>({});
  const handVpipRef = useRef<Set<number>>(new Set());

  // --- Game Loop Helpers ---

  const addLog = (msg: string) => {
    logEvent('log_line', { game: gameNumberRef.current, hand: gameStateRef.current.handNumber, message: msg });
    setGameState(prev => ({ ...prev, history: [...prev.history, msg] }));
  };

  const logSnapshot = (type: string, state: GameState = gameStateRef.current) => {
    logEvent(type, {
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
    });
  };

  const startNewGame = () => {
    const nextGame = gameNumberRef.current + 1;
    logEvent('new_game', { game: nextGame, reason: 'only one player left', carriedTotals: gameStateRef.current.players.map(p => ({ id: p.id, chips: p.chips, totalWinnings: p.totalWinnings })) });
    setGameNumber(() => nextGame);
    handOpeningStacksRef.current = {};
    handVpipRef.current = new Set();
    // Reset hand history for the new game
    setHandHistory([]);
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
        // Reset all cumulative stats for the new game
        totalWinnings: 0,
        thinkTotalMs: 0,
        thinkCount: 0,
        handsPlayed: 0,
        folds: 0,
        biggestWin: 0,
        biggestLoss: 0,
        vpipCount: 0
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
      history: [`--- New Game #${nextGame} ---`]
    }));
  };

  const startNewHand = () => {
    handVpipRef.current = new Set();
    setGameState(prev => {
      // Check if any player has 0 chips - if so, reset all stacks to initial amount
      const anyBusted = prev.players.some(p => p.chips <= 0);
      let playersToUse = prev.players;

      if (anyBusted) {
        logEvent('stack_reset', {
          game: gameNumberRef.current,
          hand: prev.handNumber,
          reason: 'player_busted',
          players: prev.players.map(p => ({ id: p.id, chips: p.chips }))
        });
        // Reset chips but keep all cumulative stats (totalWinnings, thinkTime, folds, etc.)
        playersToUse = prev.players.map(p => ({
          ...p,
          chips: INITIAL_STACK
        }));
      }

      handOpeningStacksRef.current = Object.fromEntries(playersToUse.map(p => [p.id, p.chips]));
      const deck = createDeck();
      // Rotate dealer
      const dealerIndex = (prev.handNumber === 0) ? 0 : (prev.dealerIndex + 1) % NUM_PLAYERS;
      // Blinds
      const sbIndex = (dealerIndex + 1) % NUM_PLAYERS;
      const bbIndex = (dealerIndex + 2) % NUM_PLAYERS;
      // First actor preflop is UTG (Left of BB)
      const firstActor = (dealerIndex + 3) % NUM_PLAYERS;

      const newPlayers = playersToUse.map(p => normalizePlayerFlags({
        ...p,
        hand: [deck.pop()!, deck.pop()!], // Deal 2 cards
        currentBet: 0,
        isFolded: false, // Everyone can play since stacks are reset if anyone was busted
        isAllIn: false,
        lastAction: null,
        status: 'waiting' as const,
        handDescription: undefined,
        handsPlayed: (p.handsPlayed || 0) + 1
      }));

      // Post Blinds
      let pot = 0;
      // SB
      if (newPlayers[sbIndex].chips > SMALL_BLIND) {
        newPlayers[sbIndex].chips -= SMALL_BLIND;
        newPlayers[sbIndex].currentBet = SMALL_BLIND;
        pot += SMALL_BLIND;
      } else {
        // All in for less than SB
        pot += newPlayers[sbIndex].chips;
        newPlayers[sbIndex].currentBet = newPlayers[sbIndex].chips;
        newPlayers[sbIndex].chips = 0;
        newPlayers[sbIndex].isAllIn = true;
      }

      // BB
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
  };

  const nextStage = () => {
    setGameState(prev => {
      let nextStage = prev.stage;
      let communityCards = [...prev.communityCards];
      let deck = [...prev.deck];

      // Move chips to pot
      let pot = prev.pot;
      let players = prev.players.map(p => {
        pot += (p.currentBet - (p.id === (prev.dealerIndex + 1) % NUM_PLAYERS + 1 || p.id === (prev.dealerIndex + 2) % NUM_PLAYERS + 1 ? 0 : 0)); // Actually chips are already deducted, currentBet is just tracking for the round matching.
        // Wait, Logic correction: 
        // In my model, I deduct chips immediately on action. So 'pot' variable holds the main pot. 
        // I need to reset 'currentBet' for the next round.
        return normalizePlayerFlags({ ...p, currentBet: 0, lastAction: null, status: 'waiting' as const });
      });

      // Burn and Turn
      if (prev.stage === GameStage.PREFLOP) {
        deck.pop(); // Burn
        communityCards.push(deck.pop()!, deck.pop()!, deck.pop()!); // Flop
        nextStage = GameStage.FLOP;

        // VPIP: Count players who voluntarily put money in AND saw the flop
        // handVpipRef tracks who put money in voluntarily during preflop
        // Now we count only those who are still active (not folded)
        const vpipPlayers = players.filter(p => !p.isFolded && handVpipRef.current.has(p.id));
        console.log('VPIP at flop:', vpipPlayers.map(p => p.id), 'voluntary set:', [...handVpipRef.current]);
        players = players.map(p => {
          if (!p.isFolded && handVpipRef.current.has(p.id)) {
            return { ...p, vpipCount: (p.vpipCount || 0) + 1 };
          }
          return p;
        });
      } else if (prev.stage === GameStage.FLOP) {
        deck.pop();
        communityCards.push(deck.pop()!); // Turn
        nextStage = GameStage.TURN;
      } else if (prev.stage === GameStage.TURN) {
        deck.pop();
        communityCards.push(deck.pop()!); // River
        nextStage = GameStage.RIVER;
      } else if (prev.stage === GameStage.RIVER) {
        nextStage = GameStage.SHOWDOWN;
      }

      // First to act is usually Small Blind (left of dealer), or first active player left of dealer
      let nextPlayer = (prev.dealerIndex + 1) % NUM_PLAYERS;
      let count = 0;
      while (players[nextPlayer].isFolded || players[nextPlayer].isAllIn) {
        nextPlayer = (nextPlayer + 1) % NUM_PLAYERS;
        count++;
        if(count > NUM_PLAYERS) break; 
      }

      const nextState: GameState = {
        ...prev,
        stage: nextStage,
        players,
        communityCards,
        deck,
        currentPlayerIndex: nextPlayer,
        currentBet: 0,
        minRaise: BIG_BLIND,
        history: [...prev.history, `--- ${nextStage} ---`]
      };
      logSnapshot('stage_transition', nextState);
      return nextState;
    });
  };

  const handleShowdown = async () => {
    const currentState = gameStateRef.current;
    
    // Evaluate hands
    const winners = determineWinners(currentState.players, currentState.communityCards);
    
    // Distribute Pot (Simplified: No side pots)
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

      // Update History for Chart
      // Snapshot current stack as "earnings" proxy (Total Stack)
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

    if (snapshot) logSnapshot('showdown', snapshot);

    const shouldResetGame = survivorsAfterHand <= 1;
    if (shouldResetGame) {
      setTimeout(() => startNewGame(), 100);
    }

    // Wait then restart
    if (isRunning) {
        setTimeout(() => {
          if (shouldResetGame) {
            setTimeout(() => startNewHand(), 300);
          } else {
            startNewHand();
          }
        }, 4000);
    }
  };

  const executeTurn = async () => {
    const state = gameStateRef.current;
    const player = state.players[state.currentPlayerIndex];

    // Skip if folded or all-in (auto-advance)
    if (player.isFolded || player.isAllIn) {
      setTimeout(() => advanceTurn(), 500);
      return;
    }

    // Set status to thinking
    setGameState(prev => ({
      ...prev,
      players: prev.players.map((p, i) => i === state.currentPlayerIndex ? { ...p, status: 'thinking' } : p)
    }));

    const startThink = Date.now();

    // Call AI
    let decision;
    try {
      decision = await Promise.race([
        getAgentDecision(state, player),
        new Promise(resolve => setTimeout(() => resolve({ action: PlayerActionType.FOLD, amount: 0, reasoning: 'Auto-fold (client 30s timeout)' }), CLIENT_THINK_TIMEOUT_MS + 1000))
      ]);
    } catch (err) {
      console.error('Decision error', err);
      decision = { action: PlayerActionType.FOLD, amount: 0, reasoning: 'Auto-fold (error during thinking)' };
    }
    const thinkElapsed = Date.now() - startThink;

    // Apply Move
    setGameState(prev => {
      let newPlayers = [...prev.players];
      let p = { ...newPlayers[prev.currentPlayerIndex] };
      let newPot = prev.pot;
      let newCurrentBet = prev.currentBet;
      let minRaise = prev.minRaise;
      let contribution = 0;
      let actionType = decision.action;

      // Handle Chips
      if (actionType === PlayerActionType.FOLD) {
        if (!p.isFolded) {
          p.folds = (p.folds || 0) + 1;
        }
        p.isFolded = true;
        p.isAllIn = false;
      } else {
        const desiredBet = decision.amount; // Total allowed wager for this round
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
            // It's a raise
            const raiseDiff = p.currentBet - newCurrentBet;
            if (raiseDiff > minRaise) minRaise = raiseDiff;
            newCurrentBet = p.currentBet;
        }

        // Track if player voluntarily put money in during preflop
        // (call, raise, all-in - NOT check or fold)
        // We'll count VPIP at flop transition for players who are still active
        const isVpipAction = actionType === PlayerActionType.CALL ||
           actionType === PlayerActionType.RAISE ||
           actionType === PlayerActionType.ALL_IN;
        if (prev.stage === GameStage.PREFLOP && isVpipAction) {
          handVpipRef.current.add(p.id); // Mark as having voluntarily put money in
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
      logEvent('action', { game: gameNumberRef.current, hand: nextState.handNumber, stage: prev.stage, playerId: p.id, model: p.model, action: p.lastAction, pot: nextState.pot });
      return nextState;
    });

    // Delay for visual effect then move on
    setTimeout(() => advanceTurn(), speed);
  };

  const advanceTurn = () => {
    const prev = gameStateRef.current;
    
    // Check if only one player remains (others folded)
    const activePlayers = prev.players.filter(p => !p.isFolded);
    if (activePlayers.length === 1) {
        // Winner by default
        const winnerId = activePlayers[0].id;
        setGameState(s => ({ ...s, winners: [winnerId], stage: GameStage.SHOWDOWN }));
        // Specialized Fold Win Handler:
        setTimeout(() => {
            setGameState(s => {
                // Check if already processed to avoid dupes
                if (s.stage !== GameStage.SHOWDOWN || s.pot === 0) return s;
                const winner = s.players.find(p => p.id === winnerId)!;
                // Add pot to winner
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
                const nextState: GameState = {
                    ...s,
                    players: nextPlayers,
                    pot: 0,
                    history: [...s.history, `Everyone folded. Player ${winnerId} wins.`]
                };
                logSnapshot('fold_win', nextState);
                return nextState;
            });
            setTimeout(() => {
              const survivors = gameStateRef.current.players.filter(p => p.chips > 0).length;
              if (survivors <= 1) {
                startNewGame();
              }
              if (isRunning) {
                setTimeout(() => startNewHand(), 300);
              }
            }, 3000);
        }, 1000);
        return;
    }

    // Check if betting round is complete
    // Condition: Everyone has acted AND (everyone matches the bet OR is all-in/folded)
    // "Acted" implies status is not 'waiting'.
    const allMatched = prev.players.every(p => 
        p.isFolded || 
        p.isAllIn || 
        (p.currentBet === prev.currentBet && p.status !== 'waiting')
    );
    
    if (allMatched && prev.stage !== GameStage.SHOWDOWN && prev.stage !== GameStage.IDLE) {
        nextStage();
    } else {
        // Move to next active player
        let nextIndex = (prev.currentPlayerIndex + 1) % NUM_PLAYERS;
        let loopCount = 0;
        
        // Find next candidate who is NOT folded and NOT all-in (unless everyone is all-in?)
        // If everyone is all-in, allMatched would be true, so we wouldn't be here.
        // So we just need to find the next player who has chips and cards.
        while(prev.players[nextIndex].isFolded || prev.players[nextIndex].isAllIn) {
            nextIndex = (nextIndex + 1) % NUM_PLAYERS;
            loopCount++;
            if (loopCount > NUM_PLAYERS) break; 
        }
        setGameState(s => ({ ...s, currentPlayerIndex: nextIndex }));
    }
  };

  // Track if showdown is being handled to prevent double-calls
  const showdownHandledRef = useRef(false);

  // --- Main Loop Trigger ---
  useEffect(() => {
    if (!isRunning) return;
    if (gameState.stage === GameStage.IDLE) {
        startNewHand();
        return;
    }
    if (gameState.stage === GameStage.SHOWDOWN) {
        // Trigger showdown handling if not already done
        if (!showdownHandledRef.current && gameState.winners.length === 0) {
            showdownHandledRef.current = true;
            handleShowdown();
        }
        return;
    }

    // Reset showdown flag when not in showdown
    showdownHandledRef.current = false;

    // If active player needs to move
    const currentPlayer = gameState.players[gameState.currentPlayerIndex];

    // FIX: Don't block if folded/all-in. executeTurn handles the skip.
    // Also block if already thinking to prevent double-calls.
    if (currentPlayer && currentPlayer.status !== 'thinking') {
         executeTurn();
    }
  }, [gameState.currentPlayerIndex, gameState.stage, isRunning]); 


  // Positioning calculations (circle)
  const getPositionClass = (index: number) => {
    // 6 players: Top, Top-Right, Bottom-Right, Bottom, Bottom-Left, Top-Left
    // Map relative to screen. Fixed positions.
    const positions = [
        "top-[70%] left-1/2 -translate-x-1/2", // User/Bottom (Player 1)
        "top-[60%] left-[5%]", // Bottom Left
        "top-[15%] left-[5%]", // Top Left
        "top-[-5%] left-1/2 -translate-x-1/2", // Top (Opposite)
        "top-[15%] right-[5%]", // Top Right
        "top-[60%] right-[5%]", // Bottom Right
    ];
    return positions[index];
  };

  return (
    <div className="w-full h-screen bg-slate-950 flex flex-col relative overflow-hidden">
        
      {/* Header / Nav */}
      <div className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6 z-50">
        <div className="flex items-center space-x-2">
            <Layers className="text-blue-500" />
            <h1 className="text-xl font-bold text-white tracking-wider">GEMINI POKER <span className="text-blue-500">PROS</span></h1>
        </div>
        
        <div className="flex space-x-4">
            <button 
                onClick={() => setView('game')}
                className={clsx("flex items-center space-x-2 px-4 py-2 rounded-lg transition", view === 'game' ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white")}
            >
                <TableIcon size={18} /> <span>Table</span>
            </button>
            <button 
                onClick={() => setView('stats')}
                className={clsx("flex items-center space-x-2 px-4 py-2 rounded-lg transition", view === 'stats' ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white")}
            >
                <BarChart2 size={18} /> <span>Analytics</span>
            </button>
        </div>

        <div className="flex items-center space-x-4">
            <button 
                onClick={() => setIsRunning(!isRunning)}
                disabled={!apiKeyOk}
                className={clsx("flex items-center space-x-2 px-4 py-2 rounded-lg font-bold shadow-lg transition hover:scale-105 active:scale-95", isRunning ? "bg-red-500 hover:bg-red-600" : "bg-green-500 hover:bg-green-600", !apiKeyOk && "opacity-60 cursor-not-allowed")}
            >
                {isRunning ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
                <span>{isRunning ? "PAUSE" : "START GAME"}</span>
            </button>
        </div>
      </div>
      {!apiKeyOk && (
        <div className="bg-red-900/70 text-red-100 text-sm px-6 py-2 border-b border-red-700">
          Missing OPENROUTER_POKER_API key. Set it in ~/.zshrc and restart the dev server; bots will auto-fold without it.
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 relative">
        
        {view === 'game' && (
            <div className="w-full h-full flex items-center justify-center p-4">
                
                {/* Poker Table */}
                <div className="relative w-full max-w-5xl aspect-[1.8/1] poker-table-felt rounded-[150px] border-[16px] border-amber-900 shadow-2xl flex items-center justify-center">
                    
                    {/* Brand Center */}
                    <div className="absolute text-green-800/30 font-black text-6xl tracking-widest select-none pointer-events-none">
                        GEMINI
                    </div>

                    {/* Community Cards & Pot */}
                    <div className="z-10 flex flex-col items-center space-y-4">
                        <div className="flex items-center justify-center space-x-3 h-24">
                            {gameState.communityCards.map((card, i) => (
                                <div key={card.id} className="animate-[fadeSlideIn_0.5s_ease-out]">
                                    <Card card={card} size="md" />
                                </div>
                            ))}
                            {/* Placeholders */}
                            {Array.from({length: 5 - gameState.communityCards.length}).map((_, i) => (
                                <div key={i} className="w-14 h-20 border-2 border-green-800/50 rounded-md"></div>
                            ))}
                        </div>
                        
                        <div className="bg-black/60 px-6 py-2 rounded-full text-yellow-400 font-mono text-xl border border-yellow-600/50 shadow-lg flex items-center space-x-2">
                             <span className="text-yellow-600">$</span>
                             <span>{gameState.pot.toLocaleString()}</span>
                        </div>
                        
                        <div className="text-green-200/60 font-medium text-sm uppercase tracking-widest">
                            {gameState.stage}
                        </div>
                    </div>

                    {/* Players */}
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

                {/* Game Log Sidebar (Floating) */}
                <div className="absolute bottom-4 right-4 w-80 h-64 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-xl p-4 overflow-hidden flex flex-col shadow-2xl z-40">
                    <h3 className="text-slate-400 text-xs font-bold uppercase mb-2 flex items-center justify-between">
                        <span>Game Log</span>
                        <span className="text-blue-500">Hand #{gameState.handNumber}</span>
                    </h3>
                    <div className="flex-1 overflow-y-auto space-y-1 text-xs font-mono scrollbar-thin">
                        {gameState.history.map((line, i) => (
                            <div key={i} className="text-slate-300 border-b border-slate-800/50 pb-0.5 last:border-0">
                                {line}
                            </div>
                        ))}
                         <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
                    </div>
                </div>

            </div>
        )}

        {view === 'stats' && (
            <StatsView players={gameState.players} history={handHistory} />
        )}

      </div>
      
      {/* CSS Animations */}
      <style>{`
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(10px); }
          10% { opacity: 1; transform: translateY(0); }
          90% { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(-10px); }
        }
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};

export default App;
