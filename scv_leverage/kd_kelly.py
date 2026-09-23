"""
kd_kelly.py -- Kelly estimators and subset statistics.

Three Kelly estimators are reported side by side:

  1. kelly_gauss  f* = mu / sigma^2         (population var; identical to the
                  compute_kelly_metrics() formula already used in
                  mf_and_kelly.py / backtest.py -- kept for comparability)

  2. kelly_quad   f* = mu / E[x^2]          (the exact maximiser of the
                  second-order expansion; differs from (1) only by mu^2,
                  negligible at daily frequency but included for correctness)

  3. kelly_emp    f* = argmax_f  E[ log(1 + rf + f*x) ]      <-- HEADLINE
                  the empirical log-optimal fraction for the ACTUAL daily
                  distribution, with the no-bankruptcy constraint
                  1 + rf_t + f*x_t > 0 enforced for every retained day.

Note on (3): the wealth relative for a portfolio holding fraction f in the
risky asset and financing the rest at the risk-free rate is
    W_{t+1}/W_t = 1 + rf_t + f * x_t ,   x_t = excess return.
The existing compute_kelly_metrics() grid search uses (1 + f*x), i.e. it drops
the rf term. The form used here is the correct one, but the difference is
numerically nil at daily frequency (measured: 0.000x for both series, because
daily rf ~ 1e-4 is negligible next to 1). It matters only at annual frequency.

(3) takes an optional borrowing spread over rf (common/leverage.py): with a
spread the log-growth curve has a kink at f = 1 and f* moves left.

Also note (3) is constrained to f >= 0 (long-only leverage). Where the reduced
sample has a negative mean the reported f* is 0.00x, meaning "the log-optimal
long position is zero", not "the optimum is unconstrained-zero".

All estimators are frequency-invariant under i.i.d. returns, so daily-estimated
f* is directly comparable to the monthly f* reported by mf_and_kelly.py.
"""
import numpy as np

_TINY = 1e-12


def _feasible_fmax(x, rf):
    """Largest f with 1 + rf_t + f*x_t > 0 for all t (i.e. no wipe-out day)."""
    neg = x < 0
    if not np.any(neg):
        return np.inf
    return float(np.min((1.0 + rf[neg]) / (-x[neg])))


def kelly_gauss(x):
    v = np.var(x)  # population variance, matches existing project code
    return 0.0 if v < _TINY else float(np.mean(x) / v)


def kelly_quad(x):
    m2 = np.mean(x * x)
    return 0.0 if m2 < _TINY else float(np.mean(x) / m2)


def kelly_emp(x, rf, tol=1e-4, fmax_cap=25.0, spread=0.0):
    """Empirical log-optimal f via coarse grid scan + golden-section refine.
    Constrained to the open interval (0, fmax) where fmax forbids bankruptcy.

    `spread` is the borrowing cost over rf PER OBSERVATION (annual spread / apy),
    charged on the borrowed part max(f - 1, 0) -- common/leverage.py's model:
        W_{t+1}/W_t = 1 + rf_t + f * x_t - max(f - 1, 0) * spread"""
    hi = min(_feasible_fmax(x, rf) * (1 - 1e-9), fmax_cap)
    if not np.isfinite(hi) or hi <= 0:
        return 0.0

    def g(f):
        w = 1.0 + rf + f * x - max(f - 1.0, 0.0) * spread
        if np.any(w <= 0):
            return -np.inf
        return float(np.mean(np.log(w)))

    grid = np.linspace(0.0, hi, 200)
    vals = np.array([g(f) for f in grid])
    k = int(np.argmax(vals))
    lo_b = grid[max(0, k - 1)]
    hi_b = grid[min(len(grid) - 1, k + 1)]

    # golden-section on [lo_b, hi_b]
    invphi = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = lo_b, hi_b
    c, d = b - invphi * (b - a), a + invphi * (b - a)
    fc, fd = g(c), g(d)
    while b - a > tol:
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - invphi * (b - a)
            fc = g(c)
        else:
            a, c, fc = c, d, fd
            d = a + invphi * (b - a)
            fd = g(d)
    return float((a + b) / 2.0)


def max_drawdown(total_returns):
    nav = np.cumprod(1.0 + total_returns)
    peak = np.maximum.accumulate(nav)
    return float((nav / peak - 1.0).min())


def subset_stats(total, exc, rf, apy, with_emp=True):
    """Full statistic block for one (possibly reduced) daily sample."""
    n = len(total)
    mu_e = float(np.mean(exc))
    sd_e = float(np.std(exc, ddof=1))
    sd_t = float(np.std(total, ddof=1))
    log_geo = float(np.mean(np.log1p(total)))
    cagr = float(np.exp(log_geo * apy) - 1.0)
    kg = kelly_gauss(exc)
    kq = kelly_quad(exc)
    ke = kelly_emp(exc, rf) if with_emp else np.nan
    return dict(
        n_obs=n,
        mean_daily_total=float(np.mean(total)),
        mean_daily_exc=mu_e,
        ann_arith_total=float(np.mean(total) * apy),
        ann_arith_exc=mu_e * apy,
        cagr=cagr,
        ann_vol=sd_t * np.sqrt(apy),
        sharpe=(mu_e * apy) / (sd_e * np.sqrt(apy)) if sd_e > 0 else np.nan,
        max_dd=max_drawdown(total),
        worst_day=float(np.min(total)),
        best_day=float(np.max(total)),
        skew=float(_skew(exc)),
        kurt=float(_kurt(exc)),
        kelly_gauss=kg, kelly_gauss_half=kg / 2, kelly_gauss_quarter=kg / 4,
        kelly_quad=kq,
        kelly_emp=ke, kelly_emp_half=ke / 2, kelly_emp_quarter=ke / 4,
        fmax_feasible=_feasible_fmax(exc, rf),
    )


def _skew(a):
    d = a - a.mean()
    s = d.std()
    return np.mean(d ** 3) / s ** 3 if s > 0 else np.nan


def _kurt(a):
    d = a - a.mean()
    s = d.std()
    return np.mean(d ** 4) / s ** 4 - 3.0 if s > 0 else np.nan
