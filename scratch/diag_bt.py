import sys, collections
sys.stdout.reconfigure(encoding='utf-8')
import os; sys.path.insert(0, os.path.abspath('.'))
from datetime import datetime, timezone
import v9_continuum.backtest as B
from v9_continuum.layers.signal import Signal

C = collections.Counter()

# wrap OU
_ou = B.fit_ou_process
def ou(*a, **k):
    C['ou_calls'] += 1
    r = _ou(*a, **k)
    if r[0] > 0: C['ou_theta_pos'] += 1
    return r
B.fit_ou_process = ou

_reg = B.EuropeRegimeDetector.detect_regime
def reg(self, *a, **k):
    C['eu_regime_calls'] += 1
    r = _reg(self, *a, **k)
    C['eu_regime_' + str(r)] += 1
    return r
B.EuropeRegimeDetector.detect_regime = reg

from v9_continuum.layers.signal import SMCEngine, MLSignalEngine
_smc = SMCEngine.evaluate_smc_signal
def smc(self, *a, **k):
    C['smc_calls'] += 1
    r = _smc(self, *a, **k)
    C['smc_' + str(r[0])] += 1
    return r
SMCEngine.evaluate_smc_signal = smc

_ml = MLSignalEngine.predict_loss_probability
def mlp(self, *a, **k):
    C['ml_calls'] += 1
    p = _ml(self, *a, **k)
    C['ml_veto' if p > 0.60 else 'ml_pass'] += 1
    C['ml_prob_sum'] += p
    return p
MLSignalEngine.predict_loss_probability = mlp

from v9_continuum.core.governor import PortfolioGovernor
for name in dir(PortfolioGovernor):
    if name.startswith('_'): continue
    fn = getattr(PortfolioGovernor, name)
    if not callable(fn): continue
    def mk(n, f):
        def w(self, *a, **k):
            r = f(self, *a, **k)
            C['gov_' + n] += 1
            if r is False or (isinstance(r, tuple) and r and r[0] is False):
                C['gov_' + n + '_DENY'] += 1
            return r
        return w
    setattr(PortfolioGovernor, name, mk(name, fn))

bt = B.V9ContinuumBacktester(data_dir='data/historical_36m')
p, m = bt.run(['XAUUSD','AUDUSD','US30'], datetime(2026,3,1,tzinfo=timezone.utc), datetime(2026,6,1,tzinfo=timezone.utc), 10000.0)
print('trades:', len(p.closed_cycles), 'opened:', C.get('gov_register_position', 0))
for k, v in sorted(C.items()):
    print(f'  {k:35s} {v}')
