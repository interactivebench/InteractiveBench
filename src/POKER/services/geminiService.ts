import { GameState, Player, PlayerActionType } from '../types';
import { logEvent } from '../utils/logger';

const OPENROUTER_API_KEY = process.env.OPENROUTER_POKER_API || process.env.OPENROUTER_API_KEY || '';
const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';
const MAX_THINK_MS = 300000;
const MAX_RETRY_ATTEMPTS = 1; // initial try + one retry driven by the validator agent

const SYSTEM_INSTRUCTION = `
You are a world-class professional Texas Hold'em poker player. 
You play aggressively but mathematically.
You calculate pot odds, imply odds, and range advantages.
You are capable of advanced moves like check-raising, floating, and bluffing.
Your goal is to maximize your stack.
Do not be timid. If you have a strong hand or good situation, value bet or raise.
If you have a weak hand and bad odds, fold.
Occasionally bluff if the spot is perfect.

Response MUST be a JSON object with:
- action: "FOLD", "CHECK", "CALL", "RAISE", or "ALL_IN"
- amount: The TOTAL amount you want to wager for this round. 
    - If CHECK or FOLD, amount is 0. 
    - If CALL, amount matches the current highest bet. 
    - If RAISE, amount must be higher than current bet.
- reasoning: A short, sharp professional thought process (max 20 words).
`;

type ParsedDecision = { action: PlayerActionType; amount: number; reasoning: string };

const parseDecision = (rawText: string): ParsedDecision | null => {
  let parsed: any;
  try {
    parsed = JSON.parse(rawText);
  } catch {
    return null;
  }
  const { action, amount, reasoning } = parsed || {};
  const actionOk = Object.values(PlayerActionType).includes(action as PlayerActionType);
  const amountOk = typeof amount === 'number' && Number.isFinite(amount);
  if (!actionOk || !amountOk) return null;
  return {
    action: action as PlayerActionType,
    amount,
    reasoning: typeof reasoning === 'string' ? reasoning : ''
  };
};

const getReasoningConfig = (model: string) => {
  if (model.startsWith('deepseek/')) {
    return { enabled: true, effort: 'high' };
  }
  if (model.startsWith('x-ai/')) {
    return { enabled: true };
  }
  return undefined;
};

const callModel = async (model: string, messages: any[], attemptLabel: string) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), MAX_THINK_MS);
  try {
    const reasoning = getReasoningConfig(model);
    const response = await fetch(OPENROUTER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
        'HTTP-Referer': 'https://poker.local',
        'X-Title': 'gemini-poker-pros'
      },
      body: JSON.stringify({
        model,
        messages,
        response_format: { type: 'json_object' },
        ...(reasoning ? { reasoning } : {})
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      throw new Error(`OpenRouter error: ${response.status} ${response.statusText} (${attemptLabel})`);
    }

    const data = await response.json();
    const text = data?.choices?.[0]?.message?.content || null;
    if (!text) throw new Error(`Empty response (${attemptLabel})`);
    return text;
  } finally {
    clearTimeout(timer);
  }
};

export const getAgentDecision = async (
  gameState: GameState,
  player: Player
): Promise<{ action: PlayerActionType; amount: number; reasoning: string }> => {
  if (!OPENROUTER_API_KEY) {
    console.error("Missing OPENROUTER_POKER_API API key.");
    logEvent('error', { source: 'openrouter', model: player.model, playerId: player.id, reason: 'missing_api_key' });
    return {
      action: PlayerActionType.FOLD,
      amount: 0,
      reasoning: "Auto-fold (missing API key)"
    };
  }
  
  // Construct a prompt that gives the AI all context
  const communityStr = gameState.communityCards.map(c => `${c.rank}${c.suit}`).join(' ');
  const handStr = player.hand.map(c => `${c.rank}${c.suit}`).join(' ');
  const toCall = gameState.currentBet - player.currentBet;
  const potOdds = toCall > 0 ? ((gameState.pot + toCall) / toCall).toFixed(2) : "N/A";
  
  // Create a sanitized history log - strip reasoning to prevent hand info leaks
  // History format is "P1 RAISE: reasoning here" - we only keep "P1 RAISE"
  const historyStr = gameState.history
    .slice(-5)
    .map(line => line.split(':')[0]) // Remove everything after the colon (the reasoning)
    .join('; ');

  const prompt = `
    Current Stage: ${gameState.stage}
    Your Hand: [${handStr}]
    Community Cards: [${communityStr}]
    Your Stack: ${player.chips}
    Current Pot: ${gameState.pot}
    Amount to Call: ${toCall}
    Minimum Raise: ${gameState.minRaise}
    Pot Odds: 1 to ${potOdds}
    Position: ${player.id === gameState.dealerIndex ? 'Dealer (Late)' : 'Standard'}
    Active Players: ${gameState.players.filter(p => !p.isFolded).length}
    Recent Action: ${historyStr}

    What is your move?
  `;

  try {
    let lastInvalidResponse: string | null = null;
    let lastError: string | null = null;

    for (let attempt = 0; attempt <= MAX_RETRY_ATTEMPTS; attempt++) {
      const retrying = attempt > 0;
      const messages = [
        { role: 'system', content: SYSTEM_INSTRUCTION },
        { role: 'user', content: prompt }
      ];

      if (retrying && lastInvalidResponse) {
        messages.push({ role: 'assistant', content: lastInvalidResponse });
        messages.push({ role: 'user', content: 'Your previous response was invalid or not JSON. Reply again NOW with only the JSON object matching the schema: { "action": "...", "amount": <number>, "reasoning": "..." }. No prose.' });
      }

      try {
        const text = await callModel(player.model, messages, retrying ? 'retry' : 'initial');
        const parsed = parseDecision(text);

        if (!parsed) {
          lastInvalidResponse = text;
          lastError = 'invalid_format';
          logEvent('invalid_format', { source: 'openrouter', model: player.model, playerId: player.id, stage: gameState.stage, hand: gameState.handNumber, attempt, text });
          continue; // retry (if allowed) with fresh 60s timer
        }

        // Validate and sanitize decision
        let actionType = parsed.action;
        let amount = parsed.amount;

        // Logic safeguards
        if (actionType === PlayerActionType.CHECK && toCall > 0) {
          if (toCall < player.chips * 0.05) {
            actionType = PlayerActionType.CALL;
            amount = gameState.currentBet;
          } else {
            actionType = PlayerActionType.FOLD;
            amount = 0;
          }
        }

        if (actionType === PlayerActionType.CALL) {
          amount = gameState.currentBet;
        }

        if (actionType === PlayerActionType.RAISE) {
          const minBet = gameState.currentBet + gameState.minRaise;
          if (amount < minBet) amount = minBet;
          if (amount >= player.chips + player.currentBet) {
              actionType = PlayerActionType.ALL_IN;
              amount = player.chips + player.currentBet;
          }
        }
        
        if (actionType === PlayerActionType.ALL_IN) {
            amount = player.chips + player.currentBet;
        }

        return {
          action: actionType,
          amount,
          reasoning: parsed.reasoning || 'Acting on validated retry.'
        };
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err);
        if (retrying) break;
      }
    }

    throw new Error(lastError || 'invalid format after retry');

  } catch (error) {
    console.error("AI Error:", error);
    logEvent('error', {
      source: 'openrouter',
      model: player.model,
      playerId: player.id,
      reason: error instanceof Error ? error.message : String(error)
    });
    // Fallback: forced fold on timeout/error
    return {
      action: PlayerActionType.FOLD,
      amount: 0,
      reasoning: "Auto-fold (timeout or error)."
    };
  }
};
