"""A small CPU PPO policy for the official variable-sized legal choices."""
import math
import random
from dataclasses import dataclass

import torch
from torch import nn
from torch.distributions import Categorical

STATE_SIZE = 20
OPTION_FIELDS = ('type', 'number', 'area', 'index', 'playerIndex', 'toolIndex',
                 'energyIndex', 'count', 'inPlayArea', 'inPlayIndex', 'attackId',
                 'cardId', 'serial', 'specialConditionType')
OPTION_SIZE = len(OPTION_FIELDS) + 2


def number(value, scale=100.0):
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return max(-10.0, min(10.0, float(value) / scale))
    return 0.0


def encode(obs):
    """Explicit allowlist: no opaque search input, opponent hand or hidden prizes."""
    s = obs['current']
    me = s['yourIndex']
    players = s['players']
    features = [number(s.get('turn'), 50), number(s.get('turnActionCount'), 20),
                float(s.get('firstPlayer') == me), float(bool(s.get('supporterPlayed'))),
                float(bool(s.get('energyAttached'))), float(bool(s.get('retreated')))]
    for idx in (me, 1 - me):
        p = players[idx]
        active = next((x for x in p.get('active', []) if x), {})
        features.extend([number(p.get('deckCount'), 60), number(p.get('handCount'), 60),
                         number(len(p.get('bench') or []), 5), number(len(p.get('prize') or []), 6),
                         number(len(p.get('discard') or []), 60), number(active.get('id'), 2000)])
    hand = players[me].get('hand') or []
    features.extend([number(sum(c.get('id', 0) for c in hand if isinstance(c, dict)), 20000), number(len(hand), 60)])
    sel = obs['select']
    options = []
    for item in sel['option']:
        row = [number(item.get(k), 2000 if k in ('cardId', 'attackId', 'serial') else 100)
               for k in OPTION_FIELDS]
        row += [float(item.get('playerIndex') == me), number(sel.get('context'), 100)]
        options.append(row)
    return torch.tensor(features, dtype=torch.float32), torch.tensor(options, dtype=torch.float32).reshape(-1, OPTION_SIZE), int(sel['minCount']), int(sel['maxCount'])


class Policy(nn.Module):
    def __init__(self, hidden=64):
        super().__init__()
        self.state = nn.Sequential(nn.Linear(STATE_SIZE, hidden), nn.Tanh())
        self.option = nn.Sequential(nn.Linear(OPTION_SIZE, hidden), nn.Tanh())
        self.score = nn.Sequential(nn.Linear(hidden * 2, hidden), nn.Tanh(), nn.Linear(hidden, 1))
        self.stop = nn.Linear(hidden, 1)
        self.value = nn.Linear(hidden, 1)

    def evaluate_action(self, state, options, minimum, maximum, sequence=None, greedy=False):
        """Sequence contains selected indices and optionally the sentinel len(options).

        The STOP sentinel is available only after minCount and before maxCount.
        PPO stores and replays the exact ordered sequence to reproduce log probability.
        """
        state_hidden = self.state(state)
        value = self.value(state_hidden).squeeze(-1)
        n = options.shape[0]
        if maximum > n or minimum > maximum or minimum < 0:
            raise ValueError('Invalid selection constraints')
        opt_hidden = self.option(options)
        if n:
            logits = self.score(torch.cat([state_hidden.expand(n, -1), opt_hidden], dim=-1)).squeeze(-1)
        else:
            logits = state_hidden.new_empty((0,))
        selected, actual = [], []
        logprob = state_hidden.sum() * 0
        entropy = state_hidden.sum() * 0
        cursor = 0
        while len(selected) < maximum:
            candidates = [i for i in range(n) if i not in selected]
            if len(selected) >= minimum:
                candidates.append(n)
            if not candidates:
                raise ValueError('No legal continuation')
            scores = torch.stack([self.stop(state_hidden).squeeze(-1) if i == n else logits[i] for i in candidates])
            dist = Categorical(logits=scores)
            if sequence is None:
                local = scores.argmax() if greedy else dist.sample()
                chosen = candidates[int(local.item())]
            else:
                if cursor >= len(sequence) or sequence[cursor] not in candidates:
                    raise ValueError('Stored action sequence is invalid')
                chosen = sequence[cursor]
                local = torch.tensor(candidates.index(chosen), device=scores.device)
            actual.append(chosen)
            cursor += 1
            logprob = logprob + dist.log_prob(local)
            entropy = entropy + dist.entropy()
            if chosen == n:
                break
            selected.append(chosen)
        if sequence is not None and cursor != len(sequence):
            raise ValueError('Stored action sequence has trailing choices')
        return selected, actual, logprob, entropy, value


@dataclass
class Transition:
    state: torch.Tensor
    options: torch.Tensor
    minimum: int
    maximum: int
    sequence: list
    logprob: float
    value: float
    reward: float = 0.0
    advantage: float = 0.0
    target: float = 0.0


def sample(policy, obs, greedy=False):
    state, options, minimum, maximum = encode(obs)
    with torch.no_grad():
        action, sequence, logp, _, value = policy.evaluate_action(state, options, minimum, maximum, greedy=greedy)
    return action, Transition(state, options, minimum, maximum, sequence, logp.item(), value.item())


def finish_trajectory(trajectory, reward, gamma=1.0, gae_lambda=0.95):
    if not trajectory:
        return
    trajectory[-1].reward = reward
    gae = 0.0
    for i in reversed(range(len(trajectory))):
        step = trajectory[i]
        next_value = trajectory[i+1].value if i+1 < len(trajectory) else 0.0
        delta = step.reward + gamma * next_value - step.value
        gae = delta + (gamma * gae_lambda * gae if i+1 < len(trajectory) else 0)
        step.advantage, step.target = gae, gae + step.value


def update(policy, optimizer, data, *, epochs=2, batch_size=128, clip=0.2, entropy_coef=0.01, rng=None):
    if not data:
        return {'updates': 0, 'transitions': 0}
    rng = rng or random.Random()
    advantages = torch.tensor([x.advantage for x in data])
    if len(data) > 1:
        advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
    indices = list(range(len(data)))
    losses = []
    for _ in range(epochs):
        rng.shuffle(indices)
        for start in range(0, len(indices), batch_size):
            batch = indices[start:start + batch_size]
            terms = []
            for i in batch:
                item = data[i]
                _, _, logp, entropy, value = policy.evaluate_action(item.state, item.options, item.minimum, item.maximum, item.sequence)
                ratio = (logp - item.logprob).exp()
                advantage = advantages[i]
                surrogate = torch.minimum(ratio * advantage, ratio.clamp(1-clip, 1+clip) * advantage)
                terms.append(-surrogate + 0.5 * (value - item.target).square() - entropy_coef * entropy)
            loss = torch.stack(terms).mean()
            if not torch.isfinite(loss):
                raise RuntimeError('PPO loss is not finite')
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(policy.parameters(), 0.5)
            optimizer.step()
            losses.append(loss.item())
    return {'updates': len(losses), 'transitions': len(data), 'loss': sum(losses)/len(losses)}
